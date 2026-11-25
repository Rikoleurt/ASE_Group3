"""Your notifications (scholars' workbench, story I): the bell in the top bar."""

from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from mysql.connector import Error as DatabaseError
from pydantic import BaseModel, Field

from backend.app.auth import AuthenticatedWrite, CurrentUser
from backend.app.model.analysis import ApiError
from backend.app.notifications import NotificationDataController

router = APIRouter(tags=["notifications"])
ERRORS = {code: {"model": ApiError} for code in (401, 403, 422, 503)}
UNAVAILABLE = "Notifications are unavailable. Please try again."


def get_notification_data_controller() -> NotificationDataController:
    return NotificationDataController()


Notifications = Annotated[NotificationDataController, Depends(get_notification_data_controller)]


class Notification(BaseModel):
    id: int
    kind: Literal["share", "comment", "mention", "vote", "override", "merge", "voting_rights"]
    actor: str | None  # who did it (None if their account was deleted)
    message: str
    link: str | None  # where to look, a page of this app
    tablet: str | None
    created_at: datetime
    read: bool


class NotificationPage(BaseModel):
    items: list[Notification]  # newest first
    next_before: int | None  # pass as `before` for older ones
    unread: int


class Unread(BaseModel):
    unread: int


class MarkRead(BaseModel):
    ids: list[int] | None = Field(default=None, max_length=200)  # None: all of them


def _item(row: dict) -> Notification:
    return Notification(
        id=row["id"],
        kind=row["kind"],
        actor=row["actor"],
        message=row["message"],
        link=row["link"],
        tablet=row["tablet_slug"],
        created_at=row["created_at"].replace(tzinfo=timezone.utc),
        read=row["read_at"] is not None,
    )


@router.get("/notifications", response_model=NotificationPage, responses=ERRORS)
def list_notifications(
    user: CurrentUser,
    notifications: Notifications,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    before: Annotated[int | None, Query(gt=0, le=2**64 - 1)] = None,
) -> NotificationPage:
    try:
        rows = notifications.page(user.id, limit, before)
        unread = notifications.unread(user.id)
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
    return NotificationPage(
        items=[_item(row) for row in rows[:limit]],
        next_before=rows[limit - 1]["id"] if len(rows) > limit else None,
        unread=unread,
    )


@router.get("/notifications/unread-count", response_model=Unread, responses=ERRORS)
def unread_count(user: CurrentUser, notifications: Notifications) -> Unread:
    try:
        return Unread(unread=notifications.unread(user.id))
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error


@router.post("/notifications/read", response_model=Unread, responses=ERRORS)
def mark_read(request: MarkRead, user: AuthenticatedWrite, notifications: Notifications) -> Unread:
    """Mark some of your notifications read (`ids`), or all of them."""
    try:
        notifications.mark_read(user.id, request.ids)
        return Unread(unread=notifications.unread(user.id))
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
