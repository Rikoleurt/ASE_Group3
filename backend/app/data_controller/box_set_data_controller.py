"""SQL for corrected copies (#83). The editing rules are in backend/app/box_edits.py."""
import json
from datetime import datetime, timezone
from typing import Callable

from mysql.connector.errorcode import ER_DUP_ENTRY, ER_NO_REFERENCED_ROW_2
from mysql.connector.errors import IntegrityError

from backend.app.box_edits import GEOMETRY, Step, plan, plan_revert, state
from backend.app.data_controller.data_controller import DataController
from backend.app.model.box_set import Change

BOX_COLUMNS = ("id, x, y, w, h, sign, deleted, origin, original_x, original_y, original_w, original_h, "
               "model_sign, model_confidence, candidates, source_kind, source_set_id, source_box_id, "
               "source_version, source_author_id")
MAX_VERSIONS = 100  # copies listed per tablet


class StaleVersion(Exception):
    """The copy was saved by someone else since the editor loaded it."""


class NotEditable(Exception):
    """The analysis cannot be corrected (generic model, or no kept image)."""


class MissingChange(Exception):
    """No such change on this copy."""


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _box_state(row: dict) -> dict:
    return state(row, row["sign"], row["deleted"])


class BoxSetDataController(DataController):
    def find_for_analysis(self, owner_id: int, analysis_id: int) -> int | None:
        rows = self._rows("SELECT id FROM box_set WHERE owner_id = %s AND analysis_id = %s", (owner_id, analysis_id))
        return rows[0]["id"] if rows else None

    def find_for_tablet(self, owner_id: int, slug: str) -> int | None:
        """The owner's most recently changed copy of a corpus tablet (they may have several)."""
        rows = self._rows("SELECT id FROM box_set WHERE owner_id = %s AND tablet_slug = %s "
                          "ORDER BY updated_at DESC, id DESC LIMIT 1", (owner_id, slug))
        return rows[0]["id"] if rows else None

    def create_from_tablet(self, owner_id: int, slug: str, start: str, signs: list[dict], width: int,
                           height: int, *, new: bool = False, title: str | None = None) -> tuple[int, bool]:
        """The owner's latest copy of a corpus tablet, or a new one (always when `new`) made from the
        given boxes (model's or scholars'). Each sign is {"id", "box": {...}, "sign", "confidence",
        "candidates"}; its id is kept as the box's source."""
        if not new and (existing := self.find_for_tablet(owner_id, slug)) is not None:
            return existing, False
        return self._insert(owner_id, None, slug, start, width, height, signs, title=title), True

    def versions_for_tablet(self, user_id: int, slug: str) -> list[dict]:
        """The copies of a tablet the user can open: their own, and others' shared with them or with
        everyone. Their own first, then the most recently changed."""
        return self._rows(
            "SELECT s.id, s.owner_id, u.username AS owner, s.title, s.kind, s.start, s.everyone, s.version, "
            "sh.permission AS share, s.created_at, s.updated_at, "
            "(SELECT COUNT(*) FROM box b WHERE b.set_id = s.id AND NOT b.deleted) AS box_count "
            "FROM box_set s JOIN `user` u ON u.id = s.owner_id "
            "LEFT JOIN box_set_share sh ON sh.set_id = s.id AND sh.user_id = %s "
            "WHERE s.tablet_slug = %s AND (s.owner_id = %s OR sh.user_id IS NOT NULL OR s.everyone <> 'none') "
            "ORDER BY s.owner_id = %s DESC, s.updated_at DESC, s.id DESC LIMIT %s",
            (user_id, slug, user_id, user_id, MAX_VERSIONS))

    def create_from_analysis(self, owner_id: int, analysis_id: int) -> tuple[int, bool] | None:
        """The owner's copy of their own analysis, made from the model's boxes if it does not exist yet.
        Returns (id, created), or None when the analysis is not theirs. Raises NotEditable."""
        existing = self.find_for_analysis(owner_id, analysis_id)
        if existing is not None:
            return existing, False
        rows = self._rows("SELECT a.result_json, i.storage_key AS image_key FROM analysis a "
                          "LEFT JOIN analysis_image i ON i.analysis_id = a.id WHERE a.user_id = %s AND a.id = %s",
                          (owner_id, analysis_id))
        if not rows:
            return None
        result = json.loads(rows[0]["result_json"])
        if not result.get("trained"):
            raise NotEditable("Boxes from the generic model are objects, not Linear A signs, so they cannot be corrected.")
        if rows[0]["image_key"] is None:
            raise NotEditable("This analysis was saved before images were kept, so its boxes cannot be shown to edit.")
        try:
            set_id = self._insert(owner_id, analysis_id, None, "model", result["width"], result["height"],
                                  result.get("signs", []))
        except IntegrityError as error:
            # Two tabs pressed "Correct the boxes" at once: the other one made the copy.
            if error.errno != ER_DUP_ENTRY:
                raise
            return self.find_for_analysis(owner_id, analysis_id), False
        return set_id, True

    def _insert(self, owner_id: int, analysis_id: int | None, slug: str | None, start: str, width: int,
                height: int, signs: list[dict], *, title: str | None = None) -> int:
        """A new copy and its starting boxes, in one transaction. `start` is also each box's origin,
        and each box records the sign it started as (its id among the model's or scholars' signs)."""
        stamp = _now()
        with self.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "INSERT INTO box_set (owner_id, analysis_id, tablet_slug, title, start, version, width, height, "
                    "created_at, updated_at) VALUES (%s, %s, %s, %s, %s, 0, %s, %s, %s, %s)",
                    (owner_id, analysis_id, slug, title, start, width, height, stamp, stamp),
                )
                set_id = cursor.lastrowid
                # A scholar's box carries no model confidence.
                boxes = [(set_id, *(sign["box"][name] for name in GEOMETRY), sign.get("sign"), start,
                          *(sign["box"][name] for name in GEOMETRY), sign.get("sign"),
                          sign.get("confidence") if start == "model" else None,
                          json.dumps(sign.get("candidates") or []), start, sign.get("id"))
                         for sign in signs]
                if boxes:
                    cursor.executemany(
                        "INSERT INTO box (set_id, x, y, w, h, sign, origin, original_x, original_y, original_w, "
                        "original_h, model_sign, model_confidence, candidates, source_kind, source_box_id) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", boxes,
                    )
            finally:
                cursor.close()
        return set_id

    def create_edition(self, owner_id: int, slug: str, title: str | None, width: int, height: int,
                       boxes: list[dict], merged_from: list[dict]) -> int:
        """A new edition of a tablet merged from several versions (workbench, story D), in one
        transaction. Each box is {"box", "sign", "origin", "source_kind", "source_set_id",
        "source_box_id", "source_version", "source_author_id"}; it starts unchanged."""
        stamp = _now()
        with self.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "INSERT INTO box_set (owner_id, analysis_id, tablet_slug, title, kind, merged_from, start, version, "
                    "width, height, created_at, updated_at) VALUES (%s, NULL, %s, %s, 'edition', %s, 'scholar', 0, "
                    "%s, %s, %s, %s)",
                    (owner_id, slug, title, json.dumps(merged_from), width, height, stamp, stamp),
                )
                set_id = cursor.lastrowid
                rows = [(set_id, *(item["box"][name] for name in GEOMETRY), item.get("sign"), item["origin"],
                         *(item["box"][name] for name in GEOMETRY), item.get("sign"), json.dumps([]),
                         item["source_kind"], item.get("source_set_id"), item.get("source_box_id"),
                         item.get("source_version"), item.get("source_author_id"))
                        for item in boxes]
                if rows:
                    cursor.executemany(
                        "INSERT INTO box (set_id, x, y, w, h, sign, origin, original_x, original_y, original_w, "
                        "original_h, model_sign, candidates, source_kind, source_set_id, source_box_id, "
                        "source_version, source_author_id) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", rows,
                    )
            finally:
                cursor.close()
        return set_id

    def contributors(self, set_id: int) -> list[str]:
        """Usernames credited for a copy: the authors of the boxes merged into it, and everyone
        who saved a change to it, in alphabetical order."""
        rows = self._rows(
            "SELECT DISTINCT u.username FROM `user` u WHERE u.id IN ("
            "SELECT b.source_author_id FROM box b WHERE b.set_id = %s AND b.source_author_id IS NOT NULL "
            "UNION SELECT c.author_id FROM box_change c WHERE c.set_id = %s) ORDER BY u.username",
            (set_id, set_id))
        return [row["username"] for row in rows]

    def load(self, set_id: int) -> dict | None:
        """The copy with its owner, source and every box (deleted ones too, for undo); None if missing."""
        sets = self._rows(
            "SELECT s.id, s.owner_id, u.username AS owner, s.analysis_id, s.tablet_slug, s.title, s.kind, "
            "s.merged_from, s.start, "
            "s.version, s.everyone, "
            "s.width, s.height, s.created_at, s.updated_at, a.filename FROM box_set s "
            "JOIN `user` u ON u.id = s.owner_id LEFT JOIN analysis a ON a.id = s.analysis_id WHERE s.id = %s",
            (set_id,))
        if not sets:
            return None
        found = sets[0]
        found["boxes"] = self._rows(
            "SELECT " + ", ".join(f"b.{column.strip()}" for column in BOX_COLUMNS.split(",")) +
            ", su.username AS source_author FROM box b LEFT JOIN `user` su ON su.id = b.source_author_id "
            "WHERE b.set_id = %s ORDER BY b.id", (set_id,))
        found["contributors"] = self.contributors(set_id)
        return found

    # Sharing (#84). The rules are in backend/app/sharing.py.

    def share_of(self, set_id: int, user_id: int) -> str | None:
        """The level this copy is shared with the user at, or None."""
        rows = self._rows("SELECT permission FROM box_set_share WHERE set_id = %s AND user_id = %s", (set_id, user_id))
        return rows[0]["permission"] if rows else None

    def shares(self, set_id: int) -> list[dict]:
        return self._rows(
            "SELECT sh.user_id, u.username, sh.permission, sh.created_at FROM box_set_share sh "
            "JOIN `user` u ON u.id = sh.user_id WHERE sh.set_id = %s ORDER BY u.username", (set_id,))

    def set_share(self, set_id: int, user_id: int, permission: str, granted_by: int) -> bool:
        """Share the copy with a user, or change their level. False when there is no such user."""
        try:
            self._rows(
                "INSERT INTO box_set_share (set_id, user_id, permission, granted_by, created_at) VALUES (%s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE permission = VALUES(permission), granted_by = VALUES(granted_by)",
                (set_id, user_id, permission, granted_by, _now()), fetch=False)
        except IntegrityError as error:
            if error.errno == ER_NO_REFERENCED_ROW_2:
                return False
            raise
        return True

    def remove_share(self, set_id: int, user_id: int) -> None:
        self._rows("DELETE FROM box_set_share WHERE set_id = %s AND user_id = %s", (set_id, user_id), fetch=False)

    def set_everyone(self, set_id: int, level: str) -> None:
        self._rows("UPDATE box_set SET everyone = %s WHERE id = %s", (level, set_id), fetch=False)

    def shared_with(self, user_id: int, limit: int) -> list[dict]:
        """Other people's copies the user can open: shared with them, or with everyone. Newest change first."""
        return self._rows(
            "SELECT s.id, u.username AS owner, s.analysis_id, s.tablet_slug, a.filename, s.everyone, "
            "sh.permission AS share, s.updated_at FROM box_set s JOIN `user` u ON u.id = s.owner_id "
            "LEFT JOIN analysis a ON a.id = s.analysis_id "
            "LEFT JOIN box_set_share sh ON sh.set_id = s.id AND sh.user_id = %s "
            "WHERE s.owner_id <> %s AND (sh.user_id IS NOT NULL OR s.everyone <> 'none') "
            "ORDER BY s.updated_at DESC, s.id DESC LIMIT %s", (user_id, user_id, limit))

    # Comments (#86).

    def comments(self, set_id: int, box_id: int | None = None, limit: int = 500) -> list[dict]:
        """The newest `limit` comments, oldest first; with box_id, that box's thread only."""
        clause, params = (" AND c.box_id = %s", (set_id, box_id)) if box_id is not None else ("", (set_id,))
        rows = self._rows(
            "SELECT c.id, c.box_id, c.author_id, u.username, c.body, c.created_at FROM box_comment c "
            "LEFT JOIN `user` u ON u.id = c.author_id WHERE c.set_id = %s" + clause + " ORDER BY c.id DESC LIMIT %s",
            (*params, limit))
        return rows[::-1]

    def comment(self, set_id: int, comment_id: int) -> dict | None:
        rows = self._rows("SELECT id, author_id FROM box_comment WHERE id = %s AND set_id = %s", (comment_id, set_id))
        return rows[0] if rows else None

    def add_comment(self, set_id: int, box_id: int | None, author_id: int, body: str) -> dict:
        stamp = _now()
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute("INSERT INTO box_comment (set_id, box_id, author_id, body, created_at) "
                               "VALUES (%s, %s, %s, %s, %s)", (set_id, box_id, author_id, body, stamp))
                comment_id = cursor.lastrowid
                cursor.execute("SELECT username FROM `user` WHERE id = %s", (author_id,))
                author = cursor.fetchone()
            finally:
                cursor.close()
        return {"id": comment_id, "box_id": box_id, "author_id": author_id,
                "username": author["username"] if author else None, "body": body, "created_at": stamp}

    def delete_comment(self, comment_id: int) -> None:
        self._rows("DELETE FROM box_comment WHERE id = %s", (comment_id,), fetch=False)

    def apply(self, set_id: int, author_id: int, version: int, changes: list[Change],
              known_sign: Callable[[str], str | None]) -> int:
        """Apply one save; returns the new version (unchanged if nothing changed).
        Raises StaleVersion, or EditError (box_edits) before anything is written."""
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                current = self._lock(cursor, set_id, version)
                cursor.execute("SELECT id, x, y, w, h, sign, deleted FROM box WHERE set_id = %s", (set_id,))
                boxes = {row["id"]: _box_state(row) for row in cursor.fetchall()}
                steps = plan(changes, boxes, known_sign)
                if not steps:
                    return current
                for step in steps:
                    if step.action == "add":
                        box = step.after["box"]
                        cursor.execute(
                            "INSERT INTO box (set_id, x, y, w, h, sign, origin) VALUES (%s, %s, %s, %s, %s, %s, 'user')",
                            (set_id, *(box[name] for name in GEOMETRY), step.after["sign"]),
                        )
                        step.box_id = cursor.lastrowid
                    else:
                        self._write_box(cursor, step)
                    self._record(cursor, set_id, author_id, current + 1, step)
                return self._bump(cursor, set_id, current)
            finally:
                cursor.close()

    def revert(self, set_id: int, author_id: int, change_id: int, version: int,
               known_sign: Callable[[str], str | None] | None = None) -> int:
        """Undo one change; returns the new version. Raises StaleVersion, MissingChange or EditError."""
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                current = self._lock(cursor, set_id, version)
                cursor.execute("SELECT id, action, box_id, before_state, after_state, reverts_id, reverted_by_id "
                               "FROM box_change WHERE id = %s AND set_id = %s", (change_id, set_id))
                row = cursor.fetchone()
                if row is None:
                    raise MissingChange()
                cursor.execute("SELECT id, x, y, w, h, sign, deleted FROM box WHERE id = %s", (row["box_id"],))
                box = cursor.fetchone()
                change = {"id": row["id"], "box_id": row["box_id"], "reverted_by": row["reverted_by_id"],
                          "before": json.loads(row["before_state"]) if row["before_state"] else None,
                          "after": json.loads(row["after_state"])}
                cursor.execute("SELECT COUNT(*) AS live FROM box WHERE set_id = %s AND deleted = FALSE", (set_id,))
                live = cursor.fetchone()["live"]
                step = plan_revert(change, _box_state(box) if box else None, live, known_sign)
                self._write_box(cursor, step)
                revert_id = self._record(cursor, set_id, author_id, current + 1, step)
                cursor.execute("UPDATE box_change SET reverted_by_id = %s WHERE id = %s", (revert_id, change_id))
                if row["action"] == "revert" and row["reverts_id"] is not None:
                    # Undoing an undo: the change it undid is in effect again, so it can be undone again.
                    cursor.execute("UPDATE box_change SET reverted_by_id = NULL WHERE id = %s", (row["reverts_id"],))
                return self._bump(cursor, set_id, current)
            finally:
                cursor.close()

    def changes(self, set_id: int, limit: int, before: int | None = None) -> list[dict]:
        """Newest first, one extra row to tell whether there are older ones."""
        clause, params = (" AND c.id < %s", (set_id, before, limit + 1)) if before else ("", (set_id, limit + 1))
        rows = self._rows(
            "SELECT c.id, c.author_id, u.username, c.created_at, c.version, c.action, c.box_id, c.before_state, "
            "c.after_state, c.reverts_id, c.reverted_by_id FROM box_change c LEFT JOIN `user` u ON u.id = c.author_id "
            "WHERE c.set_id = %s" + clause + " ORDER BY c.id DESC LIMIT %s", params)
        for row in rows:
            row["before_state"] = json.loads(row["before_state"]) if row["before_state"] else None
            row["after_state"] = json.loads(row["after_state"])
        return rows

    def delete(self, set_id: int) -> None:
        self._rows("DELETE FROM box_set WHERE id = %s", (set_id,), fetch=False)

    def image(self, set_id: int) -> tuple[str, str] | None:
        """Storage key and format of the copy's image (an upload's kept image)."""
        rows = self._rows("SELECT i.storage_key, a.format FROM box_set s JOIN analysis a ON a.id = s.analysis_id "
                          "JOIN analysis_image i ON i.analysis_id = a.id WHERE s.id = %s", (set_id,))
        return (rows[0]["storage_key"], rows[0]["format"]) if rows else None

    @staticmethod
    def _lock(cursor, set_id: int, version: int) -> int:
        # Locks the copy until the transaction ends, so two saves cannot interleave.
        cursor.execute("SELECT version FROM box_set WHERE id = %s FOR UPDATE", (set_id,))
        row = cursor.fetchone()
        if row is None or row["version"] != version:
            raise StaleVersion()
        return row["version"]

    @staticmethod
    def _write_box(cursor, step: Step) -> None:
        box = step.after["box"]
        cursor.execute("UPDATE box SET x = %s, y = %s, w = %s, h = %s, sign = %s, deleted = %s WHERE id = %s",
                       (*(box[name] for name in GEOMETRY), step.after["sign"], step.after["deleted"], step.box_id))

    @staticmethod
    def _record(cursor, set_id: int, author_id: int, version: int, step: Step) -> int:
        cursor.execute(
            "INSERT INTO box_change (set_id, author_id, created_at, version, action, box_id, before_state, "
            "after_state, reverts_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (set_id, author_id, _now(), version, step.action, step.box_id,
             json.dumps(step.before) if step.before is not None else None, json.dumps(step.after), step.reverts),
        )
        return cursor.lastrowid

    @staticmethod
    def _bump(cursor, set_id: int, current: int) -> int:
        cursor.execute("UPDATE box_set SET version = %s, updated_at = %s WHERE id = %s", (current + 1, _now(), set_id))
        return current + 1

    def _rows(self, query: str, params: tuple, fetch: bool = True) -> list[dict]:
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(query, params)
                return cursor.fetchall() if fetch else []
            finally:
                cursor.close()
