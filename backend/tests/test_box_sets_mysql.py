"""Real database round trip for corrected copies (#83): make, edit, conflict, log, undo, delete."""
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.data_controller.analysis_data_controller import AnalysisDataController
from backend.app.data_controller.user_data_controller import UserDataController
from backend.app.main import app
from backend.tests.test_history import png, result

pytestmark = [pytest.mark.mysql, pytest.mark.skipif(os.getenv("RUN_MYSQL_TESTS") != "1", reason="Set RUN_MYSQL_TESTS=1")]


def test_a_copy_is_made_edited_logged_undone_and_deleted(monkeypatch):
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "0")
    monkeypatch.setattr(AnalysisDataController, "analyze", lambda *a, **kw: result())
    name = uuid4().hex
    controller = UserDataController()
    users = []
    clients = [TestClient(app, headers={"X-Requested-With": "ASE"}) for _ in range(2)]
    owner, other = clients
    try:
        for index, client in enumerate(clients):
            client.__enter__()
            payload = {"username": f"boxes-{name}-{index}", "email": f"box-{name}-{index}@ase3.com", "password": "secret"}
            users.append(client.post("/users/register", json=payload).json()["id"])
            client.headers["X-CSRF-Token"] = client.post("/users/login", json=payload).json()["csrf_token"]
        analysis_id = owner.post("/analysis", files={"file": ("tablet.png", png(), "image/png")}).json()["analysis_id"]

        made = owner.post("/box-sets", json={"analysis_id": analysis_id})
        assert made.status_code == 201
        copy = made.json()
        assert owner.post("/box-sets", json={"analysis_id": analysis_id}).status_code == 200
        (model_box,) = copy["boxes"]
        assert (model_box["sign"], model_box["origin"], model_box["changed"]) == ("AB81", "model", False)
        path = f"/box-sets/{copy['id']}"

        saved = owner.patch(path, json={"version": 0, "changes": [
            {"op": "update", "box_id": model_box["id"], "sign": "AB02", "box": {"x": 0.1, "y": 0.1, "w": 0.5, "h": 0.5}},
            {"op": "add", "box": {"x": 0.6, "y": 0.6, "w": 0.2, "h": 0.2}, "sign": "A707"},
        ]})
        assert saved.status_code == 200
        body = saved.json()
        assert body["version"] == 1 and len(body["boxes"]) == 2
        assert {(b["sign"], b["origin"], b["changed"]) for b in body["boxes"]} == {("AB02", "model", True), ("A707", "user", True)}

        stale = owner.patch(path, json={"version": 0, "changes": [{"op": "delete", "box_id": model_box["id"]}]})
        assert (stale.status_code, stale.json()["current"]["version"]) == (409, 1)

        changes = owner.get(f"{path}/changes").json()["items"]
        assert [c["action"] for c in changes] == ["add", "update"]
        assert changes[1]["before"]["sign"] == "AB81" and changes[1]["after"]["sign"] == "AB02"
        undone = owner.post(f"{path}/changes/{changes[1]['id']}/revert", json={"version": 1}).json()
        restored = next(b for b in undone["boxes"] if b["id"] == model_box["id"])
        assert (restored["sign"], restored["box"]["w"], restored["changed"]) == ("AB81", 1.0, False)

        image = owner.get(f"{path}/image")
        assert (image.status_code, image.content) == (200, png())
        assert other.get(path).status_code == 404
        assert other.patch(path, json={"version": 2, "changes": [{"op": "delete", "box_id": model_box["id"]}]}).status_code == 404

        assert owner.delete(path).status_code == 204
        assert owner.get(path).status_code == 404
        assert owner.get(f"/users/me/analyses/{analysis_id}").status_code == 200  # the analysis stays
    finally:
        for client in clients:
            client.__exit__(None, None, None)
        with controller.connection() as connection:
            cursor = connection.cursor()
            for identifier in users:
                cursor.execute("DELETE FROM `user` WHERE id = %s", (identifier,))
            cursor.close()
