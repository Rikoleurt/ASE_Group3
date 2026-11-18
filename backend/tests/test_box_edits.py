"""The rules for editing a corrected copy (#83), on plain dictionaries."""
import pytest
from pydantic import TypeAdapter, ValidationError

from backend.app.box_edits import EditError, plan, plan_revert, same, state
from backend.app.model.box_set import MAX_BOXES, BoxSetEdit, Change

CHANGES = TypeAdapter(list[Change])
KNOWN = {"AB81": "AB81", "ab81": "AB81", "AB02": "AB02", "J": "J"}


def known(sign):
    return KNOWN.get(sign)


def box(x=0.1, y=0.1, w=0.05, h=0.05):
    return {"x": x, "y": y, "w": w, "h": h}


def boxes():
    return {1: state(box(), "AB81"), 2: state(box(x=0.3), "J"), 3: state(box(x=0.5), None, deleted=True)}


def changes(*items):
    return CHANGES.validate_python(list(items))


def test_add_move_relabel_and_delete_in_one_batch():
    steps = plan(changes(
        {"op": "add", "box": box(x=0.7), "sign": "ab81"},
        {"op": "update", "box_id": 1, "box": box(x=0.2)},
        {"op": "update", "box_id": 2, "sign": "AB02"},
        {"op": "delete", "box_id": 1},
    ), boxes(), known)
    assert [(step.action, step.box_id) for step in steps] == [("add", None), ("update", 1), ("update", 2), ("delete", 1)]
    assert steps[0].before is None and steps[0].after == state(box(x=0.7), "AB81")  # the catalogue's spelling
    assert steps[1].after["box"]["x"] == 0.2 and steps[1].after["sign"] == "AB81"  # moving keeps the sign
    assert steps[2].after["box"] == box(x=0.3) and steps[2].after["sign"] == "AB02"  # relabelling keeps the box
    # The delete sees the move made earlier in the same batch.
    assert steps[3].before["box"]["x"] == 0.2 and steps[3].after["deleted"] is True


def test_sign_null_clears_the_sign_and_leaving_it_out_keeps_it():
    cleared, = plan(changes({"op": "update", "box_id": 1, "sign": None}), boxes(), known)
    assert cleared.after["sign"] is None
    moved, = plan(changes({"op": "update", "box_id": 1, "box": box(y=0.4)}), boxes(), known)
    assert moved.after["sign"] == "AB81"


def test_changes_that_alter_nothing_are_dropped():
    assert plan(changes({"op": "update", "box_id": 1, "box": box(), "sign": "AB81"}), boxes(), known) == []


@pytest.mark.parametrize("change,message", [
    ({"op": "update", "box_id": 9, "sign": "J"}, "Box 9 is not on this copy."),
    ({"op": "delete", "box_id": 3}, "Box 3 is not on this copy."),  # already deleted
    ({"op": "add", "box": box(), "sign": "XYZ"}, "XYZ is not a sign in the catalogue."),
])
def test_unknown_boxes_and_signs_are_refused(change, message):
    with pytest.raises(EditError, match=message):
        plan(changes(change), boxes(), known)


def test_a_box_cannot_be_changed_after_it_is_deleted_in_the_same_batch():
    with pytest.raises(EditError):
        plan(changes({"op": "delete", "box_id": 1}, {"op": "update", "box_id": 1, "sign": "J"}), boxes(), known)


def test_a_copy_holds_a_limited_number_of_boxes():
    full = {index: state(box(), None) for index in range(1, MAX_BOXES + 1)}
    with pytest.raises(EditError, match="at most"):
        plan(changes({"op": "add", "box": box()}), full, known)
    # Deleting one makes room for one.
    assert len(plan(changes({"op": "delete", "box_id": 1}, {"op": "add", "box": box()}), full, known)) == 2


@pytest.mark.parametrize("bad", [
    {"op": "add", "box": box(x=0.98)},  # past the right edge
    {"op": "add", "box": box(x=-0.01)},
    {"op": "add", "box": box(w=0.0005)},  # too small
    {"op": "update", "box_id": 1},  # changes nothing
    {"op": "update", "box_id": 1, "box": None},
    {"op": "move", "box_id": 1},
    {"op": "add", "box": box(), "sign": ""},
])
def test_malformed_changes_are_rejected_before_planning(bad):
    with pytest.raises(ValidationError):
        changes(bad)


def test_a_save_needs_at_least_one_change():
    with pytest.raises(ValidationError):
        BoxSetEdit(version=0, changes=[])


def change(**fields):
    return {"id": 7, "box_id": 1, "reverted_by": None, "before": state(box(), "AB81"),
            "after": state(box(x=0.2), "AB81"), **fields}


def test_undo_puts_the_box_back():
    step = plan_revert(change(), state(box(x=0.2), "AB81"))
    assert (step.action, step.box_id, step.reverts) == ("revert", 1, 7)
    assert step.after == state(box(), "AB81") and step.before == state(box(x=0.2), "AB81")


def test_undoing_an_add_deletes_the_box_and_undoing_a_delete_restores_it():
    added = plan_revert(change(before=None), state(box(x=0.2), "AB81"))
    assert added.after["deleted"] is True
    deleted = change(before=state(box(), "J"), after=state(box(), "J", deleted=True))
    assert plan_revert(deleted, state(box(), "J", deleted=True)).after == state(box(), "J")


def test_undo_is_refused_when_the_box_changed_since_or_it_was_undone():
    with pytest.raises(EditError, match="changed again later"):
        plan_revert(change(), state(box(x=0.3), "AB81"))
    with pytest.raises(EditError, match="already undone"):
        plan_revert(change(reverted_by=8), state(box(x=0.2), "AB81"))


def test_states_compare_with_a_tolerance_for_stored_doubles():
    assert same(state(box(x=0.1), "J"), state(box(x=0.1 + 1e-12), "J"))
    assert not same(state(box(), "J"), state(box(), "AB81"))
    assert not same(state(box(), "J"), state(box(), "J", deleted=True))
