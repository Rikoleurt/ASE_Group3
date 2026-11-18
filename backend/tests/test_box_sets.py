"""Corrected copies (#83): the API over an in-memory controller that follows the same rules,
and the SQL controller's own checks with a mocked connection."""
import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from mysql.connector import Error as DatabaseError
from mysql.connector.errorcode import ER_DUP_ENTRY
from mysql.connector.errors import IntegrityError

from backend.app import image_store
from backend.app.auth import COOKIE_NAME, csrf_token, token_hash
from backend.app.box_edits import plan, plan_revert, state
from backend.app.data_controller.box_set_data_controller import (BoxSetDataController, MissingChange, NotEditable,
                                                                 StaleVersion)
from backend.app.data_controller.user_data_controller import UserDataController
from backend.app.main import app
from backend.app.model.user import UserPublic
from backend.app.routes.box_set_routes import get_box_set_data_controller
from backend.tests.test_history import png

STAMP = datetime(2026, 11, 18, 9, 0)
# A tiny KU-RO tablet: ku ro and a fraction the model read as E (A704, 1/4), unsure of it.
MODEL_SIGNS = [
    {"id": 1, "sign": "AB81", "box": {"x": 0.1, "y": 0.1, "w": 0.05, "h": 0.05}, "confidence": 90.0,
     "candidates": [{"sign": "AB81", "label": "AB81 (ku)", "roles": ["syllabogram"], "probability": 90.0}]},
    {"id": 2, "sign": "AB02", "box": {"x": 0.2, "y": 0.1, "w": 0.05, "h": 0.05}, "confidence": 85.0, "candidates": []},
    {"id": 3, "sign": "A704", "box": {"x": 0.3, "y": 0.1, "w": 0.05, "h": 0.05}, "confidence": 40.0, "candidates": []},
]


class FakeController:
    """BoxSetDataController in memory: same interface, same rules (box_edits)."""

    def __init__(self):
        self.sets, self.boxes, self.log = {}, {}, {}
        self.analyses = {12: {"owner": 7, "trained": True, "image": ("a" * 32, "PNG")}}

    def find_for_analysis(self, owner_id, analysis_id):
        return next((key for key, value in self.sets.items()
                     if value["owner_id"] == owner_id and value["analysis_id"] == analysis_id), None)

    def create_from_analysis(self, owner_id, analysis_id):
        if (existing := self.find_for_analysis(owner_id, analysis_id)) is not None:
            return existing, False
        analysis = self.analyses.get(analysis_id)
        if analysis is None or analysis["owner"] != owner_id:
            return None
        if not analysis["trained"]:
            raise NotEditable("Boxes from the generic model are objects, not Linear A signs, so they cannot be corrected.")
        set_id = len(self.sets) + 1
        self.sets[set_id] = {"id": set_id, "owner_id": owner_id, "owner": "owner", "analysis_id": analysis_id,
                             "tablet_slug": None, "start": "model", "version": 0, "width": 1000, "height": 800,
                             "created_at": STAMP, "updated_at": STAMP, "filename": "tablet.png"}
        for sign in MODEL_SIGNS:
            box_id = len(self.boxes) + 1
            self.boxes[box_id] = {"id": box_id, "set": set_id, **sign["box"], "sign": sign["sign"], "deleted": False,
                                  "origin": "model", **{f"original_{k}": v for k, v in sign["box"].items()},
                                  "model_sign": sign["sign"], "model_confidence": sign["confidence"],
                                  "candidates": json.dumps(sign["candidates"])}
        return set_id, True

    def load(self, set_id):
        found = self.sets.get(set_id)
        return found and {**found, "boxes": [dict(b) for b in self.boxes.values() if b["set"] == set_id]}

    def _lock(self, set_id, version):
        if self.sets[set_id]["version"] != version:
            raise StaleVersion()

    def _write(self, set_id, author_id, steps):
        version = self.sets[set_id]["version"] + 1
        for step in steps:
            if step.action == "add":
                step.box_id = len(self.boxes) + 1
                self.boxes[step.box_id] = {"id": step.box_id, "set": set_id, "origin": "user", "original_x": None,
                                           "original_y": None, "original_w": None, "original_h": None,
                                           "model_sign": None, "model_confidence": None, "candidates": None}
            self.boxes[step.box_id].update(**step.after["box"], sign=step.after["sign"], deleted=step.after["deleted"])
            change_id = len(self.log) + 1
            self.log[change_id] = {"id": change_id, "set": set_id, "author_id": author_id, "username": "owner",
                                   "created_at": STAMP, "version": version, "action": step.action,
                                   "box_id": step.box_id, "before_state": step.before, "after_state": step.after,
                                   "reverts_id": step.reverts, "reverted_by_id": None}
            if step.reverts:
                self.log[step.reverts]["reverted_by_id"] = change_id
        self.sets[set_id]["version"] = version
        return version

    def apply(self, set_id, author_id, version, changes, known_sign):
        self._lock(set_id, version)
        current = {b["id"]: state(b, b["sign"], b["deleted"]) for b in self.boxes.values() if b["set"] == set_id}
        steps = plan(changes, current, known_sign)
        return self._write(set_id, author_id, steps) if steps else version

    def revert(self, set_id, author_id, change_id, version):
        self._lock(set_id, version)
        row = self.log.get(change_id)
        if row is None or row["set"] != set_id:
            raise MissingChange()
        target = self.boxes[row["box_id"]]
        step = plan_revert({"id": row["id"], "box_id": row["box_id"], "reverted_by": row["reverted_by_id"],
                            "before": row["before_state"], "after": row["after_state"]},
                           state(target, target["sign"], target["deleted"]))
        return self._write(set_id, author_id, [step])

    def changes(self, set_id, limit, before=None):
        rows = sorted((r for r in self.log.values() if r["set"] == set_id and (before is None or r["id"] < before)),
                      key=lambda r: -r["id"])
        return [dict(r) for r in rows[:limit + 1]]

    def delete(self, set_id):
        self.sets.pop(set_id)

    def image(self, set_id):
        return self.analyses[self.sets[set_id]["analysis_id"]]["image"]


