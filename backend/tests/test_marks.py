"""Scholars' workbench, story F: epigraphic marks on boxes, and manual reading order."""

import json
from types import SimpleNamespace

import pytest

from backend.app.box_edits import EditError, MARK_DEFAULTS, marks_of, plan, same, state
from backend.app.model.box_set import UpdateBox
from backend.app.reading_pipeline.transliterate import line_text, marked
from backend.tests.test_box_sets import login, sql_controller
from backend.tests.test_corpus_tablets import corpus_index, fake, tracing  # noqa: F401  (fixtures)

KNOWN = {"AB81": "AB81", "AB01": "AB01", "AB59": "AB59", "AB77": "AB77"}.get


def syllable(id, reading, x):
    return SimpleNamespace(
        id=id,
        sign="AB81",
        reading=reading,
        role="syllabogram",
        box=SimpleNamespace(x=x, y=0, w=0.1, h=0.1),
    )


def test_marks_follow_gorila_conventions():
    assert marked("ku", None) == "ku"
    assert marked("ku", {"certainty": "uncertain"}) == "ḳụ"
    assert marked("ku", {"certainty": "illegible"}) == "•"
    assert marked("ku", {"damage": "partial"}) == "⸢ku⸣"
    assert marked("ku", {"damage": "restored"}) == "[ku]"
    assert marked("ku", {"certainty": "uncertain", "damage": "restored"}) == "[ḳụ]"


def test_a_word_ends_where_marked_and_marks_decorate_the_line():
    line = [syllable(1, "ku", 0.0), syllable(2, "ro", 0.11), syllable(3, "ka", 0.22)]
    assert line_text(line)[0] == "ku-ro-ka"  # close together: one word
    text, _ = line_text(line, {2: {"word_end": True}, 3: {"damage": "restored"}})
    assert text == "ku-ro [ka]"


def test_states_without_marks_read_as_the_defaults():
    old = {"box": {"x": 0.1, "y": 0.1, "w": 0.1, "h": 0.1}, "sign": "AB81", "deleted": False}
    assert same(old, state(old["box"], "AB81"))
    assert not same(old, state(old["box"], "AB81", marks={"certainty": "uncertain"}))
    assert (
        marks_of(None) == MARK_DEFAULTS
        and marks_of(json.dumps({"word_end": True, "x": 1}))["word_end"] is True
    )


def test_planning_marks_checks_and_spells_the_alternatives():
    boxes = {5: state({"x": 0.1, "y": 0.1, "w": 0.1, "h": 0.1}, "AB81")}
    change = UpdateBox(
        op="update",
        box_id=5,
        marks={"certainty": "uncertain", "alternatives": ["AB01", "AB81", "AB01"]},
    )
    (step,) = plan([change], boxes, KNOWN)
    assert step.after["marks"]["certainty"] == "uncertain"
    assert step.after["marks"]["alternatives"] == ["AB01"]  # its own sign and repeats left out
    with pytest.raises(EditError, match="ZZ9 is not a sign"):
        plan([UpdateBox(op="update", box_id=5, marks={"alternatives": ["ZZ9"]})], boxes, KNOWN)
    assert plan([UpdateBox(op="update", box_id=5, marks={})], boxes, KNOWN) == []  # nothing changes
    with pytest.raises(ValueError):
        UpdateBox(op="update", box_id=5, marks=None)


def test_marks_are_saved_shown_in_the_reading_and_undone(monkeypatch, corpus_index, fake):
    with login(monkeypatch) as owner:
        copy = owner.post("/box-sets", json={"tablet": "HT-1", "start": "scholar"}).json()
        box = copy["boxes"][0]
        assert box["marks"] == {**MARK_DEFAULTS}
        edited = owner.patch(
            f"/box-sets/{copy['id']}",
            json={
                "version": 0,
                "changes": [
                    {
                        "op": "update",
                        "box_id": box["id"],
                        "marks": {
                            "certainty": "uncertain",
                            "damage": "restored",
                            "alternatives": ["AB01"],
                            "word_end": True,
                        },
                    }
                ],
            },
        )
        assert edited.status_code == 200, edited.text
        body = edited.json()
        assert (
            body["boxes"][0]["marks"]["alternatives"] == ["AB01"]
            and body["boxes"][0]["changed"] is True
        )
        assert body["reading"]["symbol_interpretation"] == "[ḳạ]"
        (change,) = owner.get(f"/box-sets/{copy['id']}/changes").json()["items"]
        assert change["after"]["marks"]["certainty"] == "uncertain"
        undone = owner.post(
            f"/box-sets/{copy['id']}/changes/{change['id']}/revert", json={"version": 1}
        )
        assert undone.status_code == 200, undone.text
        assert undone.json()["boxes"][0]["marks"]["certainty"] == "certain"
        assert undone.json()["reading"]["symbol_interpretation"] == "ka"


def test_a_scholar_can_set_the_reading_order_by_hand(monkeypatch, corpus_index, fake):
    with login(monkeypatch) as owner:
        copy = owner.post("/box-sets", json={"tablet": "HT-1", "start": "scholar"}).json()
        first = copy["boxes"][0]
        added = owner.patch(
            f"/box-sets/{copy['id']}",
            json={
                "version": 0,
                "changes": [
                    {"op": "add", "box": {"x": 0.6, "y": 0.1, "w": 0.1, "h": 0.2}, "sign": "AB01"}
                ],
            },
        ).json()
        new = next(b for b in added["boxes"] if b["id"] != first["id"])
        assert [s["sign"] for s in added["reading"]["signs"]] == ["AB77", "AB01"]  # left to right
        ordered = owner.patch(
            f"/box-sets/{copy['id']}",
            json={
                "version": 1,
                "changes": [
                    {"op": "update", "box_id": new["id"], "marks": {"line": 0, "seq": 0}},
                    {"op": "update", "box_id": first["id"], "marks": {"line": 1, "seq": 0}},
                ],
            },
        ).json()
        assert [s["sign"] for s in ordered["reading"]["signs"]] == ["AB01", "AB77"]
        assert [line["sign_ids"] for line in ordered["reading"]["lines"]] == [
            [new["id"]],
            [first["id"]],
        ]


def test_sql_writes_marks_with_each_change(monkeypatch):
    controller, _connection, cursor = sql_controller(monkeypatch)
    cursor.fetchone.return_value = {"version": 0}
    cursor.fetchall.side_effect = [
        [
            {
                "id": 5,
                "x": 0.1,
                "y": 0.1,
                "w": 0.1,
                "h": 0.1,
                "sign": "AB81",
                "deleted": 0,
                "marks": None,
            }
        ]
    ]
    change = UpdateBox(op="update", box_id=5, marks={"damage": "partial"})
    assert controller.apply(1, 7, 0, [change], KNOWN) == 1
    statements = [call.args for call in cursor.execute.call_args_list]
    update = next(args for args in statements if args[0].startswith("UPDATE box SET"))
    assert "marks = %s" in update[0] and json.loads(update[1][6])["damage"] == "partial"
    assert "marks" in statements[1][0]  # the boxes are read with their marks
