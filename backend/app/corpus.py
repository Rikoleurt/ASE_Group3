"""Corpus tablets with their boxes (#82): the scholars' published boxes, or the reader's own.

The scholars' boxes come from the training annotations (`la.signboxes`, loaded by the glyph
index); the reader's come from running the sign reader on the tablet's tracing, once per
tablet and model version. Both are returned as DetectedSign lists, like an analysis, so the
overlay, the reading and corrected copies (#83) treat them the same way.
"""
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


def tablets(index: glyph_index.GlyphIndex) -> list[TabletSummary]:
    """Tablets that have published boxes, by corpus id."""
    return _tablets(id(index), index)


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


_MODEL_LOCK = Lock()


def model_signs(slug: str, path: Path) -> list[DetectedSign]:
    """The reader's boxes on the tablet's tracing, computed once per tablet and model version."""
    with _MODEL_LOCK:  # one reading per tablet at a time; the reader itself is serialised anyway
        signs = _model_signs(slug, str(path), path.stat().st_mtime_ns, tablet_demo.model_version())
    return [sign.model_copy(deep=True) for sign in signs]  # callers fill in line and order


@lru_cache(maxsize=256)
def _model_signs(slug: str, path: str, _modified_ns: int, _version: str) -> list[DetectedSign]:
    read = tablet_demo.predictions_for(tablet_demo.read_image(Path(path)), tablet=slug)
    if not read["trained"]:
        raise ReaderMissing("The Linear A sign reader is not installed (python scripts/fetch_models.py).")
    catalogue = _catalogue()
    # The crops are only for the analysis page's comparison pane; keep the cached copy small.
    return [sign.model_copy(update={"crop": None}) for sign in
            (sign_from_prediction(prediction, catalogue) for prediction in read["predictions"])]


def _catalogue() -> dict:
    classifier = tablet_demo.active_classifier()
    return tablet_demo.sign_catalogue(classifier) if classifier else {}
