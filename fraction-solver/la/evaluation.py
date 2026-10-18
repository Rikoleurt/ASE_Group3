"""Scoring a sign reader on whole tablets, with confidence intervals.

The question the web demo answers is "which signs are on this tablet?", so that
is what is scored, end to end: a labelled sign counts as read when a predicted
box overlaps it (IoU >= 0.5) and that box names its sign ID. The same scoring
applies to a one-stage identity detector and to a detector + classifier, so the
two can be compared directly.

Test tablets are few (about 100), so every rate comes with a 95% bootstrap
interval that resamples whole tablets: signs on one tablet share a scribe and a
drawing, and resampling them individually would overstate the certainty.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

IOU_MATCH = 0.5


@dataclass
class Prediction:
    box: tuple[float, float, float, float]
    confidence: float
    labels: list[str]         # sign IDs, best first; empty if the model does not name signs


@dataclass
class Truth:
    box: tuple[float, float, float, float]
    sign: str | None          # None for a box added by review, whose identity is unknown
    learnable: bool = True    # the sign ID occurs in training


@dataclass
class TabletScore:
    tablet: str
    truths: int = 0
    predictions: int = 0
    found: int = 0            # truths matched by a prediction
    found_named: int = 0      # ...of which have a known sign ID: what a classifier is scored on
    named: int = 0            # truths with a known sign ID
    named_learnable: int = 0
    read_top1: int = 0
    read_top3: int = 0
    read_top1_learnable: int = 0


def iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def match(predictions: list[Prediction], truths: list[Truth], threshold: float = IOU_MATCH) -> dict[int, int]:
    """Truth index -> prediction index; greedy by confidence, each used once."""
    pairs: dict[int, int] = {}
    for p in sorted(range(len(predictions)), key=lambda i: -predictions[i].confidence):
        best, best_iou = None, threshold
        for t, truth in enumerate(truths):
            if t in pairs:
                continue
            overlap = iou(predictions[p].box, truth.box)
            if overlap >= best_iou:
                best, best_iou = t, overlap
        if best is not None:
            pairs[best] = p
    return pairs


def score_tablet(tablet: str, predictions: list[Prediction], truths: list[Truth]) -> TabletScore:
    score = TabletScore(tablet=tablet, truths=len(truths), predictions=len(predictions))
    pairs = match(predictions, truths)
    for t, truth in enumerate(truths):
        if truth.sign is not None:
            score.named += 1
            score.named_learnable += truth.learnable
        if t not in pairs:
            continue
        score.found += 1
        if truth.sign is None:
            continue
        score.found_named += 1
        labels = predictions[pairs[t]].labels
        top1 = bool(labels) and labels[0] == truth.sign
        score.read_top1 += top1
        score.read_top3 += truth.sign in labels[:3]
        score.read_top1_learnable += top1 and truth.learnable
    return score


RATES = {
    # rate: (numerator, denominator)
    "precision": ("found", "predictions"),
    "recall": ("found", "truths"),
    "read_top1": ("read_top1", "named"),
    "read_top3": ("read_top3", "named"),
    "read_top1_learnable": ("read_top1_learnable", "named_learnable"),
    "named_given_found": ("read_top1", "found_named"),
}


def totals(scores: list[TabletScore]) -> dict[str, int]:
    keys = [k for k in asdict(TabletScore("")) if k != "tablet"]
    return {k: sum(getattr(s, k) for s in scores) for k in keys}


def rates(scores: list[TabletScore]) -> dict[str, float]:
    t = totals(scores)
    return {name: (t[num] / t[den] if t[den] else float("nan")) for name, (num, den) in RATES.items()}


def bootstrap(scores: list[TabletScore], resamples: int = 1000, seed: int = 0,
              level: float = 0.95) -> dict[str, tuple[float, float]]:
    """Percentile intervals for every rate, resampling tablets with replacement."""
    if not scores:
        return {name: (float("nan"), float("nan")) for name in RATES}
    rng = np.random.default_rng(seed)
    draws = {name: [] for name in RATES}
    for _ in range(resamples):
        sample = [scores[i] for i in rng.integers(0, len(scores), len(scores))]
        for name, value in rates(sample).items():
            draws[name].append(value)
    tail = (1 - level) / 2 * 100
    return {name: (float(np.nanpercentile(v, tail)), float(np.nanpercentile(v, 100 - tail)))
            for name, v in draws.items()}


def report(scores: list[TabletScore], resamples: int = 1000, seed: int = 0) -> dict:
    return {"tablets": len(scores), "totals": totals(scores), "rates": rates(scores),
            "ci95": bootstrap(scores, resamples, seed)}
