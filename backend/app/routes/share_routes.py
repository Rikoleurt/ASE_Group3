"""Sharing corrected copies (#84): with named people at a level, or with everyone logged in.

The levels and what they allow are in backend/app/sharing.py.
"""
from datetime import timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from mysql.connector import Error as DatabaseError
from pydantic import BaseModel, Field

from backend.app.auth import AuthenticatedWrite, CurrentUser
from backend.app.data_controller.box_set_data_controller import BoxSetDataController
from backend.app.data_controller.user_data_controller import UserDataController
from backend.app.model.analysis import ApiError
from backend.app.notifications import copy_name, notify
from backend.app.routes.box_set_routes import UNAVAILABLE, Controller, access
from backend.app.sharing import EveryoneLevel, ShareLevel, allows, rank

router = APIRouter(tags=["sharing"])
OWNER_ONLY_MANAGE = "Only the owner can give, change or take away Manage access."
Identifier = Annotated[int, Path(gt=0, le=2**64 - 1)]
ERRORS = {code: {"model": ApiError} for code in (401, 403, 404, 503)}


class UserRef(BaseModel):
    id: int
    username: str


class Share(BaseModel):
    user: UserRef
    permission: ShareLevel


class Sharing(BaseModel):
    everyone: EveryoneLevel
    shares: list[Share]


class ShareRequest(BaseModel):
    permission: ShareLevel


class EveryoneRequest(BaseModel):
    permission: EveryoneLevel


class SharedCopy(BaseModel):
    id: int
    owner: str
    kind: str  # analysis or tablet
    title: str  # the upload's filename, or the tablet id
    permission: ShareLevel  # your level: your own share or the everyone-level, whichever is higher
    shared_with_everyone: bool
    updated_at: str


def get_user_data_controller() -> UserDataController:
    return UserDataController()


Users = Annotated[UserDataController, Depends(get_user_data_controller)]


def _sharing(controller: BoxSetDataController, set_id: int, everyone: str) -> Sharing:
    try:
        rows = controller.shares(set_id)
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
    return Sharing(everyone=everyone, shares=[
        Share(user=UserRef(id=row["user_id"], username=row["username"]), permission=row["permission"]) for row in rows])


@router.get("/users/search", response_model=list[UserRef], responses=ERRORS)
def search_users(user: CurrentUser, users: Users,
                 q: Annotated[str, Query(min_length=2, max_length=255)]) -> list[UserRef]:
    """Usernames starting with `q`, to share with. Logged-in users only; at most 10; never emails."""
    try:
        rows = users.search_usernames(q.strip(), 10, user.id)
    except DatabaseError as error:
        raise HTTPException(503, "User storage is unavailable.") from error
    return [UserRef(**row) for row in rows]


@router.get("/box-sets/{set_id}/shares", response_model=Sharing, responses=ERRORS)
def get_sharing(set_id: Identifier, user: CurrentUser, controller: Controller) -> Sharing:
    """Who the copy is shared with. For the owner and people who manage it."""
    record = access(controller, set_id, user, "manage")
    return _sharing(controller, set_id, record.get("everyone") or "none")


@router.put("/box-sets/{set_id}/shares/{user_id}", response_model=Sharing,
            responses={**ERRORS, 409: {"model": ApiError}})
def share(set_id: Identifier, user_id: Identifier, request: ShareRequest, user: AuthenticatedWrite,
          controller: Controller) -> Sharing:
    """Share the copy with someone, or change their level."""
    record = access(controller, set_id, user, "manage")
    if user_id == record["owner_id"]:
        raise HTTPException(409, "The owner always has full access.")
    if user_id == user.id:
        raise HTTPException(409, "You cannot change your own access.")
    try:
        if record["permission"] != "owner" and "manage" in (request.permission, controller.share_of(set_id, user_id)):
            raise HTTPException(403, OWNER_ONLY_MANAGE)
        if not controller.set_share(set_id, user_id, request.permission, user.id):
            raise HTTPException(404, "User not found.")
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
    can = {"view": "view it", "comment": "comment on it", "edit": "edit it", "manage": "manage it"}[request.permission]
    notify([user_id], "share", user.id, f"{user.username} shared {copy_name(record)} with you: you can {can}.",
           f"/box-sets/{set_id}", record.get("tablet_slug"))
    return _sharing(controller, set_id, record.get("everyone") or "none")


@router.delete("/box-sets/{set_id}/shares/{user_id}", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS)
def unshare(set_id: Identifier, user_id: Identifier, user: AuthenticatedWrite, controller: Controller) -> Response:
    """Stop sharing the copy with someone. Anyone may also remove their own access."""
    record = access(controller, set_id, user, "view" if user_id == user.id else "manage")
    try:
        if user_id != user.id and record["permission"] != "owner" and controller.share_of(set_id, user_id) == "manage":
            raise HTTPException(403, OWNER_ONLY_MANAGE)
        controller.remove_share(set_id, user_id)
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/box-sets/{set_id}/everyone", response_model=Sharing, responses=ERRORS)
def share_with_everyone(set_id: Identifier, request: EveryoneRequest, user: AuthenticatedWrite,
                        controller: Controller) -> Sharing:
    """Every logged-in user's level on the copy: none, view, comment or edit."""
    access(controller, set_id, user, "manage")
    try:
        controller.set_everyone(set_id, request.permission)
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
    return _sharing(controller, set_id, request.permission)


@router.get("/users/me/shared-copies", response_model=list[SharedCopy], responses=ERRORS)
def shared_with_me(user: CurrentUser, controller: Controller,
                   limit: Annotated[int, Query(ge=1, le=200)] = 100) -> list[SharedCopy]:
    """Other people's corrected copies you can open, most recently changed first."""
    try:
        rows = controller.shared_with(user.id, limit)
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
    copies = []
    for row in rows:
        everyone = row["everyone"] if row["everyone"] != "none" else None
        best = max((row["share"], everyone), key=rank)
        if not allows(best, "view"):
            continue
        copies.append(SharedCopy(
            id=row["id"], owner=row["owner"], kind="analysis" if row["analysis_id"] is not None else "tablet",
            title=row["filename"] or (row["tablet_slug"] or "").replace("-", " "), permission=best,
            shared_with_everyone=everyone is not None,
            updated_at=row["updated_at"].replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")))
    return copies
