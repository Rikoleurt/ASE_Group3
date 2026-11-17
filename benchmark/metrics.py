"""Benchmark metrics over per-tablet records. Pure numpy: no models, no files.

A benchmark run turns every (model, tablet) pair into a `TabletRecord`:

* `detections`: every box the detector returned at the low sweep threshold, with
  its confidence, its top labels and the truth it matched (greedy by confidence,
  IoU >= 0.5, as in `la.evaluation`). Greedy matching visits boxes from most to
  least confident, so the matches of the boxes above any higher threshold are the
  same as if only those boxes had been predicted: one matching serves the whole
  confidence sweep.
* `identifications`: the reader run on the *true* boxes, so naming is scored
  without detection errors.

Every metric is a function of a list of records, so a bootstrap can resample
whole tablets (signs on one tablet share a scribe and a drawing) and a paired
bootstrap can resample the *same* tablets for two models.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

OPERATING_CONF = 0.25          # the web app's detection threshold
SWEEP = (0.05, 0.10, 0.15, 0.25, 0.35, 0.50, 0.65, 0.80)
COVERAGES = (0.5, 0.8, 1.0)
ECE_BINS = 15
BUCKETS = ("unseen", "1", "2-4", "5+")
LOWER_IS_BETTER = {"id_ece"}
MACRO = "id_macro_top1"      # resampled within each sign, not by tablet: see `_macro_draws`


def bucket_of(train_count: int) -> str:
    """Training-frequency bucket of a sign: how many real train crops it has."""
    if train_count <= 0:
        return "unseen"
    if train_count == 1:
        return "1"
    return "2-4" if train_count <= 4 else "5+"


@dataclass
class Detection:
    confidence: float
    labels: list[str]               # best first; empty if the model does not name signs
    probs: list[float]              # same length as labels
    truth: int = -1                 # index into the tablet's truths, -1 if unmatched


@dataclass
class Identification:
    sign: str                       # true sign ID
    labels: list[str]               # reader's top labels on the true box, best first
    probs: list[float]
    role: str = "unknown"
    bucket: str = "5+"


@dataclass
class TabletRecord:
    tablet: str
    truth_signs: list[str | None]   # per truth; None = identity unknown (review-added box)
    truth_learnable: list[bool]
    detections: list[Detection] = field(default_factory=list)
    identifications: list[Identification] = field(default_factory=list)


# --- detection and end to end -------------------------------------------------

def _at(record: TabletRecord, conf: float) -> list[Detection]:
    return [d for d in record.detections if d.confidence >= conf]


def detection_counts(records: list[TabletRecord], conf: float = OPERATING_CONF) -> dict[str, int]:
    out = defaultdict(int)
    for r in records:
        kept = _at(r, conf)
        found = {d.truth for d in kept if d.truth >= 0}
        out["predictions"] += len(kept)
        out["truths"] += len(r.truth_signs)
        out["found"] += len(found)
        for d in kept:
            if d.truth < 0:
                continue
            sign = r.truth_signs[d.truth]
            if sign is None:
                continue
            out["found_named"] += 1
            top1 = bool(d.labels) and d.labels[0] == sign
            out["read_top1"] += top1
            out["read_top3"] += sign in d.labels[:3]
            out["read_top1_learnable"] += top1 and r.truth_learnable[d.truth]
        out["named"] += sum(s is not None for s in r.truth_signs)
        out["named_learnable"] += sum(s is not None and l for s, l in zip(r.truth_signs, r.truth_learnable))
    return dict(out)


def _ratio(num: float, den: float) -> float:
    return num / den if den else float("nan")


def end_to_end(records: list[TabletRecord], conf: float = OPERATING_CONF) -> dict[str, float]:
    """The rates `evaluate.py` reports, at one detection threshold."""
    c = detection_counts(records, conf)
    g = c.get
    return {
        "precision": _ratio(g("found", 0), g("predictions", 0)),
        "recall": _ratio(g("found", 0), g("truths", 0)),
        "read_top1": _ratio(g("read_top1", 0), g("named", 0)),
        "read_top3": _ratio(g("read_top3", 0), g("named", 0)),
        "read_top1_learnable": _ratio(g("read_top1_learnable", 0), g("named_learnable", 0)),
        "named_given_found": _ratio(g("read_top1", 0), g("found_named", 0)),
    }


def average_precision(records: list[TabletRecord]) -> float:
    """Class-agnostic AP at IoU 0.5 over the pooled boxes (all-point interpolation)."""
    scored = [(d.confidence, d.truth >= 0) for r in records for d in r.detections]
    truths = sum(len(r.truth_signs) for r in records)
    if not truths:
        return float("nan")
    if not scored:
        return 0.0
    scored.sort(key=lambda x: -x[0])
    hits = np.array([h for _, h in scored], dtype=float)
    tp = np.cumsum(hits)
    precision = tp / np.arange(1, len(hits) + 1)
    recall = tp / truths
    # Precision envelope, then integrate over recall steps.
    envelope = np.maximum.accumulate(precision[::-1])[::-1]
    steps = np.diff(np.concatenate([[0.0], recall]))
    return float((envelope * steps).sum())


# --- identification on true boxes ----------------------------------------------

def _idents(records: list[TabletRecord]) -> list[Identification]:
    return [i for r in records for i in r.identifications]


def _top(idents: list[Identification], k: int) -> float:
    return _ratio(sum(i.sign in i.labels[:k] for i in idents), len(idents))


def macro_top1(idents: list[Identification]) -> float:
    """Mean over sign IDs of each sign's top-1 accuracy: every sign counts once."""
    per: dict[str, list[bool]] = defaultdict(list)
    for i in idents:
        per[i.sign].append(bool(i.labels) and i.labels[0] == i.sign)
    return float(np.mean([np.mean(v) for v in per.values()])) if per else float("nan")


