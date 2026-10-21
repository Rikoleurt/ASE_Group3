from io import BytesIO
from unittest.mock import patch
from fastapi.testclient import TestClient
from PIL import Image
from backend.app.main import app
from backend.app.routes.analysis_routes import MAX_FILESIZE


def _png() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def _post(content: bytes):
    with patch("mysql.connector.connect", side_effect=AssertionError("No DB for analysis")):
        with TestClient(app) as client:
            return client.post("/analysis", files={"file": ("sign.png", content, "image/png")})


def test_valid_image_is_analysed():
    response = _post(_png())

    assert response.status_code == 200
    assert response.json()["symbol_interpretation"]


def test_upload_at_the_size_limit_is_not_rejected_for_size():
    content = _png()
    response = _post(content + b"\0" * (MAX_FILESIZE - len(content)))

    assert response.status_code == 200


def test_upload_over_the_size_limit_is_rejected_instead_of_truncated():
    content = _png()
    response = _post(content + b"\0" * (MAX_FILESIZE + 1 - len(content)))

    assert response.status_code == 413
    assert response.json()["detail"] == "The image is larger than 10 MB."
