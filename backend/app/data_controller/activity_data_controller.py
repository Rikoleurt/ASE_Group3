"""Activity on corpus glyphs since a user last opened them (scholars' workbench, story I).

A glyph is a sign of a corpus tablet, keyed "<slug>:<position>" (the scholars' transcription
position). Its activity is read from what is already recorded, with times:

* comments saved against it in the glyph pane (glyph_annotation_target);
* comments on, and saved changes to, a box that started as that scholars' sign
  (box.source_kind = 'scholar', source_box_id = position) in a copy the user can open.

Your own activity does not count. A glyph never opened counts the last NEW_DAYS days.
"""

from datetime import datetime, timezone

from backend.app.data_controller.data_controller import DataController

NEW_DAYS = 14

VISIBLE_COPY = "(s.owner_id = %s OR sh.user_id IS NOT NULL OR s.everyone <> 'none')"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ActivityDataController(DataController):
    def glyph_activity(self, user_id: int, slug: str) -> dict[int, int]:
        """position -> number of others' comments and changes since the user last opened it."""
        copies = (
            "FROM box b JOIN box_set s ON s.id = b.set_id "
            "LEFT JOIN box_set_share sh ON sh.set_id = s.id AND sh.user_id = %s "
            f"WHERE s.tablet_slug = %s AND b.source_kind = 'scholar' AND {VISIBLE_COPY}"
        )
        query = (
            "SELECT e.position, COUNT(*) AS n FROM ("
            "SELECT t.position, a.created_at FROM glyph_annotation a "
            "JOIN glyph_annotation_target t ON t.annotation_id = a.id "
            "WHERE t.tablet_id = %s AND a.author_id <> %s "
            "UNION ALL SELECT b.source_box_id, c.created_at FROM box_comment c "
            f"JOIN (SELECT b.id, b.source_box_id {copies}) b ON b.id = c.box_id WHERE c.author_id <> %s "
            "UNION ALL SELECT b.source_box_id, ch.created_at FROM box_change ch "
            f"JOIN (SELECT b.id, b.source_box_id {copies}) b ON b.id = ch.box_id WHERE ch.author_id <> %s"
            ") e LEFT JOIN glyph_seen g ON g.user_id = %s AND g.glyph_key = CONCAT(%s, ':', e.position) "
            f"WHERE e.created_at > COALESCE(g.seen_at, UTC_TIMESTAMP(6) - INTERVAL {NEW_DAYS} DAY) "
            "GROUP BY e.position"
        )
        params = (
            slug,
            user_id,
            user_id,
            slug,
            user_id,
            user_id,
            user_id,
            slug,
            user_id,
            user_id,
            user_id,
            slug,
        )
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(query, params)
                return {int(row["position"]): int(row["n"]) for row in cursor.fetchall()}
            finally:
                cursor.close()

    def mark_seen(self, user_id: int, glyph_key: str) -> None:
        with self.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "INSERT INTO glyph_seen (user_id, glyph_key, seen_at) VALUES (%s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE seen_at = VALUES(seen_at)",
                    (user_id, glyph_key, _now()),
                )
            finally:
                cursor.close()
