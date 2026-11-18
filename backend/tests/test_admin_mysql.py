"""Real database round trip for the admin and reviewer roles (#80)."""
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.data_controller.user_data_controller import UserDataController
from backend.app.main import app

pytestmark = [pytest.mark.mysql, pytest.mark.skipif(os.getenv("RUN_MYSQL_TESTS") != "1", reason="Set RUN_MYSQL_TESTS=1")]


def test_admin_finds_users_and_changes_their_roles(monkeypatch):
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "0")
    monkeypatch.delenv("SIGN_REVIEWERS", raising=False)
    name = uuid4().hex
    controller = UserDataController()
    users = []
    clients = [TestClient(app, headers={"X-Requested-With": "ASE"}) for _ in range(2)]
    admin, member = clients
    payloads = [{"username": f"roles-{name}-{index}", "email": f"{name}-{index}@ase3.com", "password": "secret"}
                for index in range(2)]
    try:
        for client, payload in zip(clients, payloads):
            client.__enter__()
            registration = client.post("/users/register", json=payload)
            assert registration.status_code == 201
            users.append(registration.json()["id"])
        # New accounts have no roles; the first admin is made in SQL, as on a fresh deployment.
        controller.set_roles(users[0], True, None)
        for client, payload in zip(clients, payloads):
            login = client.post("/users/login", json=payload).json()
            client.headers["X-CSRF-Token"] = login["csrf_token"]
        assert (admin.get("/users/me").json()["admin"], member.get("/users/me").json()["admin"]) == (True, False)
        assert member.get("/admin/users").status_code == 403

        page = admin.get("/admin/users", params={"q": f"roles-{name}"}).json()
        assert page["total"] == 2
        assert [(user["username"], user["admin"], user["reviewer"]) for user in page["items"]] == [
            (f"roles-{name}-0", True, False), (f"roles-{name}-1", False, False)]
        # "_" in a search matches only an underscore, not any character.
        assert admin.get("/admin/users", params={"q": f"roles_{name}"}).json()["total"] == 0

        changed = admin.patch(f"/admin/users/{users[1]}", json={"reviewer": True})
        assert (changed.status_code, changed.json()["reviewer"], changed.json()["admin"]) == (200, True, False)
        assert member.get("/users/me").json()["reviewer"] is True
        assert admin.patch(f"/admin/users/{users[0]}", json={"admin": False}).status_code == 409
        assert admin.patch(f"/admin/users/{users[1]}", json={"admin": True}).json()["admin"] is True
        assert member.get("/admin/users").status_code == 200
    finally:
        for client in clients:
            client.__exit__(None, None, None)
        with controller.connection() as connection:
            cursor = connection.cursor()
            for identifier in users:
                cursor.execute("DELETE FROM `user` WHERE id = %s", (identifier,))
            cursor.close()
