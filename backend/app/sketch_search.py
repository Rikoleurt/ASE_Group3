"""Sketch to search: which real Linear A signs look like a drawing made with a mouse, finger or pen.

A sketch is reduced to its skeleton and redrawn with an even pen as wide as the corpus
tracings' strokes (about 3.8% of a sign's longest side, measured on the SigLA drawings), so a
thin mouse line and a fat finger stroke both look like a tracing. It is then scored the way
the reader names a sign (`la.reader`): the classifier's probabilities blended with the
neighbour bank's (best cosine to each sign's training crops), with the reader's own weights.

`scripts/eval_sketch.py` measures how well this finds the right sign.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import ndimage

from la import glyphembed

PEN = 0.038  # stroke width / the sign's longest side, the corpus tracings' median
MIN_INK = 12  # pixels; less than this is a stray tap, not a sketch
BUSY_SECONDS = 5  # a sketch waits this long for a tablet reading to finish, then gives up


class SketchBusy(RuntimeError):
    """The reader is busy with a tablet; try again in a moment."""


SIDE = 256  # sketches are drawn at this size before the pen is applied


def _thin(ink: np.ndarray) -> np.ndarray:
    """Zhang-Suen thinning: the one-pixel skeleton of a binary image."""
    image = np.pad(ink.astype(np.uint8), 1)
    while True:
        changed = False
        for step in (0, 1):
            p = [
                np.roll(np.roll(image, -dy, 0), -dx, 1)
                for dy, dx in ((-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1))
            ]
            neighbours = sum(p)
            transitions = sum(
                ((p[i] == 0) & (p[(i + 1) % 8] == 1)).astype(np.uint8) for i in range(8)
            )
            if step == 0:
                a, b = p[0] * p[2] * p[4], p[2] * p[4] * p[6]
            else:
                a, b = p[0] * p[2] * p[6], p[0] * p[4] * p[6]
            remove = (
                (image == 1)
                & (neighbours >= 2)
                & (neighbours <= 6)
                & (transitions == 1)
                & (a == 0)
                & (b == 0)
            )
            if remove.any():
                image[remove] = 0
                changed = True
        if not changed:
            return image[1:-1, 1:-1].astype(bool)


def sketch_ink(data: bytes) -> np.ndarray:
    """The ink of a sketch PNG. A fully transparent canvas is empty (the shared crop reader
    would read its black, invisible pixels as ink)."""
    from io import BytesIO

    from PIL import Image

    try:
        with Image.open(BytesIO(data)) as image:
            if image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info:
                if image.convert("RGBA").getextrema()[3][1] == 0:
                    raise glyphembed.BadCrop("Draw a sign first.")
    except glyphembed.BadCrop:
        raise
    except (OSError, SyntaxError, Image.DecompressionBombError):
        pass  # ink_from_png_bytes reports an invalid image
    return glyphembed.ink_from_png_bytes(data)


def even_pen(ink: np.ndarray) -> np.ndarray:
    """The ink trimmed to its strokes, scaled to SIDE, thinned and redrawn with the corpus pen."""
    ys, xs = np.nonzero(ink)
    if len(ys) < MIN_INK:
        raise glyphembed.BadCrop("Draw a sign first.")
    crop = ink[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    scale = SIDE / max(crop.shape)
    resized = ndimage.zoom(crop.astype(np.float32), scale, order=1) > 0.3
    pad = SIDE // 8
    skeleton = _thin(np.pad(resized, pad))
    radius = max(1.0, PEN * SIDE / 2)
    return ndimage.distance_transform_edt(~skeleton) <= radius


@dataclass
class Scorer:
    classifier: object
    bank: object  # la.reader.NeighbourBank
    names: list[str]

    def scores(
        self, inks: list[np.ndarray], batch: int = 64
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """(classifier, neighbours, blend) probability matrices, one row per ink, columns `names`.
        Scored in small batches so a long evaluation stays within a laptop's memory."""
        parts = [self._scores(inks[start : start + batch]) for start in range(0, len(inks), batch)]
        return tuple(np.concatenate([part[i] for part in parts]) for i in range(3))

    def _scores(self, inks: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        from la import reader

        crops = [glyphembed.prepared(ink) for ink in inks]
        _names, probs = reader.class_probabilities(self.classifier, crops, device="cpu")
        queries = self.bank.embed(crops)
        scaled = self.bank.scores(self.names, queries) / self.bank.temperature
        scaled = np.exp(scaled - scaled.max(axis=1, keepdims=True))
        neighbours = scaled / scaled.sum(axis=1, keepdims=True)
        return probs, neighbours, self.bank.blend(self.names, probs, queries)


def scorer() -> Scorer | None:
    """The installed classifier and neighbour bank, or None when either is missing."""
    from backend.app import glyph_index, tablet_demo

    weights: Path = tablet_demo.CLASSIFIER_WEIGHTS
    if not weights.is_file():
        return None
    extra = tablet_demo.refinements(weights)
    if not extra or extra.get("bank") is None:
        return None
    classifier = glyph_index._classifier(str(weights.resolve()), weights.stat().st_mtime_ns)
    return Scorer(
        classifier, extra["bank"], [classifier.names[i] for i in range(len(classifier.names))]
    )


def candidates(data: bytes, top: int = 12) -> list[tuple[str, float]]:
    """The `top` signs most like the sketch (a PNG: transparent with strokes, or dark on light),
    best first, with the blended probability. Raises glyphembed.BadCrop for an unusable sketch
    and FileNotFoundError when the reader is not installed."""
    from backend.app import tablet_demo

    pen = even_pen(sketch_ink(data))
    found = scorer()
    if found is None:
        raise FileNotFoundError("The sign reader is not installed.")
    if not tablet_demo.INFERENCE_LOCK.acquire(timeout=BUSY_SECONDS):
        raise SketchBusy("The reader is busy. Try again in a moment.")
    try:
        import torch

        torch.set_num_threads(tablet_demo.INFERENCE_THREADS)
        _probs, _neighbours, blend = found.scores([pen])
    finally:
        tablet_demo.INFERENCE_LOCK.release()
    order = np.argsort(-blend[0])
    return [
        (found.names[i], float(blend[0][i])) for i in order if found.names[i] != "unidentified"
    ][:top]