def ece(idents: list[Identification], bins: int = ECE_BINS) -> float:
    """Expected calibration error of the top-1 probability."""
    if not idents:
        return float("nan")
    conf = np.array([i.probs[0] if i.probs else 0.0 for i in idents])
    hit = np.array([bool(i.labels) and i.labels[0] == i.sign for i in idents], dtype=float)
    edges = np.linspace(0, 1, bins + 1)
    which = np.clip(np.digitize(conf, edges[1:-1]), 0, bins - 1)
    total = 0.0
    for b in range(bins):
        mask = which == b
        if mask.any():
            total += mask.mean() * abs(hit[mask].mean() - conf[mask].mean())
    return float(total)


def selective(idents: list[Identification], coverage: float) -> float:
    """Top-1 accuracy on the `coverage` share of signs the reader is most confident about."""
    if not idents:
        return float("nan")
    order = sorted(idents, key=lambda i: -(i.probs[0] if i.probs else 0.0))
    kept = order[:max(1, round(coverage * len(order)))]
    return _top(kept, 1)


def identification(records: list[TabletRecord]) -> dict[str, float]:
    idents = _idents(records)
    out = {"id_top1": _top(idents, 1), "id_top3": _top(idents, 3), "id_top5": _top(idents, 5),
           "id_macro_top1": macro_top1(idents), "id_ece": ece(idents)}
    for b in BUCKETS:
        out[f"id_top1_bucket_{b}"] = _top([i for i in idents if i.bucket == b], 1)
    for role in sorted({i.role for i in idents}):
        out[f"id_top1_role_{role}"] = _top([i for i in idents if i.role == role], 1)
    for c in COVERAGES:
        out[f"id_top1_at_{int(c * 100)}pct"] = selective(idents, c)
    return out


def counts(records: list[TabletRecord]) -> dict[str, int]:
    idents = _idents(records)
    out = {"tablets": len(records), "identified_truths": len(idents)}
    for b in BUCKETS:
        out[f"bucket_{b}"] = sum(i.bucket == b for i in idents)
    out.update(detection_counts(records))
    return out


def all_metrics(records: list[TabletRecord], detects: bool = True, identifies: bool = True) -> dict[str, float]:
    out: dict[str, float] = {}
    if detects:
        out.update(end_to_end(records))
        out["ap50"] = average_precision(records)
    if identifies:
        out.update(identification(records))
    return out


