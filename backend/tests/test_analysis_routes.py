"""Upload edge cases for POST /analysis. The size limit, oversized uploads and a
missing model are covered in test_analysis.py."""

from io import BytesIO
from datetime import datetime, timezone
from unittest.mock import MagicMock
import struct
import zlib

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.auth import COOKIE_NAME, csrf_token, token_hash
from backend.app.data_controller.analysis_data_controller import AnalysisDataController
from backend.app.data_controller.user_data_controller import UserDataController
from backend.app.main import app
from backend.app.model.analysis import AnalysisMetadata, SavedAnalysisResult
from backend.app.model.user import UserPublic


@pytest.fixture(autouse=True)
def no_trained_detector(monkeypatch, tmp_path):
    # Use the generic baseline even where trained weights exist locally.
    monkeypatch.setattr("backend.app.tablet_demo.SIGN_WEIGHTS", tmp_path / "missing-signs.pt")
    monkeypatch.setattr("backend.app.tablet_demo.CLASSIFIER_WEIGHTS", tmp_path / "missing-classifier.pt")


@pytest.fixture
def save_analysis(monkeypatch):
    def save(user_id, filename, image_format, size_bytes, result, *, image_bytes):
        return AnalysisMetadata(id=12, created_at=datetime.now(timezone.utc),
                                filename=filename, format=image_format, size_bytes=size_bytes)

    save = MagicMock(side_effect=save)
    monkeypatch.setattr(AnalysisDataController, "save_analysis", save)
    return save


@pytest.fixture
def client(monkeypatch, save_analysis):
    token = "a" * 43
    monkeypatch.setattr(UserDataController, "get_session_user", lambda self, digest:
                        UserPublic(id=7, email="owner@ase3.com", username="owner")
                        if digest == token_hash(token) else None)
    # Report server errors as 500 responses, as a browser would see them.
    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set(COOKIE_NAME, token)
        client.headers["X-CSRF-Token"] = csrf_token(token)
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
    result = SavedAnalysisResult.model_validate(response.json())
    assert (result.width, result.height, result.trained) == (32, 32, False)
    assert result.analysis_id == 12


@pytest.mark.parametrize("mode", ["L", "RGBA", "P"])
def test_non_rgb_images_are_converted_before_analysis(client, mode):
    assert upload(client, image_bytes("PNG", mode=mode)).status_code == 200


@pytest.mark.parametrize("content,detail", [
    (b"", "Only PNG or JPEG images are supported."),
    (b"not an image", "Only PNG or JPEG images are supported."),
    (image_bytes("PNG")[:40], "Invalid image."),
])
def test_unreadable_upload_is_rejected_with_422(client, save_analysis, content, detail):
    response = upload(client, content)
    assert response.status_code == 422
    assert response.json() == {"detail": detail}
    save_analysis.assert_not_called()


def test_missing_file_field_is_rejected(client):
    response = client.post("/analysis", data={"other": "value"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "file"]


def test_upload_saves_the_analysis_for_the_authenticated_user(client, save_analysis):
    content = image_bytes("PNG")
    response = upload(client, content)
    assert response.status_code == 200
    save_analysis.assert_called_once()
    user_id, filename, image_format, size_bytes, result = save_analysis.call_args.args
    assert (user_id, filename, image_format, size_bytes) == (7, "sign.png", "PNG", len(content))
    assert response.json()["analysis_id"] == 12
    assert response.json()["symbol_interpretation"] == result.symbol_interpretation


@pytest.mark.parametrize("size", [(10_000, 5_000), (30_000, 30_000)])
def test_oversized_dimensions_are_rejected_before_decoding(client, save_analysis, size):
    # Declare dimensions above the application's 40 MP limit (and Pillow's bomb
    # limit in the second case) without allocating a huge image. Keep a valid
    # IHDR checksum so the request reaches the dimension check.
    content = bytearray(image_bytes("PNG"))
    content[16:24] = struct.pack(">II", *size)
    content[29:33] = struct.pack(">I", zlib.crc32(content[12:29]))
    response = upload(client, bytes(content))
    assert response.status_code == 422
    assert response.json() == {"detail": "The image exceeds the 40 megapixel limit."}
    save_analysis.assert_not_called()
