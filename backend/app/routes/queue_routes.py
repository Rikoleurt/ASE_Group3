"""Work queues (scholars' workbench, story J); see work_queues.py. For logged-in users, like the
model's readings they draw on."""

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from mysql.connector import Error as DatabaseError
from pydantic import BaseModel

from backend.app import corpus, glyph_index, work_queues
from backend.app.auth import CurrentUser
from backend.app.model.analysis import ApiError
from backend.app.routes.edition_routes import UNAVAILABLE, Editions, _editions

router = APIRouter(tags=["work queues"])
ERRORS = {code: {"model": ApiError} for code in (401, 422, 503)}
Offset = Annotated[int, Query(ge=0, le=100_000)]
Limit = Annotated[int, Query(ge=1, le=100)]


class DisagreementRow(BaseModel):
    slug: str
    tablet: str
    agree: int  # places where both readings name the same sign
    differs: int  # both have a box there, with different signs
    missing: int  # only one of them has a box there
    total: int
    score: float  # share of places that do not agree, 0 to 1
    release_id: int | None = None  # against=edition: the accepted release compared
    edition_id: int | None = None  # ...and its edition (a box set), for comparing it


class DisagreementQueue(BaseModel):
    against: Literal["model", "edition"]
    built_at: str | None = None  # against=model: when the offline run finished
    model_version: str | None = None
    missing_hint: str | None = None  # against=model: how to build the file when it is absent
    total: int
    items: list[DisagreementRow]  # most places that differ first, then the largest share


class CandidateSign(BaseModel):
    sign: str | None
    label: str
    probability: float  # percent


class LowConfidenceSign(BaseModel):
    slug: str
    tablet: str
    id: int  # the sign's id in the model's reading of the tablet
    sign: str | None
    label: str
    reading: str | None = None
    confidence: float  # percent
    box: dict[str, float]  # fractions of the tracing
    candidates: list[CandidateSign] = []


class LowConfidenceQueue(BaseModel):
    built_at: str | None = None
    model_version: str | None = None
    missing_hint: str | None = None
    threshold: float
    total: int
    items: list[LowConfidenceSign]  # least confident first


class TabletRow(BaseModel):
    slug: str
    tablet: str
    signs: int  # published boxes


class TabletQueue(BaseModel):
    total: int
    items: list[TabletRow]  # most signs first


class CloseRelease(BaseModel):
    id: int
    title: str | None
    owner: str
    votes: int


class CloseVote(BaseModel):
    slug: str
    tablet: str
    gap: int  # votes between the two most-backed releases
    votes: int  # all votes on the tablet
    releases: list[CloseRelease]  # the two most backed


class CloseVoteQueue(BaseModel):
    total: int
    items: list[CloseVote]  # closest first


def _index() -> glyph_index.GlyphIndex:
    try:
        return glyph_index.get_index()
    except glyph_index.CorpusMissing as error:
        raise HTTPException(503, str(error)) from error


def _accepted(editions, slugs: list[str]) -> dict[str, object]:
    return {slug: _editions(slug, editions, None) for slug in slugs}


