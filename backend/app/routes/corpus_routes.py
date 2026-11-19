"""Corpus tablets (#82): find a tablet, see its tracing, and its boxes from the scholars or the reader.

Public, like the other corpus routes: the drawings and transcriptions are published data
(CC BY-NC-SA, credited in every response). Correcting a tablet's boxes needs a login (#83).
"""
from pathlib import Path as FilePath
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Request, Response
from fastapi.responses import FileResponse

from backend.app import corpus, glyph_index, reading
from backend.app.auth import COOKIE_NAME, current_user
from backend.app.data_controller.analysis_data_controller import read_signs
from backend.app.model.analysis import ApiError
from backend.app.model.corpus import Credit, Source, TabletBoxes, TabletItem, TabletPage
from backend.app.routes.glyph_routes import Index

router = APIRouter(prefix="/tablets", tags=["corpus tablets"])
SLUG_PATH = Path(pattern=r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$", max_length=64)
Slug = Annotated[str, SLUG_PATH]
ERRORS = {code: {"model": ApiError} for code in (404, 503)}


def tracing(slug: str) -> FilePath:
    path = glyph_index.tracing_path(slug)
    if path is None:
        raise HTTPException(404, "This tablet's drawing is not on this server.")
    return path


@router.get("", response_model=TabletPage, responses={503: {"model": ApiError}})
def list_tablets(index: Index,
                 q: Annotated[str, Query(max_length=64)] = "",
                 limit: Annotated[int, Query(ge=1, le=200)] = 50,
                 offset: Annotated[int, Query(ge=0, le=100_000)] = 0) -> TabletPage:
    """Tablets with published boxes, by corpus id; `q` matches the id ("HT 13", "ht13", "HT-13")."""
    needle = "".join(q.lower().split()).replace("-", "")
    found = [tablet for tablet in corpus.tablets(index)
             if needle in "".join(tablet.tablet.lower().split()).replace("-", "")]
    return TabletPage(items=[TabletItem(**vars(tablet)) for tablet in found[offset:offset + limit]], total=len(found))


@router.get("/{slug}/image", response_class=FileResponse, responses={200: {"content": {"image/png": {}}}, **ERRORS})
def tablet_image(slug: Slug, index: Index) -> FileResponse:
    """The whole tablet's tracing, full size."""
    path = tracing(slug)
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@router.get("/{slug}/boxes", response_model=TabletBoxes, responses=ERRORS)
def tablet_boxes(slug: Slug, index: Index, request: Request, source: Source = "scholar") -> TabletBoxes:
    """The tablet's boxes from the scholars' published transcription, or as the reader finds them.
    The reader's need a login: reading a tablet runs the model, as an upload does (#98)."""
    if source == "model":
        current_user(Response(), request.cookies.get(COOKIE_NAME))
    if slug not in index.slugs:
        raise HTTPException(404, "Tablet not found.")
    path = tracing(slug)
    if source == "scholar":
        signs = corpus.scholar_signs(index, slug)
    else:
        try:
            signs = corpus.model_signs(slug, path)
        except (corpus.ReaderMissing, corpus.ReaderBusy) as error:
            raise HTTPException(503, str(error)) from error
        except (FileNotFoundError, RuntimeError) as error:
            raise HTTPException(503, "The sign reader is unavailable.") from error
    width, height = corpus.image_size(path)
    return TabletBoxes(slug=slug, tablet=index.slugs[slug], source=source, width=width, height=height,
                       image_url=f"/tablets/{slug}/image", credit=Credit(**reading.CREDIT), **read_signs(signs))
