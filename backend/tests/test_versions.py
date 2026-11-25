"""Scholars' workbench, story C: several copies per tablet, the versions list, and comparing versions."""

import pytest
from fastapi.testclient import TestClient

from backend.app import box_matching
from backend.app.main import app
from backend.tests.test_box_sets import login, sql_controller
from backend.tests.test_corpus_tablets import corpus_index, fake, tracing  # noqa: F401  (fixtures)


def box(x, y, w=0.1, h=0.1, sign="AB77", id=1):
    return {"id": id, "box": {"x": x, "y": y, "w": w, "h": h}, "sign": sign}


# --- matching ---------------------------------------------------------------------------


def test_boxes_in_the_same_place_are_one_cluster_and_their_signs_compared():
    clusters = box_matching.cluster(
        {
            "scholar": [box(0.1, 0.1, sign="AB77"), box(0.5, 0.1, sign="AB01", id=2)],
            "model": [box(0.51, 0.11, sign="AB02", id=7), box(0.1, 0.1, sign="AB77", id=8)],
        }
    )
    assert [(sorted(c.members), c.status(["scholar", "model"])) for c in clusters] == [
        (["model", "scholar"], "agree"),
        (["model", "scholar"], "differs"),
    ]
    assert clusters[1].members["model"]["id"] == 7 and not clusters[0].moved
    assert clusters[1].moved  # shifted 0.01 each way: they overlap 68%, under 80%


def test_a_box_only_one_version_has_is_missing_and_a_shifted_box_has_moved():
    clusters = box_matching.cluster(
        {"a": [box(0.1, 0.1), box(0.7, 0.7, id=2)], "b": [box(0.12, 0.1, id=3)], "c": []}
    )
    assert [c.status(["a", "b"]) for c in clusters] == ["agree", "missing"]
    assert clusters[0].moved  # 0.02 to the right: overlap 0.67, under 0.8
    assert box_matching.agreement(clusters, "a", "b") == (1, 2)


def test_each_version_has_at_most_one_box_per_cluster():
    # Two of b's boxes overlap a's one box: only the better one joins it, the other starts its own.
    clusters = box_matching.cluster(
        {"a": [box(0.1, 0.1)], "b": [box(0.1, 0.1, id=2), box(0.13, 0.1, id=3)]}
    )
    assert [sorted((key, m["id"]) for key, m in c.members.items()) for c in clusters] == [
        [("a", 1), ("b", 2)],
        [("b", 3)],
    ]


def test_clusters_come_in_reading_order():
    clusters = box_matching.cluster(
        {
            "a": [
                box(0.6, 0.42, id=1),
                box(0.1, 0.4, id=2),
                box(0.3, 0.1, id=3),
                box(0.1, 0.12, id=4),
            ]
        }
    )
    assert [c.members["a"]["id"] for c in clusters] == [
        4,
        3,
        2,
        1,
    ]  # line 1 left to right, then line 2
    assert box_matching.cluster({}) == []


# --- several copies, the versions list ---------------------------------------------------


def test_new_makes_another_titled_copy_and_the_latest_one_opens(monkeypatch, corpus_index, fake):
    with login(monkeypatch) as owner:
        first = owner.post("/box-sets", json={"tablet": "HT-1", "start": "scholar"}).json()
        second = owner.post(
            "/box-sets",
            json={"tablet": "HT-1", "start": "model", "new": True, "title": "  My   reading "},
        )
        assert second.status_code == 201
        body = second.json()
        assert body["id"] != first["id"] and (body["title"], body["kind"], body["start"]) == (
            "My reading",
            "copy",
            "model",
        )
        assert first["title"] is None
        assert owner.post("/box-sets", json={"analysis_id": 12, "new": True}).status_code == 422
        assert (
            owner.post("/box-sets", json={"tablet": "HT-1", "title": "x" * 121}).status_code == 422
        )
    fake.sets[second.json()["id"]]["updated_at"] = fake.sets[first["id"]]["updated_at"].replace(
        year=2027
    )
    with login(monkeypatch) as owner:
        assert owner.get("/tablets/HT-1/box-set").json()["id"] == second.json()["id"]
    assert fake.boxes[1]["source_kind"] == "scholar" and fake.boxes[1]["source_box_id"] == 1


def test_versions_list_your_copies_and_those_shared_with_you(monkeypatch, corpus_index, fake):
    with login(monkeypatch, user_id=8) as other:
        private = other.post("/box-sets", json={"tablet": "HT-1", "start": "scholar"}).json()["id"]
        public = other.post(
            "/box-sets", json={"tablet": "HT-1", "start": "model", "new": True, "title": "Shared"}
        ).json()["id"]
    fake.sets[public]["everyone"] = "view"
    with login(monkeypatch, user_id=9) as third:
        shared = third.post("/box-sets", json={"tablet": "HT-1", "start": "scholar"}).json()["id"]
    fake.share_rows[(shared, 7)] = "comment"
    with login(monkeypatch) as owner:
        mine = owner.post("/box-sets", json={"tablet": "HT-1", "start": "scholar"}).json()["id"]
        page = owner.get("/tablets/HT-1/versions").json()
    assert (page["slug"], page["tablet"]) == ("HT-1", "HT 1")
    items = page["items"]
    assert [item["key"] for item in items[:2]] == ["scholar", "model"]
    assert items[0]["box_count"] == 1 and items[1]["needs_login"] is True
    copies = {item["key"]: item for item in items[2:]}
    assert items[2]["key"] == f"copy:{mine}"  # your own first
    assert set(copies) == {
        f"copy:{mine}",
        f"copy:{public}",
        f"copy:{shared}",
    }  # not the private one
    assert f"copy:{private}" not in copies
    assert (copies[f"copy:{mine}"]["mine"], copies[f"copy:{mine}"]["permission"]) == (True, "owner")
    assert (copies[f"copy:{public}"]["title"], copies[f"copy:{public}"]["permission"]) == (
        "Shared",
        "view",
    )
    assert (
        copies[f"copy:{shared}"]["permission"] == "comment"
        and copies[f"copy:{shared}"]["box_count"] == 1
    )