@router.get("/queues/disagreement", response_model=DisagreementQueue, responses=ERRORS)
def disagreement(
    _user: CurrentUser,
    editions: Editions,
    against: Literal["model", "edition"] = "model",
    offset: Offset = 0,
    limit: Limit = 25,
) -> DisagreementQueue:
    """Tablets where the scholars' reading differs most from the model's (from the offline run)
    or from the tablet's accepted edition: most places that differ first, then the largest share."""
    index = _index()
    if against == "model":
        data = work_queues.offline()
        if data is None:
            return DisagreementQueue(
                against=against, missing_hint=work_queues.BUILD_HINT, total=0, items=[]
            )
        rows = [
            DisagreementRow(
                slug=slug, **{**row, "tablet": index.slugs.get(slug, row.get("tablet", slug))}
            )
            for slug, row in data["tablets"].items()
            if row.get("total")
        ]
        meta = {"built_at": data.get("built_at"), "model_version": data.get("model_version")}
    else:
        meta = {}
        try:
            tablets = _accepted(editions, editions.released_tablets())
            rows = []
            for slug, found in tablets.items():
                row = (
                    editions.release(found.accepted_release_id)
                    if found.accepted_release_id
                    else None
                )
                if row is None or slug not in index.slugs:
                    continue
                scholars = [
                    {"id": sign.id, "box": sign.box.model_dump(), "sign": sign.sign}
                    for sign in corpus.scholar_signs(index, slug)
                ]
                if not scholars:
                    continue
                counts = work_queues.compare(scholars, row["boxes"], "scholar", "edition")
                rows.append(
                    DisagreementRow(
                        slug=slug,
                        tablet=index.slugs[slug],
                        release_id=row["id"],
                        edition_id=row["set_id"],
                        **counts,
                    )
                )
        except DatabaseError as error:
            raise HTTPException(503, UNAVAILABLE) from error
    rows.sort(key=lambda row: (-(row.differs + row.missing), -row.score, row.tablet))
    return DisagreementQueue(
        against=against, total=len(rows), items=rows[offset : offset + limit], **meta
    )


@router.get("/queues/low-confidence", response_model=LowConfidenceQueue, responses=ERRORS)
def low_confidence(_user: CurrentUser, offset: Offset = 0, limit: Limit = 25) -> LowConfidenceQueue:
    """The model's least confident signs across the corpus (from the offline run)."""
    index = _index()
    data = work_queues.offline()
    if data is None:
        return LowConfidenceQueue(
            missing_hint=work_queues.BUILD_HINT,
            threshold=work_queues.LOW_CONFIDENCE,
            total=0,
            items=[],
        )
    rows = sorted(
        data.get("low_confidence", []), key=lambda row: (row["confidence"], row["slug"], row["id"])
    )
    items = [
        LowConfidenceSign(
            **{**row, "tablet": index.slugs.get(row["slug"], row.get("tablet", row["slug"]))}
        )
        for row in rows[offset : offset + limit]
    ]
    return LowConfidenceQueue(
        built_at=data.get("built_at"),
        model_version=data.get("model_version"),
        threshold=work_queues.LOW_CONFIDENCE,
        total=len(rows),
        items=items,
    )


@router.get("/queues/no-edition", response_model=TabletQueue, responses=ERRORS)
def no_edition(
    _user: CurrentUser, editions: Editions, offset: Offset = 0, limit: Limit = 25
) -> TabletQueue:
    """Tablets with a drawing here but no released edition open to everyone, most signs first."""
    drawn, _missing = corpus.tablets(_index())
    try:
        released = set(editions.released_tablets())
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
    rows = sorted(
        (
            TabletRow(slug=t.slug, tablet=t.tablet, signs=t.signs)
            for t in drawn
            if t.slug not in released
        ),
        key=lambda row: (-row.signs, row.tablet),
    )
    return TabletQueue(total=len(rows), items=rows[offset : offset + limit])


@router.get("/queues/close-votes", response_model=CloseVoteQueue, responses=ERRORS)
def close_votes(
    _user: CurrentUser, editions: Editions, offset: Offset = 0, limit: Limit = 25
) -> CloseVoteQueue:
    """Tablets whose two most-backed releases are at most one vote apart, with no admin override:
    where one more vote decides the community edition."""
    index = _index()
    try:
        tablets = _accepted(editions, editions.released_tablets())
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
    rows = []
    for slug, found in tablets.items():
        if found.override is not None:
            continue
        gap = work_queues.close_votes([item.votes for item in found.items])
        if gap is None:
            continue
        top = sorted(found.items, key=lambda item: -item.votes)[:2]
        rows.append(
            CloseVote(
                slug=slug,
                tablet=index.slugs.get(slug, slug),
                gap=gap,
                votes=sum(item.votes for item in found.items),
                releases=[
                    CloseRelease(id=item.id, title=item.title, owner=item.owner, votes=item.votes)
                    for item in top
                ],
            )
        )
    rows.sort(key=lambda row: (row.gap, -row.votes, row.tablet))
    return CloseVoteQueue(total=len(rows), items=rows[offset : offset + limit])
