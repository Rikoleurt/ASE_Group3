"""Run with RUN_MYSQL_TESTS=1 against a database initialized with init.sql."""

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.data_controller.user_data_controller import UserDataController, verify_password
from backend.app.main import app


pytestmark = [
    pytest.mark.mysql,
    pytest.mark.skipif(os.getenv("RUN_MYSQL_TESTS") != "1", reason="Set RUN_MYSQL_TESTS=1 to use MySQL"),
]


def test_mysql_registration_login_uniqueness_and_seed():
    controller = UserDataController()
    email = f"test-{uuid4().hex}@ase3.com"
    try:
        with TestClient(app) as client:
            seed = client.post("/users/login", json={"email": "dev@ase3.com", "password": "dev"})
            assert seed.status_code == 200
            assert "password" not in seed.json()["user"]

            payload = {"email": email, "username": f"test-{uuid4().hex}", "password": "integration-secret"}
            registered = client.post("/users/register", json=payload)
            assert registered.status_code == 201
            user = controller.get_by_email(email)
            assert user.id == registered.json()["id"]
            assert user.username == registered.json()["username"] == payload["username"]
            for field in ("email", "username"):
                profile_field = client.get(f"/users/{user.id}/{field}")
                assert profile_field.status_code == 200
                assert profile_field.json() == {field: payload[field]}
            assert user.password != payload["password"]
            assert verify_password(payload["password"], user.password)
            assert "password" not in registered.json()

            duplicate = client.post("/users/register", json={**payload, "email": email.upper()})
            assert duplicate.status_code == 409
            login_payload = {"email": email, "password": payload["password"]}
            logged_in = client.post("/users/login", json=login_payload)
            assert logged_in.status_code == 200
            assert logged_in.json()["user"] == registered.json()
            username_login = client.post("/users/login", json={
                "username": payload["username"], "password": payload["password"],
            })
            assert username_login.status_code == 200
            assert username_login.json()["user"] == registered.json()
            assert client.post("/users/login", json={**payload, "password": "wrong"}).status_code == 401
    finally:
        # Delete only the account created by this test, even if an assertion fails.
        with controller.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute("DELETE FROM `user` WHERE email = %s", (email,))
            finally:
                cursor.close()
