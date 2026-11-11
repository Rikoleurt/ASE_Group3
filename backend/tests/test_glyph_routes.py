"""Glyph routes without a database or the dataset: synthetic corpus, mocked MySQL driver."""
from io import BytesIO
from unittest.mock import MagicMock

import numpy as np
import pytest
from fastapi.testclient import TestClient
from mysql.connector import Error as DatabaseError
from PIL import Image

from backend.app import glyph_index
from backend.app.auth import COOKIE_NAME, csrf_token, token_hash
from backend.app.data_controller.user_data_controller import UserDataController
from backend.app.main import app
from backend.app.model.user import UserPublic
from backend.app.routes import glyph_routes
from la import glyphembed
from backend.tests.glyph_fixtures import index as fixture_index

TOKEN = "a" * 43


@pytest.fixture
def connection(monkeypatch):
    connection = MagicMock()
    monkeypatch.setattr("backend.app.data_controller.data_controller.mysql.connector.connect",
                        MagicMock(return_value=connection))
    return connection


@pytest.fixture
def client(connection, monkeypatch):
    monkeypatch.setattr(UserDataController, "get_session_user", lambda self, digest:
                        UserPublic(id=7, email="owner@ase3.com", username="owner") if digest == token_hash(TOKEN) else None)
    app.dependency_overrides[glyph_routes.get_index] = fixture_index
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def login(client):
    client.cookies.set(COOKIE_NAME, TOKEN)
    client.headers["X-CSRF-Token"] = csrf_token(TOKEN)


def test_occurrences_page_with_default_order_and_paging(client):
    body = client.get("/glyphs/AB77/occurrences", params={"limit": 3}).json()
    assert body["total"] == 7 and body["ranked_by"] == "centre" and len(body["items"]) == 3
    first = body["items"][0]
    assert first["sign"] == "AB77" and first["similarity"] > 0.9 and first["outlier"] is False
    assert body["credit"]["licence"] == "CC BY-NC-SA 4.0"
    rest = client.get("/glyphs/AB77/occurrences", params={"limit": 3, "offset": 6}).json()
    assert len(rest["items"]) == 1
    flagged = client.get("/glyphs/AB77/occurrences", params={"limit": 100}).json()["items"]
    assert [i["position"] for i in flagged if i["outlier"]] == [11]


def test_item_links_and_boxes(client):
    item = next(i for i in client.get("/glyphs/AB77/occurrences", params={"limit": 100}).json()["items"]
                if i["tablet"] == "HT-1")
    assert item["crop_url"] == "/tablets/HT-1/signs/1.png"
    assert item["thumbnail_url"] == "/tablets/HT-1/thumbnail.png?position=1"
    assert item["box"] == {"x": 0.1, "y": 0.1, "w": 0.1, "h": 0.2}
    no_crop = next(i for i in client.get("/glyphs/AB77/occurrences", params={"limit": 100}).json()["items"]
                   if (i["tablet"], i["position"]) == ("HT-2", 4))
    assert no_crop["crop_url"] is None and no_crop["box"] is None and no_crop["similarity"] is None


def test_reference_glyph_orders_by_similarity(client):
    body = client.get("/glyphs/AB77/occurrences",
                      params={"ref_tablet": "KN-Zb-5", "ref_position": 11, "limit": 100}).json()
    assert body["ranked_by"] == "glyph"
    assert body["items"][0]["position"] == 11 and body["items"][0]["similarity"] == 1.0
    assert client.get("/glyphs/AB77/occurrences", params={"ref_tablet": "HT-1"}).status_code == 422
    assert client.get("/glyphs/AB77/occurrences", params={"ref_tablet": "HT-9", "ref_position": 1}).status_code == 404


@pytest.mark.parametrize("path", [
    "/glyphs/NOPE9/occurrences", "/glyphs/AB77%2F..%2Fx/occurrences", "/glyphs/AB-77/occurrences",
    "/glyphs/ABCDEFGHIJKLM/occurrences", "/glyphs/AB77/occurrences?limit=0", "/glyphs/AB77/occurrences?limit=101",
    "/glyphs/AB77/occurrences?offset=-1", "/glyphs/AB77/occurrences?ref_tablet=../x&ref_position=1",
])
def test_bad_input_is_rejected(client, path):
    assert client.get(path).status_code in (404, 422)


