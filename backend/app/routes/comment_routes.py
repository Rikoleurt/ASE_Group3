"""Comments on a corrected copy (#86): a thread on each box, and one on the whole copy.

Anyone who can see the copy reads them; Comment access or higher writes them. An author can
delete their own comment, and the owner and managers can delete any (to moderate).
"""
from datetime import timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Response, status
from mysql.connector import Error as DatabaseError
from pydantic import BaseModel, Field, field_validator

from backend.app.auth import AuthenticatedWrite, CurrentUser
from backend.app.model.analysis import ApiError
from backend.app.model.box_set import Author
from backend.app.routes.box_set_routes import UNAVAILABLE, Controller, access
from backend.app.sharing import allows

router = APIRouter(tags=["box set comments"])
Identifier = Annotated[int, Path(gt=0, le=2**64 - 1)]
ERRORS = {code: {"model": ApiError} for code in (401, 403, 404, 503)}


class CommentCreate(BaseModel):
    box_id: int | None = Field(default=None, gt=0, le=2**64 - 1)  # None: about the whole copy
    body: str = Field(max_length=4000)

    @field_validator("body")
    @classmethod
    def plain_text(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= 2000:
            raise ValueError("A comment is 1 to 2000 characters.")
        return value


class Comment(BaseModel):
    id: int
    box_id: int | None
    author: Author
    body: str
    created_at: str
    can_delete: bool  # yours, or you own or manage the copy


def _comment(row: dict, user_id: int, moderator: bool) -> Comment:
    return Comment(id=row["id"], box_id=row["box_id"], author=Author(id=row["author_id"], username=row["username"]),
                   body=row["body"], created_at=row["created_at"].replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
                   can_delete=moderator or row["author_id"] == user_id)


@router.get("/box-sets/{set_id}/comments", response_model=list[Comment], responses=ERRORS)
def list_comments(set_id: Identifier, user: CurrentUser, controller: Controller,
                  box_id: Annotated[int | None, Query(gt=0, le=2**64 - 1)] = None) -> list[Comment]:
    """The copy's comments, oldest first; with box_id, only that box's thread."""
    record = access(controller, set_id, user)
    try:
        rows = controller.comments(set_id, box_id)
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
    moderator = allows(record["permission"], "manage")
    return [_comment(row, user.id, moderator) for row in rows]


@router.post("/box-sets/{set_id}/comments", response_model=Comment, status_code=status.HTTP_201_CREATED,
             responses={**ERRORS, 422: {"model": ApiError}})
def add_comment(set_id: Identifier, request: CommentCreate, user: AuthenticatedWrite, controller: Controller) -> Comment:
    record = access(controller, set_id, user, "comment")
    if request.box_id is not None and not any(box["id"] == request.box_id and not box["deleted"] for box in record["boxes"]):
        raise HTTPException(422, f"Box {request.box_id} is not on this copy.")
    try:
        row = controller.add_comment(set_id, request.box_id, user.id, request.body)
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
    return _comment(row, user.id, allows(record["permission"], "manage"))


@router.delete("/box-sets/{set_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS)
def delete_comment(set_id: Identifier, comment_id: Identifier, user: AuthenticatedWrite, controller: Controller) -> Response:
    record = access(controller, set_id, user)
    try:
        found = controller.comment(set_id, comment_id)
        if found is None:
            raise HTTPException(404, "Comment not found.")
        if found["author_id"] != user.id and not allows(record["permission"], "manage"):
            raise HTTPException(403, "You can only delete your own comments.")
        controller.delete_comment(comment_id)
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
