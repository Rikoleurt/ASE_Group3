"""Choose the test-time augmentation and nearest-neighbour settings on the val split.

    python -m benchmark.tune_hybrid --backbone yolo
    python -m benchmark.tune_hybrid --backbone dinov2

The classifier's probabilities and every embedding are computed once for the
true val boxes; the blend weight and temperature are then searched in numpy, so
the whole grid costs one pass of the models. Scores are naming on the true boxes
(the identification stage of the benchmark). The chosen settings are then run
end to end through `benchmark.run` and, for the final candidate, confirmed once
on test. Writes `runs/benchmark/tune_<backbone>.json`.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "fraction-solver"))

from la import embeddings, reader
from la.shapes import load_mask
from la.signboxes import DATASET_DIR
from la.signcrops import identified, sign_id

from benchmark import metrics as M
from benchmark.run import train_counts

WEIGHTS = (0.0, 0.2, 0.35, 0.5, 0.65, 0.8, 1.0)
TEMPERATURES = (0.02, 0.05, 0.1)
ALPHAS = (0.0, 0.25, 0.5, 1.0)       # frequency-prior strength (la.reader.prior_correction)


def split_crops(annotations, dataset: Path, split: str):
    """(sign IDs, roles, crops, boxes per tablet) of the real, identified signs in one split."""
    signs, roles, crops, per_tablet = [], [], [], []
    for tablet in annotations:
        if tablet["split"] != split:
            continue
        ink = load_mask(dataset / tablet["image"])
        named = identified(tablet)
        boxes = [tuple(s["xyxy"]) for s in named]
        signs += [sign_id(s) for s in named]
        roles += [s.get("role") or "unknown" for s in named]
        crops += reader.crops_of(ink, boxes)
        per_tablet.append((ink, boxes))
    return signs, roles, crops, per_tablet


def scores(names, probs, signs, roles, seen) -> dict[str, float]:
    tops = reader.top_labels(names, probs)
    idents = [M.Identification(s, [x for x, _ in t], [p for _, p in t], r, M.bucket_of(seen[s]))
              for s, r, t in zip(signs, roles, tops)]
    return M.identification([M.TabletRecord("val", [], [], identifications=idents)])


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backbone", choices=["yolo", "resnet50", "dinov2"], default="yolo")
    parser.add_argument("--classifier", type=Path, default=ROOT / "models" / "linear_a_classifier.pt")
    parser.add_argument("--dataset", type=Path, default=DATASET_DIR)
    parser.add_argument("--threads", type=int, default=2)
    args = parser.parse_args(argv)

    import torch
    from ultralytics import YOLO
    torch.set_num_threads(args.threads)

    started = time.time()
    annotations = json.loads((args.dataset / "annotations.json").read_text(encoding="utf-8"))
    seen = train_counts(annotations)
    classifier = YOLO(str(args.classifier))
    cached = (ROOT / "runs" / "benchmark" / f"tune_cache_{args.backbone}.npz").is_file()
    embed = None if cached else embeddings.embedder(args.backbone, classifier)

    train_signs, _, train_crops, _ = split_crops(annotations, args.dataset, "train")
    val_signs, val_roles, val_crops, val_tablets = split_crops(annotations, args.dataset, "val")
    print(f"{len(train_crops)} train crops, {len(val_crops)} val crops; embedding with {args.backbone}", flush=True)
    # Model outputs are cached, so re-tuning (a new grid, a new correction) costs seconds.
    cache = ROOT / "runs" / "benchmark" / f"tune_cache_{args.backbone}.npz"
    if cache.is_file():
        c = np.load(cache, allow_pickle=False)
        names, plain, tta = list(c["names"]), c["plain"], c["tta"]
        bank = reader.NeighbourBank(None, c["bank_signs"], c["bank_vectors"])
        queries = c["queries"]
    else:
        bank = reader.NeighbourBank.build(embed, train_signs, train_crops)
        queries = bank.embed(val_crops)
        names, plain = reader.class_probabilities(classifier, val_crops, "cpu")
        tta = np.concatenate([reader.boxed_probabilities(classifier, ink, boxes, "cpu", tta=True)[1]
                              for ink, boxes in val_tablets if boxes])
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.savez(cache, names=np.array(names), plain=plain, tta=tta, bank_signs=bank.signs,
                 bank_vectors=bank.vectors, queries=queries)

    grid = []
    for use_tta, probs in (("off", plain), ("on", tta)):
        for w in WEIGHTS:
            for t in TEMPERATURES if w > 0 else TEMPERATURES[:1]:
                bank.weight, bank.temperature = w, t
                blended = bank.blend(names, probs, queries) if w > 0 else probs
                for a in ALPHAS:
                    final = reader.prior_correction(names, blended, seen, a)
                    grid.append({"tta": use_tta, "weight": w, "temperature": t, "prior_alpha": a,
                                 **scores(names, final, val_signs, val_roles, seen)})
    grid.sort(key=lambda g: (-g["id_top1"], -g["id_macro_top1"]))
    out = ROOT / "runs" / "benchmark" / f"tune_{args.backbone}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"backbone": args.backbone, "classifier": str(args.classifier),
                               "seconds": round(time.time() - started, 1), "grid": grid}, indent=2) + "\n",
                   encoding="utf-8")
    keys = ("id_top1", "id_macro_top1", "id_top1_bucket_1", "id_top1_bucket_2-4", "id_top1_bucket_5+")
    base = next(g for g in grid if g["tta"] == "off" and g["weight"] == 0 and g["prior_alpha"] == 0)
    print("baseline (classifier only): " + "  ".join(f"{k} {base[k]:.3f}" for k in keys))
    for g in grid[:8]:
        print(f"tta {g['tta']:<3} w {g['weight']:.2f} T {g['temperature']:.2f} prior {g['prior_alpha']:.2f}: "
              + "  ".join(f"{k} {g[k]:.3f}" for k in keys))
    print(f"Written to {out}")


if __name__ == "__main__":
    main()
