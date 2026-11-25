"""Scholars' workbench, story E: edition releases, votes, the admin override and voting rights."""

import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from backend.app.auth import COOKIE_NAME, csrf_token, token_hash
from backend.app.data_controller.edition_data_controller import EditionDataController
from backend.app.data_controller.user_data_controller import UserDataController
from backend.app.main import app
from backend.app.model.user import Account
from backend.app.routes.edition_routes import get_edition_data_controller
from backend.tests.test_box_sets import sql_controller
from backend.tests.test_corpus_tablets import corpus_index, fake, tracing  # noqa: F401  (fixtures)

USERS = {7: "dev", 8: "anouk", 9: "ahmed", 10: "newbie", 11: "boss"}


class FakeEditions:
    """EditionDataController in memory, with the same rules as its SQL."""

    def __init__(self, box_sets):
        self.box_sets = box_sets
        self.releases, self.votes, self.overrides, self.rights_log = {}, {}, [], []
        self.users = {
            uid: {"can_vote": True, "old_enough": uid != 10, "is_reviewer": uid == 9}
            for uid in USERS
        }

    def _row(self, release):
        copy = self.box_sets.sets[release["set_id"]]
        return {
            **release,
            "owner": USERS.get(copy["owner_id"], copy["owner"]),
            "everyone": copy.get("everyone", "none"),
            "owner_id": copy["owner_id"],
        }

    def create_release(self, set_id, created_by, snapshot):
        number = 1 + max(
            (r["number"] for r in self.releases.values() if r["set_id"] == set_id), default=0
        )
        release_id = len(self.releases) + 1
        self.releases[release_id] = {
            "id": release_id,
            "set_id": set_id,
            "number": number,
            "tablet_slug": snapshot["tablet"],
            "title": snapshot["title"],
            "notes": snapshot["notes"],
            "version": snapshot["version"],
            "width": snapshot["width"],
            "height": snapshot["height"],
            "boxes": snapshot["boxes"],
            "merged_from": snapshot["merged_from"],
            "contributors": snapshot["contributors"],
            "created_at": datetime(2026, 11, 25, 9, release_id),
        }
        if self.box_sets.sets[set_id].get("everyone", "none") == "none":
            self.box_sets.sets[set_id]["everyone"] = "view"
        return release_id

    def release(self, release_id):
        found = self.releases.get(release_id)
        return self._row(found) if found else None

    def releases_of(self, set_id):
        return [
            self._row(r)
            for r in sorted(self.releases.values(), key=lambda r: -r["number"])
            if r["set_id"] == set_id
        ]

    def tablet_releases(self, slug):
        return [
            self._row(r)
            for r in self.releases.values()
            if r["tablet_slug"] == slug
            and self.box_sets.sets[r["set_id"]].get("everyone", "none") != "none"
        ]

    def released_tablets(self):
        return sorted({r["tablet_slug"] for r in self.tablet_releases_all()})

    def tablet_releases_all(self):
        return [
            r
            for r in self.releases.values()
            if self.box_sets.sets[r["set_id"]].get("everyone", "none") != "none"
        ]

    def vote_counts(self, slug):
        counts = {}
        for (tablet, user), release in self.votes.items():
            if tablet == slug and self.users[user]["can_vote"]:
                total, reviewers = counts.get(release, (0, 0))
                counts[release] = (total + 1, reviewers + int(self.users[user]["is_reviewer"]))
        return counts

    def my_vote(self, slug, user_id):
        return self.votes.get((slug, user_id))

    def voter(self, user_id):
        user = self.users.get(user_id)
        return {"can_vote": user["can_vote"], "old_enough": user["old_enough"]} if user else None

    def vote(self, slug, user_id, release_id):
        self.votes[(slug, user_id)] = release_id

    def unvote(self, slug, user_id):
        self.votes.pop((slug, user_id), None)

    def current_override(self, slug):
        live = [o for o in self.overrides if o["tablet"] == slug and not o["cleared"]]
        return (
            {k: live[-1][k] for k in ("release_id", "admin", "comment", "created_at")}
            if live
            else None
        )

    def set_override(self, slug, release_id, admin_id, comment):
        for o in self.overrides:
            if o["tablet"] == slug:
                o["cleared"] = True
        self.overrides.append(
            {
                "tablet": slug,
                "release_id": release_id,
                "admin": USERS[admin_id],
                "comment": comment,
                "created_at": datetime(2026, 11, 25, 10),
                "cleared": False,
            }
        )

    def clear_override(self, slug, admin_id, comment):
        live = [o for o in self.overrides if o["tablet"] == slug and not o["cleared"]]
        for o in live:
            o["cleared"] = True
        return bool(live)

    def voting_rights(self, user_id):
        if user_id not in self.users:
            return None
        last = [c for c in self.rights_log if c["user_id"] == user_id]
        return {
            "can_vote": self.users[user_id]["can_vote"],
            "reason": last[-1]["reason"] if last else None,
            "changed_by": last[-1]["by"] if last else None,
            "changed_at": datetime(2026, 11, 25, 11) if last else None,
        }

    def set_voting_rights(self, user_id, admin_id, can_vote, reason):
        if user_id not in self.users:
            return False
        self.users[user_id]["can_vote"] = can_vote
        self.rights_log.append({"user_id": user_id, "by": USERS[admin_id], "reason": reason})
        return True


