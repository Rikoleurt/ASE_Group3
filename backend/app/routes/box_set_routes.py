"""Corrected copies of a tablet's boxes (#83): make one, edit it, see and undo its changes.

Who may do what is decided by backend/app/sharing.py (#84). Someone who may not see a copy
gets 404, as if it did not exist; someone who may see it but not do this gets 403.
"""
import json
from datetime import timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from fastapi.responses import FileResponse, JSONResponse
from mysql.connector import Error as DatabaseError

from backend.app import corpus, glyph_index, tablet_demo
from backend.app.routes.community_routes import tablet_response
from backend.app.auth import AuthenticatedWrite, CurrentUser
from backend.app.box_edits import GEOMETRY, EditError, same, state
from backend.app.data_controller.analysis_data_controller import describe_sign, read_signs
from backend.app.data_controller.box_set_data_controller import (BoxSetDataController, MissingChange, NotEditable,
                                                                 StaleVersion)
from backend.app.data_controller.correction_data_controller import catalogue_sign
from backend.app.model.analysis import ApiError, DetectedSign
from backend.app.model.box_set import (Author, BoxChange, BoxChangePage, BoxSet, BoxSetConflict, BoxSetCreate,
                                       BoxSetEdit, BoxSetSource, BoxSource, BoxState, EditedBox, MergedFrom, Reading,
                                       Revert)
from backend.app.model.user import UserPublic
from backend.app.sharing import REFUSALS, allows, level_of

router = APIRouter(tags=["box sets"])
Identifier = Annotated[int, Path(gt=0, le=2**64 - 1)]
ERRORS = {code: {"model": ApiError} for code in (401, 403, 404, 503)}
UNAVAILABLE = "Corrected copies are unavailable. Please try again."


def get_box_set_data_controller() -> BoxSetDataController:
    return BoxSetDataController()


Controller = Annotated[BoxSetDataController, Depends(get_box_set_data_controller)]


def _catalogue() -> dict:
    classifier = tablet_demo.active_classifier()
    return tablet_demo.sign_catalogue(classifier) if classifier else {}


def _edited(row: dict) -> EditedBox:
    box = {name: row[name] for name in GEOMETRY}
    original = None if row["original_x"] is None else state(
        {name: row[f"original_{name}"] for name in GEOMETRY}, row["model_sign"])
    candidates = row["candidates"]
    return EditedBox(
        id=row["id"], box=box, sign=row["sign"], origin=row["origin"], model_sign=row["model_sign"],
        model_confidence=row["model_confidence"],
        candidates=json.loads(candidates) if isinstance(candidates, (str, bytes)) else candidates or [],
        changed=original is None or not same(original, state(box, row["sign"])),
        source=BoxSource(kind=row["source_kind"], copy_id=row.get("source_set_id"), version=row.get("source_version"),
                         author=row.get("source_author")) if row.get("source_kind") else None,
    )


def _reading(boxes: list[EditedBox]) -> Reading:
    catalogue = _catalogue()
    signs = []
    for box in boxes:
        # The model's confidence still describes a box the user left as the model read it;
        # a box the user drew or named is the user's call.
        kept = not box.changed and box.model_confidence is not None
        confidence = box.model_confidence if kept else 100.0
        signs.append(DetectedSign(id=box.id, **describe_sign(box.sign, catalogue), confidence=confidence,
                                  detection_confidence=confidence, box=box.box, candidates=box.candidates))
    return Reading(**read_signs(signs))


def _merged_from(value) -> list[MergedFrom]:
    items = json.loads(value) if isinstance(value, (str, bytes)) else value or []
    return [MergedFrom(**item) for item in items]


def build(record: dict) -> BoxSet:
    boxes = [_edited(row) for row in record["boxes"] if not row["deleted"]]
    source = (BoxSetSource(kind="analysis", analysis_id=record["analysis_id"], filename=record["filename"])
              if record["analysis_id"] is not None else BoxSetSource(kind="tablet", tablet=record["tablet_slug"]))
    return BoxSet(
        id=record["id"], owner=record["owner"], permission=record.get("permission", "owner"),
        everyone=record.get("everyone") or "none", source=source, title=record.get("title"),
        kind=record.get("kind") or "copy", merged_from=_merged_from(record.get("merged_from")),
        contributors=record.get("contributors") or [], start=record["start"], version=record["version"],
        width=record["width"], height=record["height"], image_url=f"/box-sets/{record['id']}/image",
        created_at=record["created_at"], updated_at=record["updated_at"], boxes=boxes, reading=_reading(boxes),
    )


