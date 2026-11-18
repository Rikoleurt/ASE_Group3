"""Admin page: find users and grant or remove the admin and reviewer roles."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from mysql.connector import Error as DatabaseError

from backend.app.auth import Admin, AdminWrite, reviewer_from_env
from backend.app.data_controller.user_data_controller import UserDataController
from backend.app.model.analysis import ApiError
from backend.app.model.user import AdminUser, AdminUserPage, RoleUpdate

router = APIRouter(prefix="/admin", tags=["admin"])
Identifier = Annotated[int, Path(gt=0, le=2**64 - 1)]
DENIED = {401: {"model": ApiError}, 403: {"model": ApiError}, 503: {"model": ApiError}}


def get_user_data_controller() -> UserDataController:
    return UserDataController()


UserController = Annotated[UserDataController, Depends(get_user_data_controller)]


def admin_user(row: dict) -> AdminUser:
    return AdminUser(id=row["id"], username=row["username"], email=row["email"], admin=bool(row["is_admin"]),
                     reviewer=bool(row["is_reviewer"]), reviewer_from_env=reviewer_from_env(row["username"]))


@router.get("/users", response_model=AdminUserPage, responses=DENIED)
def list_users(_admin: Admin, controller: UserController,
               q: Annotated[str, Query(max_length=255)] = "",
               limit: Annotated[int, Query(ge=1, le=100)] = 50,
               offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0) -> AdminUserPage:
    try:
        rows, total = controller.list_users(q.strip(), limit, offset)
    except DatabaseError as error:
        raise HTTPException(503, "User storage is unavailable.") from error
    return AdminUserPage(items=[admin_user(row) for row in rows], total=total)


@router.patch("/users/{user_id}", response_model=AdminUser,
              responses={**DENIED, 404: {"model": ApiError}, 409: {"model": ApiError}})
def set_roles(user_id: Identifier, roles: RoleUpdate, admin: AdminWrite, controller: UserController) -> AdminUser:
    # Removing your own admin role could leave the site with no admin at all.
    if user_id == admin.id and roles.admin is False:
        raise HTTPException(409, "You cannot remove your own admin role.")
    try:
        row = controller.set_roles(user_id, roles.admin, roles.reviewer)
    except DatabaseError as error:
        raise HTTPException(503, "User storage is unavailable.") from error
    if row is None:
        raise HTTPException(404, "User not found.")
    return admin_user(row)
