"""The rules for editing a corrected copy (#83), with no database: what a batch of changes
does to the boxes, and whether a past change can be undone.

The data controller loads the boxes, asks `plan` or `plan_revert` what to write, and
writes it. Keeping the rules here makes them testable on plain dictionaries.
"""
import json
from dataclasses import dataclass
from typing import Callable

from backend.app.model.box_set import MAX_BOXES, AddBox, Change, DeleteBox, UpdateBox

# Box coordinates come back from MySQL DOUBLE columns exactly as written; compare loosely anyway.
TOLERANCE = 1e-9
GEOMETRY = ("x", "y", "w", "h")
# A box's epigraphic marks (workbench, story F); states saved before them read as these defaults.
MARK_DEFAULTS = {"certainty": "certain", "damage": "none", "alternatives": [], "word_end": False,
                 "line": None, "seq": None}


class EditError(ValueError):
    """The batch cannot be applied as sent (unknown box or sign, too many boxes, nothing to undo)."""


@dataclass
class Step:
    action: str  # add, update, delete or revert
    box_id: int | None  # None for a box this batch adds; the controller fills it in
    before: dict | None  # {"box": {...}, "sign": ..., "deleted": ...}; None for an added box
    after: dict
    reverts: int | None = None


def marks_of(value) -> dict:
    """A box's marks with every field (from a dict, the JSON column, or None)."""
    if isinstance(value, (str, bytes)):
        value = json.loads(value)
    found = {**MARK_DEFAULTS, **{key: item for key, item in (value or {}).items() if key in MARK_DEFAULTS}}
    found["alternatives"] = list(found["alternatives"] or [])
    return found


def state(box: dict, sign: str | None, deleted: bool = False, marks=None) -> dict:
    return {"box": {name: float(box[name]) for name in GEOMETRY}, "sign": sign, "deleted": bool(deleted),
            "marks": marks_of(marks)}


def same(one: dict | None, other: dict | None) -> bool:
    if one is None or other is None:
        return one is other
    return (one["sign"] == other["sign"] and bool(one.get("deleted")) == bool(other.get("deleted"))
            and all(abs(one["box"][name] - other["box"][name]) <= TOLERANCE for name in GEOMETRY)
            and marks_of(one.get("marks")) == marks_of(other.get("marks")))


def plan(changes: list[Change], boxes: dict[int, dict], known_sign: Callable[[str], str | None]) -> list[Step]:
    """The steps a batch makes, in order. `boxes` maps box id to its current state (see `state`);
    `known_sign` returns the catalogue's spelling of a sign, or None if it is not a sign.
    Changes that alter nothing are dropped. Raises EditError, and then nothing is written."""
    current = {box_id: dict(value) for box_id, value in boxes.items()}
    steps: list[Step] = []
    added = 0

    def sign_of(proposed: str | None) -> str | None:
        if proposed is None:
            return None
        spelled = known_sign(proposed)
        if spelled is None:
            raise EditError(f"{proposed} is not a sign in the catalogue.")
        return spelled

    def marks(proposed, sign: str | None) -> dict:
        """The marks with each alternative in the catalogue's spelling, the box's own sign left out."""
        found = marks_of(proposed.model_dump() if hasattr(proposed, "model_dump") else proposed)
        found["alternatives"] = list(dict.fromkeys(
            spelled for spelled in (sign_of(item) for item in found["alternatives"]) if spelled != sign))
        return found

    def live(box_id: int) -> dict:
        found = current.get(box_id)
        if found is None or found["deleted"]:
            raise EditError(f"Box {box_id} is not on this copy.")
        return found

    for change in changes:
        if isinstance(change, AddBox):
            sign = sign_of(change.sign)
            steps.append(Step("add", None, None, state(change.box.model_dump(), sign, marks=marks(change.marks, sign))))
            added += 1
        elif isinstance(change, UpdateBox):
            before = live(change.box_id)
            box = change.box.model_dump() if "box" in change.model_fields_set else before["box"]
            sign = sign_of(change.sign) if "sign" in change.model_fields_set else before["sign"]
            proposed = change.marks if "marks" in change.model_fields_set else before.get("marks")
            after = state(box, sign, marks=marks(proposed, sign))
            if not same(before, after):
                steps.append(Step("update", change.box_id, before, after))
                current[change.box_id] = after
        elif isinstance(change, DeleteBox):
            before = live(change.box_id)
            after = {**before, "deleted": True}
            steps.append(Step("delete", change.box_id, before, after))
            current[change.box_id] = after
    if sum(not value["deleted"] for value in current.values()) + added > MAX_BOXES:
        raise EditError(f"A copy can hold at most {MAX_BOXES} boxes.")
    return steps


def plan_revert(change: dict, current: dict | None, live_boxes: int = 0,
                known_sign: Callable[[str], str | None] | None = None) -> Step:
    """Undo one past change: put its box back as the change found it.

    `change` has the stored action, box_id, before, after and reverted_by; `current` is the box
    as it is now; `live_boxes` counts the copy's boxes that are not deleted. Refused when the
    change was already undone, when the box was changed again since (undoing it would silently
    throw the later change away), when bringing a box back would pass the box limit, or when the
    sign it would bring back is no longer in the catalogue."""
    if change["reverted_by"] is not None:
        raise EditError("This change was already undone.")
    if current is None or not same(current, change["after"]):
        raise EditError("This box was changed again later. Undo the later change first.")
    target = change["before"] if change["before"] is not None else {**change["after"], "deleted": True}
    if current["deleted"] and not target["deleted"] and live_boxes >= MAX_BOXES:
        raise EditError(f"A copy can hold at most {MAX_BOXES} boxes.")
    if target["sign"] is not None and known_sign is not None and known_sign(target["sign"]) is None:
        raise EditError(f"{target['sign']} is no longer a sign in the catalogue.")
    return Step("revert", change["box_id"], current, dict(target), reverts=change["id"])
