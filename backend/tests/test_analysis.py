from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from ultralytics.engine.results import Results

from backend.app.data_controller.analysis_data_controller import role_of
from backend.app.main import app
from backend.app.routes.analysis_routes import MAX_FILESIZE
from backend.app.tablet_demo import HT13_IMAGE

MODELS = Path(__file__).resolve().parents[2] / "models"


@pytest.fixture(autouse=True)
def no_trained_detector(monkeypatch, tmp_path):
    # Tests describe the generic baseline unless they opt in, even where trained weights exist locally.
    monkeypatch.setattr("backend.app.tablet_demo.SIGN_WEIGHTS", tmp_path / "missing-signs.pt")
    monkeypatch.setattr("backend.app.tablet_demo.CLASSIFIER_WEIGHTS", tmp_path / "missing-classifier.pt")


def _png(size=(8, 8), colour="white") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, colour).save(buffer, format="PNG")
    return buffer.getvalue()


def _post(content: bytes):
    with patch("mysql.connector.connect", side_effect=AssertionError("No DB for analysis")):
        with TestClient(app) as client:
            return client.post("/analysis", files={"file": ("sign.png", content, "image/png")})


def test_valid_image_is_analysed_by_the_generic_model_without_weights():
    response = _post(_png())

    assert response.status_code == 200
    data = response.json()
    assert (data["width"], data["height"], data["trained"]) == (8, 8, False)
    assert data["signs"] == []  # a blank image: empty is a valid reading
    assert data["time_taken"] >= 0
    # The Analysis page's own fields are always present.
    assert (data["symbol_interpretation"], data["confidence"]) == ("No signs found", 0)
    assert "generic model" in data["summary"]


def test_upload_at_the_size_limit_is_not_rejected_for_size():
    content = _png()
    response = _post(content + b"\0" * (MAX_FILESIZE - len(content)))

    assert response.status_code == 200


def test_upload_over_the_size_limit_is_rejected_instead_of_truncated():
    content = _png()
    response = _post(content + b"\0" * (MAX_FILESIZE + 1 - len(content)))

    assert response.status_code == 413
    assert response.json()["detail"] == "The image is larger than 10 MB."


def test_a_file_that_is_not_an_image_is_rejected():
    response = _post(b"not an image")

    assert response.status_code == 422


def test_missing_model_reports_unavailable_reader():
    with patch("backend.app.tablet_demo.read_image", side_effect=FileNotFoundError("weights")):
        response = _post(_png())

    assert response.status_code == 503
    assert response.json() == {"detail": "The sign reader is unavailable."}


def test_the_reader_gets_the_upload_as_a_bgr_array():
    empty = Results(np.zeros((4, 6, 3), dtype=np.uint8), path="", names={0: "sign"}, boxes=np.empty((0, 6)))
    with patch("backend.app.tablet_demo.read_image", return_value=empty) as read:
        assert _post(_png(size=(6, 4), colour="red")).status_code == 200

    image = read.call_args.args[0]
    assert image.shape == (4, 6, 3)
    assert image[0, 0].tolist() == [0, 0, 255]


