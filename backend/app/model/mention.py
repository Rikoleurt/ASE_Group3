from typing import Literal

from pydantic import BaseModel, Field

from backend.app.model.analysis import DetectedSign


class MentionTarget(BaseModel):
    key: str
    kind: Literal['user', 'symbol']
    label: str
    available: bool = True
    user_id: int | None = None
    analysis_id: int | None = None
    sign_id: int | None = None
    tablet_filename: str | None = None
    image_url: str | None = None
    discussion_id: int | None = None


class ResolvedMention(MentionTarget):
    token: str


class MentionPage(BaseModel):
    items: list[MentionTarget]
    next_after: int | None = None


class SymbolPreview(BaseModel):
    target: MentionTarget
    symbol: DetectedSign