@pytest.fixture
def editions(fake):
    store = FakeEditions(fake)
    fake.usernames.update(USERS)
    app.dependency_overrides[get_edition_data_controller] = lambda: store
    yield store
    app.dependency_overrides.pop(get_edition_data_controller, None)


def person(monkeypatch, user_id, admin=False, csrf=True):
    """A client logged in as `user_id` (admins: user 11). Several can be used in one test."""
    sessions = getattr(person, "sessions", {})
    token = f"{user_id}".rjust(43, "s")
    sessions[token_hash(token)] = Account(
        id=user_id, email=f"u{user_id}@ase3.com", username=USERS[user_id], is_admin=admin
    )
    person.sessions = sessions
    monkeypatch.setattr(
        UserDataController, "get_session_user", lambda self, digest: sessions.get(digest)
    )
    client = TestClient(app)
    client.cookies.set(COOKIE_NAME, token)
    if csrf:
        client.headers["X-CSRF-Token"] = csrf_token(token)
    return client


def an_edition(fake, owner=7, sign="AB77", title="Agreed"):
    """An edition of HT-1 with one box, as a merge would make it."""
    box = {
        "box": {"x": 0.1, "y": 0.1, "w": 0.1, "h": 0.2},
        "sign": sign,
        "origin": "scholar",
        "source_kind": "copy",
        "source_set_id": 99,
        "source_box_id": 1,
        "source_version": 2,
        "source_author_id": 8,
    }
    return fake.create_edition(
        owner, "HT-1", title, 1000, 500, [box], [{"key": "scholar", "kind": "scholar"}]
    )


def release(client, set_id, notes=None):
    return client.post(f"/box-sets/{set_id}/releases", json={"notes": notes} if notes else {})


# --- releases -----------------------------------------------------------------------------


def test_releasing_snapshots_the_edition_and_opens_it_for_voting(
    monkeypatch, corpus_index, fake, editions
):
    set_id = an_edition(fake)
    with person(monkeypatch, 7) as owner:
        made = release(owner, set_id, notes="  First agreed reading ")
        assert made.status_code == 201, made.text
        body = made.json()
        assert (body["number"], body["notes"], body["title"], body["owner"], body["tablet"]) == (
            1,
            "First agreed reading",
            "Agreed",
            "dev",
            "HT-1",
        )
        assert (
            body["boxes"][0]["sign"] == "AB77" and body["boxes"][0]["source"]["author"] == "anouk"
        )
        assert body["contributors"] == ["anouk", "dev"]
        assert fake.sets[set_id]["everyone"] == "view"
        fake.boxes[max(fake.boxes)]["sign"] = "AB01"  # editing the edition afterwards...
        assert (
            owner.get(f"/editions/{body['id']}").json()["boxes"][0]["sign"] == "AB77"
        )  # ...leaves the release
        assert release(owner, set_id).json()["number"] == 2
        assert [r["number"] for r in owner.get(f"/box-sets/{set_id}/releases").json()] == [2, 1]


