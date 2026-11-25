"""Notifications (scholars' workbench, story I): a short message and a link for the people a change
concerns, shown under the bell in the top bar.

Write paths call `notify(...)` after their change succeeded. A notification is never worth failing
the change for, so a failure here is logged and swallowed. The actor is never notified of their
own action. Tests swap `SINK` for an in-memory recorder (backend/tests/conftest.py).
"""

import logging
from datetime import datetime, timezone

from backend.app.data_controller.data_controller import DataController

log = logging.getLogger(__name__)
KINDS = ("share", "comment", "mention", "vote", "override", "merge", "voting_rights")
MAX_MESSAGE = 300


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class NotificationDataController(DataController):
    def add(self, rows: list[tuple]) -> None:
        """rows: (user_id, kind, actor_id, message, link, tablet_slug, created_at)."""
        with self.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.executemany(
                    "INSERT INTO notification (user_id, kind, actor_id, message, link, tablet_slug, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    rows,
                )
            finally:
                cursor.close()

    def page(self, user_id: int, limit: int, before: int | None = None) -> list[dict]:
        """The user's notifications, newest first, one more than `limit` (to tell if there are more)."""
        query = (
            "SELECT n.id, n.kind, u.username AS actor, n.message, n.link, n.tablet_slug, n.created_at, n.read_at "
            "FROM notification n LEFT JOIN `user` u ON u.id = n.actor_id WHERE n.user_id = %s"
        )
        params: tuple = (user_id,)
        if before is not None:
            query += " AND n.id < %s"
            params += (before,)
        return self._rows(query + " ORDER BY n.id DESC LIMIT %s", params + (limit + 1,))

    def unread(self, user_id: int) -> int:
        rows = self._rows(
            "SELECT COUNT(*) AS n FROM notification WHERE user_id = %s AND read_at IS NULL",
            (user_id,),
        )
        return int(rows[0]["n"]) if rows else 0

    def mark_read(self, user_id: int, ids: list[int] | None) -> None:
        """Mark the given notifications read, or all of the user's when `ids` is None."""
        query = "UPDATE notification SET read_at = %s WHERE user_id = %s AND read_at IS NULL"
        params: tuple = (_now(), user_id)
        if ids is not None:
            if not ids:
                return
            query += f" AND id IN ({', '.join(['%s'] * len(ids))})"
            params += tuple(ids)
        self._rows(query, params, fetch=False)

    def _rows(self, query: str, params: tuple, fetch: bool = True) -> list[dict]:
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(query, params)
                return cursor.fetchall() if fetch else []
            finally:
                cursor.close()


def tablet_name(slug: str | None) -> str:
    return slug.replace("-", " ") if slug else "a tablet"


def copy_name(record: dict) -> str:
    """How a message names a copy: "the copy “Mine” of HT 13", "a copy of HT 13", "a copy of photo.png"."""
    of = (
        tablet_name(record.get("tablet_slug"))
        if record.get("tablet_slug")
        else record.get("filename") or "an upload"
    )
    what = "edition" if record.get("kind") == "edition" else "copy"
    return (
        f"the {what} “{record['title']}” of {of}"
        if record.get("title")
        else f"{'an' if what == 'edition' else 'a'} {what} of {of}"
    )


def quote(text: str, length: int = 80) -> str:
    text = " ".join(text.split())
    return f"“{text[:length]}{'…' if len(text) > length else ''}”"


SINK = None  # tests set an in-memory recorder; None means the database


def notify(
    user_ids,
    kind: str,
    actor_id: int | None,
    message: str,
    link: str | None = None,
    tablet: str | None = None,
) -> None:
    """Tell these users about a change, except the actor. Never raises."""
    targets = sorted(
        {int(user_id) for user_id in user_ids if user_id is not None and user_id != actor_id}
    )
    if not targets:
        return
    assert kind in KINDS, kind
    stamp = _now()
    rows = [
        (user_id, kind, actor_id, message[:MAX_MESSAGE], link, tablet, stamp) for user_id in targets
    ]
    try:
        (SINK or NotificationDataController()).add(rows)
    except Exception:  # noqa: BLE001  (a notification must never fail the change that caused it)
        log.warning("Could not save %d notification(s) of kind %s", len(rows), kind, exc_info=True)