def sweep(records: list[TabletRecord], thresholds=SWEEP) -> list[dict[str, float]]:
    return [{"conf": t, **end_to_end(records, t)} for t in thresholds]


def coverage_curve(records: list[TabletRecord], points: int = 20) -> list[dict[str, float]]:
    idents = _idents(records)
    return [{"coverage": c, "id_top1": selective(idents, c)} for c in np.linspace(0.05, 1.0, points)]


# --- bootstrap -------------------------------------------------------------------

def resample_indices(n: int, resamples: int = 1000, seed: int = 0) -> np.ndarray:
    """Tablet indices for every resample. Share them between models to pair the comparison."""
    return np.random.default_rng(seed).integers(0, n, size=(resamples, n))


def _interval(values: list[float], level: float) -> tuple[float, float]:
    v = np.asarray(values, dtype=float)
    v = v[~np.isnan(v)]
    if not len(v):
        return float("nan"), float("nan")
    tail = (1 - level) / 2 * 100
    return float(np.percentile(v, tail)), float(np.percentile(v, 100 - tail))


def _macro_hits(records: list[TabletRecord]) -> dict[str, np.ndarray]:
    per: dict[str, list[bool]] = defaultdict(list)
    for i in _idents(records):
        per[i.sign].append(bool(i.labels) and i.labels[0] == i.sign)
    return {k: np.array(v, dtype=float) for k, v in per.items()}


def _macro_draws(hits: dict[str, np.ndarray], resamples: int, seed: int) -> dict[str, np.ndarray]:
    """Per sign, resampled indices of its attestations: the set of signs stays fixed.

    Resampling tablets instead drops rare signs more often than common ones, which
    shifts a per-sign average (rare signs are read worse) and leaves its interval
    off the estimate. Sharing these indices between models pairs the comparison.
    """
    rng = np.random.default_rng(seed)
    return {k: rng.integers(0, len(v), size=(resamples, len(v))) for k, v in sorted(hits.items())}


def _macro_values(hits: dict[str, np.ndarray], draws: dict[str, np.ndarray]) -> np.ndarray:
    return np.mean([hits[k][d].mean(axis=1) for k, d in draws.items()], axis=0)


def bootstrap(records: list[TabletRecord], metric: Callable[[list[TabletRecord]], dict[str, float]],
              draws: np.ndarray, level: float = 0.95) -> dict[str, tuple[float, float]]:
    values: dict[str, list[float]] = defaultdict(list)
    for row in draws:
        for k, v in metric([records[i] for i in row]).items():
            values[k].append(v)
    out = {k: _interval(v, level) for k, v in values.items()}
    if MACRO in out and (hits := _macro_hits(records)):
        out[MACRO] = _interval(list(_macro_values(hits, _macro_draws(hits, len(draws), 0))), level)
    return out


def paired_difference(records: list[TabletRecord], reference: list[TabletRecord],
                      metric: Callable[[list[TabletRecord]], dict[str, float]],
                      draws: np.ndarray, level: float = 0.95) -> dict[str, dict[str, float]]:
    """Model minus reference on the same resampled tablets: point estimate and CI."""
    if [r.tablet for r in records] != [r.tablet for r in reference]:
        raise ValueError("paired comparison needs the same tablets in the same order")
    point_a, point_b = metric(records), metric(reference)
    diffs: dict[str, list[float]] = defaultdict(list)
    for row in draws:
        a = metric([records[i] for i in row])
        b = metric([reference[i] for i in row])
        for k in a.keys() & b.keys():
            diffs[k].append(a[k] - b[k])
    out = {}
    for k, v in diffs.items():
        if k == MACRO:
            ha, hb = _macro_hits(records), _macro_hits(reference)
            if ha.keys() != hb.keys():
                raise ValueError("paired comparison needs the same true boxes")
            md = _macro_draws(ha, len(draws), 0)
            v = list(_macro_values(ha, md) - _macro_values(hb, md))
        lo, hi = _interval(v, level)
        up, down = ("worse", "better") if k in LOWER_IS_BETTER else ("better", "worse")
        out[k] = {"diff": point_a[k] - point_b[k], "lo": lo, "hi": hi,
                  "verdict": up if lo > 0 else down if hi < 0 else "tie"}
    return out
