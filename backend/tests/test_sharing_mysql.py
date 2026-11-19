"""Real database round trip for sharing (#84): share, levels, everyone, leave, revoke."""
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.data_controller.analysis_data_controller import AnalysisDataController
from backend.app.data_controller.user_data_controller import UserDataController
from backend.app.main import app
from backend.tests.test_history import png, result

pytestmark = [pytest.mark.mysql, pytest.mark.skipif(os.getenv("RUN_MYSQL_TESTS") != "1", reason="Set RUN_MYSQL_TESTS=1")]


def test_a_copy_is_shared_edited_by_others_and_revoked(monkeypatch):
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "0")
    monkeypatch.setattr(AnalysisDataController, "analyze", lambda *a, **kw: result())
    name = uuid4().hex[:12]
    controller = UserDataController()
    users = []
    clients = [TestClient(app, headers={"X-Requested-With": "ASE"}) for _ in range(3)]
    owner, editor, stranger = clients
    try:
        for index, client in enumerate(clients):
            client.__enter__()
            payload = {"username": f"share{name}{index}", "email": f"share-{name}-{index}@ase3.com", "password": "secret"}
            users.append(client.post("/users/register", json=payload).json()["id"])
            client.headers["X-CSRF-Token"] = client.post("/users/login", json=payload).json()["csrf_token"]
        analysis_id = owner.post("/analysis", files={"file": ("tablet.png", png(), "image/png")}).json()["analysis_id"]
        copy = owner.post("/box-sets", json={"analysis_id": analysis_id}).json()
        path = f"/box-sets/{copy['id']}"
        (box,) = copy["boxes"]

        found = owner.get("/users/search", params={"q": f"share{name}"}).json()
        assert [user["id"] for user in found] == users[1:]  # not yourself
        assert stranger.get(path).status_code == 404

        assert owner.put(f"{path}/shares/{users[1]}", json={"permission": "edit"}).status_code == 200
        assert editor.get(path).json()["permission"] == "edit"
        saved = editor.patch(path, json={"version": 0, "changes": [{"op": "update", "box_id": box["id"], "sign": "AB02"}]})
        assert saved.status_code == 200
        assert owner.get(f"{path}/changes").json()["items"][0]["author"]["id"] == users[1]
        assert editor.delete(path).status_code == 403
        assert editor.get(f"{path}/shares").status_code == 403

        assert owner.put(f"{path}/everyone", json={"permission": "view"}).json()["everyone"] == "view"
        assert stranger.get(path).json()["permission"] == "view"
        assert [c["id"] for c in stranger.get("/users/me/shared-copies").json()] == [copy["id"]]
        assert stranger.patch(path, json={"version": 1, "changes": [{"op": "delete", "box_id": box["id"]}]}).status_code == 403

        assert owner.put(f"{path}/shares/999999999", json={"permission": "view"}).status_code == 404
        assert owner.delete(f"{path}/shares/{users[1]}").status_code == 204
        assert editor.get(path).json()["permission"] == "view"  # still everyone's view
        assert owner.put(f"{path}/everyone", json={"permission": "none"}).status_code == 200
        assert editor.get(path).status_code == 404
        assert editor.get(f"{path}/image").status_code == 404
    finally:
        for client in clients:
            client.__exit__(None, None, None)
        with controller.connection() as connection:
            cursor = connection.cursor()
            for identifier in users:
                cursor.execute("DELETE FROM `user` WHERE id = %s", (identifier,))
            cursor.close()
