"""Fixes from the security and state-machine reviews (#98)."""
import os
import zipfile
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.box_edits import EditError, plan_revert, state
from backend.app.data_controller.analysis_data_controller import AnalysisDataController
from backend.app.data_controller.user_data_controller import LastAdmin, UserDataController
from backend.app.main import app
from backend.app.model.box_set import MAX_BOXES, EditBox
from backend.app.rate_limit import RateLimit
from backend.app.routes.admin_routes import get_correction_controller, get_export_data_controller
from backend.app.routes.box_set_routes import get_box_set_data_controller
from backend.app.routes.admin_routes import get_user_data_controller as admin_users
from backend.tests.test_admin import logged_in
from backend.tests.test_box_sets import FakeController, login
from backend.tests.test_history import png, result
from backend.tests.test_training_export import copies


# Rate limits

def test_a_rate_limit_counts_a_sliding_window(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("backend.app.rate_limit.time.monotonic", lambda: now[0])
    limit = RateLimit(limit=2, seconds=60)
    limit.record("a"), limit.record("a")
    assert limit.blocked_for("a") == pytest.approx(60)
    assert limit.blocked_for("b") == 0
    now[0] += 61
    assert limit.blocked_for("a") == 0


def test_failed_logins_are_limited_per_account(monkeypatch):
    monkeypatch.setattr(UserDataController, "authenticate", lambda self, **kwargs: None)
    with TestClient(app, headers={"X-Requested-With": "ASE"}) as client:
        for _ in range(10):
            assert client.post("/users/login", json={"username": "dev", "password": "guess"}).status_code == 401
        blocked = client.post("/users/login", json={"username": "DEV", "password": "guess"})
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0
    assert "Too many failed logins" in blocked.json()["detail"]


def test_comments_are_limited_per_person(monkeypatch):
    controller = FakeController()
    controller.create_from_analysis(7, 12)
    app.dependency_overrides[get_box_set_data_controller] = lambda: controller
    try:
        with login(monkeypatch) as owner:
            for number in range(10):
                assert owner.post("/box-sets/1/comments", json={"body": f"note {number}"}).status_code == 201
            refused = owner.post("/box-sets/1/comments", json={"body": "one more"})
        assert (refused.status_code, len(controller.comment_rows)) == (429, 10)
    finally:
        app.dependency_overrides.clear()


def test_uploads_are_limited_per_person_per_day(monkeypatch):
    monkeypatch.setattr("backend.app.rate_limit.UPLOADS.limit", 1)
    monkeypatch.setattr(AnalysisDataController, "analyze", lambda *a, **kw: result())
    monkeypatch.setattr(AnalysisDataController, "save_analysis", MagicMock(
        return_value=MagicMock(id=1, created_at=__import__("datetime").datetime(2026, 11, 18))))
    with login(monkeypatch) as owner:
        assert owner.post("/analysis", files={"file": ("a.png", png(), "image/png")}).status_code == 200
        refused = owner.post("/analysis", files={"file": ("a.png", png(), "image/png")})
    assert refused.status_code == 429


# Upload size before parsing

def test_oversized_or_unsized_uploads_are_refused_before_reading(monkeypatch):
    analyze = MagicMock()
    monkeypatch.setattr(AnalysisDataController, "analyze", analyze)
    with TestClient(app) as client:
        big = client.post("/analysis", content=b"x", headers={"content-length": str(11 * 1024 * 1024),
                                                             "content-type": "multipart/form-data; boundary=x"})
        assert (big.status_code, big.json()["detail"]) == (413, "The image is larger than 10 MB.")

        def chunks():
            yield b"--x\r\n"
        unsized = client.post("/analysis", content=chunks(), headers={"content-type": "multipart/form-data; boundary=x"})
        assert unsized.status_code == 411
    analyze.assert_not_called()


# Box coordinates

@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_box_coordinates_refuse_nan_and_infinity(bad):
    with pytest.raises(ValidationError):
        EditBox(x=bad, y=0.1, w=0.1, h=0.1)


# The last admin

def test_the_last_admin_cannot_be_removed_by_another_admin(monkeypatch):
    controller = MagicMock()
    controller.set_roles.side_effect = LastAdmin()
    app.dependency_overrides[admin_users] = lambda: controller
    try:
        with logged_in(monkeypatch, admin=True) as admin:
            response = admin.patch("/admin/users/9", json={"admin": False})
        assert (response.status_code, response.json()["detail"]) == (409, "The site needs at least one admin.")
    finally:
        app.dependency_overrides.clear()


def test_set_roles_refuses_to_remove_the_last_admin(monkeypatch):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchall.return_value = []  # no other admin
    monkeypatch.setattr("mysql.connector.connect", lambda **kwargs: connection)
    with pytest.raises(LastAdmin):
        UserDataController().set_roles(9, False, None)
    sql = cursor.execute.call_args_list[0].args[0]
    assert "FOR UPDATE" in sql and "is_admin = TRUE" in sql
    connection.rollback.assert_called_once()


# Training export: trusted owners by default, streamed from disk

@pytest.fixture
def export_stores(monkeypatch, tmp_path):
    exports = MagicMock()
    exports.copies.return_value = [{**copy, "owner_trusted": copy["id"] == 1} for copy in copies(None)]
    corrections = MagicMock()
    corrections.export_approved.return_value = []
    app.dependency_overrides[get_export_data_controller] = lambda: exports
    app.dependency_overrides[get_correction_controller] = lambda: corrections
    monkeypatch.setattr("backend.app.glyph_index.tracing_path", lambda slug: None)
    yield exports
    app.dependency_overrides.clear()


def test_the_export_asks_for_trusted_owners_unless_told_otherwise(monkeypatch, export_stores):
    with logged_in(monkeypatch, admin=True) as admin:
        body = admin.get("/admin/export/corrections").json()
        export_stores.copies.assert_called_with(False)
        assert body["copies"][0]["owner_trusted"] is True
        admin.get("/admin/export/corrections", params={"everyone": "true"})
        export_stores.copies.assert_called_with(True)


def test_the_zip_streams_from_a_temporary_file_that_is_then_removed(monkeypatch, export_stores):
    made = []
    real = __import__("backend.app.training_export", fromlist=["yolo_zip"]).yolo_zip

    def recording(*args):
        made.append(real(*args))
        return made[-1]
    monkeypatch.setattr("backend.app.training_export.yolo_zip", recording)
    with logged_in(monkeypatch, admin=True) as admin:
        response = admin.get("/admin/export/corrections.zip")
    assert response.status_code == 200
    assert "corrections.json" in zipfile.ZipFile(__import__("io").BytesIO(response.content)).namelist()
    assert not os.path.exists(made[0])


def test_the_export_query_marks_and_filters_untrusted_owners(monkeypatch):
    from backend.app.training_export import ExportDataController
    monkeypatch.setenv("SIGN_REVIEWERS", "listed")
    rows = [{"id": 1, "is_admin": 1, "is_reviewer": 0, "owner_username": "boss"},
            {"id": 2, "is_admin": 0, "is_reviewer": 0, "owner_username": "listed"},
            {"id": 3, "is_admin": 0, "is_reviewer": 0, "owner_username": "stranger"}]
    for everyone, expected in ((False, [1, 2]), (True, [1, 2, 3])):
        connection = MagicMock()
        connection.cursor.return_value.fetchall.side_effect = [[dict(r) for r in rows], []]
        monkeypatch.setattr("mysql.connector.connect", lambda **kwargs: connection)
        found = ExportDataController().copies(everyone)
        assert [c["id"] for c in found] == expected
        assert {c["id"]: c["owner_trusted"] for c in found}.get(3, False) is False


# Sharing: Manage is the owner's to give

@pytest.fixture
def shared(monkeypatch):
    controller = FakeController()
    controller.create_from_analysis(7, 12)
    controller.share_rows[(1, 8)] = "manage"
    controller.share_rows[(1, 9)] = "edit"
    app.dependency_overrides[get_box_set_data_controller] = lambda: controller
    yield controller
    app.dependency_overrides.clear()


def test_a_manager_cannot_give_change_or_take_manage(monkeypatch, shared):
    shared.usernames[10] = "u10"
    with login(monkeypatch, 8) as manager:
        assert manager.put("/box-sets/1/shares/9", json={"permission": "manage"}).status_code == 403
        assert manager.put("/box-sets/1/shares/9", json={"permission": "view"}).status_code == 200
        shared.share_rows[(1, 10)] = "manage"
        refused = manager.put("/box-sets/1/shares/10", json={"permission": "view"})
        assert (refused.status_code, refused.json()["detail"]) == (403, "Only the owner can give, change or take away Manage access.")
        assert manager.delete("/box-sets/1/shares/10").status_code == 403
    with login(monkeypatch, 7) as owner:
        assert owner.put("/box-sets/1/shares/9", json={"permission": "manage"}).status_code == 200
        assert owner.delete("/box-sets/1/shares/10").status_code == 204


# Revert edge cases

def test_undoing_a_delete_respects_the_box_limit_and_the_catalogue():
    deleted = {"id": 1, "box_id": 1, "reverted_by": None, "before": state({"x": 0, "y": 0, "w": .1, "h": .1}, "OLD"),
               "after": state({"x": 0, "y": 0, "w": .1, "h": .1}, "OLD", deleted=True)}
    current = deleted["after"]
    with pytest.raises(EditError, match="at most"):
        plan_revert(deleted, current, MAX_BOXES, lambda sign: sign)
    with pytest.raises(EditError, match="no longer a sign"):
        plan_revert(deleted, current, 1, lambda sign: None)
    assert plan_revert(deleted, current, 1, lambda sign: sign).after["deleted"] is False


def test_undoing_an_undo_puts_the_change_back_in_effect(monkeypatch):
    controller = FakeController()
    controller.create_from_analysis(7, 12)
    app.dependency_overrides[get_box_set_data_controller] = lambda: controller
    try:
        with login(monkeypatch) as owner:
            saved = owner.patch("/box-sets/1", json={"version": 0, "changes": [{"op": "update", "box_id": 1, "sign": "AB02"}]}).json()
            undone = owner.post("/box-sets/1/changes/1/revert", json={"version": saved["version"]}).json()
            redone = owner.post("/box-sets/1/changes/2/revert", json={"version": undone["version"]})
            assert redone.status_code == 200
            assert redone.json()["boxes"][0]["sign"] == "AB02"
            log = {c["id"]: c for c in owner.get("/box-sets/1/changes").json()["items"]}
            assert log[1]["reverted_by"] is None  # in effect again, so it can be undone again
            assert owner.post("/box-sets/1/changes/1/revert", json={"version": redone.json()["version"]}).status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_a_copy_deleted_during_a_save_is_404_not_500(monkeypatch):
    from backend.app.data_controller.box_set_data_controller import StaleVersion
    controller = FakeController()
    controller.create_from_analysis(7, 12)
    app.dependency_overrides[get_box_set_data_controller] = lambda: controller

    def gone(*args, **kwargs):
        controller.sets.clear()
        raise StaleVersion()
    monkeypatch.setattr(controller, "apply", gone)
    try:
        with login(monkeypatch) as owner:
            response = owner.patch("/box-sets/1", json={"version": 0, "changes": [{"op": "delete", "box_id": 1}]})
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


# #93's private analysis comments now need the CSRF token like every other write

def test_private_analysis_comments_need_the_csrf_token(monkeypatch):
    with login(monkeypatch) as client:
        del client.headers["X-CSRF-Token"]
        assert client.post("/users/me/analyses/12/comments", json={"body": "hi"}).status_code == 403
        assert client.delete("/users/me/comments/3").status_code == 403
