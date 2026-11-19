"""Admin roles (#80): who may manage roles, what the routes accept, and the session flags."""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from mysql.connector import Error as DatabaseError

from backend.app.auth import COOKIE_NAME, csrf_token, is_admin, is_reviewer, token_hash
from backend.app.data_controller.user_data_controller import UserDataController, like_escape
from backend.app.main import app
from backend.app.model.user import Account, UserPublic
from backend.app.routes.admin_routes import get_user_data_controller

TOKEN = "a" * 43
ROW = {"id": 9, "username": "anouk", "email": "anouk@ase3.com", "is_admin": 0, "is_reviewer": 1}


def logged_in(monkeypatch, admin=False, reviewer=False, username="boss", csrf=True):
    monkeypatch.setattr(UserDataController, "get_session_user", lambda self, digest: Account(
        id=7, email=f"{username}@ase3.com", username=username, is_admin=admin, is_reviewer=reviewer)
        if digest == token_hash(TOKEN) else None)
    client = TestClient(app)
    client.cookies.set(COOKIE_NAME, TOKEN)
    if csrf:
        client.headers["X-CSRF-Token"] = csrf_token(TOKEN)
    return client


@pytest.fixture
def controller():
    controller = MagicMock()
    controller.list_users.return_value = ([ROW], 1)
    controller.set_roles.return_value = {**ROW, "is_admin": 1}
    app.dependency_overrides[get_user_data_controller] = lambda: controller
    yield controller
    app.dependency_overrides.clear()


@pytest.fixture
def admin(monkeypatch, controller):
    monkeypatch.delenv("SIGN_REVIEWERS", raising=False)
    with logged_in(monkeypatch, admin=True) as client:
        yield client


def test_roles_come_from_the_account_and_reviewers_also_from_the_environment(monkeypatch):
    monkeypatch.setenv("SIGN_REVIEWERS", "Legacy, other")
    assert is_admin(Account(id=1, email="a@b.co", username="x", is_admin=True))
    assert not is_admin(UserPublic(id=1, email="a@b.co", username="x"))
    assert is_reviewer(Account(id=1, email="a@b.co", username="x", is_reviewer=True))
    assert is_reviewer(UserPublic(id=1, email="a@b.co", username="legacy"))
    assert not is_reviewer(UserPublic(id=1, email="a@b.co", username="x"))


def test_session_reports_admin_and_reviewer_without_adding_fields_to_the_user(monkeypatch):
    monkeypatch.delenv("SIGN_REVIEWERS", raising=False)
    with logged_in(monkeypatch, admin=True, reviewer=True) as client:
        body = client.get("/users/me").json()
    assert (body["admin"], body["reviewer"]) == (True, True)
    assert body["user"] == {"id": 7, "email": "boss@ase3.com", "username": "boss"}


def test_admin_lists_users_with_their_roles(admin, controller, monkeypatch):
    monkeypatch.setenv("SIGN_REVIEWERS", "anouk")
    response = admin.get("/admin/users", params={"q": "  ano ", "limit": 10, "offset": 20})
    assert response.status_code == 200
    assert response.json() == {"total": 1, "items": [{"id": 9, "username": "anouk", "email": "anouk@ase3.com",
                                                      "admin": False, "reviewer": True, "reviewer_from_env": True}]}
    controller.list_users.assert_called_once_with("ano", 10, 20)


def test_admin_grants_a_role(admin, controller):
    response = admin.patch("/admin/users/9", json={"admin": True})
    assert response.status_code == 200
    assert response.json()["admin"] is True
    controller.set_roles.assert_called_once_with(9, True, None)


@pytest.mark.parametrize("body", [{}, {"admin": None, "reviewer": None}, {"admin": "maybe"}])
def test_role_change_needs_a_role(admin, body):
    assert admin.patch("/admin/users/9", json=body).status_code == 422


def test_admin_cannot_remove_their_own_admin_role(admin, controller):
    response = admin.patch("/admin/users/7", json={"admin": False})
    assert response.status_code == 409
    controller.set_roles.assert_not_called()
    # Changing their own reviewer role is fine.
    assert admin.patch("/admin/users/7", json={"reviewer": False}).status_code == 200


def test_unknown_user_is_404(admin, controller):
    controller.set_roles.return_value = None
    assert admin.patch("/admin/users/404", json={"reviewer": True}).status_code == 404


def test_database_errors_are_503(admin, controller):
    controller.list_users.side_effect = DatabaseError("down")
    controller.set_roles.side_effect = DatabaseError("down")
    assert admin.get("/admin/users").status_code == 503
    assert admin.patch("/admin/users/9", json={"reviewer": True}).status_code == 503


def test_reviewers_and_users_are_not_admins(monkeypatch, controller):
    monkeypatch.setenv("SIGN_REVIEWERS", "boss")
    with logged_in(monkeypatch, reviewer=True) as client:
        assert client.get("/admin/users").status_code == 403
        assert client.patch("/admin/users/9", json={"admin": True}).status_code == 403
    controller.list_users.assert_not_called()
    controller.set_roles.assert_not_called()


def test_admin_routes_need_a_login(controller):
    with TestClient(app) as client:
        assert client.get("/admin/users").status_code == 401
        assert client.patch("/admin/users/9", json={"admin": True}).status_code == 401


def test_role_changes_need_the_csrf_token(monkeypatch, controller):
    with logged_in(monkeypatch, admin=True, csrf=False) as client:
        assert client.patch("/admin/users/9", json={"admin": True}).status_code == 403
    controller.set_roles.assert_not_called()


def test_user_search_matches_wildcards_literally():
    assert like_escape(r"a_b%c\d") == r"a\_b\%c\\d"


def test_set_roles_updates_only_the_given_roles():
    controller = UserDataController()
    cursor = MagicMock()
    cursor.fetchone.return_value = ROW
    connection = MagicMock()
    connection.cursor.return_value = cursor
    controller.connection = MagicMock()
    controller.connection.return_value.__enter__.return_value = connection
    assert controller.set_roles(9, None, True) == ROW
    sql, parameters = cursor.execute.call_args_list[0].args
    assert sql == "UPDATE `user` SET is_reviewer = %s WHERE id = %s"
    assert parameters == (True, 9)
