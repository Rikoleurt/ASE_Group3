"""The versions of a corpus tablet and how they compare (scholars' workbench, story C)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from backend.app.model.analysis import Box

VersionKind = Literal["scholar", "model", "copy", "edition"]


class TabletVersion(BaseModel):
    key: str  # "scholar", "model" or "copy:<id>": what /compare takes in `v`
    kind: VersionKind
    title: str | None = None
    owner: str | None = None  # username, for copies
    mine: bool = False
    permission: Literal["view", "comment", "edit", "manage", "owner"] | None = None  # for copies
    needs_login: bool = False  # the model's boxes run the reader, so they need a login
    box_count: int | None = None  # unknown for the model until it has read the tablet
    version: int | None = None
    updated_at: datetime | None = None


class TabletVersions(BaseModel):
    slug: str
    tablet: str  # corpus id, e.g. "HT 13"
    items: list[TabletVersion]  # the scholars', the model's, then the copies you can open


class VersionBox(BaseModel):
    id: int  # the box's id in its version (the sign's position for the scholars')
    box: Box
    sign: str | None
    label: str | None = None  # e.g. "AB81 (ku)"


class CompareCluster(BaseModel):
    box: Box  # where the boxes are: their mean
    members: dict[str, VersionBox]  # version key -> its box here
    status: Literal["agree", "differs", "missing"]
    moved: bool  # two of its boxes overlap less than 80%


class Agreement(BaseModel):
    a: str
    b: str
    same: int  # places where both have a box with the same sign
    total: int  # places where either has a box


class TabletComparison(BaseModel):
    slug: str
    tablet: str
    width: int
    height: int
    image_url: str
    versions: list[TabletVersion]  # in the order asked for
    clusters: list[CompareCluster]  # in reading order
    agreement: list[Agreement]  # every pair of versions


class MergeSource(BaseModel):
    key: str = Field(pattern=r"^(scholar|model|copy:[1-9][0-9]{0,19})$")
    version: int | None = Field(default=None, ge=0)  # a copy's version as the merge page saw it


class MergeRequest(BaseModel):
    """Merge versions of a tablet into a new edition (workbench, story D). `picks` has one entry per
    place of GET /compare for these sources in this order: the version whose box to keep there,
    or null to leave the place out."""

    tablet: str = Field(pattern=r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$", max_length=64)
    title: str | None = Field(default=None, min_length=1, max_length=120)
    sources: list[MergeSource] = Field(min_length=2, max_length=6)
    picks: list[str | None] = Field(max_length=2000)

    @field_validator("title")
    @classmethod
    def tidy_title(cls, title: str | None) -> str | None:
        if title is None:
            return None
        return " ".join(title.split()) or None