def access(controller: BoxSetDataController, set_id: int, user: UserPublic, needed: str = "view") -> dict:
    """The copy, with the user's level on it as record["permission"]; 404 if they may not see it,
    403 if they may see it but not do what needs `needed`."""
    try:
        record = controller.load(set_id)
        share = controller.share_of(set_id, user.id) if record and record["owner_id"] != user.id else None
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
    level = level_of(record["owner_id"], record.get("everyone") or "none", user.id, share) if record else None
    if level is None:
        raise HTTPException(404, "Corrected copy not found.")
    if not allows(level, needed):
        raise HTTPException(403, REFUSALS[needed])
    record["permission"] = level
    return record


def _current(controller: BoxSetDataController, set_id: int, level: str = "owner") -> BoxSet:
    try:
        record = controller.load(set_id)
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
    if record is None:  # deleted while this request ran
        raise HTTPException(404, "Corrected copy not found.")
    return build({**record, "permission": level})


def _conflict(controller: BoxSetDataController, set_id: int, level: str) -> JSONResponse:
    current = _current(controller, set_id, level)
    body = BoxSetConflict(detail="Someone else changed this copy since you opened it. Reload to see their changes.",
                          current=current)
    return JSONResponse(status_code=409, content=body.model_dump(mode="json"))


@router.post("/box-sets", response_model=BoxSet, status_code=status.HTTP_201_CREATED,
             responses={200: {"model": BoxSet, "description": "The copy already existed"}, 422: {"model": ApiError},
                        **ERRORS})
def create_box_set(request: BoxSetCreate, user: AuthenticatedWrite, controller: Controller,
                   response: Response) -> BoxSet:
    """Open your corrected copy of one of your analyses or of a corpus tablet, making it the first time:
    an analysis from the model's boxes, a tablet from the model's or the scholars' (`start`).
    A tablet may have several copies: `new` makes another (with an optional `title`) instead of
    opening your most recently changed one."""
    if request.tablet is not None:
        set_id, created = _tablet_copy(request, user, controller)
        if not created:
            response.status_code = status.HTTP_200_OK
        return _current(controller, set_id)
    try:
        made = controller.create_from_analysis(user.id, request.analysis_id)
    except NotEditable as error:
        raise HTTPException(422, str(error)) from error
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
    if made is None:
        raise HTTPException(404, "Analysis not found.")
    set_id, created = made
    if not created:
        response.status_code = status.HTTP_200_OK
    return _current(controller, set_id)


def _tablet_copy(request: BoxSetCreate, user: UserPublic, controller: BoxSetDataController) -> tuple[int, bool]:
    slug = request.tablet
    try:
        existing = None if request.new else controller.find_for_tablet(user.id, slug)
        if existing is not None:
            return existing, False
        index = glyph_index.get_index()
        path = glyph_index.tracing_path(slug) if slug in index.slugs else None
        if path is None:
            raise HTTPException(404, "Tablet not found.")
        signs = corpus.scholar_signs(index, slug) if request.start == "scholar" else corpus.model_signs(slug, path)
        width, height = corpus.image_size(path)
        return controller.create_from_tablet(user.id, slug, request.start,
                                             [sign.model_dump(mode="json") for sign in signs], width, height,
                                             new=request.new, title=request.title)
    except glyph_index.CorpusMissing as error:
        raise HTTPException(503, str(error)) from error
    except (corpus.ReaderMissing, corpus.ReaderBusy) as error:
        raise HTTPException(503, str(error)) from error
    except (FileNotFoundError, RuntimeError) as error:
        raise HTTPException(503, "The sign reader is unavailable.") from error
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error


