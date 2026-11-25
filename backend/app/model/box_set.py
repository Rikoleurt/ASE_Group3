"""Corrected copies of a tablet's boxes (#83): what the API accepts and returns."""
from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, model_validator

from backend.app.model.analysis import Box, Candidate, DetectedSign, Formula, Line

Origin = Literal["model", "scholar", "user"]
Action = Literal["add", "update", "delete", "revert"]
SignId = Annotated[str, Field(min_length=1, max_length=32)]
# Smallest box side, as a fraction of the image: about 2 px on a 1000 px tablet.
MIN_SIDE = 0.002
MAX_CHANGES = 500
MAX_BOXES = 2000


class EditBox(Box):
    """A box from the editor: inside the image (a hair of rounding allowed) and not degenerate.
    NaN would pass every comparison below, so it is refused outright (#98)."""
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)
    w: float = Field(allow_inf_nan=False)
    h: float = Field(allow_inf_nan=False)

    @model_validator(mode="after")
    def inside_the_image(self):
        slack = 1e-6
        if self.x < -slack or self.y < -slack or self.x + self.w > 1 + slack or self.y + self.h > 1 + slack:
            raise ValueError("The box must lie inside the image.")
        if self.w < MIN_SIDE or self.h < MIN_SIDE:
            raise ValueError("The box is too small.")
        return self


class AddBox(BaseModel):
    op: Literal["add"]
    box: EditBox
    sign: SignId | None = None  # None: drawn but not named yet


class UpdateBox(BaseModel):
    """Move or resize a box, and/or set its sign. A field left out stays as it is; sign: null clears it."""
    op: Literal["update"]
    box_id: int = Field(gt=0)
    box: EditBox | None = None
    sign: SignId | None = None

    @model_validator(mode="after")
    def changes_something(self):
        if "box" not in self.model_fields_set and "sign" not in self.model_fields_set:
            raise ValueError("Give box, sign or both.")
        if "box" in self.model_fields_set and self.box is None:
            raise ValueError("box cannot be null.")
        return self


class DeleteBox(BaseModel):
    op: Literal["delete"]
    box_id: int = Field(gt=0)


Change = Annotated[Union[AddBox, UpdateBox, DeleteBox], Field(discriminator="op")]


class BoxSetEdit(BaseModel):
    """One save from the editor: the version it started from, and its changes in order."""
    version: int = Field(ge=0)
    changes: list[Change] = Field(min_length=1, max_length=MAX_CHANGES)


class Revert(BaseModel):
    version: int = Field(ge=0)


class BoxSetCreate(BaseModel):
    """Start a corrected copy of one of your analyses (always from the model's boxes) or of a
    corpus tablet (#82), from the model's boxes or the scholars'. Give analysis_id or tablet."""
    analysis_id: int | None = Field(default=None, gt=0, le=2**64 - 1)
    tablet: str | None = Field(default=None, pattern=r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$", max_length=64)
    start: Literal["model", "scholar"] = "model"
    new: bool = False  # a tablet: make another copy rather than open your latest one
    title: str | None = Field(default=None, min_length=1, max_length=120)  # a name for a new tablet copy

    @model_validator(mode="after")
    def one_source(self):
        if (self.analysis_id is None) == (self.tablet is None):
            raise ValueError("Give analysis_id or tablet, not both.")
        if self.analysis_id is not None and self.start != "model":
            raise ValueError("An upload has no scholars' boxes: start from the model.")
        if self.analysis_id is not None and (self.new or self.title):
            raise ValueError("An upload has one corrected copy: new copies and titles are for tablets.")
        if self.title is not None:
            self.title = " ".join(self.title.split()) or None
        return self


class BoxSource(BaseModel):
    """Where a box came from: the scholars' or the model's sign it started as, or another
    copy's box at a version (merged editions), with that box's author for credit."""
    kind: Literal["scholar", "model", "copy"]
    box_id: int | None = None  # the sign's id there: its position for the scholars', the box's id in a copy
    copy_id: int | None = None
    version: int | None = None
    author: str | None = None  # username


class MergedFrom(BaseModel):
    key: str  # "scholar", "model" or "copy:<id>"
    kind: Literal["scholar", "model", "copy", "edition"]
    title: str | None = None
    owner: str | None = None
    version: int | None = None  # the copy's version when it was merged


class EditedBox(BaseModel):
    id: int
    box: Box
    sign: str | None
    origin: Origin  # where the box first came from
    model_sign: str | None  # the sign when the copy was made (the model's or the scholars'); None for drawn boxes
    model_confidence: float | None  # the model's confidence; None for scholars' and drawn boxes
    candidates: list[Candidate]  # the model's top guesses, for the sign picker
    source: BoxSource | None = None  # None for boxes drawn by hand
    changed: bool  # moved, resized or relabelled since the copy was made (always True for drawn boxes)


class Reading(BaseModel):
    """The reading worked out from the corrected boxes, in the same shape as an analysis."""
    symbol_interpretation: str
    summary: str
    signs: list[DetectedSign]  # one per box, in reading order; a sign's id is its box's id
    lines: list[Line]
    formulas: list[Formula]


class BoxSetSource(BaseModel):
    kind: Literal["analysis", "tablet"]
    analysis_id: int | None = None
    tablet: str | None = None
    filename: str | None = None  # the upload's name, for the page title


class BoxSet(BaseModel):
    id: int
    owner: str  # username
    permission: Literal["view", "comment", "edit", "manage", "owner"]  # what you may do with it (#84)
    everyone: Literal["none", "view", "comment", "edit"]  # access for every logged-in user
    source: BoxSetSource
    title: str | None = None  # a tablet copy's name, if it has one
    kind: Literal["copy", "edition"] = "copy"  # an edition is merged from several versions (workbench)
    merged_from: list[MergedFrom] = []  # an edition's sources
    contributors: list[str] = []  # usernames: authors of merged boxes and everyone who saved a change
    start: Literal["model", "scholar"]
    version: int  # send it back with each edit; it goes up by one per save
    width: int
    height: int
    image_url: str
    created_at: datetime
    updated_at: datetime
    boxes: list[EditedBox]
    reading: Reading


class BoxSetConflict(BaseModel):
    detail: str
    current: BoxSet  # the copy as it is now, so the editor can reload


class Author(BaseModel):
    id: int | None  # None once the account is deleted
    username: str | None


class BoxState(BaseModel):
    """A box as one change left it."""
    box: Box
    sign: str | None
    deleted: bool = False


class BoxChange(BaseModel):
    id: int
    author: Author
    created_at: datetime
    version: int  # the copy's version this change produced
    action: Action
    box_id: int
    before: BoxState | None  # None when the box was added
    after: BoxState
    reverts: int | None  # the change this one undid
    reverted_by: int | None  # the change that undid this one


class BoxChangePage(BaseModel):
    items: list[BoxChange]  # newest first
    next_before: int | None  # pass as ?before= for older changes