def test_missing_corpus_is_503_with_a_message(monkeypatch):
    def missing():
        raise glyph_index.CorpusMissing("The cached lineara.eu corpus is not installed on this server.")

    monkeypatch.setattr(glyph_index, "get_index", missing)
    with TestClient(app) as client:
        response = client.get("/glyphs/AB77/occurrences")
    assert response.status_code == 503 and "corpus" in response.json()["detail"]


def png(size=(30, 40)) -> bytes:
    stream = BytesIO()
    image = Image.new("RGB", size, "white")
    image.paste((0, 0, 0), (5, 5, 25, 20))
    image.save(stream, "PNG")
    return stream.getvalue()


def test_search_by_uploaded_crop(client, monkeypatch):
    login(client)
    monkeypatch.setattr(glyph_index, "embed_crop", lambda data: np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32))
    response = client.post("/glyphs/AB77/occurrences/search", files={"file": ("c.png", png())}, data={"limit": "2"})
    assert response.status_code == 200
    body = response.json()
    assert body["ranked_by"] == "glyph" and body["items"][0]["position"] == 11 and len(body["items"]) == 2


def test_search_needs_a_session_and_never_embeds_without_one(client, monkeypatch):
    embed = MagicMock()
    monkeypatch.setattr(glyph_index, "embed_crop", embed)
    files = {"file": ("c.png", png())}
    assert client.post("/glyphs/AB77/occurrences/search", files=files).status_code == 401
    client.cookies.set(COOKIE_NAME, TOKEN)  # session but no CSRF token
    assert client.post("/glyphs/AB77/occurrences/search", files=files).status_code == 403
    embed.assert_not_called()


def test_search_rejects_big_and_bad_uploads(client, monkeypatch):
    login(client)
    monkeypatch.setattr(glyph_index, "embed_crop", MagicMock(side_effect=glyphembed.BadCrop("Invalid image.")))
    big = b"PNG" + b"0" * (2 * 1024 * 1024 + 100 * 1024)
    assert client.post("/glyphs/AB77/occurrences/search", files={"file": ("c.png", big)}).status_code == 413
    assert client.post("/glyphs/AB77/occurrences/search", files={"file": ("c.png", b"junk")}).status_code == 422
    assert client.post("/glyphs/ZZ99/occurrences/search", files={"file": ("c.png", png())}).status_code == 404


def targets(*pairs):
    return [{"tablet": t, "position": p} for t, p in pairs]


def test_comment_requires_login_and_csrf(client, connection):
    payload = {"body": "same stroke", "targets": targets(("HT-1", 1))}
    assert client.post("/glyphs/AB77/annotations", json=payload).status_code == 401
    client.cookies.set(COOKIE_NAME, TOKEN)
    assert client.post("/glyphs/AB77/annotations", json=payload).status_code == 403
    assert client.post("/glyphs/AB77/annotations", json=payload,
                       headers={"X-CSRF-Token": csrf_token("other")}).status_code == 403
    assert client.delete("/glyphs/annotations/1").status_code == 403
    connection.cursor.assert_not_called()


def test_comment_is_saved_once_against_every_target(client, connection):
    login(client)
    cursor = connection.cursor.return_value
    cursor.lastrowid = 41
    response = client.post("/glyphs/AB77/annotations", json={
        "body": "  rounder than usual \n", "targets": targets(("HT-1", 1), ("HT-2", 1), ("KN-Zb-5", 11))})
    assert response.status_code == 201
    saved = response.json()
    assert saved["id"] == 41 and saved["body"] == "rounder than usual" and saved["author"] == {"id": 7, "username": "owner"}
    assert saved["created_at"].endswith("Z") or saved["created_at"].endswith("+00:00")
    insert = cursor.execute.call_args_list[0].args
    assert insert[0].startswith("INSERT INTO glyph_annotation ") and insert[1][:3] == (7, "AB77", "rounder than usual")
    rows = cursor.executemany.call_args.args[1]
    assert rows == [(41, "HT-1", 1), (41, "HT-2", 1), (41, "KN-Zb-5", 11)]
    connection.commit.assert_called_once()


