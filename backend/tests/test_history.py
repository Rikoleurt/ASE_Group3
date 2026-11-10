"""API authorization, CSRF and history regression tests without a running database."""
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from mysql.connector import Error as DatabaseError
from PIL import Image

from backend.app.auth import COOKIE_NAME, csrf_token, token_hash
from backend.app.data_controller.analysis_data_controller import AnalysisDataController
from backend.app.data_controller.user_data_controller import UserDataController
from backend.app.main import app
from backend.app.model.analysis import AnalysisMetadata, AnalysisResult, DetectedSign
from backend.app.model.user import UserPublic


def result():
    return AnalysisResult(symbol_interpretation="ku", confidence=80, time_taken=0.1,
                          summary="One sign", width=8, height=8, trained=True,
                          signs=[DetectedSign(id=1, sign="AB81", label="ku", reading="ku", role="syllabogram",
                                              confidence=80, detection_confidence=90,
                                              box={"x": 0, "y": 0, "w": 1, "h": 1}, candidates=[],
                                              crop="data:image/png;base64,PRIVATE_PIXELS")])


def png():
    stream = BytesIO()
    Image.new("RGB", (8, 8)).save(stream, "PNG")
    return stream.getvalue()


@pytest.fixture
def client(monkeypatch):
    token = "a" * 43
    monkeypatch.setattr(UserDataController, "get_session_user", lambda self, digest:
                        UserPublic(id=7, email="owner@ase3.com", username="owner") if digest == token_hash(token) else None)
    with TestClient(app) as client:
        client.cookies.set(COOKIE_NAME, token)
        client.headers["X-CSRF-Token"] = csrf_token(token)
        yield client


def test_authentication_is_required_before_inference(monkeypatch):
    analyze = MagicMock()
    monkeypatch.setattr(AnalysisDataController, "analyze", analyze)
    with TestClient(app) as client:
        for path in ("/users/me", "/users/me/analyses", "/users/me/analyses/1"):
            response = client.get(path)
            assert response.status_code == 401
            assert response.headers["cache-control"] == "no-store"
        assert client.post("/analysis", files={"file": ("a.png", png())}).status_code == 401
    analyze.assert_not_called()


def test_unknown_session_is_rejected(client):
    client.cookies.set(COOKIE_NAME, "b" * 43)
    assert client.get("/users/me/analyses").status_code == 401


def test_write_requires_csrf_bound_to_session(client, monkeypatch):
    analyze = MagicMock()
    monkeypatch.setattr(AnalysisDataController, "analyze", analyze)
    for token in ("", csrf_token("another-session")):
        response = client.post("/analysis", files={"file": ("a.png", png())}, headers={"X-CSRF-Token": token})
        assert response.status_code == 403
        assert client.post("/users/logout", headers={"X-CSRF-Token": token}).status_code == 403
    analyze.assert_not_called()


def test_login_requires_non_simple_header():
    with TestClient(app) as client:
        assert client.post("/users/login", json={"username": "dev", "password": "dev"}).status_code == 403


def test_save_uses_server_identity_and_actual_file_metadata(client, monkeypatch):
    monkeypatch.setattr(AnalysisDataController, "analyze", lambda *args, **kwargs: result())
    save = MagicMock(return_value=AnalysisMetadata(id=12, created_at=datetime.now(timezone.utc), filename="photo.jpg", format="PNG", size_bytes=len(png())))
    monkeypatch.setattr(AnalysisDataController, "save_analysis", save)
    response = client.post("/analysis", data={"user_id": "999"}, files={"file": ("../photo.jpg", png(), "image/jpeg")})
    assert response.status_code == 200
    assert response.json()["analysis_id"] == 12
    assert response.json()["created_at"].endswith("Z")
    assert save.call_args.args[:4] == (7, "photo.jpg", "PNG", len(png()))


def test_failed_save_is_not_reported_as_success(client, monkeypatch):
    monkeypatch.setattr(AnalysisDataController, "analyze", lambda *args, **kwargs: result())
    monkeypatch.setattr(AnalysisDataController, "save_analysis", MagicMock(side_effect=DatabaseError()))
    response = client.post("/analysis", files={"file": ("a.png", png())})
    assert response.status_code == 503
    assert "could not be saved" in response.json()["detail"]


