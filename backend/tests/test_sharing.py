"""Sharing corrected copies (#84): the levels, every route against every level, and the share routes."""
from unittest.mock import MagicMock

import pytest
from mysql.connector import Error as DatabaseError
from mysql.connector.errorcode import ER_NO_REFERENCED_ROW_2
from mysql.connector.errors import IntegrityError

from backend.app import image_store
from backend.app.data_controller.box_set_data_controller import BoxSetDataController
from backend.app.data_controller.user_data_controller import UserDataController
from backend.app.main import app
from backend.app.routes.box_set_routes import get_box_set_data_controller
from backend.app.routes.share_routes import get_user_data_controller
from backend.app.sharing import allows, level_of, rank
from backend.tests.test_box_sets import FakeController, login
from backend.tests.test_history import png

OWNER, OTHER = 7, 8


def test_levels_combine_a_share_with_the_everyone_level():
    assert level_of(OWNER, "none", OWNER, None) == "owner"
    assert level_of(OWNER, "none", OTHER, None) is None
    assert level_of(OWNER, "view", OTHER, None) == "view"
    assert level_of(OWNER, "edit", OTHER, "view") == "edit"  # the higher of the two
    assert level_of(OWNER, "comment", OTHER, "manage") == "manage"
    assert [rank(level) for level in (None, "view", "comment", "edit", "manage", "owner")] == [0, 1, 2, 3, 4, 5]
    assert allows("edit", "comment") and not allows("comment", "edit") and not allows(None, "view")


@pytest.fixture
def fake():
    controller = FakeController()
    controller.create_from_analysis(OWNER, 12)
    stored = image_store.save(png(), "PNG")
    controller.analyses[12]["image"] = (stored.key, "PNG")
    app.dependency_overrides[get_box_set_data_controller] = lambda: controller
    yield controller
    app.dependency_overrides.clear()


def as_level(fake, monkeypatch, level):
    """A client for user 8 with the given access to copy 1 (None: no access, 'owner': user 7)."""
    if level == "owner":
        return login(monkeypatch, OWNER)
    if level == "everyone-edit":
        fake.sets[1]["everyone"] = "edit"
    elif level is not None:
        fake.share_rows[(1, OTHER)] = level
    return login(monkeypatch, OTHER)


EDIT = {"version": 0, "changes": [{"op": "update", "box_id": 1, "sign": "AB02"}]}
ROUTES = {  # name: (method, path, body)
    "read": ("get", "/box-sets/1", None),
    "changes": ("get", "/box-sets/1/changes", None),
    "image": ("get", "/box-sets/1/image", None),
    "edit": ("patch", "/box-sets/1", EDIT),
    "shares": ("get", "/box-sets/1/shares", None),
    "share": ("put", "/box-sets/1/shares/9", {"permission": "view"}),
    "everyone": ("put", "/box-sets/1/everyone", {"permission": "view"}),
    "delete": ("delete", "/box-sets/1", None),
}
# What each level gets from each route: 404 hides the copy, 403 refuses a visible one.
EXPECTED = {
    None: {"read": 404, "changes": 404, "image": 404, "edit": 404, "shares": 404, "share": 404, "everyone": 404, "delete": 404},
    "view": {"read": 200, "changes": 200, "image": 200, "edit": 403, "shares": 403, "share": 403, "everyone": 403, "delete": 403},
    "comment": {"read": 200, "changes": 200, "image": 200, "edit": 403, "shares": 403, "share": 403, "everyone": 403, "delete": 403},
    "edit": {"read": 200, "changes": 200, "image": 200, "edit": 200, "shares": 403, "share": 403, "everyone": 403, "delete": 403},
    "everyone-edit": {"read": 200, "changes": 200, "image": 200, "edit": 200, "shares": 403, "share": 403, "everyone": 403, "delete": 403},
    "manage": {"read": 200, "changes": 200, "image": 200, "edit": 200, "shares": 200, "share": 200, "everyone": 200, "delete": 403},
    "owner": {"read": 200, "changes": 200, "image": 200, "edit": 200, "shares": 200, "share": 200, "everyone": 200, "delete": 204},
}


@pytest.mark.parametrize("level", list(EXPECTED))
@pytest.mark.parametrize("route", list(ROUTES))
def test_every_route_against_every_level(fake, monkeypatch, level, route):
    method, path, body = ROUTES[route]
    with as_level(fake, monkeypatch, level) as client:
        response = getattr(client, method)(path, **({"json": body} if body is not None else {}))
    assert response.status_code == EXPECTED[level][route], response.text


def test_the_copy_says_what_you_may_do(fake, monkeypatch):
    with as_level(fake, monkeypatch, "comment") as client:
        body = client.get("/box-sets/1").json()
    assert (body["permission"], body["everyone"]) == ("comment", "none")
    with as_level(fake, monkeypatch, "owner") as client:
        assert client.get("/box-sets/1").json()["permission"] == "owner"


def test_refusals_say_why(fake, monkeypatch):
    with as_level(fake, monkeypatch, "view") as client:
        assert client.patch("/box-sets/1", json=EDIT).json()["detail"] == "You can view this copy but not change it."
        assert client.delete("/box-sets/1").json()["detail"] == "Only the owner can delete this copy."