def test_logged_out_visitors_see_the_scholars_and_the_model_only(corpus_index, fake):
    with TestClient(app) as client:
        items = client.get("/tablets/HT-1/versions").json()["items"]
        assert [item["key"] for item in items] == ["scholar", "model"]
        assert client.get("/tablets/NOPE/versions").status_code == 404
        assert (
            client.get("/tablets/HT-1/compare", params={"v": ["scholar", "model"]}).status_code
            == 401
        )


# --- compare ------------------------------------------------------------------------------


def test_compare_matches_the_versions_boxes(monkeypatch, corpus_index, fake):
    with login(monkeypatch) as owner:
        copy = owner.post("/box-sets", json={"tablet": "HT-1", "start": "scholar"}).json()
        renamed = copy["boxes"][0]
        edited = owner.patch(
            f"/box-sets/{copy['id']}",
            json={
                "version": 0,
                "changes": [{"op": "update", "box_id": renamed["id"], "sign": "AB01"}],
            },
        )
        assert edited.status_code == 200, edited.text
        response = owner.get(
            "/tablets/HT-1/compare", params={"v": ["scholar", "model", f"copy:{copy['id']}"]}
        )
    assert response.status_code == 200
    body = response.json()
    assert [v["key"] for v in body["versions"]] == ["scholar", "model", f"copy:{copy['id']}"]
    assert (body["width"], body["height"], body["image_url"]) == (1000, 500, "/tablets/HT-1/image")
    (place,) = body["clusters"]
    assert place["status"] == "differs" and set(place["members"]) == {
        "scholar",
        "model",
        f"copy:{copy['id']}",
    }
    assert (
        place["members"]["scholar"]["sign"] == "AB77"
        and place["members"][f"copy:{copy['id']}"]["sign"] == "AB01"
    )
    agreement = {(a["a"], a["b"]): (a["same"], a["total"]) for a in body["agreement"]}
    assert agreement[("scholar", "model")] == (1, 1)
    assert agreement[("scholar", f"copy:{copy['id']}")] == (0, 1)


def test_compare_checks_the_versions(monkeypatch, corpus_index, fake):
    with login(monkeypatch, user_id=8) as other:
        private = other.post("/box-sets", json={"tablet": "HT-1", "start": "scholar"}).json()["id"]
    fake.create_from_tablet(7, "HT-2", "scholar", [], 10, 10)  # a copy of another tablet
    with login(monkeypatch) as owner:
        for v in (
            ["scholar"],
            ["scholar", "scholar"],
            ["scholar", "copy:abc"],
            ["scholar", "guess"],
            ["scholar"] + [f"copy:{n}" for n in range(1, 7)],
        ):
            assert owner.get("/tablets/HT-1/compare", params={"v": v}).status_code == 422, v
        assert (
            owner.get(
                "/tablets/HT-1/compare", params={"v": ["scholar", f"copy:{private}"]}
            ).status_code
            == 404
        )
        other_tablet = max(fake.sets)
        assert (
            owner.get(
                "/tablets/HT-1/compare", params={"v": ["scholar", f"copy:{other_tablet}"]}
            ).status_code
            == 404
        )
        assert (
            owner.get("/tablets/NOPE/compare", params={"v": ["scholar", "model"]}).status_code
            == 404
        )


# --- SQL ----------------------------------------------------------------------------------


def test_sql_lists_versions_visible_to_the_user(monkeypatch):
    controller, _connection, cursor = sql_controller(monkeypatch, [[{"id": 3}]])
    assert controller.versions_for_tablet(7, "HT-1") == [{"id": 3}]
    sql, params = cursor.execute.call_args.args
    assert (
        "s.tablet_slug = %s" in sql
        and "s.everyone <> 'none'" in sql
        and "sh.user_id IS NOT NULL" in sql
    )
    assert params == (7, "HT-1", 7, 7, 100)


@pytest.mark.parametrize("new,expected", [(False, (4, False)), (True, (5, True))])
def test_sql_new_skips_the_existing_copy(monkeypatch, new, expected):
    controller, _connection, cursor = sql_controller(monkeypatch, [[{"id": 4}]])
    cursor.lastrowid = 5
    assert (
        controller.create_from_tablet(7, "HT-1", "scholar", [], 10, 10, new=new, title="T")
        == expected
    )
