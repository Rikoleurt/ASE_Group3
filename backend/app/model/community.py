from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from backend.app.model.analysis import AnalysisResult, DetectedSign

PositiveId = Annotated[int, Field(gt=0, le=2**64 - 1)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
CommentBody = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class DiscussionCreate(BaseModel):
    analysis_id: PositiveId
    title: Title
    sign_id: Annotated[int, Field(ge=0, le=2**63 - 1)] | None = None


class DiscussionSummary(BaseModel):
    id: int
    analysis_id: int
    author_id: int
    author_username: str
    title: str
    created_at: datetime
    sign_id: int | None = None
    symbol_name: str | None = None
    tablet_filename: str = ""


class DiscussionPage(BaseModel):
    items: list[DiscussionSummary]
    next_before: int | None = None


class DiscussionDetail(DiscussionSummary):
    image_url: str
    result: AnalysisResult | None = None
    symbol: DetectedSign | None = None
    parent_discussion: DiscussionSummary | None = None
    symbol_discussions: list[DiscussionSummary] = Field(default_factory=list)


class CommunityCommentCreate(BaseModel):
    body: CommentBody


class DiscussionComment(BaseModel):
    id: int
    discussion_id: int
    author_id: int
    author_username: str
    created_at: datetime
    body: str