def test_two_stage_reading_names_each_sign(monkeypatch, tmp_path):
    trained = tmp_path / "linear_a_signs.pt"
    trained.write_bytes(b"weights")
    monkeypatch.setattr("backend.app.tablet_demo.SIGN_WEIGHTS", trained)
    image = np.full((200, 100, 3), 255, dtype=np.uint8)
    result = Results(image, path="", names={0: "sign"}, boxes=np.array([[10, 40, 40, 120, 0.8, 0]]))
    candidates = [[
        {"sign": "AB81", "label": "AB81 (ku)", "roles": ["syllabogram"], "probability": 50.0},
        {"sign": "AB02", "label": "AB02 (ro)", "roles": ["syllabogram"], "probability": 20.0},
    ]]
    with patch("backend.app.tablet_demo.read_image", return_value=result), \
         patch("backend.app.tablet_demo.name_signs", return_value=candidates):
        response = _post(_png())

    assert response.status_code == 200
    data = response.json()
    assert data["trained"] is True
    # The page's fields: the transliteration (no catalogue here, so the sign ID) and mean confidence.
    assert (data["symbol_interpretation"], data["confidence"]) == ("AB81", 40)
    assert data["summary"] == "1 sign found: 1 syllabogram."
    assert data["lines"] == [{"index": 0, "sign_ids": [1], "text": "AB81", "gloss": "AB81"}]
    assert data["formulas"] == []
    (sign,) = data["signs"]
    assert sign.pop("crop").startswith("data:image/png;base64,")
    assert sign == {
        "id": 1,
        "sign": "AB81",
        "label": "AB81 (ku)",
        "reading": None,  # no catalogue beside the mocked classifier
        "role": "syllabogram",
        "confidence": pytest.approx(40.0),
        "detection_confidence": pytest.approx(80.0),
        "box": {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4},
        "candidates": candidates[0],
        "shape_guesses": None,
        "glyph": chr(0x10642),
        "meaning": None,  # a syllable has a sound, not a meaning
        "line": 0,
        "order": 0,
    }


@pytest.mark.parametrize(("sign", "reading", "roles", "role"), [
    ("AB81", "ku", ["logogram", "syllabogram"], "syllabogram"),  # catalogue lists logogram first
    ("AB131a", "VIN", ["logogram", "syllabogram"], "logogram"),
    ("AB21", "qi OVIS", ["logogram"], "logogram"),
    ("AB30", "ni FIC", ["logogram", "syllabogram"], "syllabogram"),  # mixed: a syllable where allowed
    ("A707", "J", ["fraction"], "fraction"),
    ("A717", "DD", ["syllabogram"], "fraction"),  # a combination fraction, catalogued oddly
    ("A710", "W", ["fraction"], "fraction"),  # open: no agreed value, still a fraction
    ("A305", None, ["transaction"], "transaction"),
    ("A301", None, ["logogram", "syllabogram"], "logogram"),
    ("X1", None, [], "unknown"),
])
def test_each_sign_gets_one_role(sign, reading, roles, role):
    assert role_of(sign, reading, roles) == role


@pytest.mark.skipif(not (MODELS / "linear_a_signs.pt").is_file(), reason="trained weights are not installed")
def test_trained_reader_reads_an_uploaded_tablet(monkeypatch):
    monkeypatch.setattr("backend.app.tablet_demo.SIGN_WEIGHTS", MODELS / "linear_a_signs.pt")
    monkeypatch.setattr("backend.app.tablet_demo.CLASSIFIER_WEIGHTS", MODELS / "linear_a_classifier.pt")
    with Image.open(HT13_IMAGE) as tablet:
        buffer = BytesIO()
        tablet.convert("RGB").save(buffer, format="PNG")

    response = _post(buffer.getvalue())

    assert response.status_code == 200
    data = response.json()
    assert data["trained"] is True
    assert (data["width"], data["height"]) == (1367, 2253)
    assert len(data["signs"]) >= 20  # HT 13 has 27 signs; the reader finds 26 of them
    assert {sign["role"] for sign in data["signs"]} >= {"syllabogram", "fraction"}
    # The KU-RO section is found, and its fractions show the scribe's known 1/2 error.
    totals = [formula for formula in data["formulas"] if formula["kind"] == "total"]
    assert [(f["verdict"], f["difference"]) for f in totals] == [("mismatch", "1/2")]
    assert data["lines"][-1]["text"] == "ku-ro J"
    ku_ro = [sign for sign in data["signs"] if sign["id"] in totals[0]["marker_ids"]]
    assert {sign["meaning"] for sign in ku_ro} == {"total (KU-RO)"}
    assert all(term["glyph"] == chr(0x10746) for term in totals[0]["total"])  # J
    assert "off by 1/2" in data["summary"]
