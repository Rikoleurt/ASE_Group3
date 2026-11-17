"""Where else does this sign occur? Sign ID -> every corpus occurrence, ordered by look.

The corpus is the lineara.eu / SigLA record of each tablet (`la.fetch.load_cached`).
A glyph is "the same" when it has the same SigLA sign ID, which is also the ID the
sign classifier predicts. Where the sign has a box on the tablet drawing
(`out/yolo_signs/annotations.json`) the box is returned too, so a thumbnail can
highlight it.

Glyph embeddings (`models/glyph_embeddings.npz`, built by
`scripts/build_glyph_embeddings.py`) order occurrences by visual similarity and
flag outliers: a sign far from the centre of its own class is a possible mislabel.
Without that file everything still works, in corpus order and without similarity.

Data licence: SigLA-derived, CC BY-NC-SA 4.0 (credit in `reading.CREDIT`).
"""

from __future__ import annotations

import json
import os
import re
from threading import Lock
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from backend.app import reading
from backend.app.reading import SLUG

from la import clustering, fetch, glyphembed, signboxes  # noqa: E402  (reading put fraction-solver on sys.path)

ROOT = Path(__file__).resolve().parents[2]
SIGN_ID = re.compile(r"[A-Za-z0-9]{1,12}")
ANNOTATIONS = ROOT / "fraction-solver" / "out" / "yolo_signs" / "annotations.json"
EMBEDDINGS = Path(os.getenv("GLYPH_EMBEDDINGS", ROOT / "models" / "glyph_embeddings.npz"))


class CorpusMissing(Exception):
    """The cached lineara.eu corpus is not on this machine."""


@dataclass(frozen=True)
class Occurrence:
    tablet: str  # corpus id, e.g. "HT 13"
    slug: str  # URL-safe tablet id, e.g. "HT-13"
    position: int
    sign: str
    reading: str | None
    role: str | None
    has_crop: bool
    box: tuple[float, float, float, float] | None = None  # x, y, w, h as fractions of the tracing


class GlyphIndex:
    def __init__(self, docs: dict[str, dict], annotations: list[dict] | None = None,
                 embeddings: dict | None = None) -> None:
        boxes: dict[tuple[str, int], tuple[float, float, float, float]] = {}
        for tablet in annotations or []:
            width, height = tablet.get("width"), tablet.get("height")
            if not width or not height:
                continue
            for sign in tablet.get("signs") or []:
                x0, y0, x1, y1 = sign["xyxy"]
                boxes[(tablet["tablet"], int(sign["position"]))] = (
                    x0 / width, y0 / height, (x1 - x0) / width, (y1 - y0) / height)
        self.by_sign: dict[str, list[Occurrence]] = {}
        self.by_key: dict[tuple[str, int], Occurrence] = {}
        self.slugs: dict[str, str] = {}  # slug -> corpus id
        for tablet, doc in docs.items():
            slug = signboxes.slug(doc)
            if not SLUG.fullmatch(slug):
                continue
            self.slugs[slug] = tablet
            for sign in doc.get("signs") or []:
                sign_id = sign.get("sign")
                if not sign_id or not SIGN_ID.fullmatch(sign_id) or sign.get("position") is None:
                    continue
                position = int(sign["position"])
                occurrence = Occurrence(
                    tablet=tablet, slug=slug, position=position, sign=sign_id,
                    reading=sign.get("reading"), role=sign.get("role"),
                    has_crop=bool(sign.get("image")), box=boxes.get((tablet, position)))
                self.by_sign.setdefault(sign_id, []).append(occurrence)
                self.by_key[(slug, position)] = occurrence
        for items in self.by_sign.values():
            items.sort(key=lambda o: (o.slug, o.position))

        self.vectors: dict[tuple[str, int], np.ndarray] = {}
        self.z: dict[tuple[str, int], float] = {}
        self.centre: dict[str, np.ndarray] = {}
        self.embedding_info: dict | None = None
        if embeddings is not None:
            self._load_embeddings(embeddings)

    def _load_embeddings(self, data: dict) -> None:
        x = clustering.normalise(np.asarray(data["vectors"], dtype=np.float32))
        slug_of = {corpus_id: slug for slug, corpus_id in self.slugs.items()}
        rows: list[int] = []
        keys: list[tuple[str, int]] = []
        labels: list[str] = []
        for i, (tablet, position) in enumerate(zip(data["tablet"], data["position"])):
            key = (slug_of.get(str(tablet)), int(position))
            occurrence = self.by_key.get(key)
            # A vector only counts for the sign it was computed for: a stale file never mislabels.
            if occurrence is None or occurrence.sign != str(data["sign"][i]):
                continue
            rows.append(i)
            keys.append(key)
            labels.append(occurrence.sign)
        if not rows:
            return
        sub, labels_array = x[rows], np.array(labels)
        _distance, z = clustering.outlier_scores(sub, labels_array)
        for key, vector, score in zip(keys, sub, z):
            self.vectors[key] = vector
            self.z[key] = float(score)
        self.centre = clustering.centres(sub, labels_array)
        self.embedding_info = {"model": str(data.get("model", "")),
                               "weights_sha256": str(data.get("weights_sha256", "")), "vectors": len(rows)}

    # --- queries -------------------------------------------------------------------------

    def counts(self) -> dict[str, int]:
        return {sign: len(items) for sign, items in sorted(self.by_sign.items())}

    def lookup(self, slug: str, position: int) -> Occurrence | None:
        return self.by_key.get((slug, position))

    def has_embeddings(self) -> bool:
        return bool(self.vectors)

    def is_outlier(self, occurrence: Occurrence) -> bool:
        z = self.z.get((occurrence.slug, occurrence.position))
        return z is not None and bool(clustering.is_outlier(np.array([z]))[0])

    def ranked(self, sign: str, reference: np.ndarray | None = None
               ) -> tuple[str, list[tuple[Occurrence, float | None]]]:
        """(ranked_by, [(occurrence, cosine similarity or None)]), best match first.

        `reference` is a unit vector; without one the sign's own centre is used, so the
        most typical examples come first. Occurrences without a vector come last.
        """
        items = self.by_sign.get(sign, [])
        if not self.has_embeddings():
            return "none", [(o, None) for o in items]
        if reference is None:
            reference = self.centre.get(sign)
            mode = "centre"
        else:
            mode = "glyph"
        if reference is None:
            return "none", [(o, None) for o in items]
        scored = []
        for o in items:
            vector = self.vectors.get((o.slug, o.position))
            scored.append((o, None if vector is None else float(vector @ reference)))
        scored.sort(key=lambda pair: (pair[1] is None, -(pair[1] or 0.0), pair[0].slug, pair[0].position))
        return mode, scored

    def vector_of(self, slug: str, position: int) -> np.ndarray | None:
        return self.vectors.get((slug, position))


