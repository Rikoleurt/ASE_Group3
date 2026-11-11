import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# Plain text: tabs and newlines are fine, other control characters are not.
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


class GlyphBox(BaseModel):
    """Top-left corner and size as fractions of the tablet drawing."""
    x: float
    y: float
    w: float
    h: float


class GlyphOccurrence(BaseModel):
    tablet: str  # URL-safe tablet id (slug), e.g. "HT-13"
    title: str  # corpus id, e.g. "HT 13"
    position: int
    sign: str
    reading: str | None
    role: str | None
    similarity: float | None  # cosine similarity to the reference; None without embeddings
    outlier: bool  # far from the centre of this sign's class: a possible mislabel
    outlier_score: float | None
    crop_url: str | None
    thumbnail_url: str | None
    box: GlyphBox | None


class GlyphOccurrencePage(BaseModel):
    sign: str
    total: int
    limit: int
    offset: int
    ranked_by: str  # "glyph" (a reference glyph), "centre" (typical first) or "none" (corpus order)
    items: list[GlyphOccurrence]
    credit: dict


class AnnotationTarget(BaseModel):
    tablet: str = Field(pattern=r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$", max_length=64)
    position: int = Field(ge=0, le=1_000_000)


class AnnotationCreate(BaseModel):
    body: str = Field(max_length=10_000)
    targets: list[AnnotationTarget] = Field(min_length=1, max_length=200)

    @field_validator("body")
    @classmethod
    def plain_trimmed_body(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= 2000:
            raise ValueError("The comment must be 1 to 2000 characters.")
        if _CONTROL.search(value):
            raise ValueError("The comment must be plain text.")
        return value

    @field_validator("targets")
    @classmethod
    def unique_targets(cls, value: list[AnnotationTarget]) -> list[AnnotationTarget]:
        if len({(t.tablet, t.position) for t in value}) != len(value):
            raise ValueError("Each occurrence can be listed once.")
        return value


class AnnotationAuthor(BaseModel):
    id: int
    username: str


class Annotation(BaseModel):
    id: int
    sign: str
    body: str
    created_at: datetime  # UTC
    author: AnnotationAuthor
    targets: list[AnnotationTarget]


class AnnotationPage(BaseModel):
    items: list[Annotation]
    next_before: int | None
