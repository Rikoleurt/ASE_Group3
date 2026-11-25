"""Edition releases, votes and the admin override (scholars' workbench, story E)."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from backend.app.model.analysis import Box
from backend.app.model.box_set import BoxSource, MergedFrom, Reading

MIN_REASON = 15  # characters: an override or a removal of voting rights must say why


def _reason(value: str) -> str:
    value = " ".join(value.split())
    if len(value) < MIN_REASON:
        raise ValueError(f"Give a reason of at least {MIN_REASON} characters.")
    return value


class ReleaseCreate(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)  # what changed, for voters


class ReleasedBox(BaseModel):
    id: int
    box: Box
    sign: str | None
    source: BoxSource | None = None


class Release(BaseModel):
    """A snapshot of an edition: it never changes, so votes, citations and exports point at it."""

    id: int
    edition_id: int  # the edition (a copy of kind "edition") it was released from
    number: int  # 1, 2, ... per edition
    tablet: str  # slug
    title: str | None
    notes: str | None
    owner: str  # the edition's owner
    version: int  # the edition's version when released
    width: int
    height: int
    image_url: str
    created_at: datetime
    boxes: list[ReleasedBox]
    merged_from: list[MergedFrom] = []
    contributors: list[str] = []
    reading: Reading | None = None  # worked out from the boxes (only on GET /editions/{id})


class ReleaseSummary(BaseModel):
    id: int
    edition_id: int
    number: int
    title: str | None
    notes: str | None
    owner: str
    box_count: int
    created_at: datetime


class EditionVotes(ReleaseSummary):
    votes: int  # by accounts that may vote
    reviewer_votes: int  # of those, by reviewers
    accepted: bool = False


class Override(BaseModel):
    release_id: int
    admin: str | None  # username
    comment: str
    created_at: datetime


class Voting(BaseModel):
    allowed: bool
    reason: str | None = None  # why not, when not allowed


class TabletEditions(BaseModel):
    """The released editions of a tablet that are open to everyone, with their votes."""

    slug: str
    items: list[EditionVotes]  # most votes first
    accepted_release_id: int | None  # the override's, else the most backed (the earlier on a tie)
    override: Override | None
    my_vote: int | None  # the release you back, if any
    voting: Voting


class VoteRequest(BaseModel):
    release_id: int = Field(gt=0)


class OverrideRequest(BaseModel):
    release_id: int = Field(gt=0)
    comment: str = Field(max_length=1000)

    _check = field_validator("comment")(classmethod(lambda cls, value: _reason(value)))


class ClearOverride(BaseModel):
    comment: str = Field(max_length=1000)

    _check = field_validator("comment")(classmethod(lambda cls, value: _reason(value)))


class VotingRights(BaseModel):
    can_vote: bool
    reason: str | None = None  # the latest change's reason
    changed_by: str | None = None
    changed_at: datetime | None = None


class VotingRightsChange(BaseModel):
    can_vote: bool
    reason: str = Field(max_length=500)

    _check = field_validator("reason")(classmethod(lambda cls, value: _reason(value)))
