"""Install the benchmark's chosen reader refinements for the app.

    python scripts/build_reader.py [--version signs-v1-tta-knn-comparer]

Reads the version's settings from benchmark/models.yaml and writes, next to the
classifier in models/:
  linear_a_reader.json    the settings (TTA, neighbour blend, prior, comparer)
  linear_a_bank.npz       embeddings of every real train crop (classifier backbone);
                          its sign list also gives the frequency prior's counts
  linear_a_comparer.pt    a copy of the trained sign comparer
backend/app/tablet_demo.py uses them when present. The bank holds embeddings
and sign IDs only, no images; like the weights it is not committed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "fraction-solver"))

from la.signboxes import DATASET_DIR

from benchmark.readers import _train_bank, _yolo


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", default="signs-v1-tta-knn-comparer")
    parser.add_argument("--dataset", type=Path, default=DATASET_DIR)
    parser.add_argument("--out", type=Path, default=ROOT / "models")
    args = parser.parse_args(argv)

    entries = yaml.safe_load((ROOT / "benchmark" / "models.yaml").read_text(encoding="utf-8"))["models"]
    entry = next((e for e in entries if e["name"] == args.version), None)
    if entry is None or entry.get("kind") != "two_stage":
        raise SystemExit(f"{args.version} is not a two_stage entry of benchmark/models.yaml")
    config = {"version": args.version, "tta": bool(entry.get("tta")), "prior": float(entry.get("prior", 0.0))}

    knn = entry.get("knn")
    if knn:
        classifier = _yolo(str(ROOT / entry["classifier"]))
        bank = _train_bank(args.dataset, classifier, **knn)
        np.savez_compressed(args.out / "linear_a_bank.npz", signs=bank.signs.astype(str), vectors=bank.vectors)
        config["knn"] = {"bank": "linear_a_bank.npz", **knn}
        print(f"bank: {len(bank.signs)} train crops, {len(set(bank.signs.tolist()))} signs")
    elif config["prior"]:
        raise SystemExit("the app takes the prior's counts from the neighbour bank: a prior needs knn")

    comparer = entry.get("comparer")
    if comparer:
        source = ROOT / comparer["weights"]
        shutil.copyfile(source, args.out / "linear_a_comparer.pt")
        config["comparer"] = {**comparer, "weights": "linear_a_comparer.pt"}
        print(f"comparer: copied {source}")

    (args.out / "linear_a_reader.json").write_text(json.dumps(config, indent=1) + "\n", encoding="utf-8")
    print(f"Written {args.out / 'linear_a_reader.json'}")


if __name__ == "__main__":
    main()
