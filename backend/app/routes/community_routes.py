from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from fastapi.responses import FileResponse

from backend.app.auth import AuthenticatedWrite
from backend.app.data_controller.community_data_controller import CommunityDataController
from backend.app.image_storage import image_path
from backend.app.model.analysis import ApiError
from backend.app.model.community import (DiscussionCreate, DiscussionSummary, DiscussionPage,
                                         DiscussionDetail, CommunityCommentCreate, DiscussionComment)

router = APIRouter(prefix="/community", tags=["community"], responses={404: {"model": ApiError}, 503: {"model": ApiError}})
Controller = Annotated[CommunityDataController, Depends(CommunityDataController)]
DiscussionId = Annotated[int, Path(gt=0, le=2**64 - 1)]


def tablet_response(image: tuple[str, str] | None) -> FileResponse:
    if image is None:
        raise HTTPException(404, "Tablet image not found.")
    path = image_path(image[0])
    if not path.is_file():
        raise HTTPException(404, "Tablet image not found.")
    return FileResponse(path, media_type={"PNG": "image/png", "JPEG": "image/jpeg"}[image[1]],
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.post("/discussions", response_model=DiscussionSummary, status_code=201,
             responses={200: {"model": DiscussionSummary}, 401: {"model": ApiError},
                        403: {"model": ApiError}, 409: {"model": ApiError}})
def share(payload: DiscussionCreate, user: AuthenticatedWrite, controller: Controller, response: Response):
    try:
        result = controller.create_discussion(user.id, payload.analysis_id, payload.title)
    except FileNotFoundError as error:
        raise HTTPException(409, str(error)) from error
    if result is None:
        raise HTTPException(404, "Analysis not found.")
    discussion, created = result
    if not created:
        response.status_code = 200
    return discussion


@router.get("/discussions", response_model=DiscussionPage)
def discussions(controller: Controller, limit: Annotated[int, Query(ge=1, le=100)] = 20,
                before: Annotated[int | None, Query(gt=0, le=2**64 - 1)] = None):
    rows = controller.list_discussions(limit, before)
    return DiscussionPage(items=rows[:limit], next_before=rows[limit - 1].id if len(rows) > limit else None)


@router.get("/discussions/{discussion_id}", response_model=DiscussionDetail, response_model_exclude_none=True)
def discussion(discussion_id: DiscussionId, controller: Controller):
    result = controller.get_discussion(discussion_id)
    if result is None:
        raise HTTPException(404, "Discussion not found.")
    return result


@router.get("/discussions/{discussion_id}/image", response_class=FileResponse)
def image(discussion_id: DiscussionId, controller: Controller):
    return tablet_response(controller.get_image(discussion_id))


@router.get("/discussions/{discussion_id}/comments", response_model=list[DiscussionComment])
def comments(discussion_id: DiscussionId, controller: Controller):
    result = controller.list_comments(discussion_id)
    if result is None:
        raise HTTPException(404, "Discussion not found.")
    return result


@router.post("/discussions/{discussion_id}/comments", response_model=DiscussionComment, status_code=201,
             responses={401: {"model": ApiError}, 403: {"model": ApiError}})
def comment(discussion_id: DiscussionId, payload: CommunityCommentCreate, user: AuthenticatedWrite, controller: Controller):
    result = controller.add_comment(discussion_id, user.id, payload.body)
    if result is None:
        raise HTTPException(404, "Discussion not found.")
    return result
