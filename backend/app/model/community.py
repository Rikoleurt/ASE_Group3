from datetime import datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from backend.app.model.analysis import AnalysisResult, DetectedSign

PositiveId = Annotated[int, Field(gt=0, le=2**64 - 1)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
CommentBody = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
DiscussionFilter = Literal["recent", "tablet", "author"]


class DiscussionCursor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    created_at: AwareDatetime
    id: Annotated[int, Field(strict=True, gt=0, le=2**64 - 1)]
    filter_by: DiscussionFilter
    q: Annotated[str, StringConstraints(max_length=255)]


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
    score: int = 0
    
class VoteSet(BaseModel):
    value: Literal[-1, 0, 1]

class VoteState(BaseModel):
    score: int
    my_vote: int

class DiscussionPage(BaseModel):
    items: list[DiscussionSummary]
    parents: list[DiscussionSummary] = Field(default_factory=list)
    next_cursor: str | None = None


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
