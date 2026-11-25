"""Corpus tablets (#82): the list, and a tablet's boxes from either source."""
from typing import Literal

from pydantic import BaseModel

from backend.app.model.analysis import DetectedSign, Formula, Line

Source = Literal["scholar", "model"]


class TabletItem(BaseModel):
    slug: str  # URL-safe id, e.g. "HT-13"
    tablet: str  # corpus id, e.g. "HT 13"
    signs: int  # signs with a published box


class TabletPage(BaseModel):
    items: list[TabletItem]
    total: int
    without_drawing: int = 0  # tablets with boxes whose drawing is not downloaded on this server
    hint: str | None = None  # how to download the missing drawings


class Credit(BaseModel):
    licence: str
    url: str
    text: str


class TabletBoxes(BaseModel):
    """A tablet's boxes and their reading, in the same shape as an analysis."""
    slug: str
    tablet: str
    source: Source
    width: int
    height: int
    image_url: str
    symbol_interpretation: str
    summary: str
    signs: list[DetectedSign]
    lines: list[Line]
    formulas: list[Formula]
    credit: Credit
