"""The rules for editing a corrected copy (#83), with no database: what a batch of changes
does to the boxes, and whether a past change can be undone.

The data controller loads the boxes, asks `plan` or `plan_revert` what to write, and
writes it. Keeping the rules here makes them testable on plain dictionaries.
"""
from dataclasses import dataclass
from typing import Callable

from backend.app.model.box_set import MAX_BOXES, AddBox, Change, DeleteBox, UpdateBox

# Box coordinates come back from MySQL DOUBLE columns exactly as written; compare loosely anyway.
TOLERANCE = 1e-9
GEOMETRY = ("x", "y", "w", "h")


class EditError(ValueError):
    """The batch cannot be applied as sent (unknown box or sign, too many boxes, nothing to undo)."""


@dataclass
class Step:
    action: str  # add, update, delete or revert
    box_id: int | None  # None for a box this batch adds; the controller fills it in
    before: dict | None  # {"box": {...}, "sign": ..., "deleted": ...}; None for an added box
    after: dict
    reverts: int | None = None


def state(box: dict, sign: str | None, deleted: bool = False) -> dict:
    return {"box": {name: float(box[name]) for name in GEOMETRY}, "sign": sign, "deleted": bool(deleted)}


def same(one: dict | None, other: dict | None) -> bool:
    if one is None or other is None:
        return one is other
    return (one["sign"] == other["sign"] and bool(one.get("deleted")) == bool(other.get("deleted"))
            and all(abs(one["box"][name] - other["box"][name]) <= TOLERANCE for name in GEOMETRY))


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

    def live(box_id: int) -> dict:
        found = current.get(box_id)
        if found is None or found["deleted"]:
            raise EditError(f"Box {box_id} is not on this copy.")
        return found

    for change in changes:
        if isinstance(change, AddBox):
            steps.append(Step("add", None, None, state(change.box.model_dump(), sign_of(change.sign))))
            added += 1
        elif isinstance(change, UpdateBox):
            before = live(change.box_id)
            box = change.box.model_dump() if "box" in change.model_fields_set else before["box"]
            sign = sign_of(change.sign) if "sign" in change.model_fields_set else before["sign"]
            after = state(box, sign)
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


def plan_revert(change: dict, current: dict | None) -> Step:
    """Undo one past change: put its box back as the change found it.

    `change` has the stored action, box_id, before, after and reverted_by; `current` is the box
    as it is now. Refused when the change was already undone, or when the box was changed again
    since: undoing it would silently throw the later change away."""
    if change["reverted_by"] is not None:
        raise EditError("This change was already undone.")
    if current is None or not same(current, change["after"]):
        raise EditError("This box was changed again later. Undo the later change first.")
    target = change["before"] if change["before"] is not None else {**change["after"], "deleted": True}
    return Step("revert", change["box_id"], current, dict(target), reverts=change["id"])