@pytest.mark.parametrize("payload", [
    {"body": "", "targets": targets(("HT-1", 1))},
    {"body": "   ", "targets": targets(("HT-1", 1))},
    {"body": "x" * 2001, "targets": targets(("HT-1", 1))},
    {"body": "bell\x07", "targets": targets(("HT-1", 1))},
    {"body": "ok", "targets": []},
    {"body": "ok", "targets": targets(("HT-1", 1), ("HT-1", 1))},
    {"body": "ok", "targets": targets(("HT-1", -1))},
    {"body": "ok", "targets": targets(("../x", 1))},
    {"body": "ok", "targets": targets(*[("HT-1", n) for n in range(201)])},
    {"targets": targets(("HT-1", 1))},
])
def test_invalid_comments_are_rejected(client, connection, payload):
    login(client)
    assert client.post("/glyphs/AB77/annotations", json=payload).status_code == 422
    connection.cursor.assert_not_called()


def test_every_target_must_really_be_that_sign(client, connection):
    login(client)
    other_sign = client.post("/glyphs/AB77/annotations", json={"body": "x", "targets": targets(("HT-1", 1), ("HT-1", 2))})
    unknown = client.post("/glyphs/AB77/annotations", json={"body": "x", "targets": targets(("HT-1", 1), ("NOPE-1", 1))})
    assert other_sign.status_code == 422 and "HT-1#2" in other_sign.json()["detail"]
    assert unknown.status_code == 422
    connection.cursor.assert_not_called()


def test_comment_save_failure_is_503(client, connection):
    login(client)
    connection.cursor.side_effect = DatabaseError("down")
    response = client.post("/glyphs/AB77/annotations", json={"body": "x", "targets": targets(("HT-1", 1))})
    assert response.status_code == 503


def test_list_comments_with_targets_and_paging(client, connection):
    from datetime import datetime

    cursor = connection.cursor.return_value
    cursor.fetchall.side_effect = [
        [{"id": 9, "sign_id": "AB77", "body": "b", "created_at": datetime(2026, 11, 1, 12), "author_id": 7, "username": "owner"},
         {"id": 8, "sign_id": "AB77", "body": "a", "created_at": datetime(2026, 11, 1, 11), "author_id": 8, "username": "other"}],
        [{"annotation_id": 9, "tablet_id": "HT-1", "position": 1}, {"annotation_id": 9, "tablet_id": "HT-2", "position": 1}],
    ]
    response = client.get("/glyphs/AB77/annotations", params={"limit": 1})
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    body = response.json()
    assert [a["id"] for a in body["items"]] == [9] and body["next_before"] == 9
    assert body["items"][0]["created_at"].startswith("2026-11-01T12:00:00")
    assert body["items"][0]["targets"] == targets(("HT-1", 1), ("HT-2", 1))
    assert cursor.execute.call_args_list[0].args[1] == ("AB77", 2)


def test_delete_is_for_the_author_only(client, connection):
    login(client)
    cursor = connection.cursor.return_value
    cursor.rowcount = 1
    assert client.delete("/glyphs/annotations/5").status_code == 204
    assert cursor.execute.call_args.args == ("DELETE FROM glyph_annotation WHERE id = %s AND author_id = %s", (5, 7))
    cursor.rowcount = 0  # someone else's comment, or none: indistinguishable
    assert client.delete("/glyphs/annotations/6").status_code == 404
    assert client.delete("/glyphs/annotations/0").status_code == 422


