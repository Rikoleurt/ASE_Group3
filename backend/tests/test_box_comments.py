"""Comments on corrected copies (#86): who reads, who writes, who deletes, and what is accepted."""
from unittest.mock import MagicMock

import pytest
from mysql.connector import Error as DatabaseError

from backend.app.data_controller.box_set_data_controller import BoxSetDataController
from backend.app.main import app
from backend.app.routes.box_set_routes import get_box_set_data_controller
from backend.tests.test_box_sets import FakeController, login

OWNER, OTHER = 7, 8


@pytest.fixture
def fake():
    controller = FakeController()
    controller.create_from_analysis(OWNER, 12)
    app.dependency_overrides[get_box_set_data_controller] = lambda: controller
    yield controller
    app.dependency_overrides.clear()


def client_for(fake, monkeypatch, level):
    if level == "owner":
        return login(monkeypatch, OWNER)
    if level:
        fake.share_rows[(1, OTHER)] = level
    return login(monkeypatch, OTHER)


def test_box_and_copy_threads(fake, monkeypatch):
    with client_for(fake, monkeypatch, "owner") as owner:
        on_box = owner.post("/box-sets/1/comments", json={"box_id": 2, "body": "  This is ro, not ra.  "})
        assert on_box.status_code == 201
        assert {k: on_box.json()[k] for k in ("box_id", "body", "can_delete")} == {"box_id": 2, "body": "This is ro, not ra.", "can_delete": True}
        assert on_box.json()["author"] == {"id": OWNER, "username": "owner"}
        owner.post("/box-sets/1/comments", json={"body": "Line 3 is worn."})
        assert [c["box_id"] for c in owner.get("/box-sets/1/comments").json()] == [2, None]
        assert [c["body"] for c in owner.get("/box-sets/1/comments", params={"box_id": 2}).json()] == ["This is ro, not ra."]


@pytest.mark.parametrize("level,read,write", [
    (None, 404, 404), ("view", 200, 403), ("comment", 200, 201), ("edit", 200, 201), ("manage", 200, 201), ("owner", 200, 201)])
def test_reading_needs_view_and_writing_needs_comment(fake, monkeypatch, level, read, write):
    with client_for(fake, monkeypatch, level) as client:
        assert client.get("/box-sets/1/comments").status_code == read
        response = client.post("/box-sets/1/comments", json={"box_id": 1, "body": "Hm."})
        assert response.status_code == write
        if write == 403:
            assert response.json()["detail"] == "You can view this copy but not comment on it."


def test_authors_delete_their_own_and_managers_moderate(fake, monkeypatch):
    fake.add_comment(1, 1, OWNER, "Owner's note")
    with client_for(fake, monkeypatch, "comment") as commenter:
        mine = commenter.post("/box-sets/1/comments", json={"box_id": 1, "body": "Mine"}).json()
        listed = {c["body"]: c["can_delete"] for c in commenter.get("/box-sets/1/comments").json()}
        assert listed == {"Owner's note": False, "Mine": True}
        refused = commenter.delete("/box-sets/1/comments/1")
        assert (refused.status_code, refused.json()["detail"]) == (403, "You can only delete your own comments.")
        assert commenter.delete(f"/box-sets/1/comments/{mine['id']}").status_code == 204
        assert commenter.delete("/box-sets/1/comments/99").status_code == 404
    fake.add_comment(1, None, OTHER, "Someone's note")
    fake.share_rows[(1, OTHER)] = "manage"
    with login(monkeypatch, OTHER) as manager:
        assert all(c["can_delete"] for c in manager.get("/box-sets/1/comments").json())
        assert manager.delete("/box-sets/1/comments/1").status_code == 204


@pytest.mark.parametrize("body", [{"body": "   "}, {"body": "x" * 2001}, {"body": "ok", "box_id": 0}, {}])
def test_malformed_comments_are_rejected(fake, monkeypatch, body):
    with client_for(fake, monkeypatch, "owner") as owner:
        assert owner.post("/box-sets/1/comments", json=body).status_code == 422


def test_comments_need_a_box_on_this_copy(fake, monkeypatch):
    fake.boxes[3]["deleted"] = True
    with client_for(fake, monkeypatch, "owner") as owner:
        for box_id in (3, 99):
            response = owner.post("/box-sets/1/comments", json={"box_id": box_id, "body": "Hm."})
            assert (response.status_code, response.json()["detail"]) == (422, f"Box {box_id} is not on this copy.")


def test_writes_need_the_csrf_token_and_storage_errors_are_503(fake, monkeypatch):
    with client_for(fake, monkeypatch, "owner") as owner:
        del owner.headers["X-CSRF-Token"]
        assert owner.post("/box-sets/1/comments", json={"body": "Hm."}).status_code == 403
    monkeypatch.setattr(fake, "comments", MagicMock(side_effect=DatabaseError()))
    with client_for(fake, monkeypatch, "owner") as owner:
        assert owner.get("/box-sets/1/comments").status_code == 503


def test_comment_queries_are_scoped_to_the_copy(monkeypatch):
    connection = MagicMock()
    connection.cursor.return_value.fetchall.return_value = []
    monkeypatch.setattr("mysql.connector.connect", lambda **kwargs: connection)
    controller = BoxSetDataController()
    controller.comments(1, 2)
    sql, params = connection.cursor.return_value.execute.call_args.args
    assert "WHERE c.set_id = %s AND c.box_id = %s" in sql and params == (1, 2, 500)
    assert "ORDER BY c.id DESC LIMIT %s" in sql  # the newest page, shown oldest first
    controller.comment(1, 5)
    sql, params = connection.cursor.return_value.execute.call_args.args
    assert "id = %s AND set_id = %s" in sql and params == (5, 1)
