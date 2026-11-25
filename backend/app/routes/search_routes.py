"""Search the corpus by sign sequence (scholars' workbench, story G); see corpus_search.py."""

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from mysql.connector import Error as DatabaseError
from pydantic import BaseModel

from backend.app import corpus_search, glyph_index
from backend.app.model.analysis import ApiError
from backend.app.routes.edition_routes import Editions, _editions, _release

router = APIRouter(tags=["corpus search"])
ERRORS = {code: {"model": ApiError} for code in (422, 503)}


class SequenceHit(BaseModel):
    line: int  # 0-based
    positions: list[int | None]  # scholars' positions (box ids); None where a sign has none
    text: str  # what matched, e.g. "ku-ro"


class TabletHits(BaseModel):
    slug: str
    tablet: str
    release_id: int | None = None  # for the accepted editions: the release searched
    hits: list[SequenceHit]


class SequenceResults(BaseModel):
    query: str
    source: Literal["scholar", "edition"]
    total_tablets: int
    total_hits: int
    items: list[TabletHits]  # by tablet id


def _text(run) -> str:
    return "-".join(sign.reading or sign.sign or "?" for sign in run)


def _group(hits, release_ids: dict[str, int] | None = None) -> list[TabletHits]:
    tablets: dict[str, TabletHits] = {}
    for line, run in hits:
        found = tablets.setdefault(
            line.slug,
            TabletHits(
                slug=line.slug,
                tablet=line.tablet,
                release_id=(release_ids or {}).get(line.slug),
                hits=[],
            ),
        )
        found.hits.append(
            SequenceHit(
                line=line.number, positions=[sign.position for sign in run], text=_text(run)
            )
        )
    return sorted(tablets.values(), key=lambda item: item.tablet)


def _edition_lines(editions) -> tuple[list[corpus_search.Line], dict[str, int]]:
    lines, release_ids = [], {}
    index = glyph_index.get_index()
    for slug in editions.released_tablets():
        accepted = _editions(slug, editions, None).accepted_release_id
        row = editions.release(accepted) if accepted else None
        if row is None:
            continue
        release = _release(row, reading=True)
        signs = {sign.id: sign for sign in release.reading.signs}
        lines.extend(
            corpus_search.edition_lines(
                slug, index.slugs.get(slug, slug.replace("-", " ")), release.reading.lines, signs
            )
        )
        release_ids[slug] = release.id
    return lines, release_ids


@router.get("/corpus/search", response_model=SequenceResults, responses=ERRORS)
def search_sequence(
    editions: Editions,
    q: Annotated[str, Query(min_length=1, max_length=200)],
    source: Literal["scholar", "edition"] = "scholar",
    across_words: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> SequenceResults:
    """Tablets whose text has a sign sequence: signs separated by "-" or spaces, each a sign ID
    (AB81), a reading (ku), * for any sign, or alternatives with | (ku|ka). `source` searches the
    scholars' transcriptions or each tablet's accepted edition. A match stays inside one word
    unless `across_words`. Results are grouped by tablet, paged by tablet."""
    try:
        query = corpus_search.parse(q)
    except corpus_search.BadQuery as error:
        raise HTTPException(422, str(error)) from error
    try:
        if source == "scholar":
            items = _group(corpus_search.search(corpus_search.corpus_lines(), query, across_words))
        else:
            lines, release_ids = _edition_lines(editions)
            items = _group(corpus_search.search(lines, query, across_words), release_ids)
    except glyph_index.CorpusMissing as error:
        raise HTTPException(503, str(error)) from error
    except DatabaseError as error:
        raise HTTPException(503, "Editions are unavailable. Please try again.") from error
    return SequenceResults(
        query=q,
        source=source,
        total_tablets=len(items),
        total_hits=sum(len(item.hits) for item in items),
        items=items[offset : offset + limit],
    )
