from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from fastapi.responses import FileResponse
from mysql.connector import Error as DatabaseError

from backend.app.auth import AuthenticatedWrite, CurrentUser
from backend.app.data_controller.community_data_controller import (
    CommunityDataController,
    DuplicateDiscussionTitle,
)
from backend.app.data_controller.mention_data_controller import MentionDataController
from backend.app.image_storage import crop_symbol, image_path
from backend.app.mentions import InvalidMention
from backend.app.model.analysis import ApiError
from backend.app.model.community import (
    CommunityCommentCreate,
    DiscussionComment,
    DiscussionCreate,
    DiscussionDetail,
    DiscussionFilter,
    DiscussionPage,
    DiscussionSummary,
    VoteSet,
    VoteState,
)
from backend.app.model.mention import MentionPage, SymbolPreview
from backend.app.notifications import notify, quote

router = APIRouter(prefix="/community", tags=["community"], responses={404: {"model": ApiError}, 503: {"model": ApiError}})
Controller = Annotated[CommunityDataController, Depends(CommunityDataController)]
MentionController = Annotated[MentionDataController, Depends(MentionDataController)]
SignId = Annotated[int, Path(ge=0, le=2**63 - 1)]
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
        result = controller.create_discussion(user.id, payload.analysis_id, payload.title, payload.sign_id)
    except (FileNotFoundError, DuplicateDiscussionTitle) as error:
        raise HTTPException(409, str(error)) from error
    if result is None:
        raise HTTPException(404, "Analysis or symbol not found.")
    discussion, created = result
    if not created:
        response.status_code = 200
    return discussion


@router.get("/discussions", response_model=DiscussionPage)
def discussions(controller: Controller, limit: Annotated[int, Query(ge=1, le=100)] = 30,
                filter_by: DiscussionFilter = "recent",
                author_id: Annotated[int | None, Query(gt=0, le=2**64 - 1)] = None,
                q: Annotated[str, Query(max_length=255)] = "",
                cursor: Annotated[str | None, Query(min_length=1, max_length=4096)] = None):
    try:
        if author_id is not None and (filter_by != "author" or q.strip()):
            raise ValueError("Use the author filter without text for an exact author mention.")
        if filter_by == "tablet":
            return controller.get_discussion_by_tablet_name(q, limit, cursor)
        if filter_by == "author":
            if author_id is not None:
                return controller.get_discussion_by_author(q, limit, cursor, author_id)
            return controller.get_discussion_by_author(q, limit, cursor)
        if q.strip():
            raise ValueError("Choose tablet or author to search by text.")
        return controller.get_discussion_by_most_recent_date(limit, cursor)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.get("/discussions/{discussion_id}", response_model=DiscussionDetail, response_model_exclude_none=True)
def discussion(discussion_id: DiscussionId, controller: Controller):
    result = controller.get_discussion(discussion_id)
    if result is None:
        raise HTTPException(404, "Discussion not found.")
    return result


@router.get("/discussions/{discussion_id}/image", response_class=FileResponse)
def image(discussion_id: DiscussionId, controller: Controller):
    saved = controller.get_image(discussion_id)
    if saved is None:
        raise HTTPException(404, "Discussion image not found.")
    key, image_format, box = saved
    if box is None:
        return tablet_response((key, image_format))
    try:
        content = crop_symbol(key, box)
    except (OSError, ValueError) as error:
        raise HTTPException(404, "Symbol image not found.") from error
    return Response(content, media_type="image/png",
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/discussions/{discussion_id}/comments", response_model=list[DiscussionComment])
def comments(discussion_id: DiscussionId, controller: Controller):
    result = controller.list_comments(discussion_id)
    if result is None:
        raise HTTPException(404, "Discussion not found.")
    return result


@router.post("/discussions/{discussion_id}/comments", response_model=DiscussionComment, status_code=201,
             responses={401: {"model": ApiError}, 403: {"model": ApiError}})
def comment(discussion_id: DiscussionId, payload: CommunityCommentCreate, user: AuthenticatedWrite, controller: Controller):
    try:
        result = controller.add_comment(discussion_id, user.id, payload.body)
    except InvalidMention as error:
        raise HTTPException(422, str(error)) from error
    if result is None:
        raise HTTPException(404, "Discussion not found.")
    mentioned = [mention.user_id for mention in result.mentions if mention.kind == "user" and mention.available]
    notify(mentioned, "mention", user.id, f"{user.username} mentioned you in a discussion: {quote(result.body)}",
           f"/community/{discussion_id}")
    return result


@router.get("/discussions/{discussion_id}/mentions", response_model=MentionPage,
            responses={401: {"model": ApiError}})
def mention_suggestions(discussion_id: DiscussionId, user: CurrentUser, controller: MentionController,
                        kind: Annotated[Literal["user", "symbol"], Query(alias="type")] = "symbol",
                        q: Annotated[str, Query(max_length=255)] = "",
                        limit: Annotated[int, Query(ge=1, le=20)] = 10,
                        after: Annotated[int, Query(ge=-1, le=2**64 - 1)] = -1):
    result = controller.search_mentions(discussion_id, kind, q, limit, after)
    if result is None:
        raise HTTPException(404, "Discussion not found.")
    return result


@router.get("/symbols/{analysis_id}/{sign_id}", response_model=SymbolPreview, response_model_exclude_none=True)
def symbol_preview(analysis_id: DiscussionId, sign_id: SignId, controller: MentionController):
    result = controller.get_public_symbol(analysis_id, sign_id)
    if result is None:
        raise HTTPException(404, "Public symbol not found.")
    return SymbolPreview(target=result.target, symbol=result.symbol)


@router.get("/symbols/{analysis_id}/{sign_id}/image", response_class=Response,
            responses={200: {"content": {"image/png": {"schema": {"type": "string", "format": "binary"}}}}})
def symbol_image(analysis_id: DiscussionId, sign_id: SignId, controller: MentionController):
    result = controller.get_public_symbol(analysis_id, sign_id)
    if result is None or result.storage_key is None:
        raise HTTPException(404, "Public symbol image not found.")
    try:
        content = crop_symbol(result.storage_key, result.symbol.box)
    except (OSError, ValueError) as error:
        raise HTTPException(404, "Public symbol image not found.") from error
    return Response(content, media_type="image/png",
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/discussions/{discussion_id}/vote", response_model=VoteState,
            responses={401: {"model": ApiError}})
def get_vote(discussion_id: DiscussionId, user: CurrentUser, controller: Controller):
    try:
        result = controller.get_vote(discussion_id, user.id)
    except DatabaseError as error:
        raise HTTPException(503, "Community storage is unavailable.") from error
    if result is None:
        raise HTTPException(404, "Discussion not found.")
    return result


@router.put("/discussions/{discussion_id}/vote", response_model=VoteState,
            responses={401: {"model": ApiError}, 403: {"model": ApiError}, 422: {"description": "Invalid vote"}})
def set_vote(discussion_id: DiscussionId, payload: VoteSet, user: AuthenticatedWrite, controller: Controller):
    try:
        result = controller.set_vote(discussion_id, user.id, payload.value)
    except DatabaseError as error:
        raise HTTPException(503, "Community storage is unavailable.") from error
    if result is None:
        raise HTTPException(404, "Discussion not found.")
    return result