@pytest.mark.parametrize("content", [b"not png", b"\x89PNG\r\n\x1a\ncorrupt", b"\xff\xd8\xffbroken"])
def test_invalid_images_never_create_history(client, monkeypatch, content):
    save = MagicMock()
    monkeypatch.setattr(AnalysisDataController, "save_analysis", save)
    assert client.post("/analysis", files={"file": ("a.png", content)}).status_code == 422
    save.assert_not_called()


def test_history_is_scoped_and_missing_or_foreign_analysis_is_404(client, monkeypatch):
    get = MagicMock(return_value=None)
    monkeypatch.setattr(AnalysisDataController, "get_analysis", get)
    assert client.get("/users/me/analyses/999").status_code == 404
    get.assert_called_once_with(7, 999)


def test_history_pagination_and_cursor_validation(client, monkeypatch):
    rows = [AnalysisMetadata(id=i, created_at=datetime(2026, 11, 10, tzinfo=timezone.utc), filename=f"{i}.png", format="PNG", size_bytes=80) for i in (3, 2, 1)]
    listing = MagicMock(return_value=rows)
    monkeypatch.setattr(AnalysisDataController, "list_analyses", listing)
    page = client.get("/users/me/analyses?limit=2").json()
    assert [row["id"] for row in page["items"]] == [3, 2]
    assert page["next_cursor"]
    listing.return_value = rows[-1:]
    response = client.get("/users/me/analyses", params={"limit": 2, "cursor": page["next_cursor"]})
    assert response.json()["next_cursor"] is None
    assert listing.call_args.args == (7, 2, (datetime(2026, 11, 10), 2))
    for params in ({"cursor": "invalid"}, {"limit": 0}, {"limit": 101}):
        assert client.get("/users/me/analyses", params=params).status_code == 422


def test_history_storage_failure(client, monkeypatch):
    monkeypatch.setattr(AnalysisDataController, "list_analyses", MagicMock(side_effect=DatabaseError()))
    assert client.get("/users/me/analyses").status_code == 503


def test_persisted_snapshot_excludes_pixels_and_is_parameterized(monkeypatch):
    connection = MagicMock()
    connection.cursor.return_value.lastrowid = 12
    monkeypatch.setattr("mysql.connector.connect", lambda **kwargs: connection)
    saved = AnalysisDataController().save_analysis(7, "'; DROP TABLE analysis; --.png", "PNG", 80, result())
    sql, params = connection.cursor.return_value.execute.call_args.args
    assert saved.id == 12
    assert "DROP TABLE" not in sql
    assert "PRIVATE_PIXELS" not in params[-1]
    assert '"crop"' not in params[-1]
    assert '"reading": "ku"' in params[-1]
    connection.commit.assert_called_once()


def test_sql_queries_always_filter_by_owner(monkeypatch):
    connection = MagicMock()
    connection.cursor.return_value.fetchone.return_value = None
    connection.cursor.return_value.fetchall.return_value = []
    monkeypatch.setattr("mysql.connector.connect", lambda **kwargs: connection)
    controller = AnalysisDataController()
    controller.get_analysis(7, 12)
    sql, params = connection.cursor.return_value.execute.call_args.args
    assert "WHERE user_id = %s AND id = %s" in sql
    assert params == (7, 12)
    controller.list_analyses(7, 20)
    sql, params = connection.cursor.return_value.execute.call_args.args
    assert "WHERE user_id = %s" in sql
    assert params == (7, 21)


def test_session_storage_failure_is_503(client, monkeypatch):
    monkeypatch.setattr(UserDataController, "get_session_user", MagicMock(side_effect=DatabaseError()))
    assert client.get("/users/me").status_code == 503


def test_openapi_documents_history_and_authentication():
    with TestClient(app) as client:
        schema = client.get('/openapi.json').json()
    for path, method in (("/users/me", "get"), ("/users/me/analyses", "get"),
                         ("/users/me/analyses/{analysis_id}", "get"), ("/analysis", "post"),
                         ("/users/logout", "post")):
        operation = schema['paths'][path][method]
        assert operation['security'] == [{'APIKeyCookie': []}]
        assert '401' in operation['responses'] and '503' in operation['responses']
    assert schema['components']['securitySchemes']['APIKeyCookie']['in'] == 'cookie'
    assert 'analysis_id' in schema['components']['schemas']['SavedAnalysisResult']['properties']
