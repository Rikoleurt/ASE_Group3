import hashlib
import hmac
import secrets
from datetime import datetime

from mysql.connector.errors import IntegrityError
from mysql.connector.errorcode import ER_DUP_ENTRY

from backend.app.data_controller.data_controller import DataController
from backend.app.model.user import Account, User, UserPublic


_PASSWORD_SCHEME = "pbkdf2_sha256"
_PASSWORD_ITERATIONS = 600_000

class DuplicateUserError(Exception):
    """Raised when an email or username is already registered."""

    def __init__(self, field: str | None = None):
        self.field = field
        super().__init__(field or "email or username")


def _normalize_email(email: str) -> str:
    """
    Normalizes an email address to lower case.
    :param email:
    :return: Email address to lower case
    """
    return email.strip().lower()

def _normalize_username(username: str) -> str:
    """
    Trims surrounding whitespace; MySQL's configured collation compares case-insensitively.
    :param username:
    :return: Username without surrounding whitespace
    """
    return username.strip()

class LastAdmin(Exception):
    """Removing this admin role would leave the site without an admin."""


def like_escape(text: str) -> str:
    """Make `text` match literally inside a LIKE pattern (MySQL's default escape is the backslash)."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def hash_password(password: str) -> str:
    """
    Hashes a password using PBKDF2-HMAC-SHA256 with a random salt.
    :param password:
    :return:
    """
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _PASSWORD_ITERATIONS,
    )
    return (
        f"{_PASSWORD_SCHEME}${_PASSWORD_ITERATIONS}"
        f"${salt.hex()}${digest.hex()}"
    )


def verify_password(password: str, stored_password: str) -> bool:
    """
    Verifies a plaintext password against the stored PBKDF2 representation.
    :param password:
    :param stored_password:
    :return:
    """
    try:
        scheme, iterations_text, salt_hex, expected_hex = stored_password.split("$", 3)
        if scheme != _PASSWORD_SCHEME:
            return False
        iterations = int(iterations_text)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hex)
        if not 1 <= iterations <= 2_000_000 or len(salt) != 16 or len(expected) != 32:
            return False
    except (ValueError, TypeError):
        return False

    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)


class UserDataController(DataController):
    """
    Inherit from DataController. This class is used whenever we want to query user data.
    """
    #region getter
    def get_by_email(self, email: str) -> User | None:
        """
        Get a user by email address.
        :param email:
        :return:
        """
        normalized_email = _normalize_email(email)
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    """
                    SELECT id, email, username, password, is_admin, is_reviewer
                    FROM `user`
                    WHERE email = %s
                    LIMIT 1
                    """,
                    (normalized_email,),
                )
                row = cursor.fetchone()
            finally:
                cursor.close()

        if row is None:
            return None

        return User(
            id=row["id"],
            email=row["email"],
            username=row["username"],
            password=row["password"],
            is_admin=bool(row.get("is_admin")),
            is_reviewer=bool(row.get("is_reviewer")),
        )

    def get_by_username(self, username: str) -> User | None:
        """
        Get a user by username.
        :param username:
        :return:
        """
        normalized_username = _normalize_username(username)
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    """
                    SELECT id, email, username, password, is_admin, is_reviewer
                    FROM `user`
                    WHERE username = %s
                    LIMIT 1
                    """,
                    (normalized_username,),
                )
                row = cursor.fetchone()
            finally:
                cursor.close()
        if row is None:
            return None

        return User(
            id=row["id"],
            email=row["email"],
            username=row["username"],
            password=row["password"],
            is_admin=bool(row.get("is_admin")),
            is_reviewer=bool(row.get("is_reviewer")),
        )

    def get_email_by_id(self, user_id: int) -> str | None:
        """
        Gets the email according to the user id.
        :param user_id:
        :return:
        """
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    """
                    SELECT email
                    FROM `user`
                    WHERE id = %s
                    LIMIT 1
                    """,
                    (user_id,),
                )
                row = cursor.fetchone()
            finally:
                cursor.close()
        if row is None:
            return None

        return row["email"]

    def get_username_by_id(self, user_id: int) -> str | None:
        """
        Gets the username according to the user id.
        :param user_id:
        :return:
        """
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    """
                    SELECT username
                    FROM `user`
                    WHERE id = %s
                    LIMIT 1
                    """,
                    (user_id,),
                )
                row = cursor.fetchone()
            finally:
                cursor.close()
        if row is None:
            return None
        return row["username"]

    #endregion

    #region setter
    def create_user(self, email: str, username: str, password: str) -> User:
        """
        Creates a new user using email, username, and password.
        :param email:
        :param username:
        :param password:
        :return:
        """
        normalized_email = _normalize_email(email)
        normalized_username = _normalize_username(username)
        password_hash = hash_password(password)

        try:
            with self.connection() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        """
                        INSERT INTO `user` (email, username, password)
                        VALUES (%s, %s, %s)
                        """,
                        (normalized_email, normalized_username, password_hash),
                    )
                    user_id = cursor.lastrowid
                finally:
                    cursor.close()
        except IntegrityError as error:
            if error.errno == ER_DUP_ENTRY:
                # Inspect the key, not the duplicate value (which is user input).
                key = error.msg.rsplit(" for key ", 1)[-1].strip("'").rsplit(".", 1)[-1]
                field = {"uq_user_email": "email", "uq_user_username": "username"}.get(key)
                raise DuplicateUserError(field) from error
            raise

        return User(
            id=user_id,
            email=normalized_email,
            username=normalized_username,
            password=password_hash,
        )
    #endregion

    #region other
    def authenticate(self, email: str | None, username: str | None, password: str) -> User | None:
        """
        Authenticates a user by email or username, password is mandatory.
        :param email:
        :param username:
        :param password:
        :return:
        """
        user = None
        if email is not None:
            user = self.get_by_email(email)
        elif username is not None:
            user = self.get_by_username(username)
        if user is None or not verify_password(password, user.password):
            return None
        return user
    #endregion

    def create_session(self, user_id: int, token_hash: str, expires_at: datetime) -> None:
        with self.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute("DELETE FROM user_session WHERE expires_at <= UTC_TIMESTAMP(6)")
                cursor.execute(
                    "INSERT INTO user_session (user_id, token_hash, expires_at) VALUES (%s, %s, %s)",
                    (user_id, token_hash, expires_at),
                )
            finally:
                cursor.close()

    def get_session_user(self, token_hash: str) -> Account | None:
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    "SELECT u.id, u.email, u.username, u.is_admin, u.is_reviewer FROM user_session s "
                    "JOIN `user` u ON u.id = s.user_id "
                    "WHERE s.token_hash = %s AND s.expires_at > UTC_TIMESTAMP(6)",
                    (token_hash,),
                )
                row = cursor.fetchone()
            finally:
                cursor.close()
        return Account(**{**row, "is_admin": bool(row.get("is_admin")), "is_reviewer": bool(row.get("is_reviewer"))}) if row else None

    def delete_session(self, token_hash: str) -> None:
        with self.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute("DELETE FROM user_session WHERE token_hash = %s", (token_hash,))
            finally:
                cursor.close()

    def list_users(self, query: str, limit: int, offset: int) -> tuple[list[dict], int]:
        """Users whose username or email contains `query`, by username, with the total count."""
        pattern = "%" + like_escape(query) + "%"
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute("SELECT COUNT(*) AS total FROM `user` WHERE username LIKE %s OR email LIKE %s",
                               (pattern, pattern))
                total = cursor.fetchone()["total"]
                cursor.execute(
                    "SELECT id, username, email, is_admin, is_reviewer FROM `user` "
                    "WHERE username LIKE %s OR email LIKE %s ORDER BY username, id LIMIT %s OFFSET %s",
                    (pattern, pattern, limit, offset),
                )
                rows = cursor.fetchall()
            finally:
                cursor.close()
        return rows, total

    def set_roles(self, user_id: int, admin: bool | None, reviewer: bool | None) -> dict | None:
        """Change the given roles; None when the user does not exist."""
        changes = [(column, value) for column, value in (("is_admin", admin), ("is_reviewer", reviewer)) if value is not None]
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                if admin is False:
                    # Lock the other admins' rows, so two admins cannot demote each other at once.
                    cursor.execute("SELECT id FROM `user` WHERE is_admin = TRUE AND id <> %s FOR UPDATE", (user_id,))
                    if not cursor.fetchall():
                        raise LastAdmin()
                cursor.execute(
                    "UPDATE `user` SET " + ", ".join(f"{column} = %s" for column, _ in changes) + " WHERE id = %s",
                    (*[value for _, value in changes], user_id),
                )
                cursor.execute("SELECT id, username, email, is_admin, is_reviewer FROM `user` WHERE id = %s", (user_id,))
                row = cursor.fetchone()
            finally:
                cursor.close()
        return row

    def search_usernames(self, prefix: str, limit: int, exclude_id: int) -> list[dict]:
        """Usernames starting with `prefix` (literally), for sharing (#84); never emails."""
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute("SELECT id, username FROM `user` WHERE username LIKE %s AND id <> %s "
                               "ORDER BY username LIMIT %s", (like_escape(prefix) + "%", exclude_id, limit))
                return cursor.fetchall()
            finally:
                cursor.close()
