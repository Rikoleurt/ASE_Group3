"""Upload edge cases for POST /analysis. The size limit, oversized uploads and a
missing model are covered in test_analysis.py."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.main import app
from backend.app.model.analysis import AnalysisResult


@pytest.fixture(autouse=True)
def no_trained_detector(monkeypatch, tmp_path):
    # Use the generic baseline even where trained weights exist locally.
    monkeypatch.setattr("backend.app.tablet_demo.SIGN_WEIGHTS", tmp_path / "missing-signs.pt")
    monkeypatch.setattr("backend.app.tablet_demo.CLASSIFIER_WEIGHTS", tmp_path / "missing-classifier.pt")


@pytest.fixture
def client():
    # Report server errors as 500 responses, as a browser would see them.
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def image_bytes(format: str, size=(32, 32), mode="RGB") -> bytes:
    buffer = BytesIO()
    Image.new(mode, size, "white").save(buffer, format=format)
    return buffer.getvalue()


def upload(client, content: bytes, filename="sign.png", content_type="image/png"):
    return client.post("/analysis", files={"file": (filename, content, content_type)})


@pytest.mark.parametrize("format,content_type", [("PNG", "image/png"), ("JPEG", "image/jpeg")])
def test_supported_image_returns_analysis_result(client, format, content_type):
    response = upload(client, image_bytes(format), f"sign.{format.lower()}", content_type)
    assert response.status_code == 200
    result = AnalysisResult.model_validate(response.json())
    assert (result.width, result.height, result.trained) == (32, 32, False)


@pytest.mark.parametrize("mode", ["L", "RGBA", "P"])
def test_non_rgb_images_are_converted_before_analysis(client, mode):
    assert upload(client, image_bytes("PNG", mode=mode)).status_code == 200


@pytest.mark.parametrize("content", [b"", b"not an image", image_bytes("PNG")[:40]])
def test_unreadable_upload_is_rejected_with_422(client, content):
    response = upload(client, content)
    assert response.status_code == 422
    assert response.json() == {"detail": "Something went wrong with the image analysis"}


def test_missing_file_field_is_rejected(client):
    response = client.post("/analysis", data={"other": "value"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "file"]


def test_upload_does_not_touch_the_database(client, monkeypatch):
    monkeypatch.setattr("mysql.connector.connect", lambda **_: pytest.fail("analysis must not use MySQL"))
    assert upload(client, image_bytes("PNG")).status_code == 200


@pytest.mark.xfail(reason="Known bug #27: DecompressionBombError is not caught and becomes a 500")
def test_decompression_bomb_is_rejected_not_a_server_error(client, monkeypatch):
    # Pillow raises DecompressionBombError above 2 x MAX_IMAGE_PIXELS. Lowering the
    # limit gives the same error as a real bomb without building a huge file.
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    response = upload(client, image_bytes("PNG", size=(20, 20)))
    assert response.status_code in {413, 422}
