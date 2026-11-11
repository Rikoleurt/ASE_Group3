"""Benchmark Linear A readers on the same held-out tablets.

    python -m benchmark.run                        # every model in benchmark/models.yaml, val split
    python -m benchmark.run --only signs-v1 shape-knn
    python -m benchmark.run --split test --final   # the test split, once per final candidate

Each reader is scored in up to three stages (see `benchmark/metrics.py`):
detection alone, identification on the true boxes, and end to end as the app
reads a tablet. Every rate has a 95% bootstrap interval over whole tablets, and
each model is compared with the reference model on the *same* resampled tablets.

Inference runs on the CPU with 2 threads, like the web app, so the latencies are
what a user of the app would see; no GPU is needed.

Tune and choose on `val`. `test` is for the final candidates only: every test run
is appended to `runs/benchmark/test_runs.csv`, so repeated peeking is visible.
Results go to `runs/benchmark/<stamp>-<split>/`; render them with
`python -m benchmark.report <that folder>`.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "fraction-solver"))

from la import evaluation
from la.shapes import load_mask
from la.signboxes import DATASET_DIR
from la.signcrops import identified, sign_id

from benchmark import metrics as M
from benchmark import readers

MODELS_FILE = ROOT / "benchmark" / "models.yaml"
OUT_DIR = ROOT / "runs" / "benchmark"


def load_models(path: Path) -> list[dict]:
    import yaml
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["models"]


def train_counts(annotations: list[dict]) -> Counter:
    """Real train attestations per sign ID: what a reader could have learnt from."""
    return Counter(sign_id(s) for t in annotations if t["split"] == "train" for s in identified(t))


def records_for(model: readers.Reader, tablets: list[dict], dataset: Path, seen: Counter) -> list[M.TabletRecord]:
    records = []
    for n, tablet in enumerate(tablets, 1):
        image = dataset / tablet["image"]
        truths = [evaluation.Truth(tuple(s["xyxy"]),
                                   sign_id(s) if s.get("source", "matched") == "matched" else None,
                                   seen[sign_id(s)] > 0) for s in tablet["signs"]]
        record = M.TabletRecord(tablet["tablet"], [t.sign for t in truths], [t.learnable for t in truths])
        if model.detects:
            found = model.detect(image)
            predictions = [evaluation.Prediction(b, c, l) for b, c, l, _ in found]
            pairs = {p: t for t, p in evaluation.match(predictions, truths).items()}
            record.detections = [M.Detection(c, list(l), list(p), pairs.get(i, -1))
                                 for i, (_, c, l, p) in enumerate(found)]
        if model.identifies:
            named = [s for s in identified(tablet)]
            if named:
                tops = model.identify(load_mask(image), [tuple(s["xyxy"]) for s in named])
                record.identifications = [
                    M.Identification(sign_id(s), [x for x, _ in top], [p for _, p in top],
                                     s.get("role") or "unknown", M.bucket_of(seen[sign_id(s)]))
                    for s, top in zip(named, tops)]
        records.append(record)
        if n % 25 == 0:
            print(f"    {n}/{len(tablets)} tablets", flush=True)
    return records


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def train_seconds(run_dirs) -> float | None:
    """Training wall time summed over Ultralytics runs (`time` in results.csv is cumulative seconds)."""
    total = None
    for run_dir in [run_dirs] if isinstance(run_dirs, str) else run_dirs or []:
        results = ROOT / run_dir / "results.csv"
        if not results.is_file():
            return None
        with results.open(encoding="utf-8") as f:
            times = [float(r["time"]) for r in csv.DictReader(f) if r.get("time")]
        total = (total or 0.0) + (max(times) if times else 0.0)
    return total


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", type=Path, default=MODELS_FILE)
    parser.add_argument("--only", nargs="*", help="model names to run (default: all)")
    parser.add_argument("--dataset", type=Path, default=DATASET_DIR)
    parser.add_argument("--split", default="val", choices=["val", "test"])
    parser.add_argument("--final", action="store_true", help="required with --split test")
    parser.add_argument("--reference", default="signs-v1", help="model every other model is compared with")
    parser.add_argument("--resamples", type=int, default=1000)
    parser.add_argument("--latency-tablets", type=int, default=20)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--limit", type=int, help="first N tablets only (smoke tests)")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if args.split == "test" and not args.final:
        parser.error("the test split is for final candidates only: add --final (each run is logged)")

    import torch
    torch.set_num_threads(args.threads)

    entries = load_models(args.models)
    if args.only:
        missing = set(args.only) - {e["name"] for e in entries}
        if missing:
            parser.error(f"not in {args.models.name}: {sorted(missing)}")
        keep = set(args.only) | {args.reference}
        entries = [e for e in entries if e["name"] in keep]

    annotations = json.loads((args.dataset / "annotations.json").read_text(encoding="utf-8"))
    seen = train_counts(annotations)
    tablets = [t for t in annotations if t["split"] == args.split][: args.limit]
    draws = M.resample_indices(len(tablets), args.resamples)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or OUT_DIR / f"{stamp}-{args.split}"
    out.mkdir(parents=True, exist_ok=True)
    print(f"{len(entries)} models, {len(tablets)} {args.split} tablets -> {out}")

    results, all_records = {}, {}
    for entry in entries:
        name = entry["name"]
        weights = [Path(entry[k]) for k in ("detector", "classifier") if k in entry]
        absent = [w for w in weights if not (w if w.is_absolute() else ROOT / w).is_file()]
        if absent:
            print(f"  {name}: skipped, missing {', '.join(map(str, absent))}")
            results[name] = {"skipped": f"missing {', '.join(map(str, absent))}"}
            continue
        print(f"  {name} ({entry['kind']})", flush=True)
        started = time.time()
        model = readers.build(entry, ROOT, args.dataset)
        built = time.time() - started
        records = records_for(model, tablets, args.dataset, seen)
        seconds = time.time() - started
        latency = sorted(model.time_app(args.dataset / t["image"]) for t in tablets[: args.latency_tablets])

        def metric(rs, m=model):
            return M.all_metrics(rs, m.detects, m.identifies)

        files = [p if p.is_absolute() else ROOT / p for p in weights]
        results[name] = {
            "kind": entry["kind"], "description": entry.get("description", ""),
            "stages": {"detection": model.detects, "identification": model.identifies},
            "metrics": metric(records), "ci95": M.bootstrap(records, metric, draws),
            "counts": M.counts(records),
            "sweep": M.sweep(records) if model.detects else [],
            "coverage_curve": M.coverage_curve(records) if model.identifies else [],
            "latency_s_median": latency[len(latency) // 2] if latency else None,
            "weights_mb": round(sum(f.stat().st_size for f in files) / 1e6, 2),
            "weights_sha256": {str(w): sha(f) for w, f in zip(weights, files)},
            "train_seconds": train_seconds(entry.get("train_run")),
            "benchmark_seconds": round(seconds, 1), "setup_seconds": round(built, 1),
        }
        all_records[name] = records

    reference = all_records.get(args.reference)
    for name, records in all_records.items():
        if reference is None or name == args.reference:
            continue
        model_kind = results[name]["stages"]
        ref_kind = results[args.reference]["stages"]

        def shared(rs, a=model_kind, b=ref_kind):
            return M.all_metrics(rs, a["detection"] and b["detection"], a["identification"] and b["identification"])
        results[name]["vs_reference"] = M.paired_difference(records, reference, shared, draws)

    summary = {"split": args.split, "tablets": len(tablets), "dataset": str(args.dataset),
               "reference": args.reference, "resamples": args.resamples, "threads": args.threads,
               "stamp": stamp, "operating_conf": M.OPERATING_CONF, "models": results}
    (out / "results.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with (out / "records.json").open("w", encoding="utf-8") as f:
        json.dump({n: [asdict(r) for r in rs] for n, rs in all_records.items()}, f)
    with (out / "results.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["model", "metric", "value", "ci_lo", "ci_hi", "diff_vs_reference", "diff_lo", "diff_hi", "verdict"])
        for name, r in results.items():
            for key, value in r.get("metrics", {}).items():
                lo, hi = r["ci95"].get(key, (None, None))
                d = r.get("vs_reference", {}).get(key, {})
                w.writerow([name, key, value, lo, hi, d.get("diff"), d.get("lo"), d.get("hi"), d.get("verdict")])
    if args.split == "test":
        log = OUT_DIR / "test_runs.csv"
        new = not log.exists()
        with log.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["stamp", "models", "out"])
            w.writerow([stamp, " ".join(all_records), str(out)])

    for name, r in results.items():
        if "metrics" not in r:
            continue
        m = r["metrics"]
        parts = [f"{k} {m[k]:.3f}" for k in ("read_top1", "recall", "ap50", "id_top1", "id_macro_top1") if k in m]
        print(f"  {name:<22} " + "  ".join(parts))
    print(f"Written to {out}")
    return out


if __name__ == "__main__":
    main()
