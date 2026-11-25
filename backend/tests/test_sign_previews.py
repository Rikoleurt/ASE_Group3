"""Sign previews for the pickers: the most typical corpus drawing, cut from the tracing when the
crops are not downloaded, else the Unicode character; and the catalogue's preview links."""

from io import BytesIO

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app import glyph_index, reading
from backend.app.data_controller import correction_data_controller
from backend.app.data_controller.correction_data_controller import catalogue_spelling
from backend.app.main import app
from backend.app.routes import glyph_routes
from backend.tests.glyph_fixtures import index as fixture_index


@pytest.fixture
def index():
    return fixture_index(with_embeddings=False)


@pytest.fixture
def client(index, monkeypatch):
    glyph_routes._previews.clear()
    app.dependency_overrides[glyph_routes.get_index] = lambda: index
    monkeypatch.setattr(reading, "sign_image", lambda slug, position: None)
    monkeypatch.setattr(glyph_index, "tracing_path", lambda slug: None)
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    glyph_routes._previews.clear()


def picture(response) -> Image.Image:
    assert response.status_code == 200 and response.headers["content-type"] == "image/png"
    assert "max-age" in response.headers["cache-control"]
    image = Image.open(BytesIO(response.content)).convert("L")
    assert image.size == (glyph_routes.PREVIEW_PX, glyph_routes.PREVIEW_PX)
    return image


def test_the_typical_occurrence_is_nearest_the_centre_and_has_a_drawing():
    with_vectors = fixture_index()
    typical = with_vectors.typical("AB77")
    assert (typical.slug, typical.position) != (
        "KN-Zb-5",
        11,
    )  # the far-off (possible mislabel) is never chosen
    assert typical.has_crop or typical.box
    assert (
        fixture_index(with_embeddings=False).typical("AB77").slug == "HT-1"
    )  # no vectors: the first drawn one
    assert fixture_index().typical("AB999") is None


def test_uses_the_downloaded_crop_when_there_is_one(client, tmp_path, monkeypatch):
    crop = tmp_path / "crop.png"
    Image.new("RGBA", (40, 80), (0, 0, 0, 255)).save(crop)  # all ink
    monkeypatch.setattr(
        reading,
        "sign_image",
        lambda slug, position: crop if (slug, position) == ("HT-1", 1) else None,
    )
    image = picture(client.get("/glyphs/AB77/preview.png"))
    centre = np.asarray(image)[40:56, 40:56]
    assert centre.max() < 64  # the ink, centred
    assert image.getpixel((2, 2)) == 255  # framed on white


def test_cuts_the_box_from_the_tracing_without_the_crops(client, tmp_path, monkeypatch):
    tracing = Image.new("RGBA", (1000, 500), (0, 0, 0, 0))  # transparent: strokes live in alpha
    for x in range(120, 180):
        for y in range(70, 130):
            tracing.putpixel(
                (x, y), (0, 0, 0, 255)
            )  # ink inside HT 1's box for sign 1 (100,50)-(200,150)
    tracing.putpixel((900, 400), (0, 0, 0, 255))  # ink elsewhere is not in the preview
    path = tmp_path / "tracing.png"
    tracing.save(path)
    monkeypatch.setattr(glyph_index, "tracing_path", lambda slug: path if slug == "HT-1" else None)
    image = np.asarray(picture(client.get("/glyphs/AB77/preview.png")))
    assert image[48, 48] < 64 and image[2, 2] == 255


def test_falls_back_to_the_character_and_matches_any_spelling(client):
    # Nothing drawn is downloaded here, so AB77 (ka) is drawn from the font; ab77 is the same sign.
    assert picture(client.get("/glyphs/ab77/preview.png")).getextrema()[0] < 64
    assert (
        client.get("/glyphs/AB01/preview.png").status_code == 200
    )  # in the corpus, no box: the font
    assert (
        client.get("/glyphs/ZZ9/preview.png").status_code == 404
    )  # neither a drawing nor a character
    assert client.get("/glyphs/not-a-sign!/preview.png").status_code == 422


def test_catalogue_spelling():
    assert [catalogue_spelling(sign) for sign in ("ab1", "AB01", "AB81", "A301", "a301")] == [
        "AB01",
        "AB01",
        "AB81",
        "A301",
        "A301",
    ]


def test_catalogue_signs_carry_their_reading_and_preview(monkeypatch):
    monkeypatch.setattr(
        correction_data_controller.tablet_demo, "active_classifier", lambda: "weights"
    )
    monkeypatch.setattr(
        correction_data_controller.tablet_demo,
        "sign_catalogue",
        lambda classifier: {
            "AB81": {"name": "AB81 (ku)", "reading": "ku"},
            "unidentified": {"name": "?"},
        },
    )
    signs = {sign.sign: sign for sign in correction_data_controller.catalogue()}
    assert signs["AB81"].reading == "ku" and signs["AB81"].preview_url == "/glyphs/AB81/preview.png"
    assert "unidentified" not in signs
    assert all(sign.preview_url == f"/glyphs/{sign.sign}/preview.png" for sign in signs.values())
