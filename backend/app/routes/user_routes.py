from typing import Annotated
from base64 import urlsafe_b64decode, urlsafe_b64encode

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, Query, status
from datetime import datetime, timedelta, timezone
import secrets
from mysql.connector import Error as DatabaseError
from backend.app.auth import (CurrentUser, AuthenticatedWrite, COOKIE_NAME, SESSION_SECONDS,
                              cookie_secure, csrf_token, token_hash, require_ajax)
from backend.app.model.user import SessionUser
from backend.app.model.analysis import AnalysisHistoryDetail, AnalysisHistoryPage, ApiError, AnalysisComment, CommentCreate
from backend.app.data_controller.analysis_data_controller import AnalysisDataController

from backend.app.data_controller.user_data_controller import DuplicateUserError, UserDataController
from backend.app.model.user import (
    LoginResponse, RegistrationConflict, UserCreate, UserEmail, UserLogin, UserPublic, UserUsername,
)


router = APIRouter(prefix="/users", tags=["users"])

def get_user_data_controller() -> UserDataController:
    return UserDataController()

UserController = Annotated[UserDataController, Depends(get_user_data_controller)]

@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_409_CONFLICT: {
            "model": RegistrationConflict,
            "description": "An account with this email or username already exists.",
            "content": {
                "application/json": {
                    "examples": {
                        "duplicate_username": {
                            "summary": "Username already taken",
                            "value": {"detail": {"code": "duplicate_user", "field": "username"}},
                        },
                        "duplicate_email": {
                            "summary": "Email already registered",
                            "value": {"detail": {"code": "duplicate_user", "field": "email"}},
                        },
                    },
                },
            },
        },
    },
)
def register(payload: UserCreate, user_data_controller: UserController) -> UserPublic:
    try:
        user = user_data_controller.create_user(
            email=str(payload.email),
            username=str(payload.username),
            password=payload.password,
        )
    except DuplicateUserError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "duplicate_user", "field": error.field},
        ) from error

    return UserPublic(id=user.id, email=user.email, username=user.username)


@router.post("/login", response_model=LoginResponse, dependencies=[Depends(require_ajax)], responses={401: {"model": ApiError}, 403: {"model": ApiError}, 503: {"model": ApiError}})
def login(payload: UserLogin, user_data_controller: UserController, request: Request, response: Response) -> LoginResponse:
    user = user_data_controller.authenticate(
        email=str(payload.email) if payload.email is not None else None,
        username=payload.username,
        password=payload.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = secrets.token_urlsafe(32)
    try:
        if old_token := request.cookies.get(COOKIE_NAME):
            user_data_controller.delete_session(token_hash(old_token))
        user_data_controller.create_session(user.id, token_hash(token),
                                            datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=SESSION_SECONDS))
    except DatabaseError as error:
        raise HTTPException(503, "Session storage is unavailable.") from error
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS, httponly=True,
                        secure=cookie_secure(), samesite="lax", path="/")
    response.headers["Cache-Control"] = "no-store"
    return LoginResponse(
        csrf_token=csrf_token(token),
        authenticated=True,
        user=UserPublic(id=user.id, email=user.email, username=user.username),
    )


@router.get("/me", response_model=SessionUser, responses={401: {"model": ApiError}, 503: {"model": ApiError}})
def me(request: Request, user: CurrentUser):
    return SessionUser(user=user, csrf_token=csrf_token(request.cookies[COOKIE_NAME]))


@router.post("/logout", status_code=204, responses={401: {"model": ApiError}, 403: {"model": ApiError}, 503: {"model": ApiError}})
def logout(request: Request, response: Response, user: AuthenticatedWrite, controller: UserController):
    try:
        controller.delete_session(token_hash(request.cookies[COOKIE_NAME]))
    except DatabaseError as error:
        raise HTTPException(503, "Session storage is unavailable.") from error
    response.delete_cookie(COOKIE_NAME, path="/", secure=cookie_secure(), httponly=True, samesite="lax")


def history_controller():
    return AnalysisDataController()


HistoryController = Annotated[AnalysisDataController, Depends(history_controller)]


@router.get("/me/analyses", response_model=AnalysisHistoryPage,
            responses={401: {"model": ApiError}, 422: {"description": "Invalid cursor or limit"}, 503: {"model": ApiError}})
