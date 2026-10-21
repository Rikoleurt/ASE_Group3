"""Sign crops for a classifier, and plausible variations of them.

The detector only says "a sign is here"; a classifier then names it from a crop.
Both training and the web demo must cut that crop the same way, so `square_crop`
is the one place that does it.

Variations stand in for the attestations a rare sign does not have: a scribe's
slight tilt, a heavier or lighter stroke, a chipped edge. They never mirror a
sign, because orientation is part of a sign's identity (J and L differ mainly by
how they are turned).
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image
from scipy import ndimage

# Context kept around a box, as a fraction of its longer side. Detector boxes are
# a few pixels loose or tight; a margin keeps the strokes inside either way.
CROP_MARGIN = 0.08
CROP_SIZE = 128

MAX_TILT = 4.0          # degrees
MAX_STRETCH = 0.10      # independent x/y scale jitter
MAX_DAMAGE = 0.20       # fraction of the sign's box erased
MIN_INK_KEPT = 0.60     # a variation keeping less of the sign is not that sign any more


def square_crop(ink: np.ndarray, box: tuple[float, float, float, float],
                margin: float = CROP_MARGIN, size: int = CROP_SIZE) -> np.ndarray:
    """The ink inside `box` (x0, y0, x1, y1), centred on a white square, as uint8.

    Padding to a square before resizing keeps the sign's proportions: a tall sign
    and a wide one stay tall and wide.
    """
    height, width = ink.shape
    x0, y0, x1, y1 = box
    pad = margin * max(x1 - x0, y1 - y0)
    x0, y0 = max(0, int(x0 - pad)), max(0, int(y0 - pad))
    x1, y1 = min(width, math.ceil(x1 + pad)), min(height, math.ceil(y1 + pad))
    return render(ink[y0:y1, x0:x1], size)


def render(mask: np.ndarray, size: int = CROP_SIZE, margin: float = 0.0) -> np.ndarray:
    """Black ink on a white `size` square, centred, aspect kept.

    `margin` adds blank space around the mask as `square_crop` adds context, so a
    varied sign is framed like a cut one.
    """
    if margin:
        mask = np.pad(mask, round(margin * max(mask.shape)))
    h, w = mask.shape
    side = max(h, w, 1)
    canvas = np.zeros((side, side), dtype=bool)
    top, left = (side - h) // 2, (side - w) // 2
    canvas[top:top + h, left:left + w] = mask
    image = Image.fromarray(np.where(canvas, 0, 255).astype(np.uint8))
    return np.asarray(image.resize((size, size), Image.LANCZOS))


def trim(mask: np.ndarray) -> np.ndarray:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return mask[:0, :0]
    return mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def vary(mask: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """One plausible variation of a sign's ink mask, trimmed to its ink.

    Tilt, stretch, stroke weight and a chipped region, each small. Returns the
    original (trimmed) when a draw would leave too little of the sign.
    """
    mask = trim(mask.astype(bool))
    if not mask.any():
        return mask
    # Pad first so a tilt or a thicker stroke cannot run off the edge.
    out = np.pad(mask, 4)
    sy, sx = 1 + rng.uniform(-MAX_STRETCH, MAX_STRETCH, size=2)
    out = ndimage.zoom(out.astype(np.float32), (sy, sx), order=1) >= 0.5
    shaped = ndimage.rotate(out.astype(np.float32), rng.uniform(-MAX_TILT, MAX_TILT),
                            reshape=True, order=1) >= 0.5
    out = shaped
    weight = rng.choice([-1, 0, 0, 1])
    if weight > 0:
        out = ndimage.binary_dilation(out)
    elif weight < 0:
        out = ndimage.binary_erosion(out)
    if rng.random() < 0.5:
        out = chip(out, rng)
    # Thinning and chipping each look harmless; together they can halve a sign.
    if out.sum() < MIN_INK_KEPT * shaped.sum():
        out = shaped
    out = trim(out)
    return out if out.any() else mask


def chip(mask: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Erase a rectangle from one edge, as a broken tablet edge would."""
    h, w = mask.shape
    area = rng.uniform(0.05, MAX_DAMAGE)
    if rng.random() < 0.5:   # a band across the top or bottom
        rows = max(1, round(h * area))
        sl = (slice(0, rows), slice(None)) if rng.random() < 0.5 else (slice(h - rows, h), slice(None))
    else:                    # a band down the left or right
        cols = max(1, round(w * area))
        sl = (slice(None), slice(0, cols)) if rng.random() < 0.5 else (slice(None), slice(w - cols, w))
    chipped = mask.copy()
    chipped[sl] = False
    return chipped if chipped.sum() >= MIN_INK_KEPT * mask.sum() else mask


def resample_count(n: int, target: int) -> int:
    """How many training crops a class with `n` real ones gets: `max(n, sqrt(n * target))`.

    The geometric mean between what a class has and a common target lifts rare
    classes without flattening the distribution: 1 real crop becomes 10 for
    target 100, 25 become 50, and classes at or above the target are left alone.
    Copying a single crop 100 times would only teach that one drawing.
    """
    if n <= 0:
        return 0
    return max(n, round(math.sqrt(n * target)))
