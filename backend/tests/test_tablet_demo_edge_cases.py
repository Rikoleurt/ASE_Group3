from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.tablet_demo import ht13_result


@pytest.fixture(autouse=True)
def no_trained_detector(monkeypatch, tmp_path):
    # Use the generic baseline even where trained weights exist locally.
    monkeypatch.setattr("backend.app.tablet_demo.SIGN_WEIGHTS", tmp_path / "missing-signs.pt")
    monkeypatch.setattr("backend.app.tablet_demo.CLASSIFIER_WEIGHTS", tmp_path / "missing-classifier.pt")


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_missing_image_fails_instead_of_running_on_nothing(tmp_path):
    with pytest.raises(FileNotFoundError, match="Cannot read HT13 image"):
        ht13_result(tmp_path / "missing.webp")


def test_predictions_report_encoding_failure_as_unavailable(client):
    with patch("backend.app.tablet_demo.ht13_result", side_effect=RuntimeError("encode")):
        response = client.get("/tablet-demo/ht13/predictions")
    assert response.status_code == 503
    assert response.json() == {"detail": "HT13 predictions are unavailable."}


def test_original_image_does_not_load_the_model(client):
    with patch("backend.app.tablet_demo.ht13_result", side_effect=AssertionError("model loaded")):
        response = client.get("/tablet-demo/ht13?annotated=false")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"


def test_invalid_annotated_flag_is_rejected(client):
    assert client.get("/tablet-demo/ht13?annotated=maybe").status_code == 422

