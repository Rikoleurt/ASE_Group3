"""Scholars' workbench, story I: activity bubbles on corpus glyphs."""

from fastapi.testclient import TestClient

from backend.app.data_controller.activity_data_controller import ActivityDataController
from backend.app.main import app
from backend.app.routes.activity_routes import get_activity_data_controller
from backend.tests.test_box_sets import login, sql_controller


class FakeActivity:
    def __init__(self):
        self.counts, self.seen = {"HT-1": {1: 3, 4: 1}}, []

    def glyph_activity(self, user_id, slug):
        return {
            position: n
            for position, n in self.counts.get(slug, {}).items()
            if (user_id, f"{slug}:{position}") not in self.seen
        }

    def mark_seen(self, user_id, key):
        self.seen.append((user_id, key))


def test_bubbles_count_activity_and_opening_a_glyph_clears_it(monkeypatch):
    fake = FakeActivity()
    app.dependency_overrides[get_activity_data_controller] = lambda: fake
    try:
        with login(monkeypatch) as user:
            assert user.get("/tablets/HT-1/glyph-activity").json() == {
                "tablet": "HT-1",
                "counts": {"1": 3, "4": 1},
            }
            assert (
                user.post("/glyphs/seen", json={"tablet": "HT-1", "position": 1}).status_code == 204
            )
            assert user.get("/tablets/HT-1/glyph-activity").json()["counts"] == {"4": 1}
            assert (
                user.post("/glyphs/seen", json={"tablet": "../x", "position": 1}).status_code == 422
            )
            assert (
                user.post("/glyphs/seen", json={"tablet": "HT-1", "position": -1}).status_code
                == 422
            )
            user.headers.pop("X-CSRF-Token")
            assert (
                user.post("/glyphs/seen", json={"tablet": "HT-1", "position": 4}).status_code == 403
            )
        with TestClient(app) as visitor:
            assert visitor.get("/tablets/HT-1/glyph-activity").status_code == 401
    finally:
        app.dependency_overrides.pop(get_activity_data_controller, None)
    assert fake.seen == [(7, "HT-1:1")]


def test_sql_counts_others_activity_since_last_seen(monkeypatch):
    _controller, _connection, cursor = sql_controller(monkeypatch, [[{"position": 2, "n": 5}]])
    controller = ActivityDataController()
    assert controller.glyph_activity(7, "HT-1") == {2: 5}
    sql, params = cursor.execute.call_args.args
    assert sql.count("%s") == len(params)  # every placeholder has its value
    for part in (
        "glyph_annotation_target",
        "box_comment",
        "box_change",
        "source_kind = 'scholar'",
        "a.author_id <> %s",
        "glyph_seen",
        "INTERVAL 14 DAY",
        "s.everyone <> 'none'",
    ):
        assert part in sql, part
    assert params[0] == "HT-1" and params[-1] == "HT-1" and params[-2] == 7


def test_sql_marks_a_glyph_seen(monkeypatch):
    _controller, _connection, cursor = sql_controller(monkeypatch)
    ActivityDataController().mark_seen(7, "HT-1:2")
    sql, params = cursor.execute.call_args.args
    assert "ON DUPLICATE KEY UPDATE" in sql and params[:2] == (7, "HT-1:2")
