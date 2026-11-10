"""Opaque server sessions; CSRF tokens are bound to the HttpOnly session cookie."""
import hashlib
import hmac
import os
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, Response
from fastapi.security import APIKeyCookie
from mysql.connector import Error as DatabaseError

from backend.app.data_controller.user_data_controller import UserDataController
from backend.app.model.user import UserPublic

COOKIE_NAME = "ase_session"
SESSION_SECONDS = 86400
session_cookie = APIKeyCookie(name=COOKIE_NAME, auto_error=False)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def csrf_token(token: str) -> str:
    return hashlib.sha256(("csrf:" + token).encode()).hexdigest()


def cookie_secure() -> bool:
    return os.getenv("SESSION_COOKIE_SECURE", "1") != "0"


def require_ajax(x_requested_with: Annotated[str | None, Header()] = None):
    # A cross-origin form cannot set this header; no credentialed CORS is enabled.
    if x_requested_with != "ASE":
        raise HTTPException(403, "The X-Requested-With: ASE header is required.")


def current_user(response: Response, token: Annotated[str | None, Depends(session_cookie)]) -> UserPublic:
    response.headers["Cache-Control"] = "no-store"
    if not token or len(token) != 43:
        raise HTTPException(401, "Please log in.")
    try:
        user = UserDataController().get_session_user(token_hash(token))
    except DatabaseError as error:
        raise HTTPException(503, "Session storage is unavailable.") from error
    if user is None:
        raise HTTPException(401, "Your session has expired. Please log in.")
    return user


CurrentUser = Annotated[UserPublic, Depends(current_user)]


def require_csrf(request: Request, user: CurrentUser,
                 x_csrf_token: Annotated[str | None, Header()] = None) -> UserPublic:
    expected = csrf_token(request.cookies.get(COOKIE_NAME, ""))
    if not x_csrf_token or not hmac.compare_digest(x_csrf_token.encode(), expected.encode()):
        raise HTTPException(403, "Invalid CSRF token.")
    return user


AuthenticatedWrite = Annotated[UserPublic, Depends(require_csrf)]
