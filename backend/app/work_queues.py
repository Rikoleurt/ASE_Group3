"""Work queues: where scholars' attention is most useful (scholars' workbench, story J).

- **Most disagreement:** tablets where two readings differ most, the scholars' against the
  model's (read offline by scripts/build_disagreement.py, since reading the whole corpus takes
  from half an hour to hours) or against the tablet's accepted edition (compared live; no model involved).
- **Low-confidence signs:** the model's least confident signs, from the same offline run.
- **Tablets with no edition** and **editions with close votes** come from the database.
- **Corrections awaiting review** are the Review page's own queue (GET /corrections).

The offline file, models/disagreement.json:
    {"model_version", "built_at",
     "tablets": {slug: {"tablet", "agree", "differs", "missing", "total"}},
     "low_confidence": [{"slug", "tablet", "id", "sign", "label", "reading", "confidence", "box",
                         "candidates": [{"sign", "label", "probability"}]}]}
"""

import json
import os
from pathlib import Path
from threading import Lock

from backend.app import box_matching

ROOT = Path(__file__).resolve().parents[2]
DISAGREEMENT = Path(os.getenv("DISAGREEMENT_FILE", ROOT / "models" / "disagreement.json"))
LOW_CONFIDENCE = 50.0  # percent: model signs below this are queued
BUILD_HINT = "Build it with: python scripts/build_disagreement.py"


def compare(first: list[dict], second: list[dict], a: str = "scholar", b: str = "model") -> dict:
    """How two readings of a tablet differ, from boxes {id, box: {x, y, w, h}, sign}: clusters
    where both name the same sign (agree), name different signs (differs), or only one has a box
    (missing); and the share of clusters that do not agree (score, 0 to 1)."""
    clusters = box_matching.cluster({a: first, b: second})
    counts = {"agree": 0, "differs": 0, "missing": 0}
    for found in clusters:
        counts[found.status([a, b])] += 1
    total = len(clusters)
    return {
        **counts,
        "total": total,
        "score": round(1 - counts["agree"] / total, 4) if total else 0.0,
    }


_LOCK = Lock()
_CACHE: dict[str, tuple[int, dict]] = {}


def offline() -> dict | None:
    """The offline run's results, re-read when the file changes; None when it was not built."""
    try:
        modified = DISAGREEMENT.stat().st_mtime_ns
    except FileNotFoundError:
        return None
    key = str(DISAGREEMENT)
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and cached[0] == modified:
            return cached[1]
    data = json.loads(DISAGREEMENT.read_text(encoding="utf-8"))
    for row in data.get("tablets", {}).values():
        total = row.get("total") or 0
        row["score"] = round(1 - row.get("agree", 0) / total, 4) if total else 0.0
    with _LOCK:
        _CACHE[key] = (modified, data)
    return data


def close_votes(counts: list[int], margin: int = 1) -> int | None:
    """The gap between the two most-backed releases when it is at most `margin` and someone
    voted; None otherwise. counts: votes per release."""
    top = sorted(counts, reverse=True)
    if len(top) < 2 or top[0] == 0 or top[0] - top[1] > margin:
        return None
    return top[0] - top[1]