def history(user: CurrentUser, controller: HistoryController,
            limit: Annotated[int, Query(ge=1, le=100)] = 20,
            cursor: Annotated[str | None, Query(max_length=100)] = None):
    before = None
    if cursor:
        try:
            date, identifier = urlsafe_b64decode(cursor.encode()).decode().split("|", 1)
            stamp = datetime.fromisoformat(date)
            identifier = int(identifier)
            if stamp.tzinfo is not None or stamp.year < 1000 or not 1 <= identifier <= 2**64 - 1:
                raise ValueError()
            before = (stamp, identifier)
        except (ValueError, UnicodeError) as error:
            raise HTTPException(422, "Invalid history cursor.") from error
    try:
        rows = controller.list_analyses(user.id, limit, before)
    except DatabaseError as error:
        raise HTTPException(503, "History storage is unavailable.") from error
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = urlsafe_b64encode(f"{last.created_at.replace(tzinfo=None).isoformat()}|{last.id}".encode()).decode()
    return AnalysisHistoryPage(items=rows[:limit], next_cursor=next_cursor)


@router.get("/me/analyses/{analysis_id}", response_model=AnalysisHistoryDetail,
            response_model_exclude_none=True,
            responses={401: {"model": ApiError}, 404: {"model": ApiError}, 503: {"model": ApiError}})
def history_detail(analysis_id: Annotated[int, Path(gt=0, le=2**64 - 1)], user: CurrentUser, controller: HistoryController):
    try:
        result = controller.get_analysis(user.id, analysis_id)
    except DatabaseError as error:
        raise HTTPException(503, "History storage is unavailable.") from error
    if result is None:
        raise HTTPException(404, "Analysis not found.")
    return result


@router.get("/{user_id}/email", response_model=UserEmail)
def get_email(user_id: Annotated[int, Path(gt=0)], user_data_controller: UserController) -> UserEmail:
    email = user_data_controller.get_email_by_id(user_id)
    if email is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return UserEmail(email=email)


@router.get("/{user_id}/username", response_model=UserUsername)
def get_username(user_id: Annotated[int, Path(gt=0)], user_data_controller: UserController) -> UserUsername:
    username = user_data_controller.get_username_by_id(user_id)
    if username is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return UserUsername(username=username)

@router.get("/me/analyses/{analysis_id}/comments", response_model=list[AnalysisComment],
            responses={401: {"model": ApiError}, 404: {"model": ApiError}, 503: {"model": ApiError}})
def list_comments(analysis_id: Annotated[int, Path(gt=0, le=2**64 - 1)], user: CurrentUser, controller: HistoryController):
    try:
        result = controller.list_comments(user.id, analysis_id)
    except DatabaseError as error:
        raise HTTPException(503, "History storage is unavailable.") from error
    if result is None:
        raise HTTPException(404, "Analysis not found.")
    return result


@router.post("/me/analyses/{analysis_id}/comments", response_model=AnalysisComment, status_code=201,
             responses={401: {"model": ApiError}, 404: {"model": ApiError}, 422: {"description": "Invalid comment"},
                        503: {"model": ApiError}})
def add_comment(analysis_id: Annotated[int, Path(gt=0, le=2**64 - 1)], payload: CommentCreate,
                user: CurrentUser, controller: HistoryController):
    try:
        result = controller.add_comment(user.id, analysis_id, payload.body)
    except DatabaseError as error:
        raise HTTPException(503, "History storage is unavailable.") from error
    if result is None:
        raise HTTPException(404, "Analysis not found.")
    return result


@router.delete("/me/comments/{comment_id}", status_code=204, response_class=Response,
               responses={401: {"model": ApiError}, 404: {"model": ApiError}, 503: {"model": ApiError}})
def delete_comment(comment_id: Annotated[int, Path(gt=0, le=2**64 - 1)], user: CurrentUser, controller: HistoryController):
    try:
        deleted = controller.delete_comment(user.id, comment_id)
    except DatabaseError as error:
        raise HTTPException(503, "History storage is unavailable.") from error
    if not deleted:
        raise HTTPException(404, "Comment not found.")
    return Response(status_code=204)