"""Real database round trip for glyph comments: one comment, many targets, author-only delete, cascade.

Needs MySQL with backend/app/database/migration-53 applied (RUN_MYSQL_TESTS=1), like the other mysql tests.
"""
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.data_controller.user_data_controller import UserDataController
from backend.app.main import app
from backend.app.routes import glyph_routes
from backend.tests.glyph_fixtures import index as fixture_index

pytestmark = [pytest.mark.mysql, pytest.mark.skipif(os.getenv("RUN_MYSQL_TESTS") != "1", reason="Set RUN_MYSQL_TESTS=1")]


def test_comment_round_trip_ownership_and_cascade(monkeypatch):
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "1")
    app.dependency_overrides[glyph_routes.get_index] = fixture_index
    name = uuid4().hex
    users = []
    controller = UserDataController()
    try:
        with TestClient(app, base_url="https://testserver", headers={"X-Requested-With": "ASE"}) as author, \
                TestClient(app, base_url="https://testserver", headers={"X-Requested-With": "ASE"}) as other:
            for index, client in enumerate((author, other)):
                payload = {"username": f"glyph-{name}-{index}", "email": f"{name}-{index}@ase3.com", "password": "secret"}
                registration = client.post("/users/register", json=payload)
                assert registration.status_code == 201
                users.append(registration.json()["id"])
                login = client.post("/users/login", json=payload)
                assert login.status_code == 200
                client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
            targets = [{"tablet": "HT-1", "position": 1}, {"tablet": "HT-2", "position": 1}, {"tablet": "KN-Zb-5", "position": 3}]
            created = author.post("/glyphs/AB77/annotations", json={"body": "  same ductus  ", "targets": targets})
            assert created.status_code == 201
            identifier = created.json()["id"]
            listed = other.get("/glyphs/AB77/annotations").json()["items"]
            mine = next(item for item in listed if item["id"] == identifier)
            assert mine["body"] == "same ductus" and mine["author"]["id"] == users[0]
            assert mine["created_at"].endswith("Z") or mine["created_at"].endswith("+00:00")
            assert sorted((t["tablet"], t["position"]) for t in mine["targets"]) == [("HT-1", 1), ("HT-2", 1), ("KN-Zb-5", 3)]
            assert other.delete(f"/glyphs/annotations/{identifier}").status_code == 404
            assert any(item["id"] == identifier for item in author.get("/glyphs/AB77/annotations").json()["items"])
            assert author.delete(f"/glyphs/annotations/{identifier}").status_code == 204
            assert not any(item["id"] == identifier for item in author.get("/glyphs/AB77/annotations").json()["items"])
            with controller.connection() as connection:
                cursor = connection.cursor()
                cursor.execute("SELECT COUNT(*) FROM glyph_annotation_target WHERE annotation_id = %s", (identifier,))
                assert cursor.fetchone()[0] == 0  # ON DELETE CASCADE
                # Deleting a user removes their comments and, through them, the targets.
                again = author.post("/glyphs/AB77/annotations", json={"body": "x", "targets": targets[:1]}).json()["id"]
                cursor.execute("DELETE FROM `user` WHERE id = %s", (users[0],))
                cursor.execute("SELECT COUNT(*) FROM glyph_annotation WHERE id = %s", (again,))
                assert cursor.fetchone()[0] == 0
                cursor.execute("SELECT COUNT(*) FROM glyph_annotation_target WHERE annotation_id = %s", (again,))
                assert cursor.fetchone()[0] == 0
    finally:
        app.dependency_overrides.clear()
        with controller.connection() as connection:
            cursor = connection.cursor()
            for user_id in users:
                cursor.execute("DELETE FROM `user` WHERE id = %s", (user_id,))