def _load_embeddings(path: Path) -> dict | None:
    if not path.is_file():
        return None
    with np.load(path, allow_pickle=False) as data:
        return {key: data[key] for key in data.files}


_BUILD_LOCK = Lock()
_index: GlyphIndex | None = None


def get_index() -> GlyphIndex:
    """Built once, under a lock, so concurrent first requests do not each read the corpus.

    A missing corpus is not cached (it may be installed later); that check is a single
    directory glob, so retrying on every request is cheap.
    """
    global _index
    if _index is not None:
        return _index
    with _BUILD_LOCK:
        if _index is None:
            if not fetch.CACHE_DIR.is_dir() or next(fetch.CACHE_DIR.glob("*.json"), None) is None:
                raise CorpusMissing("The cached lineara.eu corpus is not installed on this server.")
            annotations = json.loads(ANNOTATIONS.read_text(encoding="utf-8")) if ANNOTATIONS.is_file() else []
            _index = GlyphIndex(fetch.load_cached(), annotations, _load_embeddings(EMBEDDINGS))
        return _index


@lru_cache(maxsize=1)
def _classifier(path: str, modified_ns: int):
    from ultralytics import YOLO

    return YOLO(path)


def embed_crop(data: bytes) -> np.ndarray:
    """Unit embedding of an uploaded crop, from the same classifier as the corpus vectors.

    Raises glyphembed.BadCrop for unusable input and FileNotFoundError without weights.
    """
    from backend.app import tablet_demo

    ink = glyphembed.ink_from_png_bytes(data)
    weights = tablet_demo.CLASSIFIER_WEIGHTS
    if not weights.is_file():
        raise FileNotFoundError(str(weights))
    with tablet_demo.INFERENCE_LOCK:
        import torch

        torch.set_num_threads(tablet_demo.INFERENCE_THREADS)
        vector = glyphembed.embed_inks(_classifier(str(weights.resolve()), weights.stat().st_mtime_ns), [ink])[0]
    return clustering.normalise(vector[None, :])[0]


def tracing_path(slug: str) -> Path | None:
    """The cached tracing (whole-tablet drawing) of a tablet."""
    if not SLUG.fullmatch(slug):
        return None
    index = get_index()
    corpus_id = index.slugs.get(slug)
    if corpus_id is None:
        return None
    doc = reading.load_document(slug)
    url = doc.get("tracing")
    if not url:
        return None
    path = signboxes.image_path(doc, url)
    return path if path.is_file() else None

