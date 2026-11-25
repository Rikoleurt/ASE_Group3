"""Scholars' workbench, story D: merging versions of a tablet into an edition."""

import json

from backend.app.box_edits import marks_of
from backend.tests.test_box_sets import login, sql_controller
from backend.tests.test_corpus_tablets import corpus_index, fake, tracing  # noqa: F401  (fixtures)


def anouk_renames_the_sign(monkeypatch, fake, sign="AB01"):
    """User 8 (u8) makes a copy of HT-1 from the scholars' boxes, opens it to everyone, and renames
    its one box; returns the copy as the API gives it."""
    with login(monkeypatch, user_id=8) as other:
        copy = other.post("/box-sets", json={"tablet": "HT-1", "start": "scholar"}).json()
        edited = other.patch(
            f"/box-sets/{copy['id']}",
            json={
                "version": 0,
                "changes": [{"op": "update", "box_id": copy["boxes"][0]["id"], "sign": sign}],
            },
        )
        assert edited.status_code == 200
    fake.sets[copy["id"]]["everyone"] = "view"
    return edited.json()


def merge(client, sources, picks, title="Agreed reading"):
    return client.post(
        "/box-sets/merge",
        json={"tablet": "HT-1", "title": title, "sources": sources, "picks": picks},
    )


def test_merging_keeps_the_chosen_boxes_with_their_source_and_credit(
    monkeypatch, corpus_index, fake
):
    theirs = anouk_renames_the_sign(monkeypatch, fake)
    key = f"copy:{theirs['id']}"
    with login(monkeypatch) as owner:
        compare = owner.get("/tablets/HT-1/compare", params={"v": ["scholar", key]}).json()
        assert len(compare["clusters"]) == 1
        made = merge(owner, [{"key": "scholar"}, {"key": key, "version": theirs["version"]}], [key])
        assert made.status_code == 201, made.text
        edition = made.json()
        assert (edition["kind"], edition["title"], edition["owner"]) == (
            "edition",
            "Agreed reading",
            "owner",
        )
        assert [item["key"] for item in edition["merged_from"]] == ["scholar", key]
        assert edition["merged_from"][1] == {
            "key": key,
            "kind": "copy",
            "title": None,
            "owner": "u8",
            "version": theirs["version"],
        }
        (kept,) = edition["boxes"]
        assert (kept["sign"], kept["origin"], kept["changed"]) == ("AB01", "scholar", False)
        assert kept["source"] == {
            "kind": "copy",
            "box_id": theirs["boxes"][0]["id"],
            "copy_id": theirs["id"],
            "version": 1,
            "author": "u8",
        }
        assert edition["contributors"] == ["u8"]
        # It is an ordinary copy from here on: editable, and listed among the versions.
        reopened = owner.get(f"/box-sets/{edition['id']}").json()
        assert reopened["permission"] == "owner"
        versions = owner.get("/tablets/HT-1/versions").json()["items"]
        assert any(v["key"] == f"copy:{edition['id']}" and v["kind"] == "edition" for v in versions)


def test_the_scholars_box_keeps_its_position_as_source(monkeypatch, corpus_index, fake):
    theirs = anouk_renames_the_sign(monkeypatch, fake)
    with login(monkeypatch) as owner:
        made = merge(
            owner, [{"key": "scholar"}, {"key": f"copy:{theirs['id']}"}], ["scholar"], title=None
        )
    (kept,) = made.json()["boxes"]
    assert (kept["sign"], kept["source"]) == (
        "AB77",
        {"kind": "scholar", "box_id": 1, "copy_id": None, "version": None, "author": None},
    )
    assert made.json()["title"] is None and made.json()["contributors"] == []


def test_merge_refuses_stale_tampered_and_empty_picks(monkeypatch, corpus_index, fake):
    theirs = anouk_renames_the_sign(monkeypatch, fake)
    key = f"copy:{theirs['id']}"
    sources = [{"key": "scholar"}, {"key": key, "version": theirs["version"]}]
    with login(monkeypatch) as owner:
        stale = merge(owner, [{"key": "scholar"}, {"key": key, "version": 0}], [key])
        assert (stale.status_code, stale.json()["detail"]) == (
            409,
            "u8's copy changed since you opened the merge. Reload to see the changes.",
        )
        assert merge(owner, sources, [key, key]).status_code == 409  # a different number of places
        assert merge(owner, sources, ["model"]).status_code == 422  # not a version of this place
        assert merge(owner, sources, [None]).json()["detail"] == "Keep at least one box."
        assert (
            merge(owner, [{"key": "scholar"}, {"key": "scholar"}], ["scholar"]).status_code == 422
        )
        assert (
            merge(owner, [{"key": "scholar"}], ["scholar"]).status_code == 422
        )  # one version is no merge
        assert merge(owner, [{"key": "scholar"}, {"key": "copy:x"}], ["scholar"]).status_code == 422
        assert (
            owner.post(
                "/box-sets/merge",
                json={"tablet": "HT-1", "title": "x" * 121, "sources": sources, "picks": [key]},
            ).status_code
            == 422
        )


def test_merge_needs_every_source_visible_and_a_login(monkeypatch, corpus_index, fake):
    theirs = anouk_renames_the_sign(monkeypatch, fake)
    fake.sets[theirs["id"]]["everyone"] = "none"  # private again
    with login(monkeypatch) as owner:
        hidden = merge(owner, [{"key": "scholar"}, {"key": f"copy:{theirs['id']}"}], ["scholar"])
        assert hidden.status_code == 404
        owner.headers.pop("X-CSRF-Token")
        assert merge(owner, [{"key": "scholar"}, {"key": "model"}], ["scholar"]).status_code == 403


def test_sql_writes_the_edition_and_its_boxes_sources(monkeypatch):
    controller, _connection, cursor = sql_controller(monkeypatch)
    cursor.lastrowid = 9
    boxes = [
        {
            "box": {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4},
            "sign": "AB01",
            "origin": "scholar",
            "source_kind": "copy",
            "source_set_id": 4,
            "source_box_id": 12,
            "source_version": 3,
            "source_author_id": 8,
        }
    ]
    merged = [{"key": "copy:4", "kind": "copy", "title": None, "owner": "u8", "version": 3}]
    assert controller.create_edition(7, "HT-1", "T", 1000, 500, boxes, merged) == 9
    sql, params = cursor.execute.call_args.args
    assert "'edition'" in sql and params[:4] == (7, "HT-1", "T", json.dumps(merged))
    sql, rows = cursor.executemany.call_args.args
    assert rows == [
        (
            9,
            0.1,
            0.2,
            0.3,
            0.4,
            "AB01",
            "scholar",
            0.1,
            0.2,
            0.3,
            0.4,
            "AB01",
            "[]",
            "copy",
            4,
            12,
            3,
            8,
            json.dumps(marks_of(None)),  # no marks: the defaults
        )
    ]


def test_sql_credits_merged_authors_and_editors(monkeypatch):
    controller, _connection, cursor = sql_controller(
        monkeypatch, [[{"username": "anouk"}, {"username": "dev"}]]
    )
    assert controller.contributors(9) == ["anouk", "dev"]
    sql, params = cursor.execute.call_args.args
    assert "source_author_id" in sql and "box_change" in sql and params == (9, 9)