def test_only_editions_are_released_and_only_by_their_managers(
    monkeypatch, corpus_index, fake, editions
):
    set_id = an_edition(fake)
    copy_id, _ = fake.create_from_tablet(7, "HT-1", "scholar", [], 1000, 500, new=True)
    with person(monkeypatch, 7) as owner:
        assert release(owner, copy_id).status_code == 422
    fake.sets[set_id]["everyone"] = "view"
    with person(monkeypatch, 8) as other:
        assert release(other, set_id).status_code == 403  # can view, not manage
    fake.share_rows[(set_id, 8)] = "manage"
    with person(monkeypatch, 8) as manager:
        assert release(manager, set_id).status_code == 201


def test_a_release_page_is_public_once_open_and_carries_its_reading(
    monkeypatch, corpus_index, fake, editions
):
    set_id = an_edition(fake)
    with person(monkeypatch, 7) as owner:
        release_id = release(owner, set_id).json()["id"]
    with TestClient(app) as visitor:
        page = visitor.get(f"/editions/{release_id}")
        assert page.status_code == 200 and page.json()["reading"]["signs"][0]["sign"] == "AB77"
        fake.sets[set_id]["everyone"] = "none"  # made private again
        assert visitor.get(f"/editions/{release_id}").status_code == 404
        assert visitor.get("/editions/999").status_code == 404
    with person(monkeypatch, 7) as owner:
        assert owner.get(f"/editions/{release_id}").status_code == 200


# --- votes --------------------------------------------------------------------------------


def two_releases(monkeypatch, fake):
    first, second = an_edition(fake, owner=7), an_edition(fake, owner=8, title="Other")
    with person(monkeypatch, 7) as dev:
        a = release(dev, first).json()["id"]
    with person(monkeypatch, 8) as anouk:
        b = release(anouk, second).json()["id"]
    return a, b


def test_one_vote_per_account_and_the_most_backed_release_is_accepted(
    monkeypatch, corpus_index, fake, editions
):
    a, b = two_releases(monkeypatch, fake)
    with TestClient(app) as visitor:
        page = visitor.get("/tablets/HT-1/editions").json()
        assert (
            page["voting"] == {"allowed": False, "reason": "Log in to vote."}
            and page["accepted_release_id"] is None
        )
    with person(monkeypatch, 7) as dev:
        assert dev.put("/tablets/HT-1/vote", json={"release_id": a}).json()["my_vote"] == a
        page = dev.put(
            "/tablets/HT-1/vote", json={"release_id": b}
        ).json()  # changing it replaces it
        assert page["my_vote"] == b and {i["id"]: i["votes"] for i in page["items"]} == {a: 0, b: 1}
    with person(monkeypatch, 9) as ahmed:
        page = ahmed.put("/tablets/HT-1/vote", json={"release_id": a}).json()
    assert page["accepted_release_id"] == a  # 1-1: the earlier release wins the tie
    assert (
        page["items"][0]["id"] == a
        and page["items"][0]["accepted"]
        and page["items"][0]["reviewer_votes"] == 1
    )
    with person(monkeypatch, 8) as anouk:
        page = anouk.put("/tablets/HT-1/vote", json={"release_id": b}).json()
        assert page["accepted_release_id"] == b
        assert anouk.delete("/tablets/HT-1/vote").json()["my_vote"] is None


