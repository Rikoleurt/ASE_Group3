import json
from datetime import datetime, timezone

from mysql.connector import IntegrityError

from backend.app.data_controller.data_controller import DataController
from backend.app.image_storage import image_path
from backend.app.model.analysis import Box, DetectedSign
from backend.app.model.community import DiscussionSummary, DiscussionDetail, DiscussionComment


def utc(row):
    return {**row, "created_at": row["created_at"].replace(tzinfo=timezone.utc)}


class DuplicateDiscussionTitle(ValueError):
    """A different discussion already uses this title."""


def find_symbol(result: dict, sign_id: int) -> DetectedSign | None:
    """Find an occurrence in the immutable saved analysis, never in client boxes."""
    for sign in result["signs"]:
        if sign["id"] == sign_id:
            return DetectedSign(**{**sign, "crop": None})
    return None


def symbol_name(symbol: DetectedSign) -> str:
    if not symbol.sign:
        return f"symbol-{symbol.id}"
    return symbol.reading or symbol.label or symbol.sign


SUMMARY = ("d.id, d.analysis_id, d.author_id, u.username AS author_username, d.title, d.created_at, "
           "d.sign_id, a.filename AS tablet_filename, a.result_json")
JOINS = " FROM community_discussion d JOIN `user` u ON u.id = d.author_id JOIN analysis a ON a.id = d.analysis_id "


def discussion_summary(row: dict) -> DiscussionSummary:
    values = dict(row)
    result = json.loads(values.pop("result_json"))
    symbol = find_symbol(result, values["sign_id"]) if values["sign_id"] is not None else None
    return DiscussionSummary(**utc(values), symbol_name=symbol_name(symbol) if symbol else None)


