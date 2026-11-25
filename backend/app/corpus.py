"""Corpus tablets with their boxes (#82): the scholars' published boxes, or the reader's own.

The scholars' boxes come from the training annotations (`la.signboxes`, loaded by the glyph
index); the reader's come from running the sign reader on the tablet's tracing, once per
tablet and model version. Both are returned as DetectedSign lists, like an analysis, so the
overlay, the reading and corrected copies (#83) treat them the same way.
"""
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from threading import Lock

from PIL import Image

from backend.app import glyph_index, tablet_demo
from backend.app.data_controller.analysis_data_controller import describe_sign, sign_from_prediction
from backend.app.model.analysis import DetectedSign

SOURCES = ("scholar", "model")


class ReaderMissing(Exception):
    """Only the generic model is installed, which finds objects, not Linear A signs."""


@dataclass(frozen=True)
class TabletSummary:
    slug: str
    tablet: str  # corpus id, e.g. "HT 13"
    signs: int  # signs with a published box


DOWNLOAD_HINT = "Download them with: cd fraction-solver && python -m la.cli images --tracings-only"
_drawn: dict[int, tuple[float, list[TabletSummary], int]] = {}
_DRAWN_SECONDS = 60  # drawings downloaded while the server runs show up within a minute


def tablets(index: glyph_index.GlyphIndex) -> tuple[list[TabletSummary], int]:
    """Tablets with published boxes whose drawing is on this server, by corpus id, and how many
    more have boxes but no drawing here (the drawings are downloaded separately; see DOWNLOAD_HINT)."""
    now = time.monotonic()
    cached = _drawn.get(id(index))
    if cached is None or now - cached[0] > _DRAWN_SECONDS:
        every = _tablets(id(index), index)
        drawn = [tablet for tablet in every if glyph_index.tracing_path(tablet.slug) is not None]
        cached = _drawn[id(index)] = (now, drawn, len(every) - len(drawn))
    return cached[1], cached[2]


@lru_cache(maxsize=2)
def _tablets(_key: int, index: glyph_index.GlyphIndex) -> list[TabletSummary]:
    counts: dict[str, int] = {}
    for (slug, _position), occurrence in index.by_key.items():
        if occurrence.box is not None:
            counts[slug] = counts.get(slug, 0) + 1
    return sorted((TabletSummary(slug, index.slugs[slug], count) for slug, count in counts.items()),
                  key=lambda tablet: tablet.tablet)


def image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.width, image.height


def scholar_signs(index: glyph_index.GlyphIndex, slug: str) -> list[DetectedSign]:
    """The published boxes of a tablet, in transcription order; a sign's id is its position."""
    catalogue = _catalogue()
    occurrences = sorted((o for (s, _), o in index.by_key.items() if s == slug and o.box is not None),
                         key=lambda o: o.position)
    return [DetectedSign(id=o.position, **describe_sign(o.sign, catalogue), confidence=100.0,
                         detection_confidence=100.0, box=dict(zip("xywh", o.box)), candidates=[])
            for o in occurrences]


class ReaderBusy(Exception):
    """The reader is reading another tablet; reading is one at a time."""


_MODEL_LOCK = Lock()
_MODEL_CACHE: dict[tuple, list[DetectedSign]] = {}
_CACHE_LOCK = Lock()
CACHE_SIZE = 1024  # more than the corpus (706 tablets), so a sweep over every tablet does not evict


def model_signs(slug: str, path: Path) -> list[DetectedSign]:
    """The reader's boxes on the tablet's tracing, computed once per tablet and model version.

    A tablet not read yet takes the reader for ~20 s. Only one runs at a time, and a request that
    finds the reader busy is refused (ReaderBusy) rather than queued, so a burst of requests cannot
    tie up the server's worker threads (#98)."""
    key = (slug, str(path), path.stat().st_mtime_ns, tablet_demo.model_version())
    with _CACHE_LOCK:
        cached = _MODEL_CACHE.get(key)
    if cached is None:
        if not _MODEL_LOCK.acquire(blocking=False):
            raise ReaderBusy("The reader is busy with another tablet. Please try again in a moment.")
        try:
            with _CACHE_LOCK:
                cached = _MODEL_CACHE.get(key)
            if cached is None:
                cached = _read_tablet(slug, path)
                with _CACHE_LOCK:
                    if len(_MODEL_CACHE) >= CACHE_SIZE:
                        _MODEL_CACHE.pop(next(iter(_MODEL_CACHE)))  # oldest first
                    _MODEL_CACHE[key] = cached
        finally:
            _MODEL_LOCK.release()
    return [sign.model_copy(deep=True) for sign in cached]  # callers fill in line and order


def _read_tablet(slug: str, path: Path) -> list[DetectedSign]:
    read = tablet_demo.predictions_for(tablet_demo.read_image(path), tablet=slug)
    if not read["trained"]:
        raise ReaderMissing("The Linear A sign reader is not installed (python scripts/fetch_models.py).")
    catalogue = _catalogue()
    # The crops are only for the analysis page's comparison pane; keep the cached copy small.
    return [sign.model_copy(update={"crop": None}) for sign in
            (sign_from_prediction(prediction, catalogue) for prediction in read["predictions"])]


def _catalogue() -> dict:
    classifier = tablet_demo.active_classifier()
    return tablet_demo.sign_catalogue(classifier) if classifier else {}
