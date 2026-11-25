"""Admin page: find users and grant or remove the admin and reviewer roles, and export corrections (#87)."""
import os
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from mysql.connector import Error as DatabaseError

from backend.app import training_export
from backend.app.auth import Admin, AdminWrite, reviewer_from_env
from backend.app.data_controller.correction_data_controller import CorrectionDataController
from backend.app.data_controller.user_data_controller import LastAdmin, UserDataController
from backend.app.training_export import ExportDataController
from backend.app.model.analysis import ApiError
from backend.app.model.user import AdminUser, AdminUserPage, RoleUpdate
from backend.app.routes.edition_routes import Editions  # accepted editions for the export (workbench)

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
    except LastAdmin as error:
        raise HTTPException(409, "The site needs at least one admin.") from error
    except DatabaseError as error:
        raise HTTPException(503, "User storage is unavailable.") from error
    if row is None:
        raise HTTPException(404, "User not found.")
    return admin_user(row)


# Training export (#87): every corrected copy, plus #73's approved label corrections.

def get_export_data_controller() -> ExportDataController:
    return ExportDataController()


def get_correction_controller() -> CorrectionDataController:
    return CorrectionDataController()


Exports = Annotated[ExportDataController, Depends(get_export_data_controller)]
Corrections = Annotated[CorrectionDataController, Depends(get_correction_controller)]


def _export_data(exports: ExportDataController, corrections: CorrectionDataController,
                 everyone: bool, accepted_only: bool = False, editions=None) -> tuple[list, list]:
    try:
        if accepted_only:
            from backend.app.routes.edition_routes import accepted_copies  # noqa: PLC0415
            return accepted_copies(editions), corrections.export_approved()
        return exports.copies(everyone), corrections.export_approved()
    except DatabaseError as error:
        raise HTTPException(503, "Correction storage is unavailable.") from error


@router.get("/export/corrections", responses=DENIED)
def export_corrections(_admin: Admin, exports: Exports, corrections: Corrections, editions: Editions,
                       everyone: bool = False, accepted_only: bool = False) -> dict:
    """Corrected copies' boxes in the training annotations' shape, and the approved label corrections.
    Copies by admins and reviewers only, unless `everyone` (anyone can register and edit);
    `accepted_only` gives each tablet's accepted edition release instead, one per tablet."""
    return training_export.corrections(*_export_data(exports, corrections, everyone, accepted_only, editions))


@router.get("/export/corrections.zip", response_class=FileResponse,
            responses={**DENIED, 200: {"content": {"application/zip": {}}, "description": "YOLO images, labels and classes"}})
def export_corrections_zip(_admin: Admin, exports: Exports, corrections: Corrections,
                           editions: Editions, everyone: bool = False, accepted_only: bool = False) -> FileResponse:
    """The same as a YOLO dataset: images/, labels/, classes.txt and corrections.json, streamed from disk."""
    path = training_export.yolo_zip(*_export_data(exports, corrections, everyone, accepted_only, editions))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return FileResponse(path, media_type="application/zip", filename=f"corrections-{stamp}.zip",
                        headers={"Cache-Control": "no-store"}, background=BackgroundTask(os.remove, path))
