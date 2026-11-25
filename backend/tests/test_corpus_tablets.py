"""Corpus tablets (#82): the list, the tracing, boxes from either source, and corrected copies of a tablet."""
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app import corpus, glyph_index
from backend.app.main import app
from backend.app.model.analysis import DetectedSign
from backend.app.routes import glyph_routes
from backend.app.routes.box_set_routes import get_box_set_data_controller
from backend.tests import glyph_fixtures
from backend.tests.test_box_sets import FakeController, login

STAMP = datetime(2026, 11, 18, 9, 0)
MODEL = [DetectedSign(id=1, sign="AB77", label="AB77 (ka)", reading="ka", role="syllabogram", confidence=70.0,
                      detection_confidence=90.0, box={"x": 0.1, "y": 0.1, "w": 0.1, "h": 0.2},
                      candidates=[{"sign": "AB77", "label": "AB77 (ka)", "roles": ["syllabogram"], "probability": 78.0}])]


@pytest.fixture
def tracing(tmp_path):
    path = tmp_path / "HT-1.png"
    Image.new("L", (1000, 500), 255).save(path)
    return path


@pytest.fixture
def corpus_index(monkeypatch, tracing):
    index = glyph_fixtures.index(with_embeddings=False)
    corpus._tablets.cache_clear()
    corpus._drawn.clear()
    app.dependency_overrides[glyph_routes.get_index] = lambda: index
    monkeypatch.setattr(glyph_index, "get_index", lambda: index)
    monkeypatch.setattr(glyph_index, "tracing_path", lambda slug: tracing if slug == "HT-1" else None)
    model = MagicMock(return_value=[sign.model_copy(deep=True) for sign in MODEL])
    monkeypatch.setattr(corpus, "model_signs", model)
    yield model
    app.dependency_overrides.clear()


@pytest.fixture
def client(corpus_index):
    with TestClient(app) as client:
        yield client


def test_lists_tablets_with_published_boxes_and_matches_ids_loosely(client):
    assert client.get("/tablets").json() == {"items": [{"slug": "HT-1", "tablet": "HT 1", "signs": 1}], "total": 1,
                                             "without_drawing": 0, "hint": None}
    for query in ("ht1", "HT 1", "ht-1"):
        assert client.get("/tablets", params={"q": query}).json()["total"] == 1
    assert client.get("/tablets", params={"q": "KN"}).json()["total"] == 0  # no published boxes


def test_serves_the_tracing(client, tracing):
    response = client.get("/tablets/HT-1/image")
    assert (response.status_code, response.content, response.headers["content-type"]) == (200, tracing.read_bytes(), "image/png")
    assert client.get("/tablets/HT-2/image").status_code == 404


def test_scholar_boxes_read_like_an_analysis(client):
    body = client.get("/tablets/HT-1/boxes").json()
    assert (body["tablet"], body["source"], body["width"], body["height"], body["image_url"]) == ("HT 1", "scholar", 1000, 500, "/tablets/HT-1/image")
    (sign,) = body["signs"]
    assert (sign["id"], sign["sign"], sign["confidence"]) == (1, "AB77", 100.0)
    assert sign["box"] == {"x": 0.1, "y": 0.1, "w": 0.1, "h": 0.2}
    assert body["credit"]["licence"] == "CC BY-NC-SA 4.0"
    assert body["symbol_interpretation"]


def test_model_boxes_come_from_the_reader(monkeypatch, corpus_index, tracing):
    with login(monkeypatch) as client:
        body = client.get("/tablets/HT-1/boxes", params={"source": "model"}).json()
    assert [(s["sign"], s["confidence"]) for s in body["signs"]] == [("AB77", 70.0)]
    corpus_index.assert_called_once_with("HT-1", tracing)


def test_model_boxes_need_a_login(client, corpus_index):
    """Reading a tablet runs the model, as an upload does: anonymous visitors see the scholars' boxes (#98)."""
    assert client.get("/tablets/HT-1/boxes", params={"source": "model"}).status_code == 401
    assert client.get("/tablets/HT-1/boxes").status_code == 200
    corpus_index.assert_not_called()


def test_a_busy_reader_refuses_instead_of_queueing(monkeypatch, corpus_index):
    corpus_index.side_effect = corpus.ReaderBusy("The reader is busy with another tablet. Please try again in a moment.")
    with login(monkeypatch) as client:
        response = client.get("/tablets/HT-1/boxes", params={"source": "model"})
    assert (response.status_code, response.json()["detail"]) == (503, "The reader is busy with another tablet. Please try again in a moment.")


def test_missing_reader_or_tablet(client, corpus_index, monkeypatch):
    corpus_index.side_effect = corpus.ReaderMissing("The Linear A sign reader is not installed.")
    with login(monkeypatch) as logged_in:
        assert logged_in.get("/tablets/HT-1/boxes", params={"source": "model"}).status_code == 503
    assert client.get("/tablets/NOPE/boxes").status_code == 404
    assert client.get("/tablets/HT-1/boxes", params={"source": "guess"}).status_code == 422


