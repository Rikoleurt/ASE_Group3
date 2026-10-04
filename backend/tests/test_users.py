import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from mysql.connector.errorcode import ER_BAD_NULL_ERROR, ER_DUP_ENTRY
from mysql.connector.errors import IntegrityError

from backend.app.data_controller.data_controller import DataController
from backend.app.data_controller.user_data_controller import (
    UserDataController,
    hash_password,
    verify_password,
)
from backend.app.main import app
from backend.app.model.user import User
from backend.app.routes.user_routes import get_user_data_controller


@pytest.fixture
def connection(monkeypatch):
    connection = MagicMock()
    monkeypatch.setattr(
        "backend.app.data_controller.data_controller.mysql.connector.connect",
        MagicMock(return_value=connection),
    )
    return connection


@pytest.fixture
def client(connection):
    # Exercise routes, controllers, hashing and SQL; replace only the DB driver.
    with TestClient(app) as client:
        yield client


def test_password_hashes_are_salted():
    first = hash_password("dev")
    second = hash_password("dev")
    assert first != second
    assert first != "dev"
    assert verify_password("dev", first)
    assert verify_password("dev", second)
    assert not verify_password("wrong", first)


@pytest.mark.parametrize("stored", [
    "dev", "unknown$600000$00$00", "pbkdf2_sha256$invalid$00$00",
    "pbkdf2_sha256$0$00$00", "pbkdf2_sha256$-1$00$00",
    "pbkdf2_sha256$9999999999$00$00", "pbkdf2_sha256$600000$zz$zz",
    "pbkdf2_sha256$600000$00$00",
])
def test_invalid_password_hash_is_rejected(stored):
    assert not verify_password("dev", stored)


def test_development_seed_password():
    sql = (Path(__file__).parents[1] / "app/database/init.sql").read_text()
    stored = re.search(r"'(pbkdf2_sha256\$[^']+)'", sql).group(1)
    assert verify_password("dev", stored)
    assert not verify_password("incorrect", stored)


def test_mysql_configuration_uses_environment(monkeypatch):
    values = {
        "MYSQL_HOST": "db.example", "MYSQL_PORT": "3307",
        "MYSQL_USER": "test-user", "MYSQL_PASSWORD": "test-password",
        "MYSQL_DATABASE": "test-db",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    assert DataController().config == {
        "host": "db.example", "port": 3307, "user": "test-user",
        "password": "test-password", "database": "test-db", "connection_timeout": 5,
    }


def test_registration_stores_hash_and_returns_public_user(client, connection):
    cursor = connection.cursor.return_value
    cursor.lastrowid = 42
    response = client.post("/users/register", json={"email": "Student@ASE3.com", "username": "Student", "password": "secret"})
    assert response.status_code == 201
    assert response.json() == {"id": 42, "email": "student@ase3.com", "username": "Student"}
    sql, parameters = cursor.execute.call_args.args
    assert "VALUES (%s, %s, %s)" in sql
    assert parameters[0] == "student@ase3.com"
    assert parameters[1] == "Student"
    assert verify_password("secret", parameters[2])
    assert parameters[2] != "secret"
    connection.commit.assert_called_once()
    connection.rollback.assert_not_called()
    cursor.close.assert_called_once()
    connection.close.assert_called_once()


def test_duplicate_email_rolls_back_and_returns_conflict(client, connection):
    connection.cursor.return_value.execute.side_effect = IntegrityError(errno=ER_DUP_ENTRY)
    response = client.post("/users/register", json={"email": "dev@ase3.com", "username": "dev", "password": "dev"})
    assert response.status_code == 409
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()
    connection.cursor.return_value.close.assert_called_once()
    connection.close.assert_called_once()


def test_other_integrity_errors_are_not_reported_as_duplicate(connection):
    connection.cursor.return_value.execute.side_effect = IntegrityError(errno=ER_BAD_NULL_ERROR)
    with pytest.raises(IntegrityError):
        UserDataController().create_user("dev@ase3.com", "dev", "dev")
    connection.rollback.assert_called_once()
    connection.close.assert_called_once()


def test_transaction_error_rolls_back_and_closes(connection):
    with pytest.raises(RuntimeError):
        with DataController().connection():
            raise RuntimeError("query failed")
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()
    connection.close.assert_called_once()


def test_login_returns_public_user(client, connection):
    connection.cursor.return_value.fetchone.return_value = {
        "id": 1, "email": "dev@ase3.com", "username": "dev", "password": hash_password("dev"),
    }
    response = client.post("/users/login", json={"email": "DEV@ase3.com", "password": "dev"})
    assert response.status_code == 200
    assert response.json() == {"authenticated": True, "user": {"id": 1, "email": "dev@ase3.com", "username": "dev"}}
    sql, parameters = connection.cursor.return_value.execute.call_args.args
    assert "WHERE email = %s" in sql
    assert parameters == ("dev@ase3.com",)
    connection.close.assert_called_once()


@pytest.mark.parametrize("exists", [True, False])
def test_login_uses_same_error_for_wrong_password_and_unknown_user(client, connection, exists):
    connection.cursor.return_value.fetchone.return_value = (
        {"id": 1, "email": "dev@ase3.com", "username": "dev", "password": hash_password("dev")}
        if exists else None
    )
    response = client.post("/users/login", json={"email": "dev@ase3.com", "password": "wrong"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password."}


@pytest.mark.parametrize("route", ["register", "login"])
@pytest.mark.parametrize("payload", [
    {"email": "invalid", "password": "dev"},
    {"email": "dev@ase3.com", "password": ""},
    {"email": "dev@ase3.com", "password": "x" * 1025},
    {"email": "dev@ase3.com"},
    {"password": "dev"},
])
def test_invalid_credentials_are_rejected_before_database_access(client, connection, route, payload):
    if route == "register":
        payload = {**payload, "username": "dev"}
    assert client.post(f"/users/{route}", json=payload).status_code == 422
    connection.cursor.assert_not_called()


@pytest.mark.parametrize("username", [None, "", "   ", "x" * 256])
def test_registration_rejects_missing_or_invalid_username(client, connection, username):
    payload = {"email": "dev@ase3.com", "password": "dev"}
    if username is not None:
        payload["username"] = username
    response = client.post("/users/register", json=payload)
    assert response.status_code == 422
    assert any(error["loc"] == ["body", "username"] for error in response.json()["detail"])
    connection.cursor.assert_not_called()


def test_lookup_parameterizes_untrusted_input(connection):
    connection.cursor.return_value.fetchone.return_value = None
    value = "' OR 1=1 --"
    assert UserDataController().get_by_email(value) is None
    sql, parameters = connection.cursor.return_value.execute.call_args.args
    assert value not in sql
    assert parameters == (value.lower(),)


def test_routes_support_controller_injection():
    controller = MagicMock()
    controller.authenticate.return_value = User(id=7, email="dev@ase3.com", username="dev", password="private-hash")
    app.dependency_overrides[get_user_data_controller] = lambda: controller
    try:
        with TestClient(app) as client:
            response = client.post("/users/login", json={"email": "dev@ase3.com", "password": "dev"})
        assert response.json() == {"authenticated": True, "user": {"id": 7, "email": "dev@ase3.com", "username": "dev"}}
    finally:
        app.dependency_overrides.clear()


def test_health_and_openapi_import_without_mysql():
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        paths = client.get("/openapi.json").json()["paths"]
    assert "post" in paths["/users/register"]
    assert "post" in paths["/users/login"]