def test_an_editor_saves_and_the_change_log_names_them(fake, monkeypatch):
    with as_level(fake, monkeypatch, "edit") as client:
        saved = client.patch("/box-sets/1", json=EDIT)
        assert (saved.status_code, saved.json()["permission"]) == (200, "edit")
        assert client.get("/box-sets/1/changes").json()["items"][0]["author"]["id"] == OTHER


def test_sharing_and_revoking(fake, monkeypatch):
    with as_level(fake, monkeypatch, "owner") as owner:
        assert owner.put("/box-sets/1/shares/8", json={"permission": "edit"}).json()["shares"] == [
            {"user": {"id": 8, "username": "u8"}, "permission": "edit"}]
        # Changing the level replaces it.
        assert owner.put("/box-sets/1/shares/8", json={"permission": "view"}).json()["shares"][0]["permission"] == "view"
        assert owner.put("/box-sets/1/everyone", json={"permission": "comment"}).json()["everyone"] == "comment"
        assert owner.get("/box-sets/1").json()["everyone"] == "comment"
        assert owner.delete("/box-sets/1/shares/8").status_code == 204
        assert owner.get("/box-sets/1/shares").json() == {"everyone": "comment", "shares": []}


@pytest.mark.parametrize("target,body,status,detail", [
    (7, {"permission": "view"}, 409, "The owner always has full access."),
    (404, {"permission": "view"}, 404, "User not found."),
    (9, {"permission": "owner"}, 422, None),
])
def test_share_requests_are_checked(fake, monkeypatch, target, body, status, detail):
    with as_level(fake, monkeypatch, "owner") as owner:
        response = owner.put(f"/box-sets/1/shares/{target}", json=body)
    assert response.status_code == status
    if detail:
        assert response.json()["detail"] == detail


def test_everyone_cannot_be_given_manage(fake, monkeypatch):
    with as_level(fake, monkeypatch, "owner") as owner:
        assert owner.put("/box-sets/1/everyone", json={"permission": "manage"}).status_code == 422


def test_a_manager_cannot_change_their_own_access_but_anyone_can_leave(fake, monkeypatch):
    with as_level(fake, monkeypatch, "manage") as manager:
        response = manager.put("/box-sets/1/shares/8", json={"permission": "view"})
        assert (response.status_code, response.json()["detail"]) == (409, "You cannot change your own access.")
    fake.share_rows[(1, OTHER)] = "view"
    with login(monkeypatch, OTHER) as viewer:
        assert viewer.delete("/box-sets/1/shares/9").status_code == 403  # not someone else's
        assert viewer.delete("/box-sets/1/shares/8").status_code == 204  # but their own
        assert viewer.get("/box-sets/1").status_code == 404


def test_shared_with_me_lists_shares_and_everyone_copies(fake, monkeypatch):
    with login(monkeypatch, OTHER) as other:
        assert other.get("/users/me/shared-copies").json() == []
        fake.share_rows[(1, OTHER)] = "comment"
        (copy,) = other.get("/users/me/shared-copies").json()
        assert {k: copy[k] for k in ("id", "owner", "kind", "title", "permission", "shared_with_everyone")} == {
            "id": 1, "owner": "owner", "kind": "analysis", "title": "tablet.png", "permission": "comment",
            "shared_with_everyone": False}
        fake.sets[1]["everyone"] = "edit"
        assert other.get("/users/me/shared-copies").json()[0]["permission"] == "edit"
    with login(monkeypatch, OWNER) as owner:
        assert owner.get("/users/me/shared-copies").json() == []  # your own copies are not "shared with you"


@pytest.fixture
def users():
    controller = MagicMock()
    controller.search_usernames.return_value = [{"id": 9, "username": "anouk"}]
    app.dependency_overrides[get_user_data_controller] = lambda: controller
    yield controller
    app.dependency_overrides.clear()


def test_user_search_finds_usernames_only(monkeypatch, users):
    with login(monkeypatch, OWNER) as client:
        assert client.get("/users/search", params={"q": " an "}).json() == [{"id": 9, "username": "anouk"}]
        assert client.get("/users/search", params={"q": "a"}).status_code == 422  # at least 2 characters
    users.search_usernames.assert_called_once_with("an", 10, OWNER)


def test_user_search_needs_a_login(users):
    from fastapi.testclient import TestClient
    with TestClient(app) as anonymous:
        assert anonymous.get("/users/search", params={"q": "an"}).status_code == 401


def test_search_matches_the_start_of_usernames_literally(monkeypatch):
    connection = MagicMock()
    monkeypatch.setattr("mysql.connector.connect", lambda **kwargs: connection)
    UserDataController().search_usernames("a_%", 10, 7)
    sql, params = connection.cursor.return_value.execute.call_args.args
    assert "email" not in sql.split("FROM")[0]
    assert params == ("a\\_\\%%", 7, 10)


def test_sharing_with_a_deleted_account_is_refused(monkeypatch):
    connection = MagicMock()
    connection.cursor.return_value.execute.side_effect = IntegrityError(errno=ER_NO_REFERENCED_ROW_2)
    monkeypatch.setattr("mysql.connector.connect", lambda **kwargs: connection)
    assert BoxSetDataController().set_share(1, 404, "view", 7) is False


def test_storage_errors_are_503(fake, monkeypatch):
    monkeypatch.setattr(fake, "shares", MagicMock(side_effect=DatabaseError()))
    with as_level(fake, monkeypatch, "owner") as owner:
        assert owner.get("/box-sets/1/shares").status_code == 503
