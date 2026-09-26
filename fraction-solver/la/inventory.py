"""Does classical shape matching scale to the whole sign inventory?

The fraction result — 88% top-1 over 16 signs — is the easy case: few strokes,
well separated, and several signs with seventy or more examples. The corpus has
~364 sign types and most are rare, so the question that matters for any reader
built on this is how accuracy falls away as attestations thin out.

Two things make this measurement honest:

* **Same-tablet neighbours are excluded.** Two marks written by one scribe on one
  tablet are unusually alike, so counting them would inflate every figure. This
  is the single biggest trap in the whole exercise.
* **Accuracy is reported against attestation count**, not as one headline number.
  A single average hides exactly the behaviour a reader needs to design around.

Distances use overlap (IoU), computed for all pairs at once as a matrix product:
contour distance scores a few points higher but cannot be vectorised, and at
5,000 glyphs that is the difference between a minute and a day.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from la import shapes


@dataclass
class Entry:
    sign: str
    role: str
    tablet: str
    path: Path


def scan(crop_dir: Path) -> list[Entry]:
    """Crops are named `<sign>__<role>__<tablet>__<position>.png`."""
    out: list[Entry] = []
    for path in sorted(crop_dir.glob("*__*__*__*.png")):
        sign, role, tablet, _pos = path.stem.split("__")
        out.append(Entry(sign=sign, role=role, tablet=tablet.replace("_", " "), path=path))
    return out


def build_matrix(entries: list[Entry], size: int = 64) -> np.ndarray:
    """One row per glyph: the normalised mask, flattened."""
    rows = np.zeros((len(entries), size * size), dtype=np.float32)
    for i, e in enumerate(entries):
        mask = shapes.normalise(shapes.load_mask(e.path), size=size)
        rows[i] = mask.reshape(-1).astype(np.float32)
    return rows


def iou_distances(rows: np.ndarray, block: int = 512) -> np.ndarray:
    """Pairwise 1 - IoU for every glyph, via matrix products.

    intersection = rows @ rows.T; union = |a| + |b| - intersection.
    Computed in blocks so peak memory stays modest.
    """
    n = rows.shape[0]
    area = rows.sum(axis=1)
    dist = np.ones((n, n), dtype=np.float32)
    for start in range(0, n, block):
        stop = min(start + block, n)
        inter = rows[start:stop] @ rows.T
        union = area[start:stop, None] + area[None, :] - inter
        with np.errstate(divide="ignore", invalid="ignore"):
            iou = np.where(union > 0, inter / union, 0.0)
        dist[start:stop] = 1.0 - iou
    np.fill_diagonal(dist, np.inf)
    return dist


def evaluate(entries: list[Entry], dist: np.ndarray, exclude_same_tablet: bool = True) -> dict:
    """Leave-one-out retrieval, scored overall and by how well attested a sign is."""
    signs = [e.sign for e in entries]
    tablets = [e.tablet for e in entries]
    counts = Counter(signs)

    tablet_ids = {t: i for i, t in enumerate(sorted(set(tablets)))}
    tablet_index = np.array([tablet_ids[t] for t in tablets])

    per_sign_hits: dict[str, list[bool]] = defaultdict(list)
    top1 = top5 = scored = 0

    for i, entry in enumerate(entries):
        row = dist[i].copy()
        if exclude_same_tablet:
            row[tablet_index == tablet_index[i]] = np.inf
        candidates = [j for j in np.argsort(row) if np.isfinite(row[j])]
        # A sign needs at least one attestation on another tablet to be findable.
        if not any(signs[j] == entry.sign for j in candidates):
            continue
        scored += 1
        labels = [signs[j] for j in candidates[:5]]
        hit1 = labels[0] == entry.sign
        top1 += hit1
        top5 += entry.sign in labels
        per_sign_hits[entry.sign].append(hit1)

    total = len(entries)
    frequency_baseline = sum((c / total) * ((c - 1) / max(total - 1, 1)) for c in counts.values())

    bins = [(1, 2), (2, 5), (5, 10), (10, 25), (25, 50), (50, 10_000)]
    by_frequency = []
    for low, high in bins:
        members = [s for s, c in counts.items() if low <= c < high]
        hits = [h for s in members for h in per_sign_hits.get(s, [])]
        if hits:
            by_frequency.append({
                "attestations": f"{low}-{high - 1}" if high < 10_000 else f"{low}+",
                "sign_types": len(members),
                "glyphs_scored": len(hits),
                "top1": sum(hits) / len(hits),
            })

    by_role: dict[str, dict] = {}
    for role in sorted({e.role for e in entries}):
        idx = [i for i, e in enumerate(entries) if e.role == role]
        hits = [h for i in idx for h in per_sign_hits.get(entries[i].sign, [])[:1]]
        role_hits = [h for s in {entries[i].sign for i in idx} for h in per_sign_hits.get(s, [])]
        if role_hits:
            by_role[role] = {"glyphs": len(idx), "top1": sum(role_hits) / len(role_hits)}

    return {
        "glyphs": total,
        "sign_types": len(counts),
        "scored": scored,
        "top1": top1 / scored if scored else 0.0,
        "top5": top5 / scored if scored else 0.0,
        "frequency_baseline": frequency_baseline,
        "random_baseline": 1 / len(counts) if counts else 0.0,
        "by_frequency": by_frequency,
        "by_role": by_role,
        "coverage": coverage_table(counts),
    }


def coverage_table(counts: Counter) -> list[dict]:
    """How much of the corpus sits in sign types above each attestation threshold."""
    total = sum(counts.values())
    out = []
    for threshold in (2, 3, 5, 10, 25, 50):
        members = [c for c in counts.values() if c >= threshold]
        out.append({
            "threshold": threshold,
            "sign_types": len(members),
            "glyphs": sum(members),
            "share_of_corpus": sum(members) / total if total else 0.0,
        })
    return out
