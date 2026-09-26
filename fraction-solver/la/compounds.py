"""Is a sign a doubling of another sign, written twice?

Corazza et al. leave W and X unvalued but suspect **W = BB** and **X = AA**. That
is a claim about shape, so it is testable — but only with calibration. A ranking
on its own cannot say whether "4th of 13" differs meaningfully from "1st", and a
null result from an unvalidated method means nothing.

So the test carries both controls:

* **Positive** — the corpus contains adjacent identical fraction pairs (`D D`)
  written by real scribes. Composing such a pair gives a known doubling, and the
  method must recognise it. It does: the true answer ranks first every time, at a
  distance of roughly 19-25.
* **Negative** — a simple single-stroke sign is not a doubling of anything. Its
  best candidate distance shows what "not a doubling" looks like.

With both in hand, a candidate is judged by *distance calibrated against the
controls*, not by its rank.
"""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median

import numpy as np

from la import shapes

MIN_ATTESTATIONS = 3  # a candidate needs enough examples to form varied pairs


@dataclass
class CompoundResult:
    target: str
    attestations: int
    ranked: list[tuple[str, float]] = field(default_factory=list)
    hypothesis: str | None = None
    hypothesis_rank: int | None = None
    hypothesis_distance: float | None = None

    @property
    def best_distance(self) -> float | None:
        return self.ranked[0][1] if self.ranked else None


def compose(a: shapes.Glyph, b: shapes.Glyph, geometry: str = "side") -> shapes.Glyph:
    """Place two tracings together as a scribe might write them in sequence.

    Ligatures are not all written the same way, so several arrangements are tried
    and the best match is taken. Assuming one fixed layout would let the geometry,
    rather than the shapes, decide the answer.
    """
    ma, mb = shapes.load_mask(a.path), shapes.load_mask(b.path)
    ha, wa = ma.shape
    hb, wb = mb.shape

    if geometry in {"side", "tight", "overlap"}:
        gap = {"side": max(4, max(ha, hb) // 20), "tight": 0, "overlap": -min(wa, wb) // 4}[geometry]
        width = wa + gap + wb
        canvas = np.zeros((max(ha, hb), max(width, 1)), dtype=bool)
        canvas[:ha, :wa] |= ma
        x0 = max(wa + gap, 0)
        canvas[:hb, x0:x0 + wb] |= mb
    elif geometry == "stack":
        canvas = np.zeros((ha + hb, max(wa, wb)), dtype=bool)
        canvas[:ha, :wa] |= ma
        canvas[ha:, :wb] |= mb
    else:
        raise ValueError(geometry)

    m = shapes.normalise(canvas)
    return shapes.Glyph("composite", "", None, m, shapes.hu_moments(m), shapes.boundary(m))


GEOMETRIES = ("side", "tight", "overlap", "stack")


def _distance_to_targets(comp: shapes.Glyph, targets: list[shapes.Glyph]) -> float:
    return median(shapes.hausdorff(comp, t) for t in targets)


def score_candidates(
    targets: list[shapes.Glyph],
    by_sign: dict[str, list[shapes.Glyph]],
    exclude_tablets: set[str],
    max_pairs: int = 10,
    seed: int = 11,
) -> list[tuple[str, float]]:
    """Distance from the target sign to composites of each candidate, doubled.

    Candidates are drawn only from tablets the target does not appear on, so a
    scribe's own hand cannot make their marks match themselves.
    """
    rng = random.Random(seed)
    scored: list[tuple[str, float]] = []
    for sign, items in by_sign.items():
        usable = [g for g in items if g.tablet not in exclude_tablets]
        if len(usable) < MIN_ATTESTATIONS:
            continue
        pairs = list(itertools.combinations(usable, 2))
        rng.shuffle(pairs)
        pairs = pairs[:max_pairs]
        best_per_pair = [
            min(_distance_to_targets(compose(a, b, g), targets) for g in GEOMETRIES)
            for a, b in pairs
        ]
        scored.append((sign, median(best_per_pair)))
    scored.sort(key=lambda t: t[1])
    return scored


def test_hypothesis(
    target_sign: str,
    hypothesis: str | None,
    by_sign: dict[str, list[shapes.Glyph]],
) -> CompoundResult:
    targets = by_sign.get(target_sign, [])
    if not targets:
        return CompoundResult(target=target_sign, attestations=0)
    exclude = {t.tablet for t in targets}
    ranked = score_candidates(targets, by_sign, exclude_tablets=exclude)
    result = CompoundResult(
        target=target_sign,
        attestations=len(targets),
        ranked=ranked,
        hypothesis=hypothesis,
    )
    if hypothesis:
        for i, (sign, dist) in enumerate(ranked, 1):
            if sign == hypothesis:
                result.hypothesis_rank = i
                result.hypothesis_distance = dist
    return result


def positive_controls(
    real_doublings: list[tuple[str, str, shapes.Glyph, shapes.Glyph]],
    by_sign: dict[str, list[shapes.Glyph]],
    limit: int = 6,
) -> list[dict]:
    """Known doublings, composed from adjacent identical marks on one tablet."""
    out: list[dict] = []
    for tablet, sign, g1, g2 in real_doublings[:limit]:
        for geometry in ("side",):
            target = compose(g1, g2, geometry)
            ranked = score_candidates([target], by_sign, exclude_tablets={tablet})
            rank = next((i for i, (s, _) in enumerate(ranked, 1) if s == sign), None)
            out.append({
                "tablet": tablet,
                "sign": sign,
                "rank": rank,
                "distance": next((d for s, d in ranked if s == sign), None),
                "best_distance": ranked[0][1] if ranked else None,
                "candidates": len(ranked),
            })
    return out


def negative_controls(
    signs: list[str],
    by_sign: dict[str, list[shapes.Glyph]],
) -> list[dict]:
    """Signs that are not doublings: what does 'not a doubling' score?"""
    out: list[dict] = []
    for sign in signs:
        targets = by_sign.get(sign, [])
        if not targets:
            continue
        exclude = {t.tablet for t in targets}
        ranked = [(s, d) for s, d in score_candidates(targets, by_sign, exclude) if s != sign]
        out.append({
            "sign": sign,
            "best_candidate": ranked[0][0] if ranked else None,
            "best_distance": ranked[0][1] if ranked else None,
        })
    return out


def load_glyphs(crop_dir: Path) -> dict[str, list[shapes.Glyph]]:
    by_sign: dict[str, list[shapes.Glyph]] = {}
    for path in sorted(crop_dir.glob("*__*.png")):
        sign, tablet, _pos = path.stem.split("__")
        by_sign.setdefault(sign, []).append(shapes.build(path, sign, tablet.replace("_", " ")))
    return by_sign


def find_real_doublings(docs: dict[str, dict], by_sign: dict[str, list[shapes.Glyph]]):
    """Tablets where two identical fraction marks stand next to each other."""
    found = []
    for doc in docs.values():
        tablet = doc.get("id", "?")
        for line in doc.get("lines") or []:
            ids = [t.get("id") for t in line if t.get("kind") == "fraction"]
            for a, b in zip(ids, ids[1:]):
                if a != b:
                    continue
                marks = [g for g in by_sign.get(a, []) if g.tablet == tablet]
                if len(marks) >= 2:
                    found.append((tablet, a, marks[0], marks[1]))
    return found
