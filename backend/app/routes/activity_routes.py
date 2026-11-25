"""Activity bubbles on corpus glyphs (scholars' workbench, story I): how much others have said or
changed about each glyph of a tablet since you last opened it; opening a glyph clears its bubble."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from mysql.connector import Error as DatabaseError
from pydantic import BaseModel, Field

from backend.app.auth import AuthenticatedWrite, CurrentUser
from backend.app.data_controller.activity_data_controller import ActivityDataController
from backend.app.model.analysis import ApiError

router = APIRouter(tags=["activity"])
Slug = Annotated[str, Path(pattern=r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$", max_length=64)]
ERRORS = {code: {"model": ApiError} for code in (401, 403, 422, 503)}
UNAVAILABLE = "Activity is unavailable. Please try again."


def get_activity_data_controller() -> ActivityDataController:
    return ActivityDataController()


Activity = Annotated[ActivityDataController, Depends(get_activity_data_controller)]


class GlyphActivity(BaseModel):
    tablet: str
    counts: dict[int, int]  # position -> others' comments and changes since you last opened it


class GlyphSeen(BaseModel):
    tablet: str = Field(pattern=r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$", max_length=64)
    position: int = Field(ge=0, le=1_000_000)


@router.get("/tablets/{slug}/glyph-activity", response_model=GlyphActivity, responses=ERRORS)
def glyph_activity(slug: Slug, user: CurrentUser, activity: Activity) -> GlyphActivity:
    """Per glyph (by the scholars' position): others' glyph comments, and comments and saved
    changes on boxes that started as that sign in copies you can open, since you last opened it
    (the last two weeks for a glyph you never opened)."""
    try:
        return GlyphActivity(tablet=slug, counts=activity.glyph_activity(user.id, slug))
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error


@router.post(
    "/glyphs/seen",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=ERRORS,
)
def glyph_seen(request: GlyphSeen, user: AuthenticatedWrite, activity: Activity) -> Response:
    """You opened this glyph: its bubble starts again from now."""
    try:
        activity.mark_seen(user.id, f"{request.tablet}:{request.position}")
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