@router.get("/tablets/{slug}/box-set", response_model=BoxSet, responses=ERRORS)
def tablet_box_set(slug: Annotated[str, Path(pattern=r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$", max_length=64)],
                   user: CurrentUser, controller: Controller) -> BoxSet:
    """Your most recently changed copy of a corpus tablet, if you made one (404 otherwise).
    GET /tablets/{slug}/versions lists all of them."""
    try:
        set_id = controller.find_for_tablet(user.id, slug)
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
    if set_id is None:
        raise HTTPException(404, "Corrected copy not found.")
    return build(access(controller, set_id, user))


@router.get("/analysis/{analysis_id}/box-set", response_model=BoxSet, responses=ERRORS)
def analysis_box_set(analysis_id: Identifier, user: CurrentUser, controller: Controller) -> BoxSet:
    """Your corrected copy of an analysis, if you made one (404 otherwise)."""
    try:
        set_id = controller.find_for_analysis(user.id, analysis_id)
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
    if set_id is None:
        raise HTTPException(404, "Corrected copy not found.")
    return build(access(controller, set_id, user))


@router.get("/box-sets/{set_id}", response_model=BoxSet, responses=ERRORS)
def get_box_set(set_id: Identifier, user: CurrentUser, controller: Controller) -> BoxSet:
    return build(access(controller, set_id, user))


@router.patch("/box-sets/{set_id}", response_model=BoxSet,
              responses={409: {"model": BoxSetConflict}, 422: {"model": ApiError}, **ERRORS})
def edit_box_set(set_id: Identifier, edit: BoxSetEdit, user: AuthenticatedWrite, controller: Controller):
    """Apply one save: add, move, resize, relabel and delete boxes. All or nothing."""
    level = access(controller, set_id, user, "edit")["permission"]
    try:
        controller.apply(set_id, user.id, edit.version, edit.changes, catalogue_sign)
    except StaleVersion:
        return _conflict(controller, set_id, level)
    except EditError as error:
        raise HTTPException(422, str(error)) from error
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
    return _current(controller, set_id, level)


@router.delete("/box-sets/{set_id}", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS)
def delete_box_set(set_id: Identifier, user: AuthenticatedWrite, controller: Controller) -> Response:
    """Throw the copy away, with its history and shares. The analysis itself stays."""
    access(controller, set_id, user, "owner")
    try:
        controller.delete(set_id)
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/box-sets/{set_id}/changes", response_model=BoxChangePage, responses=ERRORS)
def box_set_changes(set_id: Identifier, user: CurrentUser, controller: Controller,
                    limit: Annotated[int, Query(ge=1, le=200)] = 50,
                    before: Annotated[int | None, Query(gt=0, le=2**64 - 1)] = None) -> BoxChangePage:
    """Every change to the copy, newest first."""
    access(controller, set_id, user)
    try:
        rows = controller.changes(set_id, limit, before)
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
    items = [BoxChange(
        id=row["id"], author=Author(id=row["author_id"], username=row["username"]),
        created_at=row["created_at"].replace(tzinfo=timezone.utc), version=row["version"],
        action=row["action"], box_id=row["box_id"],
        before=BoxState(**row["before_state"]) if row["before_state"] else None,
        after=BoxState(**row["after_state"]), reverts=row["reverts_id"], reverted_by=row["reverted_by_id"],
    ) for row in rows[:limit]]
    return BoxChangePage(items=items, next_before=items[-1].id if len(rows) > limit else None)


@router.post("/box-sets/{set_id}/changes/{change_id}/revert", response_model=BoxSet,
             responses={409: {"model": BoxSetConflict}, 422: {"model": ApiError}, **ERRORS})
def revert_change(set_id: Identifier, change_id: Identifier, request: Revert, user: AuthenticatedWrite,
                  controller: Controller):
    """Undo one change. Refused if the box was changed again since, or the change was already undone."""
    level = access(controller, set_id, user, "edit")["permission"]
    try:
        controller.revert(set_id, user.id, change_id, request.version, catalogue_sign)
    except StaleVersion:
        return _conflict(controller, set_id, level)
    except MissingChange as error:
        raise HTTPException(404, "Change not found.") from error
    except EditError as error:
        raise HTTPException(422, str(error)) from error
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
    return _current(controller, set_id, level)


@router.get("/box-sets/{set_id}/image", response_class=FileResponse,
            responses={200: {"content": {"image/png": {}, "image/jpeg": {}}, "description": "The tablet image"},
                       **ERRORS})
def box_set_image(set_id: Identifier, user: CurrentUser, controller: Controller) -> FileResponse:
    """The image the copy's boxes are drawn on."""
    record = access(controller, set_id, user)
    if record["tablet_slug"] is not None:
        # A corpus tablet's published tracing.
        try:
            path = glyph_index.tracing_path(record["tablet_slug"])
        except glyph_index.CorpusMissing as error:
            raise HTTPException(503, str(error)) from error
        if path is None:
            raise HTTPException(404, "Image not found.")
        return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})
    try:
        stored = controller.image(set_id)
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
    # #93's image storage: the kept upload, never cached, served as the type it was checked to be.
    return tablet_response(stored)
