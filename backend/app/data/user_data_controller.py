import hashlib
import hmac
import secrets

from mysql.connector.errors import IntegrityError

from backend.app.data.data_controller import DataController
from backend.app.model.user import User


_PASSWORD_SCHEME = "pbkdf2_sha256"
_PASSWORD_ITERATIONS = 600_000


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a random salt."""
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
        normalized_email = _normalize_email(email)

        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    """
                    SELECT id, email, password
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
            password=row["password"],
        )

    def create_user(self, email: str, password: str) -> User | None:
        normalized_email = _normalize_email(email)
        password_hash = hash_password(password)

        try:
            with self.connection() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        """
                        INSERT INTO `user` (email, password)
                        VALUES (%s, %s)
                        """,
                        (normalized_email, password_hash),
                    )
                    user_id = cursor.lastrowid
                finally:
                    cursor.close()
        except IntegrityError:
            return None

        return User(
            id=user_id,
            email=normalized_email,
            password=password_hash,
        )

    def authenticate(self, email: str, password: str) -> User | None:
        user = self.get_by_email(email)
        if user is None or not verify_password(password, user.password):
            return None
        return user
