"""Upload edge cases for POST /analysis. The size limit, oversized uploads and a
missing model are covered in test_analysis.py.

Uploading needs a logged-in user (with a CSRF token) since the history feature
(#65), and each result is saved to that user's history. Most tests stand in a
user and mock the save; the login itself is tested at the end."""

from datetime import datetime, timezone
import struct
import zlib
from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.auth import require_csrf
from backend.app.main import app
from backend.app.model.analysis import AnalysisMetadata, AnalysisResult
from backend.app.model.user import UserPublic

DEV = UserPublic(id=1, email="dev@ase3.com", username="dev")


@pytest.fixture(autouse=True)
def no_trained_detector(monkeypatch, tmp_path):
    # Use the generic baseline even where trained weights exist locally.
    monkeypatch.setattr("backend.app.tablet_demo.SIGN_WEIGHTS", tmp_path / "missing-signs.pt")
    monkeypatch.setattr("backend.app.tablet_demo.CLASSIFIER_WEIGHTS", tmp_path / "missing-classifier.pt")


def saved(user_id, filename, image_format, size_bytes, result):
    return AnalysisMetadata(id=1, created_at=datetime.now(timezone.utc), filename=filename,
                            format=image_format, size_bytes=size_bytes)


@pytest.fixture
def client():
    # A logged-in user whose history save is mocked. Report server errors as 500
    # responses, as a browser would see them.
    app.dependency_overrides[require_csrf] = lambda: DEV
    try:
        with patch("backend.app.data_controller.analysis_data_controller.AnalysisDataController.save_analysis",
                   side_effect=saved), TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        app.dependency_overrides.pop(require_csrf, None)


@pytest.fixture
def anonymous():
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


@pytest.mark.parametrize("content,detail", [
    (b"", "Only PNG or JPEG images are supported."),
    (b"not an image", "Only PNG or JPEG images are supported."),
    (image_bytes("PNG")[:40], "Invalid image."),  # a PNG cut off after its header
])
def test_unreadable_upload_is_rejected_with_422(client, content, detail):
    response = upload(client, content)
    assert response.status_code == 422
    assert response.json() == {"detail": detail}


def test_missing_file_field_is_rejected(client):
    response = client.post("/analysis", data={"other": "value"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "file"]


def test_reading_an_upload_needs_no_database_besides_the_history_save(client, monkeypatch):
    monkeypatch.setattr("mysql.connector.connect", lambda **_: pytest.fail("reading must not use MySQL"))
    assert upload(client, image_bytes("PNG")).status_code == 200


def test_decompression_bomb_is_rejected_not_a_server_error(client, monkeypatch):
    # Pillow raises DecompressionBombError above 2 x MAX_IMAGE_PIXELS. Lowering the
    # limit gives the same error as a real bomb without building a huge file.
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    response = upload(client, image_bytes("PNG", size=(20, 20)))
    assert response.status_code == 422
    assert response.json() == {"detail": "The image dimensions are too large."}


@pytest.mark.filterwarnings("ignore::PIL.Image.DecompressionBombWarning")
def test_image_between_one_and_two_pixel_limits_is_rejected_before_decoding(client, monkeypatch):
    # Pillow only warns here and would decode the whole image.
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 300)
    response = upload(client, image_bytes("PNG", size=(20, 20)))
    assert response.status_code == 422
    assert response.json() == {"detail": "The image dimensions are too large."}


def test_tiny_file_declaring_huge_dimensions_is_rejected(client):
    content = bytearray(image_bytes("PNG", size=(1, 1)))
    header = struct.pack(">II", 20_000, 20_000) + content[24:29]
    content[16:29] = header
    content[29:33] = struct.pack(">I", zlib.crc32(b"IHDR" + header))
    response = upload(client, bytes(content))
    assert response.status_code == 422
    # The route's 40-megapixel check (#65) catches 400 megapixels before the reader's own check (#64).
    assert response.json() == {"detail": "The image exceeds the 40 megapixel limit."}


def test_upload_without_login_is_refused(anonymous, monkeypatch):
    monkeypatch.setattr("mysql.connector.connect", lambda **_: pytest.fail("no session to look up"))
    response = upload(anonymous, image_bytes("PNG"))
    assert response.status_code == 401
    assert response.json() == {"detail": "Please log in."}


def test_upload_without_the_csrf_token_is_refused(anonymous):
    anonymous.cookies.set("ase_session", "t" * 43)
    with patch("backend.app.auth.UserDataController.get_session_user", return_value=DEV):
        response = upload(anonymous, image_bytes("PNG"))
    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid CSRF token."}


def test_a_failed_history_save_is_a_503_not_a_lost_result(client):
    from mysql.connector import Error as DatabaseError

    with patch("backend.app.data_controller.analysis_data_controller.AnalysisDataController.save_analysis",
               side_effect=DatabaseError("down")):
        response = upload(client, image_bytes("PNG"))
    assert response.status_code == 503
    assert response.json() == {"detail": "The analysis could not be saved. Please try again."}
