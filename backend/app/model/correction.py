from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from backend.app.model.analysis import Box

ReviewStatus = Literal["pending", "approved", "rejected"]


class CatalogueSign(BaseModel):
    sign: str  # sign ID, e.g. "AB81"
    name: str  # e.g. "AB81 (ku)"
    glyph: str | None  # the Unicode Linear A character, when there is one
    reading: str | None = None  # the sign's phonetic value, e.g. "ku", when it has one
    preview_url: str | None = None  # a small picture: its most typical corpus drawing or its character


class CorrectionCreate(BaseModel):
    """Either a replacement sign from the catalogue, or a flag that the reading is uncertain."""
    sign_id: int = Field(gt=0)  # the detected sign's id in the analysis
    proposed_sign: str | None = Field(default=None, min_length=1, max_length=32)
    uncertain: bool = False
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def one_kind(self):
        if (self.proposed_sign is None) == (not self.uncertain):
            raise ValueError("Give either proposed_sign or uncertain: true, not both.")
        return self


class SignCorrection(BaseModel):
    id: int
    analysis_id: int
    sign_id: int
    created_at: datetime
    box: Box  # the sign's region, as fractions of the image size
    original_sign: str | None
    original_label: str
    original_confidence: float
    model_version: str
    proposed_sign: str | None
    uncertain: bool
    note: str | None
    status: ReviewStatus


class CorrectionReview(BaseModel):
    decision: Literal["approved", "rejected"]


class CorrectionExportSign(BaseModel):
    """One sign as in the training annotations (la.signboxes): its ID and pixel box."""
    sign: str
    xyxy: list[int]  # x0, y0, x1, y1 in pixels of the uploaded image
    source: Literal["correction"] = "correction"
    original_sign: str | None
    model_version: str
    correction_id: int


class CorrectionExportTablet(BaseModel):
    """Approved corrections of one analysis, grouped like a tablet in the training annotations."""
    analysis_id: int
    filename: str
    width: int
    height: int
    signs: list[CorrectionExportSign]
