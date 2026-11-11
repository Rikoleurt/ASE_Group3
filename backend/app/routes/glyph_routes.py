"""Corpus occurrences of a sign, ordered by look, and comments saved against many of them."""

import re
from functools import lru_cache
from io import BytesIO
from typing import Annotated

import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Query, Request, Response, UploadFile
from mysql.connector import Error as DatabaseError
from PIL import Image, ImageDraw

from backend.app import glyph_index
from backend.app.auth import AuthenticatedWrite
from backend.app.data_controller.glyph_data_controller import GlyphDataController
from backend.app.model.analysis import ApiError
from backend.app.model.glyph import (Annotation, AnnotationCreate, AnnotationPage, GlyphBox,
                                     GlyphOccurrence, GlyphOccurrencePage)
from backend.app.reading import CREDIT
from backend.app.reading_pipeline.glyphs import glyph as unicode_glyph
from la import glyphembed

router = APIRouter(tags=["glyphs"])

SIGN_PATH = Path(pattern=r"^[A-Za-z0-9]{1,12}$")
SLUG_PATH = Path(pattern=r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$", max_length=64)
MAX_THUMBNAIL = 960
MAX_CHARACTERS = 20
SIGN_ID = re.compile(r"[A-Za-z0-9]{1,12}")
ERRORS = {code: {"model": ApiError} for code in (404, 503)}


def get_index() -> glyph_index.GlyphIndex:
    try:
        return glyph_index.get_index()
    except glyph_index.CorpusMissing as error:
        raise HTTPException(503, str(error)) from error


Index = Annotated[glyph_index.GlyphIndex, Depends(get_index)]


def get_glyph_data_controller() -> GlyphDataController:
    return GlyphDataController()


GlyphController = Annotated[GlyphDataController, Depends(get_glyph_data_controller)]


def _item(index: glyph_index.GlyphIndex, occurrence: glyph_index.Occurrence, similarity: float | None) -> GlyphOccurrence:
    z = index.z.get((occurrence.slug, occurrence.position))
    base = f"/tablets/{occurrence.slug}"
    return GlyphOccurrence(
        tablet=occurrence.slug, title=occurrence.tablet, position=occurrence.position, sign=occurrence.sign,
        reading=occurrence.reading, role=occurrence.role,
        similarity=None if similarity is None else round(similarity, 4),
        outlier=index.is_outlier(occurrence), outlier_score=None if z is None or np.isnan(z) else round(z, 2),
        crop_url=f"{base}/signs/{occurrence.position}.png" if occurrence.has_crop else None,
        thumbnail_url=f"{base}/thumbnail.png?position={occurrence.position}" if occurrence.box else f"{base}/thumbnail.png",
        box=GlyphBox(x=occurrence.box[0], y=occurrence.box[1], w=occurrence.box[2], h=occurrence.box[3])
        if occurrence.box else None,
    )


def _page(index: glyph_index.GlyphIndex, sign: str, limit: int, offset: int, reference) -> GlyphOccurrencePage:
    if sign not in index.by_sign:
        raise HTTPException(404, "No corpus tablet has this sign.")
    mode, ranked = index.ranked(sign, reference)
    return GlyphOccurrencePage(
        sign=sign, glyph=unicode_glyph(sign), total=len(ranked), limit=limit, offset=offset, ranked_by=mode,
        items=[_item(index, o, s) for o, s in ranked[offset:offset + limit]], credit=CREDIT)


@router.get("/glyphs/characters", response_model=dict[str, str | None], responses={422: {"model": ApiError}})
def characters(signs: Annotated[str, Query(min_length=1, max_length=400)]) -> dict[str, str | None]:
    """The Unicode Linear A character of each sign ID (null where Unicode has none).

    `signs` is a comma-separated list of at most 20 distinct sign IDs, e.g. AB45,AB47,A343.
    """
    wanted = signs.split(",")
    if len(wanted) > MAX_CHARACTERS:
        raise HTTPException(422, f"At most {MAX_CHARACTERS} signs per request.")
    if not all(SIGN_ID.fullmatch(sign) for sign in wanted):
        raise HTTPException(422, "Sign IDs are 1 to 12 letters or digits, separated by commas.")
    return {sign: unicode_glyph(sign) for sign in dict.fromkeys(wanted)}


@router.get("/glyphs/{sign}/occurrences", response_model=GlyphOccurrencePage, responses=ERRORS)
def occurrences(sign: Annotated[str, SIGN_PATH], index: Index,
                limit: Annotated[int, Query(ge=1, le=100)] = 30,
                offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
                ref_tablet: Annotated[str | None, Query(pattern=r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$", max_length=64)] = None,
                ref_position: Annotated[int | None, Query(ge=0, le=1_000_000)] = None):
    """Every corpus tablet with this sign. With ref_tablet + ref_position, ordered by similarity to that
    corpus glyph; without, the most typical examples come first."""
    reference = None
    if (ref_tablet is None) != (ref_position is None):
        raise HTTPException(422, "ref_tablet and ref_position go together.")
    if ref_tablet is not None:
        if index.lookup(ref_tablet, ref_position) is None:
            raise HTTPException(404, "Unknown reference glyph.")
        reference = index.vector_of(ref_tablet, ref_position)
    return _page(index, sign, limit, offset, reference)


def limit_body(request: Request) -> None:
    """Refuse an oversized upload before it is parsed (the multipart overhead is small)."""
    declared = request.headers.get("content-length", "")
    if not declared.isdigit() or int(declared) > glyphembed.MAX_CROP_BYTES + 64 * 1024:
        raise HTTPException(413, "The crop is larger than 2 MB.")


@router.post("/glyphs/{sign}/occurrences/search", response_model=GlyphOccurrencePage,
             dependencies=[Depends(limit_body)],
             responses={**ERRORS, 401: {"model": ApiError}, 403: {"model": ApiError},
                        413: {"model": ApiError}, 422: {"model": ApiError}})
def occurrences_for_crop(sign: Annotated[str, SIGN_PATH], index: Index, user: AuthenticatedWrite,
                         file: Annotated[UploadFile, File()],
                         limit: Annotated[int, Form(ge=1, le=100)] = 30,
                         offset: Annotated[int, Form(ge=0, le=100_000)] = 0):
    """Order the occurrences by similarity to an uploaded crop (the PNG of a detected sign).

    Needs a login session: embedding holds the shared inference lock, which /analysis also uses.
    The crop is embedded on the server with the same classifier as the corpus; it is not stored.
    """
    data = file.file.read(glyphembed.MAX_CROP_BYTES + 1)
    if len(data) > glyphembed.MAX_CROP_BYTES:
        raise HTTPException(413, "The crop is larger than 2 MB.")
    if sign not in index.by_sign:
        raise HTTPException(404, "No corpus tablet has this sign.")
    reference = None
    if index.has_embeddings():
        try:
            reference = glyph_index.embed_crop(data)
        except glyphembed.BadCrop as error:
            raise HTTPException(422, str(error)) from error
        except (FileNotFoundError, RuntimeError) as error:
            raise HTTPException(503, "The sign reader is unavailable.") from error
    return _page(index, sign, limit, offset, reference)


@router.get("/glyphs/{sign}/annotations", response_model=AnnotationPage, responses={503: {"model": ApiError}})
def annotations(sign: Annotated[str, SIGN_PATH], controller: GlyphController, response: Response,
                limit: Annotated[int, Query(ge=1, le=100)] = 50,
                before: Annotated[int | None, Query(ge=1, le=2**64 - 1)] = None):
    response.headers["Cache-Control"] = "no-store"
    try:
        rows = controller.list_annotations(sign, limit, before)
    except DatabaseError as error:
        raise HTTPException(503, "Comment storage is unavailable.") from error
    return AnnotationPage(items=rows[:limit], next_before=rows[limit - 1].id if len(rows) > limit else None)


@router.post("/glyphs/{sign}/annotations", response_model=Annotation, status_code=201,
             responses={**ERRORS, 401: {"model": ApiError}, 403: {"model": ApiError}, 422: {"model": ApiError}})
def create_annotation(sign: Annotated[str, SIGN_PATH], payload: AnnotationCreate, index: Index,
                      user: AuthenticatedWrite, controller: GlyphController):
    """One comment, saved against every listed occurrence. Each must really be this sign."""
    wrong = [f"{t.tablet}#{t.position}" for t in payload.targets
             if (found := index.lookup(t.tablet, t.position)) is None or found.sign != sign]
    if wrong:
        raise HTTPException(422, f"Not occurrences of {sign}: {', '.join(wrong[:5])}")
    try:
        return controller.create_annotation(user.id, sign, payload.body,
                                            [(t.tablet, t.position) for t in payload.targets], user.username)
    except DatabaseError as error:
        raise HTTPException(503, "The comment could not be saved. Please try again.") from error


@router.delete("/glyphs/annotations/{annotation_id}", status_code=204,
               responses={401: {"model": ApiError}, 403: {"model": ApiError}, 404: {"model": ApiError},
                          503: {"model": ApiError}})
def delete_annotation(annotation_id: Annotated[int, Path(gt=0, le=2**64 - 1)], user: AuthenticatedWrite,
                      controller: GlyphController):
    try:
        deleted = controller.delete_annotation(annotation_id, user.id)
    except DatabaseError as error:
        raise HTTPException(503, "The comment could not be deleted. Please try again.") from error
    if not deleted:
        raise HTTPException(404, "Comment not found.")
    return Response(status_code=204)


@router.get("/tablets/{slug}/thumbnail.png", response_class=Response,
            responses={**ERRORS, 200: {"content": {"image/png": {}}}})
def tablet_thumbnail(slug: Annotated[str, SLUG_PATH], index: Index,
                     position: Annotated[int | None, Query(ge=0, le=1_000_000)] = None,
                     width: Annotated[int, Query(ge=64, le=MAX_THUMBNAIL)] = 480) -> Response:
    """The tablet drawing, downscaled, with one sign's box outlined when `position` has a known box."""
    path = glyph_index.tracing_path(slug)
    if path is None:
        raise HTTPException(404, "This tablet's drawing is not cached.")
    box = None
    if position is not None and (found := index.lookup(slug, position)) is not None:
        box = found.box
    return Response(_thumbnail(str(path), path.stat().st_mtime_ns, width, box), media_type="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})


@lru_cache(maxsize=128)
def _thumbnail(path: str, _modified_ns: int, width: int, box) -> bytes:
    with Image.open(path) as source:
        image = source.convert("RGBA")
    flat = Image.new("RGBA", image.size, "white")
    flat.alpha_composite(image)  # SigLA strokes live in the alpha channel
    image = flat.convert("RGB")
    scale = min(1.0, width / image.width)
    image = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.LANCZOS)
    if box:
        draw = ImageDraw.Draw(image)
        x, y, w, h = box
        pad = 2
        draw.rectangle([x * image.width - pad, y * image.height - pad,
                        (x + w) * image.width + pad, (y + h) * image.height + pad],
                       outline=(220, 38, 38), width=max(2, round(image.width / 240)))
    out = BytesIO()
    image.save(out, "PNG", optimize=True)
    return out.getvalue()
