#!/usr/bin/env python3
"""Read every drawn tablet with the model and compare it with the scholars' reading, for the
work queues (scholars' workbench, story J; see backend/app/work_queues.py).

    python scripts/build_disagreement.py              # every tablet with a drawing here
    python scripts/build_disagreement.py --limit 30   # the first 30 not done yet

A model reading takes a few seconds per tablet (up to ~20 s on a slow machine), so a full run
takes from half an hour to a few hours. The file is rewritten after
each tablet, and tablets already read with the same model version are skipped, so a run can be
stopped and resumed. The server picks up the new file by itself.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app import corpus, glyph_index, tablet_demo, work_queues  # noqa: E402


def boxes(signs) -> list[dict]:
    return [{"id": sign.id, "box": sign.box.model_dump(), "sign": sign.sign} for sign in signs]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--limit", type=int, default=0, help="read at most this many new tablets (0: all)"
    )
    parser.add_argument("--out", type=Path, default=work_queues.DISAGREEMENT)
    parser.add_argument("--threshold", type=float, default=work_queues.LOW_CONFIDENCE)
    args = parser.parse_args()

    index = glyph_index.get_index()
    drawn, missing = corpus.tablets(index)
    version = str(tablet_demo.model_version())
    data = {"model_version": version, "tablets": {}, "low_confidence": []}
    if args.out.exists():
        previous = json.loads(args.out.read_text(encoding="utf-8"))
        if previous.get("model_version") == version:  # a new model starts over
            data = previous
    todo = [tablet for tablet in drawn if tablet.slug not in data["tablets"]]
    if args.limit:
        todo = todo[: args.limit]
    print(
        f"{len(drawn)} drawn tablets ({missing} more without a drawing); {len(todo)} to read",
        flush=True,
    )

    for number, tablet in enumerate(todo, 1):
        started = time.monotonic()
        model = corpus.model_signs(tablet.slug, glyph_index.tracing_path(tablet.slug))
        counts = work_queues.compare(boxes(corpus.scholar_signs(index, tablet.slug)), boxes(model))
        data["tablets"][tablet.slug] = {
            "tablet": tablet.tablet,
            **{k: counts[k] for k in ("agree", "differs", "missing", "total")},
        }
        data["low_confidence"] = [
            row for row in data["low_confidence"] if row["slug"] != tablet.slug
        ] + [
            {
                "slug": tablet.slug,
                "tablet": tablet.tablet,
                "id": sign.id,
                "sign": sign.sign,
                "label": sign.label,
                "reading": sign.reading,
                "confidence": round(sign.confidence, 1),
                "box": sign.box.model_dump(),
                "candidates": [
                    {"sign": c.sign, "label": c.label, "probability": round(c.probability, 1)}
                    for c in sign.candidates[:3]
                ],
            }
            for sign in model
            if sign.confidence < args.threshold
        ]
        data["built_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        temporary = args.out.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        temporary.replace(args.out)
        print(
            f"[{number}/{len(todo)}] {tablet.tablet}: {counts['agree']}/{counts['total']} agree "
            f"({time.monotonic() - started:.0f} s)",
            flush=True,
        )
    print(
        f"Wrote {args.out}: {len(data['tablets'])} tablets, {len(data['low_confidence'])} low-confidence signs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