def test_thumbnail_highlights_the_box_and_validates_paths(client, tmp_path, monkeypatch):
    image = Image.new("RGBA", (1000, 500), (0, 0, 0, 0))  # strokes live in alpha, background transparent
    image.putpixel((10, 10), (0, 0, 0, 255))
    path = tmp_path / "tracing.png"
    image.save(path)
    monkeypatch.setattr(glyph_index, "tracing_path", lambda slug: path if slug == "HT-1" else None)
    glyph_routes._thumbnail.cache_clear()
    response = client.get("/tablets/HT-1/thumbnail.png", params={"position": 1, "width": 200})
    assert response.status_code == 200 and response.headers["content-type"] == "image/png"
    assert "max-age" in response.headers["cache-control"]
    thumb = Image.open(BytesIO(response.content)).convert("RGB")
    assert thumb.size == (200, 100)
    assert thumb.getpixel((199, 99)) == (255, 255, 255)  # transparent background composited on white
    assert thumb.getpixel((30, 9)) == (220, 38, 38)  # top edge of the box at y=0.1, x from 0.1
    plain = Image.open(BytesIO(client.get("/tablets/HT-1/thumbnail.png", params={"width": 200}).content)).convert("RGB")
    assert plain.getpixel((30, 9)) == (255, 255, 255)
    assert client.get("/tablets/HT-9/thumbnail.png").status_code == 404
    assert client.get("/tablets/HT-1/thumbnail.png", params={"width": 5000}).status_code == 422
    assert client.get("/tablets/..%2F..%2Fsecret/thumbnail.png").status_code in (404, 422)


def test_failed_target_insert_rolls_back_and_commits_nothing(client, connection):
    login(client)
    cursor = connection.cursor.return_value
    cursor.lastrowid = 3
    cursor.executemany.side_effect = DatabaseError("boom")
    response = client.post("/glyphs/AB77/annotations", json={"body": "x", "targets": targets(("HT-1", 1), ("HT-2", 1))})
    assert response.status_code == 503
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()
    connection.close.assert_called_once()


def test_index_is_built_once_under_a_lock_and_missing_corpus_is_not_cached(monkeypatch, tmp_path):
    from backend.app.glyph_index import CorpusMissing

    monkeypatch.setattr(glyph_index, "_index", None)
    monkeypatch.setattr(glyph_index.fetch, "CACHE_DIR", tmp_path / "absent")
    with pytest.raises(CorpusMissing):
        glyph_index.get_index()
    built = MagicMock(return_value=fixture_index())
    (tmp_path / "cache").mkdir()
    (tmp_path / "cache" / "HT-1.json").write_text("{}")
    monkeypatch.setattr(glyph_index.fetch, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(glyph_index.fetch, "load_cached", lambda: {"HT 1": {}})
    monkeypatch.setattr(glyph_index, "GlyphIndex", built)
    monkeypatch.setattr(glyph_index, "_load_embeddings", lambda path: None)
    first = glyph_index.get_index()
    assert glyph_index.get_index() is first
    built.assert_called_once()
    monkeypatch.setattr(glyph_index, "_index", None)


def test_characters_endpoint_maps_sign_ids_to_unicode(client):
    response = client.get("/glyphs/characters", params={"signs": "AB45,AB81,N800,AB45"})
    assert response.status_code == 200
    body = response.json()
    assert list(body) == ["AB45", "AB81", "N800"]  # duplicates collapse, order kept
    assert body["AB81"] == "\U00010642" and len(body["AB45"]) == 1
    assert body["N800"] is None  # Unicode has no character for it
    assert client.get("/glyphs/characters", params={"signs": "ZZ999"}).json() == {"ZZ999": None}


@pytest.mark.parametrize("signs", ["", "AB45,", "AB45,,AB47", "AB-45", "AB45;AB47", "ABCDEFGHIJKLM", "../x",
                                   ",".join(f"AB{n:02d}" for n in range(1, 22))])
def test_characters_endpoint_rejects_bad_or_too_many(client, signs):
    assert client.get("/glyphs/characters", params={"signs": signs}).status_code == 422


def test_characters_accepts_exactly_twenty(client):
    assert len(client.get("/glyphs/characters", params={"signs": ",".join(f"AB{n:02d}" for n in range(1, 21))}).json()) == 20


def test_occurrences_report_the_requested_signs_character(client):
    body = client.get("/glyphs/AB77/occurrences").json()
    assert body["glyph"] is not None and len(body["glyph"]) == 1
