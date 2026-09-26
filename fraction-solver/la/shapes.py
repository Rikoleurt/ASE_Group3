"""Shape analysis of the fraction tracings.

Two questions the arithmetic cannot reach:

  * **Are W and X compound signs?** Corazza et al. suspect W = BB and X = AA but
    leave both unvalued. That is a claim about shape, and shape is measurable.
  * **Could an editor confuse A with B?** Our own A-window rests on reading
    KH 86.2 as `A B B`, which Corazza et al. re-read as `A A`. If A and B are
    visually far apart in every attestation, their re-reading is surprising.

Everything is measured before it is used: leave-one-out retrieval says whether
the descriptors can tell the signs apart at all. If they cannot, the rest is
not evidence and the analysis stops there.

No OpenCV or scikit-image — Hu moments are normalised central moments, and the
alpha channel of a tracing is already a clean binary mask.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.spatial.distance import directed_hausdorff

CANON = 128  # canonical raster size


@dataclass
class Glyph:
    sign: str
    tablet: str
    path: Path
    mask: np.ndarray          # canonical CANON x CANON boolean
    hu: np.ndarray            # 7 log-scaled Hu moments
    contour: np.ndarray       # boundary pixel coordinates in canonical space


def load_mask(path: Path) -> np.ndarray:
    """Extract the ink from a tracing.

    SigLA serves RGBA with the strokes in the alpha channel; lineara.eu re-encodes
    the same drawings as opaque palette PNGs on white. Keying on alpha alone is
    therefore wrong for half the sources — and silently so: a fully opaque image
    yields a mask of every pixel, i.e. a solid rectangle, which still produces
    plausible-looking distances. Alpha is only used when it actually varies.
    """
    im = Image.open(path).convert("RGBA")
    alpha = np.array(im)[:, :, 3]
    if alpha.min() != alpha.max():
        return alpha > 64
    grey = np.array(im.convert("L"))
    return grey < 128


def normalise(mask: np.ndarray, size: int = CANON, rotate: bool = False) -> np.ndarray:
    """Trim to ink, align the principal axis, scale and centre.

    Two attestations of one sign differ in position, size and tilt. Removing all
    three is what makes them comparable; anything left is real difference of form.
    """
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return np.zeros((size, size), dtype=bool)

    pts = np.stack([xs, ys], axis=1).astype(float)
    centre = pts.mean(axis=0)
    centred = pts - centre

    # Principal axis from the covariance of the ink.
    rot = np.eye(2)
    # Orientation is part of a sign's identity in a writing system: J and L differ
    # mainly by how they are turned. Aligning the principal axis therefore throws
    # away signal rather than noise, so it is off by default.
    cov = np.cov(centred.T)
    if rotate and cov.shape == (2, 2) and np.isfinite(cov).all():
        _, vecs = np.linalg.eigh(cov)
        axis = vecs[:, -1]
        angle = math.atan2(axis[1], axis[0])
        c, s = math.cos(-angle), math.sin(-angle)
        rot = np.array([[c, -s], [s, c]])
        centred = centred @ rot.T

    extent = np.abs(centred).max()
    if extent == 0:
        return np.zeros((size, size), dtype=bool)
    scale = (size / 2 - 2) / extent

    # Sample backwards: for every canonical pixel, find where it came from in the
    # source and read the mask there. Mapping forwards instead scatters the ink
    # and leaves holes in small glyphs, which corrupts area, moments and boundary.
    grid = np.arange(size)
    gx, gy = np.meshgrid(grid, grid)
    canon = np.stack([gx.ravel(), gy.ravel()], axis=1).astype(float)
    src = (canon - size / 2) / scale @ rot + centre  # rot is orthonormal: rot.T.T == rot

    cols = np.rint(src[:, 0]).astype(int)
    rows = np.rint(src[:, 1]).astype(int)
    inside = (cols >= 0) & (cols < mask.shape[1]) & (rows >= 0) & (rows < mask.shape[0])

    out = np.zeros(size * size, dtype=bool)
    out[inside] = mask[rows[inside], cols[inside]]
    return out.reshape(size, size)


def hu_moments(mask: np.ndarray) -> np.ndarray:
    """The seven Hu invariants, log-scaled. Implemented directly so it is inspectable."""
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return np.zeros(7)
    x, y = xs.astype(float), ys.astype(float)
    xb, yb = x.mean(), y.mean()
    m00 = float(len(x))

    def mu(p: int, q: int) -> float:
        return float(np.sum((x - xb) ** p * (y - yb) ** q))

    def nu(p: int, q: int) -> float:
        return mu(p, q) / (m00 ** (1 + (p + q) / 2))

    n20, n02, n11 = nu(2, 0), nu(0, 2), nu(1, 1)
    n30, n03, n21, n12 = nu(3, 0), nu(0, 3), nu(2, 1), nu(1, 2)

    h = np.zeros(7)
    h[0] = n20 + n02
    h[1] = (n20 - n02) ** 2 + 4 * n11 ** 2
    h[2] = (n30 - 3 * n12) ** 2 + (3 * n21 - n03) ** 2
    h[3] = (n30 + n12) ** 2 + (n21 + n03) ** 2
    h[4] = ((n30 - 3 * n12) * (n30 + n12) * ((n30 + n12) ** 2 - 3 * (n21 + n03) ** 2)
            + (3 * n21 - n03) * (n21 + n03) * (3 * (n30 + n12) ** 2 - (n21 + n03) ** 2))
    h[5] = ((n20 - n02) * ((n30 + n12) ** 2 - (n21 + n03) ** 2)
            + 4 * n11 * (n30 + n12) * (n21 + n03))
    h[6] = ((3 * n21 - n03) * (n30 + n12) * ((n30 + n12) ** 2 - 3 * (n21 + n03) ** 2)
            - (n30 - 3 * n12) * (n21 + n03) * (3 * (n30 + n12) ** 2 - (n21 + n03) ** 2))
    return np.sign(h) * np.log1p(np.abs(h) * 1e6)


def boundary(mask: np.ndarray) -> np.ndarray:
    """Ink pixels with at least one empty neighbour."""
    padded = np.pad(mask, 1)
    interior = (padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:])
    edge = mask & ~interior
    ys, xs = np.nonzero(edge)
    return np.stack([xs, ys], axis=1).astype(float)


def build(path: Path, sign: str, tablet: str, rotate: bool = False) -> Glyph:
    mask = normalise(load_mask(path), rotate=rotate)
    return Glyph(sign=sign, tablet=tablet, path=path, mask=mask,
                 hu=hu_moments(mask), contour=boundary(mask))


def iou(a: Glyph, b: Glyph) -> float:
    inter = np.logical_and(a.mask, b.mask).sum()
    union = np.logical_or(a.mask, b.mask).sum()
    return float(inter / union) if union else 0.0


def hausdorff(a: Glyph, b: Glyph) -> float:
    if len(a.contour) == 0 or len(b.contour) == 0:
        return float(CANON)
    return max(directed_hausdorff(a.contour, b.contour)[0],
               directed_hausdorff(b.contour, a.contour)[0])


def distance(a: Glyph, b: Glyph) -> float:
    """One combined distance: shape moments, overlap, and outline agreement.

    Each term is scaled to roughly [0, 1] so no single measure dominates. The
    weights are deliberately equal — there is no training set to tune them on,
    and tuning them on the answers would be circular.
    """
    hu_d = float(np.linalg.norm(a.hu - b.hu)) / 10.0
    iou_d = 1.0 - iou(a, b)
    haus_d = hausdorff(a, b) / CANON
    return (hu_d + iou_d + haus_d) / 3.0


def retrieval_evaluation(glyphs: list[Glyph]) -> dict:
    """Leave-one-out: does a glyph's nearest neighbours share its sign?

    This gates everything else. Without it, a confusability matrix is decoration.
    """
    from collections import Counter

    n = len(glyphs)
    counts = Counter(g.sign for g in glyphs)
    eligible = [i for i, g in enumerate(glyphs) if counts[g.sign] >= 2]
    if not eligible:
        return {"evaluated": 0}

    dist = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            dist[i, j] = dist[j, i] = distance(glyphs[i], glyphs[j])

    top1 = top5 = 0
    for i in eligible:
        order = [j for j in np.argsort(dist[i]) if j != i]
        labels = [glyphs[j].sign for j in order]
        top1 += labels[0] == glyphs[i].sign
        top5 += glyphs[i].sign in labels[:5]

    total = sum(counts.values())
    frequency_baseline = sum((c / total) * (c - 1) / max(total - 1, 1) for c in counts.values())
    return {
        "evaluated": len(eligible),
        "top1": top1 / len(eligible),
        "top5": top5 / len(eligible),
        "random_baseline": 1 / len(counts),
        "frequency_baseline": frequency_baseline,
        "distances": dist,
    }


def sign_distance_matrix(glyphs: list[Glyph]) -> dict[tuple[str, str], float]:
    """Median distance between the attestations of each pair of signs."""
    from collections import defaultdict
    from statistics import median

    buckets: dict[tuple[str, str], list[float]] = defaultdict(list)
    for i, a in enumerate(glyphs):
        for b in glyphs[i + 1:]:
            key = tuple(sorted((a.sign, b.sign)))
            buckets[key].append(distance(a, b))
    return {k: median(v) for k, v in buckets.items() if v}


def ink_profile(glyphs: list[Glyph]) -> dict[str, dict]:
    """Per sign: how much ink, and how many separate strokes.

    A compound sign written as two marks should carry roughly twice the ink of
    its part, and show more components. Crude, but it is the direct prediction of
    the W = BB and X = AA hypotheses.
    """
    from collections import defaultdict
    from statistics import median

    by_sign: dict[str, list[Glyph]] = defaultdict(list)
    for g in glyphs:
        by_sign[g.sign].append(g)

    out: dict[str, dict] = {}
    for sign, items in by_sign.items():
        out[sign] = {
            "n": len(items),
            "ink": median(float(g.mask.sum()) for g in items),
            "components": median(float(_components(g.mask)) for g in items),
        }
    return out


def _components(mask: np.ndarray) -> int:
    """Count connected ink regions (8-connectivity), without scikit-image."""
    seen = np.zeros_like(mask, dtype=bool)
    count = 0
    h, w = mask.shape
    for sy in range(h):
        for sx in range(w):
            if not mask[sy, sx] or seen[sy, sx]:
                continue
            count += 1
            stack = [(sy, sx)]
            seen[sy, sx] = True
            while stack:
                y, x = stack.pop()
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((ny, nx))
    return count
