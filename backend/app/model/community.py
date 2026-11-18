from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from backend.app.model.analysis import AnalysisResult

PositiveId = Annotated[int, Field(gt=0, le=2**64 - 1)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
CommentBody = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class DiscussionCreate(BaseModel):
    analysis_id: PositiveId
    title: Title


class DiscussionSummary(BaseModel):
    id: int
    analysis_id: int
    author_id: int
    author_username: str
    title: str
    created_at: datetime


class DiscussionPage(BaseModel):
    items: list[DiscussionSummary]
    next_before: int | None = None


class DiscussionDetail(DiscussionSummary):
    image_url: str
    result: AnalysisResult


class CommunityCommentCreate(BaseModel):
    body: CommentBody


class DiscussionComment(BaseModel):
    id: int
    discussion_id: int
    author_id: int
    author_username: str
    created_at: datetime
    body: str
