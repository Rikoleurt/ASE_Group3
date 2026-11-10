import json
from datetime import datetime, timezone

from backend.app.data_controller.data_controller import DataController
from backend.app.image_storage import image_path
from backend.app.model.community import DiscussionSummary, DiscussionDetail, DiscussionComment


def utc(row):
    return {**row, "created_at": row["created_at"].replace(tzinfo=timezone.utc)}


SUMMARY = "d.id, d.analysis_id, d.author_id, u.username AS author_username, d.title, d.created_at"


class CommunityDataController(DataController):
    def create_discussion(self, user_id: int, analysis_id: int, title: str) -> tuple[DiscussionSummary, bool] | None:
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                # Lock the owned analysis so simultaneous shares cannot create two threads.
                cursor.execute("SELECT id FROM analysis WHERE id = %s AND user_id = %s FOR UPDATE",
                               (analysis_id, user_id))
                if cursor.fetchone() is None:
                    return None
                cursor.execute(f"SELECT {SUMMARY} FROM community_discussion d JOIN `user` u ON u.id = d.author_id "
                               "WHERE d.analysis_id = %s", (analysis_id,))
                existing = cursor.fetchone()
                if existing:
                    return DiscussionSummary(**utc(existing)), False
                cursor.execute("SELECT storage_key FROM analysis_image WHERE analysis_id = %s", (analysis_id,))
                image = cursor.fetchone()
                if not image or not image_path(image["storage_key"]).is_file():
                    raise FileNotFoundError("The tablet image is unavailable. Upload and analyze it again before sharing.")
                created_at = datetime.now(timezone.utc)
                cursor.execute("INSERT INTO community_discussion (analysis_id, author_id, title, created_at) "
                               "VALUES (%s, %s, %s, %s)",
                               (analysis_id, user_id, title, created_at.replace(tzinfo=None)))
                discussion_id = cursor.lastrowid
                cursor.execute("SELECT username FROM `user` WHERE id = %s", (user_id,))
                username = cursor.fetchone()["username"]
            finally:
                cursor.close()
        return DiscussionSummary(id=discussion_id, analysis_id=analysis_id, author_id=user_id,
                                 author_username=username, title=title, created_at=created_at), True

    def list_discussions(self, limit: int, before: int | None) -> list[DiscussionSummary]:
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(f"SELECT {SUMMARY} FROM community_discussion d JOIN `user` u ON u.id = d.author_id "
                               + ("WHERE d.id < %s " if before else "") + "ORDER BY d.id DESC LIMIT %s",
                               (before, limit + 1) if before else (limit + 1,))
                rows = cursor.fetchall()
            finally:
                cursor.close()
        return [DiscussionSummary(**utc(row)) for row in rows]

    def get_discussion(self, discussion_id: int) -> DiscussionDetail | None:
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(f"SELECT {SUMMARY}, a.result_json FROM community_discussion d "
                               "JOIN `user` u ON u.id = d.author_id JOIN analysis a ON a.id = d.analysis_id "
                               "WHERE d.id = %s", (discussion_id,))
                row = cursor.fetchone()
            finally:
                cursor.close()
        if row is None:
            return None
        result = json.loads(row.pop("result_json"))
        return DiscussionDetail(**utc(row), result=result, image_url=f"/api/community/discussions/{discussion_id}/image")

    def get_image(self, discussion_id: int) -> tuple[str, str] | None:
        with self.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute("SELECT i.storage_key, a.format FROM community_discussion d "
                               "JOIN analysis a ON a.id = d.analysis_id JOIN analysis_image i ON i.analysis_id = a.id "
                               "WHERE d.id = %s", (discussion_id,))
                return cursor.fetchone()
            finally:
                cursor.close()

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
