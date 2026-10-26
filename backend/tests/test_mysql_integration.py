"""Run with RUN_MYSQL_TESTS=1 against a database initialized with init.sql."""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
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
            assert duplicate.json()["detail"]["field"] == "email"
            login_payload = {"email": email, "password": payload["password"]}
            logged_in = client.post("/users/login", json=login_payload)
            assert logged_in.status_code == 200
            assert logged_in.json()["user"] == registered.json()
            username_login = client.post("/users/login", json={
                "username": f"  {payload['username'].upper()}  ", "password": payload["password"],
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


@pytest.mark.parametrize("variant", ["same", "uppercase", "whitespace"])
def test_mysql_duplicate_username_is_rejected(variant):
    controller = UserDataController()
    token = uuid4().hex
    username = f"Test-{token}"
    emails = [f"first-{token}@ase3.com", f"second-{token}@ase3.com"]
    duplicate_username = {
        "same": username,
        "uppercase": username.upper(),
        "whitespace": f"  {username}\t",
    }[variant]
    try:
        with TestClient(app) as client:
            first = client.post("/users/register", json={
                "email": emails[0], "username": username, "password": "first-secret",
            })
            assert first.status_code == 201
            second = client.post("/users/register", json={
                "email": emails[1], "username": duplicate_username, "password": "second-secret",
            })
            assert second.status_code == 409
            assert second.json() == {"detail": {"code": "duplicate_user", "field": "username"}}
            assert controller.get_by_email(emails[1]) is None
            login = client.post("/users/login", json={
                "username": username.lower(), "password": "first-secret",
            })
            assert login.status_code == 200
            assert login.json()["user"] == first.json()
            assert client.post("/users/login", json={
                "username": username, "password": "second-secret",
            }).status_code == 401
    finally:
        with controller.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute("DELETE FROM `user` WHERE email IN (%s, %s)", tuple(emails))
            finally:
                cursor.close()


def test_mysql_concurrent_registrations_cannot_share_username():
    controller = UserDataController()
    token = uuid4().hex
    emails = [f"race-a-{token}@ase3.com", f"race-b-{token}@ase3.com"]
    start = Barrier(2)
    try:
        with TestClient(app) as client:
            def register(email):
                start.wait(timeout=10)
                return client.post("/users/register", json={
                    "email": email, "username": f"race-{token}", "password": "secret",
                })

            with ThreadPoolExecutor(max_workers=2) as executor:
                responses = list(executor.map(register, emails))
            assert sorted(response.status_code for response in responses) == [201, 409]
            conflict = next(response for response in responses if response.status_code == 409)
            assert conflict.json()["detail"]["field"] == "username"
            assert sum(controller.get_by_email(email) is not None for email in emails) == 1
    finally:
        with controller.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute("DELETE FROM `user` WHERE email IN (%s, %s)", tuple(emails))
            finally:
                cursor.close()
