"""Sketch to search: the even pen, and POST /glyphs/sketch (the reader itself is faked)."""
from io import BytesIO

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from backend.app import sketch_search
from backend.app.data_controller import correction_data_controller
from backend.app.main import app
from backend.app.model.correction import CatalogueSign
from backend.app.rate_limit import SKETCHES
from la import glyphembed


def png(draw=None, size=(200, 200), mode="RGBA", background=(0, 0, 0, 0)) -> bytes:
    image = Image.new(mode, size, background)
    if draw:
        draw(ImageDraw.Draw(image))
    out = BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def stroke(width):
    return lambda pen: pen.line([(30, 40), (170, 160)], fill=(0, 0, 0, 255), width=width)


def test_thin_and_thick_strokes_are_redrawn_with_the_same_pen():
    thin = sketch_search.even_pen(glyphembed.ink_from_png_bytes(png(stroke(3))))
    thick = sketch_search.even_pen(glyphembed.ink_from_png_bytes(png(stroke(25))))
    assert abs(int(thin.sum()) - int(thick.sum())) < 0.15 * thin.sum()  # about the same amount of ink
    side = sketch_search.SIDE
    width = thin.sum() / (side * 2 ** 0.5)  # ink area over the diagonal's length
    assert 0.5 * sketch_search.PEN * side < width < 2 * sketch_search.PEN * side


def test_a_tap_or_an_empty_canvas_is_not_a_sketch():
    with pytest.raises(glyphembed.BadCrop):
        sketch_search.even_pen(sketch_search.sketch_ink(png(lambda pen: pen.point((5, 5), fill=(0, 0, 0, 255)))))
    with pytest.raises(glyphembed.BadCrop, match="Draw a sign first"):
        sketch_search.sketch_ink(png())  # a blank, fully transparent canvas


def test_dark_strokes_on_white_work_too():
    data = png(lambda pen: pen.line([(30, 40), (170, 160)], fill=0, width=6), mode="L", background=255)
    assert sketch_search.even_pen(glyphembed.ink_from_png_bytes(data)).any()


@pytest.fixture
def client(monkeypatch):
    SKETCHES.reset()
    monkeypatch.setattr(correction_data_controller, "catalogue", lambda: [
        CatalogueSign(sign="AB81", name="AB81 (ku)", glyph="\U00010642", reading="ku", preview_url="/glyphs/AB81/preview.png")])
    with TestClient(app) as client:
        yield client
    SKETCHES.reset()


def test_returns_the_most_similar_signs_with_their_names_and_pictures(client, monkeypatch):
    seen = {}

    def candidates(data, top):
        seen["top"] = top
        sketch_search.even_pen(sketch_search.sketch_ink(data))  # the real checks still run
        return [("AB81", 0.81234), ("A999", 0.05)]

    monkeypatch.setattr(sketch_search, "candidates", candidates)
    response = client.post("/glyphs/sketch", files={"file": ("sketch.png", png(stroke(4)), "image/png")}, data={"limit": "5"})
    assert response.status_code == 200 and seen["top"] == 5
    assert response.json()["items"] == [
        {"sign": "AB81", "name": "AB81 (ku)", "reading": "ku", "glyph": "\U00010642",
         "preview_url": "/glyphs/AB81/preview.png", "score": 81.23},
        {"sign": "A999", "name": "A999", "reading": None, "glyph": None, "preview_url": "/glyphs/A999/preview.png",
         "score": 5.0}]


def test_refuses_empty_large_and_busy_sketches(client, monkeypatch):
    empty = client.post("/glyphs/sketch", files={"file": ("sketch.png", png(), "image/png")})
    assert (empty.status_code, empty.json()["detail"]) == (422, "Draw a sign first.")
    big = client.post("/glyphs/sketch", files={"file": ("sketch.png", b"x" * (300 * 1024), "image/png")})
    assert big.status_code == 413

    def busy(data, top):
        raise sketch_search.SketchBusy("The reader is busy. Try again in a moment.")

    monkeypatch.setattr(sketch_search, "candidates", busy)
    assert client.post("/glyphs/sketch", files={"file": ("sketch.png", png(stroke(4)), "image/png")}).status_code == 503

    def missing(data, top):
        raise FileNotFoundError("weights")

    monkeypatch.setattr(sketch_search, "candidates", missing)
    response = client.post("/glyphs/sketch", files={"file": ("sketch.png", png(stroke(4)), "image/png")})
    assert (response.status_code, response.json()["detail"]) == (503, "The sign reader is unavailable.")


def test_sketches_are_rate_limited_per_address(client, monkeypatch):
    monkeypatch.setattr(sketch_search, "candidates", lambda data, top: [])
    monkeypatch.setattr(SKETCHES, "limit", 2)
    statuses = [client.post("/glyphs/sketch", files={"file": ("s.png", png(stroke(4)), "image/png")}).status_code
                for _ in range(3)]
    assert statuses == [200, 200, 429]


def test_busy_reader_gives_up_instead_of_waiting(monkeypatch):
    from backend.app import tablet_demo

    monkeypatch.setattr(sketch_search, "BUSY_SECONDS", 0.05)
    monkeypatch.setattr(sketch_search, "scorer", lambda: sketch_search.Scorer(None, None, []))
    assert tablet_demo.INFERENCE_LOCK.acquire(timeout=1)
    try:
        with pytest.raises(sketch_search.SketchBusy):
            sketch_search.candidates(png(stroke(4)))
    finally:
        tablet_demo.INFERENCE_LOCK.release()


def test_ranks_signs_by_the_blended_score_without_unidentified(monkeypatch):
    class FakeScorer:
        names = ["AB01", "unidentified", "AB81"]

        def scores(self, inks):
            assert len(inks) == 1 and inks[0].dtype == bool
            blend = np.array([[0.2, 0.7, 0.1]])
            return blend, blend, blend

    monkeypatch.setattr(sketch_search, "scorer", FakeScorer)
    assert sketch_search.candidates(png(stroke(4)), top=5) == [("AB01", 0.2), ("AB81", 0.1)]