def login(monkeypatch, user_id=7):
    token = f"{user_id}".rjust(43, "a")
    monkeypatch.setattr(UserDataController, "get_session_user", lambda self, digest: UserPublic(
        id=user_id, email=f"u{user_id}@ase3.com", username=f"u{user_id}") if digest == token_hash(token) else None)
    client = TestClient(app)
    client.cookies.set(COOKIE_NAME, token)
    client.headers["X-CSRF-Token"] = csrf_token(token)
    return client


@pytest.fixture
def fake():
    controller = FakeController()
    app.dependency_overrides[get_box_set_data_controller] = lambda: controller
    yield controller
    app.dependency_overrides.clear()


@pytest.fixture
def owner(monkeypatch, fake):
    with login(monkeypatch) as client:
        yield client


@pytest.fixture
def copy(owner):
    response = owner.post("/box-sets", json={"analysis_id": 12})
    assert response.status_code == 201
    return response.json()


def save(client, copy, *changes, version=None):
    return client.patch(f"/box-sets/{copy['id']}", json={"version": copy["version"] if version is None else version,
                                                        "changes": list(changes)})


def test_a_copy_starts_from_the_model_and_reads_like_the_analysis(copy):
    assert (copy["version"], copy["start"], copy["owner"], copy["image_url"]) == (0, "model", "owner", "/box-sets/1/image")
    assert copy["source"] == {"kind": "analysis", "analysis_id": 12, "tablet": None, "filename": "tablet.png"}
    assert [(b["sign"], b["origin"], b["changed"]) for b in copy["boxes"]] == [
        ("AB81", "model", False), ("AB02", "model", False), ("A704", "model", False)]
    assert copy["boxes"][0]["candidates"][0]["label"] == "AB81 (ku)"
    reading = copy["reading"]
    assert [sign["id"] for sign in reading["signs"]] == [1, 2, 3]  # a sign's id is its box's id
    assert reading["signs"][2]["confidence"] == 40.0  # untouched boxes keep the model's confidence
    assert reading["formulas"][0]["kind"] == "total"


def test_opening_it_again_returns_the_same_copy(owner, copy):
    again = owner.post("/box-sets", json={"analysis_id": 12})
    assert (again.status_code, again.json()["id"]) == (200, copy["id"])
    assert owner.get("/analysis/12/box-set").json()["id"] == copy["id"]


def test_a_save_changes_the_boxes_and_the_reading(owner, copy):
    response = save(owner, copy,
                    {"op": "update", "box_id": 3, "sign": "A707"},
                    {"op": "update", "box_id": 1, "box": {"x": 0.11, "y": 0.1, "w": 0.05, "h": 0.05}},
                    {"op": "add", "box": {"x": 0.5, "y": 0.5, "w": 0.1, "h": 0.1}})
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    boxes = {b["id"]: b for b in body["boxes"]}
    assert (boxes[3]["sign"], boxes[3]["model_sign"], boxes[3]["changed"]) == ("A707", "A704", True)
    assert boxes[1]["box"]["x"] == 0.11 and boxes[1]["changed"]
    assert (boxes[4]["origin"], boxes[4]["sign"], boxes[4]["changed"]) == ("user", None, True)
    signs = {sign["id"]: sign for sign in body["reading"]["signs"]}
    assert signs[3]["confidence"] == 100.0  # the user's call
    assert signs[4]["label"] == "Unnamed sign" and signs[4]["role"] == "unknown"
    assert body["reading"]["formulas"][0]["total"][0]["sign"] == "A707"


