import hashlib
import hmac
import secrets

from mysql.connector.errors import IntegrityError
from mysql.connector.errorcode import ER_DUP_ENTRY

from backend.app.data_controller.data_controller import DataController
from backend.app.model.user import User


_PASSWORD_SCHEME = "pbkdf2_sha256"
_PASSWORD_ITERATIONS = 600_000


def _normalize_email(email: str) -> str:
    """
    Normalize an email address to lower case.
    :param email:
    :return: Email address to lower case
    """
    return email.strip().lower()

def _normalize_username(username: str) -> str:
    """
    Normalize a username to lower case.
    :param username:
    :return: Lower case username
    """
    return username.strip().lower()

def hash_password(password: str) -> str:
    """
    Hash a password using PBKDF2-HMAC-SHA256 with a random salt.
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
    """Verify a plaintext password against the stored PBKDF2 representation."""
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
                    SELECT id, email, username, password
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
        )

    def get_by_username(self, username: str) -> User | None:
        """
        Get a user by username.
        :param username:
        :return:
        """
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    """
                    SELECT id, email, username, password
                    FROM `user`
                    WHERE username = %s
                    LIMIT 1
                    """,
                    (username,),
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
        )

    def get_by_id(self, user_id: int) -> User | None:
        raise NotImplementedError

    def create_user(self, email: str, username: str, password: str) -> User | None:
        normalized_email = _normalize_email(email)
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
                        (normalized_email, username, password_hash),
                    )
                    user_id = cursor.lastrowid
                finally:
                    cursor.close()
        except IntegrityError as error:
            if error.errno == ER_DUP_ENTRY:
                return None
            raise

        return User(
            id=user_id,
            email=normalized_email,
            username=username,
            password=password_hash,
        )

    def authenticate(self, email: str, username: str | None, password: str) -> User | None:
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
