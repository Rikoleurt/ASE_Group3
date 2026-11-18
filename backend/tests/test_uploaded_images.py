"""Kept uploads (#81): the file on disk, its database record, and who may fetch it."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from mysql.connector import Error as DatabaseError

from backend.app import image_store
from backend.app.auth import COOKIE_NAME, csrf_token, token_hash
from backend.app.data_controller.analysis_data_controller import AnalysisDataController
from backend.app.data_controller.user_data_controller import UserDataController
from backend.app.main import app
from backend.app.model.analysis import AnalysisMetadata
from backend.app.model.user import UserPublic
from backend.tests.test_history import client, png, result  # noqa: F401  (client is a fixture)


def saved(*args, image=None, **kwargs):
    return AnalysisMetadata(id=12, created_at=datetime.now(timezone.utc), filename="a.png", format="PNG",
                            size_bytes=len(png()), has_image=image is not None)


def files_in(folder):
    return sorted(path for path in folder.rglob("*") if path.is_file()) if folder.exists() else []


@pytest.fixture
def analyzed(monkeypatch):
    monkeypatch.setattr(AnalysisDataController, "analyze", lambda *args, **kwargs: result())


def test_store_writes_the_file_under_a_random_key(upload_dir):
    stored = image_store.save(png(), "PNG")
    path = upload_dir / stored.key[:2] / f"{stored.key}.png"
    assert path.read_bytes() == png()
    assert len(stored.key) == 32 and stored.size_bytes == len(png()) and len(stored.sha256) == 64
    assert image_store.find(stored.key, "PNG") == path
    assert image_store.save(png(), "PNG").key != stored.key
    image_store.delete(stored.key, "PNG")
    assert image_store.find(stored.key, "PNG") is None
    image_store.delete(stored.key, "PNG")  # deleting twice is fine


@pytest.mark.parametrize("key,image_format", [("../" + "a" * 29, "PNG"), ("A" * 32, "PNG"), ("a" * 32, "GIF"), ("", "PNG")])
def test_only_well_formed_keys_become_paths(key, image_format):
    with pytest.raises(ValueError):
        image_store.path_for(key, image_format)


def test_a_failed_write_leaves_no_partial_file(upload_dir, monkeypatch):
    def refuse(*args):
        raise OSError("disk full")
    monkeypatch.setattr(image_store.os, "replace", refuse)
    with pytest.raises(OSError):
        image_store.save(png(), "PNG")
    assert files_in(upload_dir) == []


def test_upload_keeps_the_image_with_the_analysis(client, analyzed, monkeypatch, upload_dir):
    save = MagicMock(side_effect=saved)
    monkeypatch.setattr(AnalysisDataController, "save_analysis", save)
    assert client.post("/analysis", files={"file": ("a.png", png(), "image/png")}).status_code == 200
    stored = save.call_args.kwargs["image"]
    assert (stored.format, stored.size_bytes) == ("PNG", len(png()))
    assert files_in(upload_dir) == [image_store.path_for(stored.key, "PNG")]


def test_a_failed_save_removes_the_file(client, analyzed, monkeypatch, upload_dir):
    monkeypatch.setattr(AnalysisDataController, "save_analysis", MagicMock(side_effect=DatabaseError()))
    assert client.post("/analysis", files={"file": ("a.png", png(), "image/png")}).status_code == 503
    assert files_in(upload_dir) == []


def test_an_unexpected_failure_also_removes_the_file(analyzed, monkeypatch, upload_dir):
    monkeypatch.setattr(AnalysisDataController, "save_analysis", MagicMock(side_effect=RuntimeError("bug")))
    token = "a" * 43
    monkeypatch.setattr(UserDataController, "get_session_user", lambda self, digest: UserPublic(
        id=7, email="owner@ase3.com", username="owner") if digest == token_hash(token) else None)
    with TestClient(app, raise_server_exceptions=False) as owner:
        owner.cookies.set(COOKIE_NAME, token)
        owner.headers["X-CSRF-Token"] = csrf_token(token)
        assert owner.post("/analysis", files={"file": ("a.png", png(), "image/png")}).status_code == 500
    assert files_in(upload_dir) == []


def test_a_full_disk_is_503_and_saves_nothing(client, analyzed, monkeypatch):
    save = MagicMock()
    monkeypatch.setattr(AnalysisDataController, "save_analysis", save)
    monkeypatch.setattr(image_store, "save", MagicMock(side_effect=OSError("disk full")))
    response = client.post("/analysis", files={"file": ("a.png", png(), "image/png")})
    assert (response.status_code, response.json()["detail"]) == (503, "The analysis could not be saved. Please try again.")
    save.assert_not_called()


def test_owner_gets_the_image_back_uncached(client, monkeypatch):
    stored = image_store.save(png(), "PNG")
    lookup = MagicMock(return_value=(stored.key, "PNG"))
    monkeypatch.setattr(AnalysisDataController, "stored_image", lookup)
    response = client.get("/analysis/12/image")
    assert response.status_code == 200
    assert response.content == png()
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    lookup.assert_called_once_with(7, 12)  # the server's identity, never one from the request


@pytest.mark.parametrize("found", [None, ("f" * 32, "JPEG")])
def test_missing_foreign_or_deleted_images_are_404(client, monkeypatch, found):
    monkeypatch.setattr(AnalysisDataController, "stored_image", MagicMock(return_value=found))
    response = client.get("/analysis/12/image")
    assert (response.status_code, response.json()["detail"]) == (404, "Image not found.")


def test_image_route_needs_a_login_and_a_valid_id(client, monkeypatch):
    monkeypatch.setattr(AnalysisDataController, "stored_image", MagicMock(side_effect=DatabaseError()))
    assert client.get("/analysis/12/image").status_code == 503
    assert client.get("/analysis/0/image").status_code == 422
    with TestClient(app) as anonymous:
        assert anonymous.get("/analysis/12/image").status_code == 401


def connection_for(monkeypatch, lastrowids=(5, 12)):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    ids = iter(lastrowids)
    type(cursor).lastrowid = property(lambda self: next(ids))
    monkeypatch.setattr("mysql.connector.connect", lambda **kwargs: connection)
    return connection, cursor


def test_image_record_and_analysis_are_one_transaction(monkeypatch):
    connection, cursor = connection_for(monkeypatch)
    stored = image_store.StoredImage("a" * 32, "b" * 64, "PNG", 80)
    meta = AnalysisDataController().save_analysis(7, "a.png", "PNG", 80, result(), image=stored)
    (image_sql, image_params), (analysis_sql, analysis_params) = [call.args for call in cursor.execute.call_args_list]
    assert image_sql.startswith("INSERT INTO uploaded_image")
    assert image_params[:7] == (7, "a" * 32, "b" * 64, "PNG", 80, 8, 8)
    assert analysis_sql.startswith("INSERT INTO analysis") and analysis_params[-1] == 5
    assert (meta.id, meta.has_image) == (12, True)
    connection.commit.assert_called_once()


def test_saving_without_an_image_links_none(monkeypatch):
    connection, cursor = connection_for(monkeypatch, lastrowids=(12,))
    meta = AnalysisDataController().save_analysis(7, "a.png", "PNG", 80, result())
    (sql, params), = [call.args for call in cursor.execute.call_args_list]
    assert sql.startswith("INSERT INTO analysis") and params[-1] is None
    assert meta.has_image is False


def test_image_lookup_is_scoped_to_the_owner(monkeypatch):
    connection, cursor = connection_for(monkeypatch)
    cursor.fetchone.return_value = {"storage_key": "a" * 32, "format": "PNG"}
    assert AnalysisDataController().stored_image(7, 12) == ("a" * 32, "PNG")
    sql, params = cursor.execute.call_args.args
    assert "WHERE a.user_id = %s AND a.id = %s" in sql and params == (7, 12)
    cursor.fetchone.return_value = None
    assert AnalysisDataController().stored_image(7, 12) is None


def test_history_says_whether_the_image_was_kept(monkeypatch):
    connection, cursor = connection_for(monkeypatch)
    stamp = datetime(2026, 11, 18, 9, 0)
    cursor.fetchall.return_value = [
        {"id": 2, "created_at": stamp, "filename": "b.png", "format": "PNG", "size_bytes": 1, "result_schema_version": 1, "has_image": 1},
        {"id": 1, "created_at": stamp, "filename": "a.png", "format": "PNG", "size_bytes": 1, "result_schema_version": 1, "has_image": 0},
    ]
    assert [item.has_image for item in AnalysisDataController().list_analyses(7, 20)] == [True, False]