def test_deleting_takes_the_box_off_the_copy_and_the_reading(owner, copy):
    body = save(owner, copy, {"op": "delete", "box_id": 2}).json()
    assert [b["id"] for b in body["boxes"]] == [1, 3]
    assert [s["id"] for s in body["reading"]["signs"]] == [1, 3]


def test_a_stale_save_is_refused_with_the_current_copy(owner, copy, fake):
    save(owner, copy, {"op": "delete", "box_id": 2})
    stale = save(owner, copy, {"op": "update", "box_id": 1, "sign": "A707"})
    assert stale.status_code == 409
    assert "Someone else changed this copy" in stale.json()["detail"]
    assert stale.json()["current"]["version"] == 1
    assert fake.boxes[1]["sign"] == "AB81"


@pytest.mark.parametrize("change,detail", [
    ({"op": "update", "box_id": 99, "sign": "A707"}, "Box 99 is not on this copy."),
    ({"op": "add", "box": {"x": 0.1, "y": 0.1, "w": 0.1, "h": 0.1}, "sign": "NOPE"}, "NOPE is not a sign in the catalogue."),
])
def test_unknown_boxes_and_signs_are_422_and_change_nothing(owner, copy, fake, change, detail):
    response = save(owner, copy, {"op": "delete", "box_id": 2}, change)
    assert (response.status_code, response.json()["detail"]) == (422, detail)
    assert fake.sets[1]["version"] == 0 and not fake.boxes[2]["deleted"]


def test_signs_are_stored_as_the_catalogue_spells_them(owner, copy):
    body = save(owner, copy, {"op": "update", "box_id": 2, "sign": "ab2"}).json()
    assert body["boxes"][1]["sign"] == "AB02"


def test_the_change_log_and_undo(owner, copy):
    saved = save(owner, copy, {"op": "update", "box_id": 3, "sign": "A707"}, {"op": "delete", "box_id": 2}).json()
    page = owner.get("/box-sets/1/changes").json()
    assert [(c["id"], c["action"], c["box_id"], c["version"]) for c in page["items"]] == [(2, "delete", 2, 1), (1, "update", 3, 1)]
    assert page["items"][1]["before"]["sign"] == "A704" and page["items"][1]["after"]["sign"] == "A707"
    assert page["items"][0]["author"] == {"id": 7, "username": "owner"}

    undone = owner.post("/box-sets/1/changes/2/revert", json={"version": saved["version"]})
    assert undone.status_code == 200
    assert [b["id"] for b in undone.json()["boxes"]] == [1, 2, 3]  # the deleted box is back
    newest = owner.get("/box-sets/1/changes").json()["items"]
    assert (newest[0]["action"], newest[0]["reverts"], newest[1]["reverted_by"]) == ("revert", 2, newest[0]["id"])

    again = owner.post("/box-sets/1/changes/2/revert", json={"version": undone.json()["version"]})
    assert (again.status_code, again.json()["detail"]) == (422, "This change was already undone.")
    assert owner.post("/box-sets/1/changes/99/revert", json={"version": 2}).status_code == 404
    assert owner.post("/box-sets/1/changes/1/revert", json={"version": 0}).status_code == 409


def test_undo_is_refused_when_the_box_changed_again(owner, copy):
    first = save(owner, copy, {"op": "update", "box_id": 3, "sign": "A707"}).json()
    save(owner, first, {"op": "update", "box_id": 3, "sign": "AB81"})
    response = owner.post("/box-sets/1/changes/1/revert", json={"version": 2})
    assert (response.status_code, response.json()["detail"]) == (422, "This box was changed again later. Undo the later change first.")


def test_the_change_log_pages_backwards(owner, copy):
    version = copy["version"]
    for sign in ("A707", "AB81", "A707"):
        version = save(owner, {**copy, "version": version}, {"op": "update", "box_id": 3, "sign": sign}).json()["version"]
    first = owner.get("/box-sets/1/changes", params={"limit": 2}).json()
    assert ([c["id"] for c in first["items"]], first["next_before"]) == ([3, 2], 2)
    rest = owner.get("/box-sets/1/changes", params={"limit": 2, "before": 2}).json()
    assert ([c["id"] for c in rest["items"]], rest["next_before"]) == ([1], None)


def test_the_image_comes_from_the_kept_upload(owner, copy, fake):
    stored = image_store.save(png(), "PNG")
    fake.analyses[12]["image"] = (stored.key, "PNG")
    response = owner.get("/box-sets/1/image")
    assert (response.status_code, response.content, response.headers["cache-control"]) == (200, png(), "no-store")
    fake.analyses[12]["image"] = ("f" * 32, "PNG")  # the file is gone
    assert owner.get("/box-sets/1/image").status_code == 404


