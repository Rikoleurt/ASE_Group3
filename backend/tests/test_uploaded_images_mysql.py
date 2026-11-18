"""Real database round trip for kept uploads (#81): save, list, fetch, and keep it private."""
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.data_controller.analysis_data_controller import AnalysisDataController
from backend.app.data_controller.user_data_controller import UserDataController
from backend.app.main import app
from backend.tests.test_history import png, result

pytestmark = [pytest.mark.mysql, pytest.mark.skipif(os.getenv("RUN_MYSQL_TESTS") != "1", reason="Set RUN_MYSQL_TESTS=1")]


def test_upload_is_kept_and_only_its_owner_can_fetch_it(monkeypatch, upload_dir):
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
            payload = {"username": f"images-{name}-{index}", "email": f"img-{name}-{index}@ase3.com", "password": "secret"}
            users.append(client.post("/users/register", json=payload).json()["id"])
            client.headers["X-CSRF-Token"] = client.post("/users/login", json=payload).json()["csrf_token"]

        analysis_id = owner.post("/analysis", files={"file": ("tablet.png", png(), "image/png")}).json()["analysis_id"]
        assert owner.get("/users/me/analyses").json()["items"][0]["has_image"] is True
        assert owner.get(f"/users/me/analyses/{analysis_id}").json()["has_image"] is True

        image = owner.get(f"/analysis/{analysis_id}/image")
        assert (image.status_code, image.content, image.headers["content-type"]) == (200, png(), "image/png")
        assert other.get(f"/analysis/{analysis_id}/image").status_code == 404
        assert len([path for path in upload_dir.rglob("*") if path.is_file()]) == 1
    finally:
        for client in clients:
            client.__exit__(None, None, None)
        with controller.connection() as connection:
            cursor = connection.cursor()
            for identifier in users:
                cursor.execute("DELETE FROM `user` WHERE id = %s", (identifier,))
            cursor.close()
