"""Scholars' workbench, story I: notifications for the people a change concerns."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from backend.app import notifications as module
from backend.app.data_controller.community_data_controller import CommunityDataController
from backend.app.main import app
from backend.app.model.community import DiscussionComment
from backend.app.model.mention import ResolvedMention
from backend.app.notifications import NotificationDataController, copy_name, notify
from backend.app.routes.notification_routes import get_notification_data_controller
from backend.tests.test_box_sets import login, sql_controller
from backend.tests.test_corpus_tablets import corpus_index, fake, tracing  # noqa: F401  (fixtures)
from backend.tests.test_editions import editions, person, release, two_releases  # noqa: F401
from backend.tests.test_merge import anouk_renames_the_sign, merge


def test_notify_skips_the_actor_and_never_fails(notifications, monkeypatch):
    notify([7, 8, 8, None], "share", 7, "x" * 400, "/box-sets/1", "HT-1")
    (row,) = notifications.rows
    assert row[:3] == (8, "share", 7) and len(row[3]) == 300 and row[4:6] == ("/box-sets/1", "HT-1")
    notify([7], "share", 7, "only the actor")
    assert len(notifications.rows) == 1

    class Broken:
        def add(self, rows):
            raise RuntimeError("database down")

    monkeypatch.setattr(module, "SINK", Broken())
    notify([8], "share", 7, "lost, quietly")  # no exception


def test_copies_are_named_for_people():
    assert copy_name({"tablet_slug": "HT-13"}) == "a copy of HT 13"
    assert copy_name({"tablet_slug": "HT-13", "title": "Mine"}) == "the copy “Mine” of HT 13"
    assert copy_name({"tablet_slug": "HT-13", "kind": "edition"}) == "an edition of HT 13"
    assert copy_name({"tablet_slug": None, "filename": "photo.png"}) == "a copy of photo.png"


def test_sharing_and_commenting_tell_the_people_concerned(
    monkeypatch, corpus_index, fake, notifications
):
    with login(monkeypatch) as owner:
        copy = owner.post(
            "/box-sets", json={"tablet": "HT-1", "start": "scholar", "new": True, "title": "Mine"}
        ).json()
        assert (
            owner.put(
                f"/box-sets/{copy['id']}/shares/8", json={"permission": "comment"}
            ).status_code
            == 200
        )
        owner.post(
            f"/box-sets/{copy['id']}/comments", json={"body": "my own note"}
        )  # the owner: no one to tell
    (shared,) = notifications.to(8)
    assert (
        shared[1] == "share"
        and shared[3] == "u7 shared the copy “Mine” of HT 1 with you: you can comment on it."
    )
    assert shared[4] == f"/box-sets/{copy['id']}"
    with login(monkeypatch, user_id=8) as guest:
        assert (
            guest.post(
                f"/box-sets/{copy['id']}/comments", json={"body": "Is the second sign  really ka?"}
            ).status_code
            == 201
        )
    (comment,) = notifications.to(7)
    assert (
        comment[1] == "comment"
        and comment[3] == "u8 commented on the copy “Mine” of HT 1: “Is the second sign really ka?”"
    )


def test_votes_overrides_and_voting_rights_are_notified(
    monkeypatch, corpus_index, fake, editions, notifications
):
    a, b = two_releases(monkeypatch, fake)
    with person(monkeypatch, 9) as ahmed:
        ahmed.put("/tablets/HT-1/vote", json={"release_id": b})
    (vote,) = notifications.to(8)  # b is anouk's (user 8)
    assert (
        vote[1] == "vote"
        and vote[3] == "ahmed backed your edition of HT 1 (release 1)."
        and vote[4] == f"/editions/{b}"
    )
    with person(monkeypatch, 11, admin=True) as boss:
        boss.put(
            "/tablets/HT-1/edition-override",
            json={"release_id": a, "comment": "Matches the new photographs"},
        )
        boss.put(
            "/admin/users/9/voting",
            json={"can_vote": False, "reason": "Voting from several accounts"},
        )
    overrides = [row for row in notifications.rows if row[1] == "override"]
    assert sorted(row[0] for row in overrides) == [7, 8]  # both editions' owners
    assert (
        "chose dev's edition (release 1)" in overrides[0][3]
        and "“Matches the new photographs”" in overrides[0][3]
    )
    (rights,) = [row for row in notifications.to(9) if row[1] == "voting_rights"]
    assert (
        rights[3]
        == "An admin (boss) removed your voting rights on editions: “Voting from several accounts”"
    )


def test_merging_someones_boxes_tells_them(monkeypatch, corpus_index, fake, notifications):
    theirs = anouk_renames_the_sign(monkeypatch, fake)
    key = f"copy:{theirs['id']}"
    with login(monkeypatch) as owner:
        merge(owner, [{"key": "scholar"}, {"key": key, "version": theirs["version"]}], [key])
        merge(
            owner, [{"key": "scholar"}, {"key": key, "version": theirs["version"]}], ["scholar"]
        )  # none of theirs
    (merged,) = [row for row in notifications.rows if row[1] == "merge"]
    assert merged[0] == 8 and merged[3] == "u7 merged boxes from your copy of HT 1 into an edition."


def test_mentioned_users_are_told(monkeypatch, notifications):
    comment = DiscussionComment(
        id=1,
        discussion_id=4,
        author_id=7,
        author_username="dev",
        created_at=datetime(2026, 11, 25),
        body="@ahmed look",
        mentions=[
            ResolvedMention(
                token="@[ahmed](user:9)", key="user:9", kind="user", label="ahmed", user_id=9
            ),
            ResolvedMention(
                token="@[ku](sign:AB81)", key="sign:AB81", kind="sign", label="ku", sign_code="AB81"
            ),
        ],
    )
    monkeypatch.setattr(
        CommunityDataController, "add_comment", lambda self, discussion, user, body: comment
    )
    with login(monkeypatch) as user:
        assert (
            user.post(
                "/community/discussions/4/comments", json={"body": "@[ahmed](user:9) look"}
            ).status_code
            == 201
        )
    (mention,) = notifications.rows
    assert mention[:2] == (9, "mention") and mention[4] == "/community/4"


class FakeNotifications:
    def __init__(self):
        self.rows = [
            {
                "id": n,
                "kind": "share",
                "actor": "anouk",
                "message": f"note {n}",
                "link": "/box-sets/1",
                "tablet_slug": "HT-1",
                "created_at": datetime(2026, 11, 25, 9, n),
                "read_at": None,
            }
            for n in range(1, 4)
        ]

    def page(self, user_id, limit, before=None):
        rows = [row for row in reversed(self.rows) if before is None or row["id"] < before]
        return rows[: limit + 1]

    def unread(self, user_id):
        return sum(row["read_at"] is None for row in self.rows)

    def mark_read(self, user_id, ids):
        for row in self.rows:
            if ids is None or row["id"] in ids:
                row["read_at"] = datetime(2026, 11, 25, 12)


@pytest.fixture
def inbox():
    store = FakeNotifications()
    app.dependency_overrides[get_notification_data_controller] = lambda: store
    yield store
    app.dependency_overrides.pop(get_notification_data_controller, None)


def test_the_bell_lists_pages_and_marks_read(monkeypatch, inbox):
    with login(monkeypatch) as user:
        page = user.get("/notifications", params={"limit": 2}).json()
        assert [item["message"] for item in page["items"]] == ["note 3", "note 2"]
        assert (page["next_before"], page["unread"], page["items"][0]["read"]) == (2, 3, False)
        assert [
            item["id"] for item in user.get("/notifications", params={"before": 2}).json()["items"]
        ] == [1]
        assert user.post("/notifications/read", json={"ids": [3]}).json() == {"unread": 2}
        assert user.get("/notifications/unread-count").json() == {"unread": 2}
        assert user.post("/notifications/read", json={}).json() == {"unread": 0}
        user.headers.pop("X-CSRF-Token")
        assert user.post("/notifications/read", json={}).status_code == 403
    with TestClient(app) as visitor:
        assert visitor.get("/notifications/unread-count").status_code == 401


def test_sql_notifications(monkeypatch):
    _c, _connection, cursor = sql_controller(monkeypatch, [[{"n": 4}]])
    controller = NotificationDataController()
    assert controller.unread(7) == 4
    controller.mark_read(7, [1, 2])
    sql, params = cursor.execute.call_args.args
    assert "id IN (%s, %s)" in sql and params[1:] == (7, 1, 2)
    controller.mark_read(7, [])  # nothing to do
    assert cursor.execute.call_args.args[1][1:] == (7, 1, 2)
