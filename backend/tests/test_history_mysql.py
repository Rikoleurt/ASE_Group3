"""Real database round trip: login, upload, persistence, ownership, expiry and logout."""
import os
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.auth import COOKIE_NAME, token_hash
from backend.app.data_controller.analysis_data_controller import AnalysisDataController
from backend.app.data_controller.user_data_controller import UserDataController
from backend.app.main import app
from backend.tests.test_history import png, result

pytestmark = [pytest.mark.mysql, pytest.mark.skipif(os.getenv("RUN_MYSQL_TESTS") != "1", reason="Set RUN_MYSQL_TESTS=1")]


def test_history_survives_new_session_and_is_private(monkeypatch):
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "1")
    monkeypatch.setattr(AnalysisDataController, "analyze", lambda *a, **kw: result())
    controller = UserDataController()
    users = []
    name = uuid4().hex
    try:
        with TestClient(app, base_url="https://testserver", headers={"X-Requested-With": "ASE"}) as owner, TestClient(app, base_url="https://testserver", headers={"X-Requested-With": "ASE"}) as other:
            for index, client in enumerate((owner, other)):
                payload = {"username": f"history-{name}-{index}", "email": f"{name}-{index}@ase3.com", "password": "secret"}
                registration = client.post("/users/register", json=payload)
                assert registration.status_code == 201
                users.append(registration.json()["id"])
                login = client.post("/users/login", json=payload)
                assert login.status_code == 200
                assert "Secure" in login.headers["set-cookie"]
                assert "HttpOnly" in login.headers["set-cookie"]
                assert "SameSite=lax" in login.headers["set-cookie"]
                client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
            for _ in range(3):
                response = owner.post("/analysis", files={"file": ("tablet.png", png(), "image/png")})
                assert response.status_code == 200
            identifier = response.json()["analysis_id"]
            first = owner.get("/users/me/analyses?limit=2").json()
            assert len(first["items"]) == 2
            second = owner.get("/users/me/analyses", params={"limit": 2, "cursor": first["next_cursor"]}).json()
            assert len(second["items"]) == 1
            assert second["next_cursor"] is None
            assert len({item["id"] for item in first["items"] + second["items"]}) == 3
            saved = owner.get(f"/users/me/analyses/{identifier}")
            assert saved.status_code == 200
            assert saved.json()["result"]["symbol_interpretation"] == "ku"
            assert "crop" not in saved.json()["result"]["signs"][0]
            assert saved.json()["size_bytes"] == len(png())
            assert saved.json()["created_at"].endswith("Z")
            assert other.get("/users/me/analyses").json()["items"] == []
            assert other.get(f"/users/me/analyses/{identifier}").status_code == 404
            token = owner.cookies.get(COOKIE_NAME)
            with controller.connection() as connection:
                cursor = connection.cursor()
                cursor.execute("SELECT result_json FROM analysis WHERE id = %s", (identifier,))
                snapshot = cursor.fetchone()[0]
                assert "PRIVATE_PIXELS" not in snapshot and '"crop"' not in snapshot
                cursor.execute("SELECT token_hash FROM user_session WHERE user_id = %s", (users[0],))
                assert cursor.fetchone()[0] == token_hash(token)
                cursor.close()
            assert owner.post("/users/logout").status_code == 204
            owner.cookies.set(COOKIE_NAME, token)
            assert owner.get("/users/me/analyses").status_code == 401
            owner.cookies.clear()
            login = owner.post("/users/login", json={"username": f"history-{name}-0", "password": "secret"})
            assert login.status_code == 200
            assert owner.get(f"/users/me/analyses/{identifier}").json() == saved.json()
            token = owner.cookies.get(COOKIE_NAME)
            with controller.connection() as connection:
                cursor = connection.cursor()
                cursor.execute("UPDATE user_session SET expires_at = %s WHERE token_hash = %s", (datetime(2000, 1, 1), token_hash(token)))
                cursor.close()
            assert owner.get("/users/me/analyses").status_code == 401
    finally:
        with controller.connection() as connection:
            cursor = connection.cursor()
            for identifier in users:
                cursor.execute("DELETE FROM `user` WHERE id = %s", (identifier,))
            cursor.close()
