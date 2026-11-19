"""Real database round trip for sign corrections (#52): submit, keep conflicts, review, export."""
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.data_controller.analysis_data_controller import AnalysisDataController
from backend.app.data_controller.user_data_controller import UserDataController
from backend.app.main import app
from backend.tests.test_history import png, result

pytestmark = [pytest.mark.mysql, pytest.mark.skipif(os.getenv("RUN_MYSQL_TESTS") != "1", reason="Set RUN_MYSQL_TESTS=1")]


def test_corrections_are_kept_reviewed_and_exported(monkeypatch):
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "0")
    monkeypatch.setattr(AnalysisDataController, "analyze", lambda *a, **kw: result())
    name = uuid4().hex
    monkeypatch.setenv("SIGN_REVIEWERS", f"corrections-{name}-2")
    controller = UserDataController()
    users = []
    try:
        clients = [TestClient(app, headers={"X-Requested-With": "ASE"}) for _ in range(3)]
        owner, other, reviewer = clients
        for index, client in enumerate(clients):
            client.__enter__()
            payload = {"username": f"corrections-{name}-{index}", "email": f"{name}-{index}@ase3.com", "password": "secret"}
            registration = client.post("/users/register", json=payload)
            assert registration.status_code == 201
            users.append(registration.json()["id"])
            client.headers["X-CSRF-Token"] = client.post("/users/login", json=payload).json()["csrf_token"]

        analysis_id = owner.post("/analysis", files={"file": ("tablet.png", png(), "image/png")}).json()["analysis_id"]
        path = f"/analysis/{analysis_id}/corrections"
        first = owner.post(path, json={"sign_id": 1, "proposed_sign": "AB59"})
        assert first.status_code == 201
        assert (first.json()["original_sign"], first.json()["proposed_sign"]) == ("AB81", "AB59")
        # A second opinion on the same sign is kept, not overwritten.
        second = owner.post(path, json={"sign_id": 1, "proposed_sign": "AB02"})
        flag = owner.post(path, json={"sign_id": 1, "uncertain": True, "note": "worn"})
        assert second.status_code == flag.status_code == 201
        assert [item["id"] for item in owner.get(path).json()] == [first.json()["id"], second.json()["id"], flag.json()["id"]]

        assert other.post(path, json={"sign_id": 1, "uncertain": True}).status_code == 404
        assert other.get(path).json() == []
        assert owner.get("/corrections").status_code == 403
        # A reviewer's own correction waits for another reviewer.
        own_analysis = reviewer.post("/analysis", files={"file": ("own.png", png(), "image/png")}).json()["analysis_id"]
        own = reviewer.post(f"/analysis/{own_analysis}/corrections", json={"sign_id": 1, "proposed_sign": "AB02"})
        assert reviewer.post(f"/corrections/{own.json()['id']}/review", json={"decision": "approved"}).status_code == 403

        queued = {item["id"] for item in reviewer.get("/corrections?limit=200").json()}
        assert {first.json()["id"], second.json()["id"], flag.json()["id"]} <= queued
        assert reviewer.post(f"/corrections/{first.json()['id']}/review", json={"decision": "approved"}).status_code == 200
        assert reviewer.post(f"/corrections/{second.json()['id']}/review", json={"decision": "rejected"}).status_code == 200
        assert reviewer.post(f"/corrections/{flag.json()['id']}/review", json={"decision": "approved"}).status_code == 200
        assert reviewer.post(f"/corrections/{first.json()['id']}/review", json={"decision": "rejected"}).status_code == 409

        exported = [tablet for tablet in reviewer.get("/corrections/export").json() if tablet["analysis_id"] == analysis_id]
        assert [sign["sign"] for sign in exported[0]["signs"]] == ["AB59"]
        assert (exported[0]["width"], exported[0]["height"], exported[0]["signs"][0]["xyxy"]) == (8, 8, [0, 0, 8, 8])
        assert owner.get(f"/users/me/analyses/{analysis_id}").json()["result"]["signs"][0]["sign"] == "AB81"
    finally:
        for client in clients:
            client.__exit__(None, None, None)
        with controller.connection() as connection:
            cursor = connection.cursor()
            for identifier in users:
                cursor.execute("DELETE FROM `user` WHERE id = %s", (identifier,))
            cursor.close()
