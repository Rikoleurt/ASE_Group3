"""Scholars' workbench, story K: bookmarked tablets."""

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.routes import bookmark_routes
from backend.app.routes.bookmark_routes import BookmarkDataController, get_bookmark_data_controller
from backend.tests.test_box_sets import login, sql_controller


class FakeBookmarks:
    def __init__(self):
        self.rows = {}

    def bookmarks(self, user_id):
        return list(reversed(self.rows.get(user_id, [])))

    def add(self, user_id, slug):
        mine = self.rows.setdefault(user_id, [])
        if slug not in mine:
            mine.append(slug)

    def remove(self, user_id, slug):
        if slug in self.rows.get(user_id, []):
            self.rows[user_id].remove(slug)


def test_bookmarks_are_added_listed_latest_first_and_removed(monkeypatch):
    fake = FakeBookmarks()
    app.dependency_overrides[get_bookmark_data_controller] = lambda: fake
    try:
        with login(monkeypatch) as user:
            assert user.get("/bookmarks").json() == {"tablets": []}
            assert user.put("/bookmarks/HT-13").json() == {"tablets": ["HT-13"]}
            assert user.put("/bookmarks/HT-9a").json() == {"tablets": ["HT-9a", "HT-13"]}
            assert user.put("/bookmarks/HT-13").json() == {
                "tablets": ["HT-9a", "HT-13"]
            }  # again is fine
            assert user.delete("/bookmarks/HT-9a").json() == {"tablets": ["HT-13"]}
            assert user.put("/bookmarks/../x").status_code in (404, 422)
            monkeypatch.setattr(bookmark_routes, "MAX_BOOKMARKS", 1)
            assert user.put("/bookmarks/KH-5").status_code == 409
            user.headers.pop("X-CSRF-Token")
            assert user.put("/bookmarks/HT-1").status_code == 403
        with login(monkeypatch, user_id=8) as other:
            assert other.get("/bookmarks").json() == {"tablets": []}  # each user's own
        with TestClient(app) as visitor:
            assert visitor.get("/bookmarks").status_code == 401
    finally:
        app.dependency_overrides.pop(get_bookmark_data_controller, None)


def test_sql_bookmarks(monkeypatch):
    _controller, _connection, cursor = sql_controller(monkeypatch, [[{"tablet_slug": "HT-13"}]])
    controller = BookmarkDataController()
    assert controller.bookmarks(7) == ["HT-13"]
    controller.add(7, "HT-9a")
    sql, params = cursor.execute.call_args.args
    assert "ON DUPLICATE KEY" in sql and params[:2] == (7, "HT-9a")
    controller.remove(7, "HT-9a")
    assert cursor.execute.call_args.args[1] == (7, "HT-9a")
