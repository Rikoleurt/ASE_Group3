"""The versions of a corpus tablet and how they compare (scholars' workbench, story C)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

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