@pytest.fixture
def fake():
    controller = FakeController()

    def create_from_tablet(owner_id, slug, start, signs, width, height):
        if (existing := controller.find_for_tablet(owner_id, slug)) is not None:
            return existing, False
        set_id = len(controller.sets) + 1
        controller.sets[set_id] = {"id": set_id, "owner_id": owner_id, "owner": "owner", "analysis_id": None,
                                   "tablet_slug": slug, "start": start, "version": 0, "width": width, "height": height,
                                   "created_at": STAMP, "updated_at": STAMP, "filename": None}
        for sign in signs:
            box_id = len(controller.boxes) + 1
            controller.boxes[box_id] = {"id": box_id, "set": set_id, **sign["box"], "sign": sign["sign"], "deleted": False,
                                        "origin": start, **{f"original_{k}": v for k, v in sign["box"].items()},
                                        "model_sign": sign["sign"],
                                        "model_confidence": sign["confidence"] if start == "model" else None,
                                        "candidates": sign["candidates"]}
        return set_id, True

    controller.find_for_tablet = lambda owner_id, slug: next(
        (key for key, value in controller.sets.items() if value["owner_id"] == owner_id and value["tablet_slug"] == slug), None)
    controller.create_from_tablet = create_from_tablet
    app.dependency_overrides[get_box_set_data_controller] = lambda: controller
    return controller




@pytest.mark.parametrize("start,confidence,origin", [("scholar", 100.0, "scholar"), ("model", 70.0, "model")])
def test_a_copy_of_a_tablet_starts_from_the_chosen_boxes(monkeypatch, corpus_index, fake, start, confidence, origin):
    with login(monkeypatch) as owner:
        made = owner.post("/box-sets", json={"tablet": "HT-1", "start": start})
        assert made.status_code == 201
        body = made.json()
        assert body["source"] == {"kind": "tablet", "analysis_id": None, "tablet": "HT-1", "filename": None}
        assert (body["start"], body["width"], body["height"]) == (start, 1000, 500)
        (box,) = body["boxes"]
        assert (box["origin"], box["sign"], box["changed"]) == (origin, "AB77", False)
        assert body["reading"]["signs"][0]["confidence"] == confidence
        # One copy per tablet, whichever start is asked for later.
        again = owner.post("/box-sets", json={"tablet": "HT-1", "start": "model" if start == "scholar" else "scholar"})
        assert (again.status_code, again.json()["id"], again.json()["start"]) == (200, body["id"], start)
        assert owner.get("/tablets/HT-1/box-set").json()["id"] == body["id"]
        image = owner.get(f"/box-sets/{body['id']}/image")
        assert (image.status_code, image.headers["content-type"]) == (200, "image/png")


def test_copy_requests_are_checked(monkeypatch, corpus_index, fake):
    with login(monkeypatch) as owner:
        for body in ({}, {"analysis_id": 12, "tablet": "HT-1"}, {"analysis_id": 12, "start": "scholar"},
                     {"tablet": "../etc"}, {"tablet": "HT-1", "start": "guess"}):
            assert owner.post("/box-sets", json=body).status_code == 422
        assert owner.post("/box-sets", json={"tablet": "HT-2"}).status_code == 404
        assert owner.get("/tablets/HT-1/box-set").status_code == 404
        corpus_index.side_effect = corpus.ReaderMissing("No reader.")
        assert owner.post("/box-sets", json={"tablet": "HT-1", "start": "model"}).status_code == 503


def test_model_readings_are_cached_and_one_at_a_time(monkeypatch, tracing):
    """The real model_signs: a second request for a tablet comes from memory, and a request for an
    unread tablet while the reader is busy is refused rather than queued (#98)."""
    corpus._MODEL_CACHE.clear()
    reads = MagicMock(return_value=[sign.model_copy(deep=True) for sign in MODEL])
    monkeypatch.setattr(corpus, "_read_tablet", reads)
    monkeypatch.setattr(corpus.tablet_demo, "model_version", lambda: "v1")
    assert [s.sign for s in corpus.model_signs("HT-1", tracing)] == ["AB77"]
    assert [s.sign for s in corpus.model_signs("HT-1", tracing)] == ["AB77"]
    reads.assert_called_once()
    assert corpus._MODEL_LOCK.acquire(blocking=False)  # someone else is reading
    try:
        with pytest.raises(corpus.ReaderBusy):
            corpus.model_signs("HT-2", tracing.with_name("HT-1.png"))  # same file, different tablet key
        assert [s.sign for s in corpus.model_signs("HT-1", tracing)] == ["AB77"]  # cached: no wait
    finally:
        corpus._MODEL_LOCK.release()
        corpus._MODEL_CACHE.clear()


def test_tablets_without_a_downloaded_drawing_are_hidden_and_explained(monkeypatch, corpus_index):
    """A fresh clone has the transcriptions but not the drawings (git-ignored): the list shows only
    tablets it can draw, says how many are hidden, and how to download them."""
    monkeypatch.setattr(glyph_index, "tracing_path", lambda slug: None)
    with TestClient(app) as client:
        page = client.get("/tablets").json()
        assert (page["items"], page["total"], page["without_drawing"]) == ([], 0, 1)
        assert "scripts/fetch_corpus.py" in page["hint"]
        missing = client.get("/tablets/HT-1/boxes")
    assert missing.status_code == 404
    assert "not on this server" in missing.json()["detail"] and "scripts/fetch_corpus.py" in missing.json()["detail"]