def test_new_accounts_and_unknown_releases_cannot_be_voted_for(
    monkeypatch, corpus_index, fake, editions
):
    a, _ = two_releases(monkeypatch, fake)
    with person(monkeypatch, 10) as newbie:
        refused = newbie.put("/tablets/HT-1/vote", json={"release_id": a})
        assert (refused.status_code, refused.json()["detail"]) == (
            403,
            "New accounts can vote one day after they are made.",
        )
    with person(monkeypatch, 7) as dev:
        assert dev.put("/tablets/HT-1/vote", json={"release_id": 999}).status_code == 404
        assert (
            dev.put("/tablets/HT-2/vote", json={"release_id": a}).status_code == 404
        )  # another tablet's
    with person(monkeypatch, 7, csrf=False) as no_token:
        assert no_token.put("/tablets/HT-1/vote", json={"release_id": a}).status_code == 403


# --- the admin override -------------------------------------------------------------------


def test_an_admin_override_needs_a_reason_everyone_sees(monkeypatch, corpus_index, fake, editions):
    a, b = two_releases(monkeypatch, fake)
    with person(monkeypatch, 7) as dev:
        dev.put("/tablets/HT-1/vote", json={"release_id": a})
        assert (
            dev.put(
                "/tablets/HT-1/edition-override", json={"release_id": b, "comment": "x" * 20}
            ).status_code
            == 403
        )
    with person(monkeypatch, 11, admin=True) as boss:
        short = boss.put(
            "/tablets/HT-1/edition-override", json={"release_id": b, "comment": "  because "}
        )
        assert short.status_code == 422
        page = boss.put(
            "/tablets/HT-1/edition-override",
            json={"release_id": b, "comment": "Matches the new photographs of the tablet"},
        ).json()
    assert page["accepted_release_id"] == b
    assert (
        page["override"]["admin"] == "boss"
        and page["override"]["comment"] == "Matches the new photographs of the tablet"
    )
    with TestClient(app) as visitor:  # shown to everyone, and the votes stay visible
        page = visitor.get("/tablets/HT-1/editions").json()
        assert (
            page["override"]["release_id"] == b
            and {i["id"]: i["votes"] for i in page["items"]}[a] == 1
        )
    with person(monkeypatch, 11, admin=True) as boss:
        assert (
            boss.post("/tablets/HT-1/edition-override/clear", json={"comment": "short"}).status_code
            == 422
        )
        cleared = boss.post(
            "/tablets/HT-1/edition-override/clear", json={"comment": "Back to the community vote"}
        )
        assert cleared.json()["override"] is None and cleared.json()["accepted_release_id"] == a
        assert (
            boss.post(
                "/tablets/HT-1/edition-override/clear",
                json={"comment": "Back to the community vote"},
            ).status_code
            == 404
        )


# --- voting rights ------------------------------------------------------------------------


def test_removed_voting_rights_hide_the_votes_until_restored(
    monkeypatch, corpus_index, fake, editions
):
    a, _ = two_releases(monkeypatch, fake)
    with person(monkeypatch, 9) as ahmed:
        ahmed.put("/tablets/HT-1/vote", json={"release_id": a})
    with person(monkeypatch, 11, admin=True) as boss:
        removed = boss.put(
            "/admin/users/9/voting",
            json={"can_vote": False, "reason": "Voting from several accounts"},
        )
        assert removed.json()["can_vote"] is False and removed.json()["changed_by"] == "boss"
        assert (
            boss.put(
                "/admin/users/11/voting",
                json={"can_vote": False, "reason": "Removing my own rights"},
            ).status_code
            == 422
        )
        assert (
            boss.put(
                "/admin/users/999/voting",
                json={"can_vote": False, "reason": "No such account here"},
            ).status_code
            == 404
        )
        assert (
            boss.put(
                "/admin/users/9/voting", json={"can_vote": False, "reason": "short"}
            ).status_code
            == 422
        )
        page = boss.get("/tablets/HT-1/editions").json()
        assert {i["id"]: i["votes"] for i in page["items"]}[a] == 0  # kept, not counted
    with person(monkeypatch, 9) as ahmed:
        page = ahmed.get("/tablets/HT-1/editions").json()
        assert page["voting"] == {
            "allowed": False,
            "reason": "Your voting rights were removed by an admin: Voting from several accounts",
        }
        assert ahmed.put("/tablets/HT-1/vote", json={"release_id": a}).status_code == 403
        assert ahmed.get("/admin/users/9/voting").status_code == 403  # admins only
    with person(monkeypatch, 11, admin=True) as boss:
        boss.put(
            "/admin/users/9/voting", json={"can_vote": True, "reason": "Explained, rights restored"}
        )
        assert {i["id"]: i["votes"] for i in boss.get("/tablets/HT-1/editions").json()["items"]}[
            a
        ] == 1