def test_deleting_the_copy(owner, copy):
    assert owner.delete("/box-sets/1").status_code == 204
    assert owner.get("/box-sets/1").status_code == 404
    assert owner.get("/analysis/12/box-set").status_code == 404


def test_other_users_cannot_see_or_touch_a_copy(monkeypatch, fake, copy):
    with login(monkeypatch, user_id=8) as other:
        for response in (other.get("/box-sets/1"), other.get("/box-sets/1/changes"), other.get("/box-sets/1/image"),
                         save(other, copy, {"op": "delete", "box_id": 1}), other.delete("/box-sets/1"),
                         other.post("/box-sets/1/changes/1/revert", json={"version": 0})):
            assert response.status_code == 404
        # Nor make a copy of someone else's analysis.
        assert other.post("/box-sets", json={"analysis_id": 12}).status_code == 404
    assert not fake.boxes[1]["deleted"] and 1 in fake.sets


def test_generic_model_analyses_cannot_be_corrected(owner, fake):
    fake.analyses[12]["trained"] = False
    response = owner.post("/box-sets", json={"analysis_id": 12})
    assert response.status_code == 422 and "generic model" in response.json()["detail"]


def test_writes_need_a_login_and_the_csrf_token(fake, monkeypatch, copy):
    with TestClient(app) as anonymous:
        assert anonymous.get("/box-sets/1").status_code == 401
        assert anonymous.post("/box-sets", json={"analysis_id": 12}).status_code == 401
    with login(monkeypatch) as owner:
        del owner.headers["X-CSRF-Token"]
        assert save(owner, copy, {"op": "delete", "box_id": 1}).status_code == 403
        assert owner.delete("/box-sets/1").status_code == 403


def test_database_errors_are_503(owner, copy, fake, monkeypatch):
    monkeypatch.setattr(fake, "load", MagicMock(side_effect=DatabaseError()))
    assert owner.get("/box-sets/1").status_code == 503
    assert save(owner, copy, {"op": "delete", "box_id": 1}).status_code == 503


# The SQL controller's own decisions, with a mocked connection.

def sql_controller(monkeypatch, rows=()):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchall.side_effect = list(rows)
    monkeypatch.setattr("mysql.connector.connect", lambda **kwargs: connection)
    return BoxSetDataController(), connection, cursor


def test_controller_refuses_generic_and_imageless_analyses(monkeypatch):
    controller, _, _ = sql_controller(monkeypatch, [[], [{"result_json": json.dumps({"trained": False}), "image_id": 3}]])
    with pytest.raises(NotEditable, match="generic model"):
        controller.create_from_analysis(7, 12)
    controller, _, _ = sql_controller(monkeypatch, [[], [{"result_json": json.dumps({"trained": True}), "image_id": None}]])
    with pytest.raises(NotEditable, match="before images were kept"):
        controller.create_from_analysis(7, 12)


def test_controller_copies_the_model_boxes(monkeypatch):
    result = {"trained": True, "width": 1000, "height": 800, "signs": MODEL_SIGNS}
    controller, connection, cursor = sql_controller(monkeypatch, [[], [{"result_json": json.dumps(result), "image_id": 3}]])
    cursor.lastrowid = 5
    assert controller.create_from_analysis(7, 12) == (5, True)
    sql, params = cursor.execute.call_args.args
    assert sql.startswith("INSERT INTO box_set") and params[:6] == (7, 12, None, "model", 1000, 800)
    sql, rows = cursor.executemany.call_args.args
    assert sql.startswith("INSERT INTO box ") and len(rows) == 3
    assert rows[2][:7] == (5, 0.3, 0.1, 0.05, 0.05, "A704", "model") and rows[2][-3:-1] == ("A704", 40.0)


def test_a_copy_made_at_the_same_moment_elsewhere_is_reused(monkeypatch):
    result = {"trained": True, "width": 10, "height": 10, "signs": []}
    controller, connection, cursor = sql_controller(
        monkeypatch, [[], [{"result_json": json.dumps(result), "image_id": 3}], [{"id": 9}]])
    cursor.execute.side_effect = [None, None, IntegrityError(errno=ER_DUP_ENTRY), None]
    assert controller.create_from_analysis(7, 12) == (9, False)


def test_controller_refuses_a_stale_version_before_writing(monkeypatch):
    controller, connection, cursor = sql_controller(monkeypatch)
    cursor.fetchone.return_value = {"version": 3}
    with pytest.raises(StaleVersion):
        controller.apply(1, 7, 2, [], lambda sign: sign)
    sql, params = cursor.execute.call_args.args
    assert "FOR UPDATE" in sql and params == (1,)
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()