class CommunityDataController(DataController):
    def create_discussion(self, user_id: int, analysis_id: int, title: str,
                          sign_id: int | None = None) -> tuple[DiscussionSummary, bool] | None:
        title = title.strip()
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                # Serialize shares of one analysis, including its individual occurrences.
                cursor.execute("SELECT id, filename, result_json FROM analysis WHERE id = %s AND user_id = %s FOR UPDATE",
                               (analysis_id, user_id))
                analysis = cursor.fetchone()
                if analysis is None:
                    return None
                symbol = find_symbol(json.loads(analysis["result_json"]), sign_id) if sign_id is not None else None
                if sign_id is not None and symbol is None:
                    return None
                cursor.execute(f"SELECT {SUMMARY}{JOINS}WHERE d.analysis_id = %s AND d.sign_id <=> %s",
                               (analysis_id, sign_id))
                existing = cursor.fetchone()
                if existing:
                    return discussion_summary(existing), False
                cursor.execute("SELECT storage_key FROM analysis_image WHERE analysis_id = %s", (analysis_id,))
                image = cursor.fetchone()
                if not image or not image_path(image["storage_key"]).is_file():
                    raise FileNotFoundError("The tablet image is unavailable. Upload and analyze it again before sharing.")
                created_at = datetime.now(timezone.utc)
                try:
                    cursor.execute("INSERT INTO community_discussion (analysis_id, sign_id, author_id, title, created_at) "
                                   "VALUES (%s, %s, %s, %s, %s)",
                                   (analysis_id, sign_id, user_id, title, created_at.replace(tzinfo=None)))
                except IntegrityError as error:
                    if error.errno == 1062 and "uq_discussion_title" in str(error):
                        raise DuplicateDiscussionTitle("A discussion with this title already exists. Choose another title.") from error
                    raise
                discussion_id = cursor.lastrowid
                cursor.execute("SELECT username FROM `user` WHERE id = %s", (user_id,))
                username = cursor.fetchone()["username"]
            finally:
                cursor.close()
        return DiscussionSummary(id=discussion_id, analysis_id=analysis_id, author_id=user_id,
                                 author_username=username, title=title, created_at=created_at,
                                 sign_id=sign_id, symbol_name=symbol_name(symbol) if symbol else None,
                                 tablet_filename=analysis["filename"]), True

    def list_discussions(self, limit: int, before: int | None) -> list[DiscussionSummary]:
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(f"SELECT {SUMMARY}{JOINS}"
                               + ("WHERE d.id < %s " if before else "") + "ORDER BY d.id DESC LIMIT %s",
                               (before, limit + 1) if before else (limit + 1,))
                rows = cursor.fetchall()
            finally:
                cursor.close()
        return [discussion_summary(row) for row in rows]

    def get_discussion(self, discussion_id: int) -> DiscussionDetail | None:
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(f"SELECT {SUMMARY}{JOINS}WHERE d.id = %s", (discussion_id,))
                row = cursor.fetchone()
                if row is None:
                    return None
                # Resolve the tree by analysis ID, even if the parent thread was shared later.
                cursor.execute(f"SELECT {SUMMARY}{JOINS}WHERE d.analysis_id = %s ORDER BY d.id", (row["analysis_id"],))
                related = [discussion_summary(item) for item in cursor.fetchall()]
            finally:
                cursor.close()
        result = json.loads(row["result_json"])
        symbol = find_symbol(result, row["sign_id"]) if row["sign_id"] is not None else None
        if row["sign_id"] is not None and symbol is None:
            return None
        return DiscussionDetail(
            **discussion_summary(row).model_dump(),
            result=result if row["sign_id"] is None else None,
            symbol=symbol,
            parent_discussion=next((item for item in related if item.sign_id is None), None),
            symbol_discussions=[item for item in related if item.sign_id is not None],
            image_url=f"/api/community/discussions/{discussion_id}/image",
        )

    def get_image(self, discussion_id: int) -> tuple[str, str, Box | None] | None:
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute("SELECT i.storage_key, a.format, d.sign_id, a.result_json FROM community_discussion d "
                               "JOIN analysis a ON a.id = d.analysis_id JOIN analysis_image i ON i.analysis_id = a.id "
                               "WHERE d.id = %s", (discussion_id,))
                row = cursor.fetchone()
            finally:
                cursor.close()
        if row is None:
            return None
        box = None
        if row["sign_id"] is not None:
            symbol = find_symbol(json.loads(row["result_json"]), row["sign_id"])
            if symbol is None:
                return None
            box = symbol.box
        return row["storage_key"], row["format"], box

    def list_comments(self, discussion_id: int) -> list[DiscussionComment] | None:
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute("SELECT id FROM community_discussion WHERE id = %s", (discussion_id,))
                if cursor.fetchone() is None:
                    return None
                cursor.execute("SELECT c.id, c.discussion_id, c.author_id, u.username AS author_username, "
                               "c.created_at, c.body FROM community_comment c JOIN `user` u ON u.id = c.author_id "
                               "WHERE c.discussion_id = %s ORDER BY c.created_at, c.id", (discussion_id,))
                rows = cursor.fetchall()
            finally:
                cursor.close()
        return [DiscussionComment(**utc(row)) for row in rows]

    def add_comment(self, discussion_id: int, user_id: int, body: str) -> DiscussionComment | None:
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute("SELECT id FROM community_discussion WHERE id = %s FOR SHARE", (discussion_id,))
                if cursor.fetchone() is None:
                    return None
                created_at = datetime.now(timezone.utc)
                cursor.execute("INSERT INTO community_comment (discussion_id, author_id, body, created_at) "
                               "VALUES (%s, %s, %s, %s)",
                               (discussion_id, user_id, body, created_at.replace(tzinfo=None)))
                comment_id = cursor.lastrowid
                cursor.execute("SELECT username FROM `user` WHERE id = %s", (user_id,))
                username = cursor.fetchone()["username"]
            finally:
                cursor.close()
        return DiscussionComment(id=comment_id, discussion_id=discussion_id, author_id=user_id,
                                 author_username=username, created_at=created_at, body=body)
