"""Publish benchmark results as model versions the web app can show.

    python -m benchmark.publish runs/benchmark/<run>            # every scored model in that run
    python -m benchmark.publish runs/benchmark/<run> --only signs-v1-tta

Each model becomes `benchmark/history/<version>.json`: its headline rates with
intervals, cost, accuracy by role and by training frequency, and per-sign and
per-tablet results, so the Benchmarks page can draw it across the corpus.
`benchmark/history/index.json` lists every version. These files hold only
derived numbers (no images, no corpus text) and are committed, so the page
works without the models or the dataset.

A version keeps its name across runs; publishing it again replaces it. Only the
`val` split is published by default: test scores are for final candidates and
are published with `--allow-test`, labelled as such.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "fraction-solver"))

from benchmark import metrics as M
from benchmark.run import load_records

HISTORY = ROOT / "benchmark" / "history"
SCHEMA = 1
HEADLINE = ("read_top1", "read_top3", "precision", "recall", "ap50",
            "id_top1", "id_top3", "id_top5", "id_macro_top1", "id_ece")


def _glyph(sign: str) -> str | None:
    try:
        from backend.app.reading_pipeline.glyphs import glyph
        return glyph(sign)
    except Exception:  # noqa: BLE001 - the glyph is decoration; publishing must not fail on it
        return None


def _num(x):
    return None if x is None or math.isnan(float(x)) else round(float(x), 4)


def per_sign(records: list[M.TabletRecord]) -> list[dict]:
    """Per sign ID: attestations, named correctly on the true boxes, and read end to end."""
    out: dict[str, dict] = defaultdict(lambda: {"n": 0, "id_correct": 0, "e2e_n": 0, "e2e_correct": 0,
                                                "role": "unknown", "bucket": None, "confusions": defaultdict(int)})
    for r in records:
        for i in r.identifications:
            s = out[i.sign]
            s["n"] += 1
            s["role"], s["bucket"] = i.role, i.bucket
            if i.labels and i.labels[0] == i.sign:
                s["id_correct"] += 1
            elif i.labels:
                s["confusions"][i.labels[0]] += 1
        read = {d.truth: d for d in r.detections if d.confidence >= M.OPERATING_CONF and d.truth >= 0}
        for t, sign in enumerate(r.truth_signs):
            if sign is None:
                continue
            s = out[sign]
            s["e2e_n"] += 1
            d = read.get(t)
            s["e2e_correct"] += bool(d and d.labels and d.labels[0] == sign)
    rows = []
    for sign, s in sorted(out.items()):
        confusions = sorted(s.pop("confusions").items(), key=lambda kv: -kv[1])[:3]
        rows.append({"sign": sign, "glyph": _glyph(sign), **s,
                     "confused_with": [{"sign": c, "count": n} for c, n in confusions]})
    return rows


def per_tablet(records: list[M.TabletRecord]) -> list[dict]:
    rows = []
    for r in records:
        c = M.detection_counts([r])
        named_ok = sum(i.labels[:1] == [i.sign] for i in r.identifications)
        rows.append({"tablet": r.tablet, "truths": c.get("truths", 0), "found": c.get("found", 0),
                     "named": c.get("named", 0), "read_top1": c.get("read_top1", 0),
                     "identified": len(r.identifications), "id_correct": named_ok})
    return rows


def version_document(name: str, result: dict, records: list[M.TabletRecord], run: dict, run_dir: Path) -> dict:
    m = result["metrics"]
    groups = {"role": {}, "bucket": {}}
    for key, value in m.items():
        if key.startswith("id_top1_role_"):
            groups["role"][key.removeprefix("id_top1_role_")] = _num(value)
        elif key.startswith("id_top1_bucket_"):
            groups["bucket"][key.removeprefix("id_top1_bucket_")] = _num(value)
    return {
        "schema": SCHEMA, "version": name, "description": result.get("description", ""),
        "kind": result["kind"], "stages": result["stages"],
        "split": run["split"], "tablets": run["tablets"], "run": run_dir.name, "scored": run["stamp"],
        "published": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reference": run["reference"],
        "metrics": {k: _num(m.get(k)) for k in HEADLINE if k in m},
        "ci95": {k: [_num(v) for v in result["ci95"][k]] for k in HEADLINE if k in result["ci95"]},
        "vs_reference": {k: {kk: (_num(vv) if kk != "verdict" else vv) for kk, vv in d.items()}
                         for k, d in result.get("vs_reference", {}).items() if k in HEADLINE},
        "by_role": groups["role"], "by_bucket": groups["bucket"],
        "bucket_counts": {b: result["counts"].get(f"bucket_{b}", 0) for b in M.BUCKETS},
        "cost": {"latency_s": _num(result.get("latency_s_median")), "weights_mb": result.get("weights_mb"),
                 "train_minutes": _num((result.get("train_seconds") or 0) / 60) if result.get("train_seconds") else None},
        "coverage_curve": [{k: _num(v) for k, v in p.items()} for p in result.get("coverage_curve", [])],
        "sweep": [{k: _num(v) for k, v in p.items()} for p in result.get("sweep", [])],
        "signs": per_sign(records),
        "tablet_results": per_tablet(records),
    }


def rebuild_index(history: Path = HISTORY) -> Path:
    versions = []
    for path in sorted(history.glob("*.json")):
        if path.name == "index.json":
            continue
        d = json.loads(path.read_text(encoding="utf-8"))
        versions.append({"version": d["version"], "description": d["description"], "kind": d["kind"],
                         "split": d["split"], "stages": d["stages"], "scored": d["scored"],
                         "read_top1": d["metrics"].get("read_top1"), "id_top1": d["metrics"].get("id_top1")})
    index = history / "index.json"
    index.write_text(json.dumps({"schema": SCHEMA, "versions": versions}, indent=2) + "\n", encoding="utf-8")
    return index


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path, help="a finished benchmark run folder")
    parser.add_argument("--only", nargs="*", help="model names to publish (default: all scored)")
    parser.add_argument("--allow-test", action="store_true", help="publish a test-split run (final candidates)")
    parser.add_argument("--history", type=Path, default=HISTORY)
    args = parser.parse_args(argv)

    run = json.loads((args.run / "results.json").read_text(encoding="utf-8"))
    if run["split"] == "test" and not args.allow_test:
        parser.error("this run is on the test split; add --allow-test for final candidates")
    records = load_records(args.run)
    args.history.mkdir(parents=True, exist_ok=True)
    for name, result in run["models"].items():
        if "metrics" not in result or (args.only and name not in args.only):
            continue
        version = name if run["split"] == "val" else f"{name}@test"
        doc = version_document(version, result, records[name], run, args.run)
        path = args.history / f"{version}.json"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{version}: {path}")
    print(rebuild_index(args.history))


if __name__ == "__main__":
    main()
