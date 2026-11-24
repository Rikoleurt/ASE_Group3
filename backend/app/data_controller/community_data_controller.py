import json
from base64 import b64decode, urlsafe_b64encode
from datetime import datetime, timezone

from mysql.connector import IntegrityError

from backend.app.data_controller.data_controller import DataController
from backend.app.image_storage import image_path
from backend.app.model.analysis import Box, DetectedSign
from backend.app.model.community import (DiscussionSummary, DiscussionDetail, DiscussionComment,
                                         DiscussionPage, DiscussionCursor, DiscussionFilter, VoteSet, VoteState)


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
           "d.sign_id, a.filename AS tablet_filename, a.result_json, "
           "CAST(COALESCE((SELECT SUM(v.value) FROM community_vote v WHERE v.discussion_id = d.id), 0) "
           "AS SIGNED) AS score")
JOINS = " FROM community_discussion d JOIN `user` u ON u.id = d.author_id JOIN analysis a ON a.id = d.analysis_id "


def discussion_summary(row: dict) -> DiscussionSummary:
    values = dict(row)
    result = json.loads(values.pop("result_json"))
    symbol = find_symbol(result, values["sign_id"]) if values["sign_id"] is not None else None
    return DiscussionSummary(**utc(values), symbol_name=symbol_name(symbol) if symbol else None)


def encode_discussion_cursor(item: DiscussionSummary, filter_by: DiscussionFilter, q: str) -> str:
    position = DiscussionCursor(created_at=item.created_at, id=item.id, filter_by=filter_by, q=q)
    return urlsafe_b64encode(position.model_dump_json().encode()).decode().rstrip("=")


def decode_discussion_cursor(value: str, filter_by: DiscussionFilter, q: str) -> DiscussionCursor:
    try:
        if len(value) > 4096:
            raise ValueError()
        raw = b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        position = DiscussionCursor.model_validate_json(raw)
        # MySQL DATETIME starts at year 1000. Never pass out-of-range dates to SQL.
        timestamp = position.created_at.astimezone(timezone.utc)
        if timestamp.year < 1000 or position.filter_by != filter_by or position.q != q:
            raise ValueError()
        return position
    except (ValueError, OverflowError) as error:
        raise ValueError("Invalid discussion cursor. Restart the search.") from error


def search_pattern(query: str) -> str:
    # A typed '%' or '_' is a literal character, not a SQL wildcard.
    return "%" + query.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"


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

    def get_discussion_by_most_recent_date(self, limit: int = 30, cursor: str | None = None) -> DiscussionPage:
        return self._get_discussion_page(limit, cursor, "recent", "")

    def get_discussion_by_tablet_name(self, name: str, limit: int = 30,
                                     cursor: str | None = None) -> DiscussionPage:
        return self._get_discussion_page(limit, cursor, "tablet", name.strip())

    def get_discussion_by_author(self, author: str, limit: int = 30,
                                 cursor: str | None = None) -> DiscussionPage:
        return self._get_discussion_page(limit, cursor, "author", author.strip())

    def _get_discussion_page(self, limit: int, cursor: str | None,
                             filter_by: DiscussionFilter, q: str) -> DiscussionPage:
        if not 1 <= limit <= 100 or len(q) > 255:
            raise ValueError("Invalid discussion search.")
        position = decode_discussion_cursor(cursor, filter_by, q) if cursor is not None else None
        conditions = []
        params = []
        if q and filter_by == "author":
            conditions.append("u.username LIKE %s ESCAPE '!'")
            params.append(search_pattern(q))
        elif q and filter_by == "tablet":
            conditions.append("(a.filename LIKE %s ESCAPE '!' OR EXISTS ("
                              "SELECT 1 FROM community_discussion p WHERE p.analysis_id = d.analysis_id "
                              "AND p.sign_id IS NULL AND p.title LIKE %s ESCAPE '!'))")
            params.extend([search_pattern(q), search_pattern(q)])
        if position:
            timestamp = position.created_at.astimezone(timezone.utc).replace(tzinfo=None)
            conditions.append("(d.created_at < %s OR (d.created_at = %s AND d.id < %s))")
            params.extend([timestamp, timestamp, position.id])
        where = "WHERE " + " AND ".join(conditions) + " " if conditions else ""
        with self.connection() as connection:
            db_cursor = connection.cursor(dictionary=True)
            try:
                db_cursor.execute(f"SELECT {SUMMARY}{JOINS}{where}"
                                  "ORDER BY d.created_at DESC, d.id DESC LIMIT %s", (*params, limit + 1))
                rows = db_cursor.fetchall()
                items = [discussion_summary(row) for row in rows[:limit]]
                # Only fetch public parent threads needed by this page's symbols.
                # They are context, not extra matches or all the tablet's children.
                parent_ids = {item.analysis_id for item in items if item.sign_id is None}
                needed = sorted({item.analysis_id for item in items if item.sign_id is not None} - parent_ids)
                parents = []
                if needed:
                    placeholders = ", ".join(["%s"] * len(needed))
                    db_cursor.execute(f"SELECT {SUMMARY}{JOINS}WHERE d.sign_id IS NULL "
                                      f"AND d.analysis_id IN ({placeholders})", tuple(needed))
                    parents = [discussion_summary(row) for row in db_cursor.fetchall()]
            finally:
                db_cursor.close()
        next_cursor = encode_discussion_cursor(items[-1], filter_by, q) if len(rows) > limit else None
        return DiscussionPage(items=items, parents=parents, next_cursor=next_cursor)

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
    
    def get_vote(self, discussion_id: int, user_id: int) -> VoteState | None:
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute("SELECT id FROM community_discussion WHERE id = %s", (discussion_id,))
                if cursor.fetchone() is None:
                    return None
                return self._vote_state(cursor, discussion_id, user_id)
            finally:
                cursor.close()
    
    def set_vote(self, discussion_id: int, user_id: int, value: int) -> VoteState | None:
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute("SELECT id FROM community_discussion WHERE id = %s FOR SHARE", (discussion_id,))
                if cursor.fetchone() is None:
                    return None
                if value == 0:
                    cursor.execute("DELETE FROM community_vote WHERE discussion_id = %s AND user_id = %s",
                                   (discussion_id, user_id))
                else:
                    cursor.execute(
                        "INSERT INTO community_vote (discussion_id, user_id, value, created_at) "
                        "VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE value = VALUES(value)",
                        (discussion_id, user_id, value, datetime.now(timezone.utc).replace(tzinfo=None)),
                    )
                return self._vote_state(cursor, discussion_id, user_id)
            finally:
                cursor.close()

    def _vote_state(self, cursor, discussion_id: int, user_id: int) -> VoteState:
        cursor.execute("SELECT CAST(COALESCE(SUM(value), 0) AS SIGNED) AS score "
                       "FROM community_vote WHERE discussion_id = %s", (discussion_id,))
        score = cursor.fetchone()["score"]
        cursor.execute("SELECT value FROM community_vote WHERE discussion_id = %s AND user_id = %s",
                       (discussion_id, user_id))
        mine = cursor.fetchone()
        return VoteState(score=score, my_vote=mine["value"] if mine else 0)