# --- the training export ------------------------------------------------------------------


def test_the_export_can_give_one_accepted_edition_per_tablet(
    monkeypatch, corpus_index, fake, editions
):
    from backend.app.routes.admin_routes import get_correction_controller

    a, b = two_releases(monkeypatch, fake)
    app.dependency_overrides[get_correction_controller] = lambda: type(
        "C", (), {"export_approved": lambda self: []}
    )()
    try:
        with person(monkeypatch, 9) as ahmed:
            ahmed.put("/tablets/HT-1/vote", json={"release_id": b})
        with person(monkeypatch, 11, admin=True) as boss:
            body = boss.get("/admin/export/corrections", params={"accepted_only": True}).json()
        (only,) = body["copies"]
        assert (only["copy_id"], only["tablet"], only["image"], only["owner_trusted"]) == (
            b,
            "HT-1",
            f"images/edition-{b}.png",
            True,
        )
        assert [sign["sign"] for sign in only["signs"]] == ["AB77"]
        with person(monkeypatch, 9) as ahmed:
            assert (
                ahmed.get("/admin/export/corrections", params={"accepted_only": True}).status_code
                == 403
            )
    finally:
        app.dependency_overrides.pop(get_correction_controller, None)


# --- SQL ----------------------------------------------------------------------------------


def edition_sql(monkeypatch, rows=()):
    controller, connection, cursor = sql_controller(monkeypatch, rows)
    return EditionDataController(), connection, cursor


def test_sql_counts_only_votes_of_accounts_that_may_vote(monkeypatch):
    controller, _, cursor = edition_sql(
        monkeypatch, [[{"release_id": 3, "votes": 2, "reviewers": 1}]]
    )
    assert controller.vote_counts("HT-1") == {3: (2, 1)}
    sql, params = cursor.execute.call_args.args
    assert "u.can_vote" in sql and params == ("HT-1",)


def test_sql_numbers_releases_and_opens_the_edition(monkeypatch):
    controller, _, cursor = edition_sql(monkeypatch)
    cursor.fetchone.side_effect = [{"everyone": "none"}, {"next": 3}]
    cursor.lastrowid = 12
    snapshot = {
        "tablet": "HT-1",
        "title": None,
        "notes": None,
        "version": 4,
        "width": 10,
        "height": 10,
        "boxes": [],
        "merged_from": [],
        "contributors": ["dev"],
    }
    assert controller.create_release(5, 7, snapshot) == 12
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert "FOR UPDATE" in statements[0] and "MAX(number)" in statements[1]
    assert cursor.execute.call_args_list[2].args[1][:2] == (5, 3)
    assert json.loads(cursor.execute.call_args_list[2].args[1][10]) == ["dev"]
    assert "everyone = 'view'" in statements[3]


def test_sql_voters_wait_a_day(monkeypatch):
    controller, _, cursor = edition_sql(monkeypatch, [[{"can_vote": 1, "old_enough": 0}]])
    assert controller.voter(7) == {"can_vote": True, "old_enough": False}
    assert "INTERVAL 1 DAY" in cursor.execute.call_args.args[0]
