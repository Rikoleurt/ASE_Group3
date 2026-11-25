"""Scholars' workbench, story J: work queues."""

import json

import pytest
from fastapi.testclient import TestClient

from backend.app import work_queues
from backend.app.main import app
from backend.tests.test_corpus_tablets import corpus_index, fake, tracing  # noqa: F401  (fixtures)
from backend.tests.test_editions import an_edition, editions, person, release  # noqa: F401

BOX = {"x": 0.1, "y": 0.1, "w": 0.1, "h": 0.2}


@pytest.fixture
def offline(monkeypatch, tmp_path):
    """A small offline run: HT-1 half agrees with the model, HT-2 fully; three model signs."""
    path = tmp_path / "disagreement.json"
    path.write_text(
        json.dumps(
            {
                "model_version": "reader-7",
                "built_at": "2026-11-25T10:00:00",
                "tablets": {
                    "HT-1": {"tablet": "HT 1", "agree": 1, "differs": 1, "missing": 0, "total": 2},
                    "HT-2": {"tablet": "HT 2", "agree": 2, "differs": 0, "missing": 0, "total": 2},
                    "KN-1": {"tablet": "KN 1", "agree": 7, "differs": 2, "missing": 1, "total": 10},
                    "Odd": {"tablet": "Odd", "agree": 0, "differs": 0, "missing": 0, "total": 0},
                },
                "low_confidence": [
                    {
                        "slug": "HT-2",
                        "tablet": "HT 2",
                        "id": i,
                        "sign": "AB77",
                        "label": "AB77 (ka)",
                        "reading": "ka",
                        "confidence": c,
                        "box": BOX,
                        "candidates": [{"sign": "AB77", "label": "AB77", "probability": c}],
                    }
                    for i, c in ((1, 40.0), (2, 12.5), (3, 33.0))
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(work_queues, "DISAGREEMENT", path)
    return path


def test_compare_counts_agreeing_differing_and_missing_places():
    first = [
        {"id": 1, "box": BOX, "sign": "AB77"},
        {"id": 2, "box": {**BOX, "x": 0.5}, "sign": "AB01"},
    ]
    second = [
        {"id": 9, "box": {**BOX, "x": 0.11}, "sign": "AB77"},  # same place, same sign
        {"id": 8, "box": {**BOX, "x": 0.5}, "sign": "AB08"},  # same place, another sign
        {"id": 7, "box": {**BOX, "y": 0.6}, "sign": "AB77"},  # only in the second
    ]
    assert work_queues.compare(first, second) == {
        "agree": 1,
        "differs": 1,
        "missing": 1,
        "total": 3,
        "score": 0.6667,
    }
    assert work_queues.compare([], [])["score"] == 0.0


@pytest.mark.parametrize(
    "counts,gap", [([3, 2], 1), ([2, 2, 0], 0), ([4, 1], None), ([1], None), ([0, 0], None)]
)
def test_votes_are_close_when_one_vote_would_decide(counts, gap):
    assert work_queues.close_votes(counts) == gap


def test_queues_need_a_login(corpus_index, offline, editions):
    with TestClient(app) as client:
        assert client.get("/queues/disagreement").status_code == 401
        assert client.get("/queues/low-confidence").status_code == 401


def test_disagreement_with_the_model_comes_from_the_offline_run(
    monkeypatch, corpus_index, offline, editions
):
    with person(monkeypatch, 7) as client:
        body = client.get("/queues/disagreement").json()
        assert (body["against"], body["model_version"], body["total"]) == (
            "model",
            "reader-7",
            3,
        )  # empty ones left out
        # Most places that differ first: KN 1 (3 of 10) before HT 1 (1 of 2), then by share.
        assert [(row["slug"], row["score"]) for row in body["items"]] == [
            ("KN-1", 0.3),
            ("HT-1", 0.5),
            ("HT-2", 0.0),
        ]
        page = client.get("/queues/disagreement?offset=1&limit=1").json()
        assert [row["slug"] for row in page["items"]] == ["HT-1"] and page["total"] == 3


def test_without_the_offline_run_the_queues_say_how_to_build_it(
    monkeypatch, tmp_path, corpus_index, editions
):
    monkeypatch.setattr(work_queues, "DISAGREEMENT", tmp_path / "none.json")
    with person(monkeypatch, 7) as client:
        for path in ("/queues/disagreement", "/queues/low-confidence"):
            body = client.get(path).json()
            assert body["total"] == 0 and "build_disagreement.py" in body["missing_hint"]


def test_low_confidence_signs_come_least_confident_first(
    monkeypatch, corpus_index, offline, editions
):
    with person(monkeypatch, 7) as client:
        body = client.get("/queues/low-confidence?limit=2").json()
        assert body["total"] == 3 and body["threshold"] == work_queues.LOW_CONFIDENCE
        assert [(row["id"], row["confidence"], row["tablet"]) for row in body["items"]] == [
            (2, 12.5, "HT 2"),
            (3, 33.0, "HT 2"),
        ]


def test_disagreement_with_accepted_editions_is_compared_live(
    monkeypatch, corpus_index, fake, editions
):
    set_id = an_edition(fake, sign="AB01")  # the scholars read AB77 there
    with person(monkeypatch, 7) as owner:
        made = release(owner, set_id).json()
        owner.put("/tablets/HT-1/vote", json={"release_id": made["id"]})
        body = owner.get("/queues/disagreement?against=edition").json()
    (row,) = body["items"]
    assert (row["slug"], row["release_id"], row["agree"], row["differs"], row["missing"]) == (
        "HT-1",
        made["id"],
        0,
        1,
        0,
    )
    assert row["edition_id"] == set_id
    assert (
        row["score"] == 1.0
    )  # the scholars' second sign (no box) is not counted; AB01 vs AB77 differs


def test_tablets_with_no_edition_are_listed_until_one_is_released(
    monkeypatch, corpus_index, fake, editions
):
    with person(monkeypatch, 7) as owner:
        assert [row["slug"] for row in owner.get("/queues/no-edition").json()["items"]] == ["HT-1"]
        release(owner, an_edition(fake))
        assert owner.get("/queues/no-edition").json() == {"total": 0, "items": []}


def test_close_votes_list_tablets_one_vote_from_changing(monkeypatch, corpus_index, fake, editions):
    with person(monkeypatch, 7) as dev:
        first = release(dev, an_edition(fake)).json()["id"]
        second = release(dev, an_edition(fake, title="Other")).json()["id"]
        assert dev.get("/queues/close-votes").json()["total"] == 0  # nobody voted yet
        dev.put("/tablets/HT-1/vote", json={"release_id": first})
    with person(monkeypatch, 8) as anouk:
        body = anouk.get("/queues/close-votes").json()
        (row,) = body["items"]
        assert (row["slug"], row["gap"], row["votes"]) == ("HT-1", 1, 1)
        assert [r["id"] for r in row["releases"]] == [first, second]
        anouk.put("/tablets/HT-1/vote", json={"release_id": first})
        assert anouk.get("/queues/close-votes").json()["total"] == 0  # 2 to 0: decided
