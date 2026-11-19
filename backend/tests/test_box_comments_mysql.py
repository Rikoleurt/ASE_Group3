"""Real database round trip for comments on corrected copies (#86)."""
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.data_controller.analysis_data_controller import AnalysisDataController
from backend.app.data_controller.user_data_controller import UserDataController
from backend.app.main import app
from backend.tests.test_history import png, result

pytestmark = [pytest.mark.mysql, pytest.mark.skipif(os.getenv("RUN_MYSQL_TESTS") != "1", reason="Set RUN_MYSQL_TESTS=1")]


def test_comments_are_posted_listed_moderated_and_deleted_with_the_copy(monkeypatch):
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "0")
    monkeypatch.setattr(AnalysisDataController, "analyze", lambda *a, **kw: result())
    name = uuid4().hex[:12]
    controller = UserDataController()
    users = []
    clients = [TestClient(app, headers={"X-Requested-With": "ASE"}) for _ in range(2)]
    owner, viewer = clients
    try:
        for index, client in enumerate(clients):
            client.__enter__()
            payload = {"username": f"note{name}{index}", "email": f"note-{name}-{index}@ase3.com", "password": "secret"}
            users.append(client.post("/users/register", json=payload).json()["id"])
            client.headers["X-CSRF-Token"] = client.post("/users/login", json=payload).json()["csrf_token"]
        analysis_id = owner.post("/analysis", files={"file": ("tablet.png", png(), "image/png")}).json()["analysis_id"]
        copy = owner.post("/box-sets", json={"analysis_id": analysis_id}).json()
        path = f"/box-sets/{copy['id']}"
        (box,) = copy["boxes"]

        on_box = owner.post(f"{path}/comments", json={"box_id": box["id"], "body": "Is this ku?"})
        assert on_box.status_code == 201
        on_copy = owner.post(f"{path}/comments", json={"body": "Whole tablet is faint."}).json()
        owner.put(f"{path}/shares/{users[1]}", json={"permission": "view"})
        listed = viewer.get(f"{path}/comments").json()
        assert [(c["box_id"], c["can_delete"]) for c in listed] == [(box["id"], False), (None, False)]
        assert viewer.post(f"{path}/comments", json={"body": "Me too"}).status_code == 403
        assert [c["body"] for c in owner.get(f"{path}/comments", params={"box_id": box["id"]}).json()] == ["Is this ku?"]

        assert owner.delete(f"{path}/comments/{on_copy['id']}").status_code == 204
        assert len(owner.get(f"{path}/comments").json()) == 1
        assert owner.delete(path).status_code == 204
        with controller.connection() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM box_comment WHERE set_id = %s", (copy["id"],))
            assert cursor.fetchone()[0] == 0
            cursor.close()
    finally:
        for client in clients:
            client.__exit__(None, None, None)
        with controller.connection() as connection:
            cursor = connection.cursor()
            for identifier in users:
                cursor.execute("DELETE FROM `user` WHERE id = %s", (identifier,))
            cursor.close()
