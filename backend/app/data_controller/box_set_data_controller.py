"""SQL for corrected copies (#83). The editing rules are in backend/app/box_edits.py."""
import json
from datetime import datetime, timezone
from typing import Callable

from mysql.connector.errorcode import ER_DUP_ENTRY
from mysql.connector.errors import IntegrityError

from backend.app.box_edits import GEOMETRY, Step, plan, plan_revert, state
from backend.app.data_controller.data_controller import DataController
from backend.app.model.box_set import Change

BOX_COLUMNS = ("id, x, y, w, h, sign, deleted, origin, original_x, original_y, original_w, original_h, "
               "model_sign, model_confidence, candidates")


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

    def create_from_analysis(self, owner_id: int, analysis_id: int) -> tuple[int, bool] | None:
        """The owner's copy of their own analysis, made from the model's boxes if it does not exist yet.
        Returns (id, created), or None when the analysis is not theirs. Raises NotEditable."""
        existing = self.find_for_analysis(owner_id, analysis_id)
        if existing is not None:
            return existing, False
        rows = self._rows("SELECT result_json, image_id FROM analysis WHERE user_id = %s AND id = %s",
                          (owner_id, analysis_id))
        if not rows:
            return None
        result = json.loads(rows[0]["result_json"])
        if not result.get("trained"):
            raise NotEditable("Boxes from the generic model are objects, not Linear A signs, so they cannot be corrected.")
        if rows[0]["image_id"] is None:
            raise NotEditable("This analysis was saved before images were kept, so its boxes cannot be shown to edit.")
        stamp = _now()
        try:
            with self.connection() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "INSERT INTO box_set (owner_id, analysis_id, start, version, width, height, created_at, updated_at) "
                        "VALUES (%s, %s, 'model', 0, %s, %s, %s, %s)",
                        (owner_id, analysis_id, result["width"], result["height"], stamp, stamp),
                    )
                    set_id = cursor.lastrowid
                    boxes = [(set_id, *(sign["box"][name] for name in GEOMETRY), sign.get("sign"),
                              *(sign["box"][name] for name in GEOMETRY), sign.get("sign"), sign.get("confidence"),
                              json.dumps(sign.get("candidates") or []))
                             for sign in result.get("signs", [])]
                    if boxes:
                        cursor.executemany(
                            "INSERT INTO box (set_id, x, y, w, h, sign, origin, original_x, original_y, original_w, "
                            "original_h, model_sign, model_confidence, candidates) "
                            "VALUES (%s, %s, %s, %s, %s, %s, 'model', %s, %s, %s, %s, %s, %s, %s)", boxes,
                        )
                finally:
                    cursor.close()
        except IntegrityError as error:
            # Two tabs pressed "Edit boxes" at once: the other one made the copy.
            if error.errno != ER_DUP_ENTRY:
                raise
            return self.find_for_analysis(owner_id, analysis_id), False
        return set_id, True

    def load(self, set_id: int) -> dict | None:
        """The copy with its owner, source and every box (deleted ones too, for undo); None if missing."""
        sets = self._rows(
            "SELECT s.id, s.owner_id, u.username AS owner, s.analysis_id, s.tablet_slug, s.start, s.version, "
            "s.width, s.height, s.created_at, s.updated_at, a.filename FROM box_set s "
            "JOIN `user` u ON u.id = s.owner_id LEFT JOIN analysis a ON a.id = s.analysis_id WHERE s.id = %s",
            (set_id,))
        if not sets:
            return None
        found = sets[0]
        found["boxes"] = self._rows(f"SELECT {BOX_COLUMNS} FROM box WHERE set_id = %s ORDER BY id", (set_id,))
        return found

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

    def revert(self, set_id: int, author_id: int, change_id: int, version: int) -> int:
        """Undo one change; returns the new version. Raises StaleVersion, MissingChange or EditError."""
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                current = self._lock(cursor, set_id, version)
                cursor.execute("SELECT id, action, box_id, before_state, after_state, reverted_by_id FROM box_change "
                               "WHERE id = %s AND set_id = %s", (change_id, set_id))
                row = cursor.fetchone()
                if row is None:
                    raise MissingChange()
                cursor.execute("SELECT id, x, y, w, h, sign, deleted FROM box WHERE id = %s", (row["box_id"],))
                box = cursor.fetchone()
                change = {"id": row["id"], "box_id": row["box_id"], "reverted_by": row["reverted_by_id"],
                          "before": json.loads(row["before_state"]) if row["before_state"] else None,
                          "after": json.loads(row["after_state"])}
                step = plan_revert(change, _box_state(box) if box else None)
                self._write_box(cursor, step)
                revert_id = self._record(cursor, set_id, author_id, current + 1, step)
                cursor.execute("UPDATE box_change SET reverted_by_id = %s WHERE id = %s", (revert_id, change_id))
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
        rows = self._rows("SELECT i.storage_key, i.format FROM box_set s JOIN analysis a ON a.id = s.analysis_id "
                          "JOIN uploaded_image i ON i.id = a.image_id WHERE s.id = %s", (set_id,))
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
