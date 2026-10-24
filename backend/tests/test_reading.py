"""Tablet reading endpoints, on synthetic tablets: no network and no corpus cache."""

import json

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app import reading
from backend.app.main import app
from la import fetch, signboxes


def sign(reading_, id_=None):
    return {"kind": "sign", "id": id_ or reading_.upper(), "reading": reading_}


def number(value):
    return {"kind": "number", "value": value}


def fraction(id_, reading_):
    return {"kind": "fraction", "id": id_, "reading": reading_}


def document(slug, total, signs=()):
    return {
        "id": slug.replace("-", " "), "url": f"https://lineara.eu/documents/{slug}/",
        "site": "Haghia Triada", "period": "LM IB", "scribe": None,
        "lines": [
            [sign("re"), sign("za"), number(5), fraction("A707", "J")],
            [sign("te"), sign("tu"), number(3)],
            [sign("ku"), sign("ro"), number(total), fraction("A707", "J")],
        ],
        "signs": list(signs),
        "arithmetic": {"status": "balances", "detail": "integers only"},
    }


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(fetch, "CACHE_DIR", cache)
    monkeypatch.setattr(signboxes, "IMAGE_DIR", tmp_path / "images")
    reading._fraction_references.cache_clear()
    yield cache
    reading._fraction_references.cache_clear()


def put(cache, doc):
    slug = doc["url"].rstrip("/").rsplit("/", 1)[-1]
    (cache / f"{slug}.json").write_text(json.dumps(doc), encoding="utf-8")


def test_reading_shows_transcription_and_a_balanced_total(corpus):
    put(corpus, document("HT-90", total=8))
    with TestClient(app) as client:
        data = client.get("/tablets/HT-90/reading").json()
    assert data["id"] == "HT 90" and data["site"] == "Haghia Triada"
    assert [t["text"] for t in data["lines"][0]["tokens"]] == ["re", "za", "5", "J"]
    assert data["lines"][0]["tokens"][3]["value"] == "1/2"
    [section] = data["sections"]
    assert section["integer_sum"] == 8 and section["entries_value"] == "17/2"
    assert section["total"]["quantity"]["value"] == "17/2"
    assert section["residual"] == "0" and section["verdict"] == "BALANCED"
    assert "CC BY-NC-SA" in data["credit"]["licence"]


def test_reading_reports_an_error_the_integer_check_misses(corpus):
    # As on HT 13: the integers balance (5 + 3 = 8), but the entries carry two J
    # (5 1/2 + 3 1/2 = 9) against a total of 8 1/2. lineara.eu checks integers only.
    doc = document("HT-91", total=8)
    doc["lines"][1].append(fraction("A707", "J"))
    put(corpus, doc)
    with TestClient(app) as client:
        [section] = client.get("/tablets/HT-91/reading").json()["sections"]
    assert section["integer_sum"] == 8
    assert section["residual"] == "-1/2"
    assert section["verdict"] == "OVERFULL"
    assert section["means"]


def test_uncached_tablet_is_fetched_once_into_the_cache(corpus, monkeypatch):
    calls = []

    def fake_get(url, timeout=30.0, retries=3):
        calls.append(url)
        return json.dumps(document("HT-92", total=8)).encode()

    monkeypatch.setattr(fetch, "_get", fake_get)
    with TestClient(app) as client:
        assert client.get("/tablets/HT-92/reading").status_code == 200
        assert client.get("/tablets/HT-92/reading").status_code == 200
    assert calls == ["https://lineara.eu/documents/HT-92/data.json"]
    assert (corpus / "HT-92.json").exists()


def test_unreachable_lineara_is_reported_not_crashed(corpus, monkeypatch):
    def offline(url, timeout=30.0, retries=3):
        raise OSError("offline")

    monkeypatch.setattr(fetch, "_get", offline)
    with TestClient(app) as client:
        response = client.get("/tablets/HT-93/reading")
    assert response.status_code == 503
    assert not (corpus / "HT-93.json").exists()


@pytest.mark.parametrize("slug", ["..", "HT_13", "HT-13-", "a b"])
def test_only_lineara_style_ids_are_accepted(corpus, slug):
    with pytest.raises(ValueError):
        reading.load_document(slug)


def bar(vertical: bool, size=60) -> np.ndarray:
    m = np.zeros((size, size), dtype=bool)
    if vertical:
        m[5:55, 25:35] = True
    else:
        m[25:35, 5:55] = True
    return m


def save_ink(mask, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.where(mask, 0, 255).astype(np.uint8)).save(path)


def fraction_doc(slug, sign_id, vertical, position=1):
    url = f"https://lineara.eu/img/tracings/crops/{slug}_{position}.png"
    doc = document(slug, total=8, signs=[{"position": position, "sign": sign_id, "role": "fraction", "image": url}])
    save_ink(bar(vertical), signboxes.IMAGE_DIR / slug / f"{slug}_{position}.png")
    return doc


def test_fraction_signs_are_identified_by_shape_against_other_tablets(corpus):
    # References: J drawn as a vertical bar, E as a horizontal one, on other tablets.
    put(corpus, fraction_doc("HT-1", "A707", vertical=True))
    put(corpus, fraction_doc("HT-2", "A704", vertical=False))
    put(corpus, fraction_doc("HT-3", "A704", vertical=True))  # the tablet under test, transcribed E
    with TestClient(app) as client:
        data = client.get("/tablets/HT-3/fraction-signs").json()
        image = client.get("/tablets/HT-3/signs/1.png")
        missing = client.get("/tablets/HT-3/signs/9.png")
    assert data["available"] is True and data["references"] == 3
    [result] = data["signs"]
    # Its own drawing is excluded, so the vertical bar matches J, and is reported as a mismatch.
    assert result["guesses"][0]["label"] == "J"
    assert result["transcribed"]["label"] == "E"
    assert result["correct"] is False
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"
    assert missing.status_code == 404


def test_fraction_signs_without_downloaded_images_are_unavailable(corpus):
    doc = document("HT-4", total=8, signs=[
        {"position": 1, "sign": "A707", "role": "fraction", "image": "https://lineara.eu/x/HT-4_1.png"}])
    put(corpus, doc)
    with TestClient(app) as client:
        data = client.get("/tablets/HT-4/fraction-signs").json()
    assert data["available"] is False and data["signs"] == []
