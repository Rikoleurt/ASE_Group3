"""A learned re-ranker over each sign's top candidates, measured honestly on val.

    python -m benchmark.tune_rerank

For every true val box and each of its top-k classifier candidates, features:
classifier probability and log-probability (with TTA), its rank, the margin to
the best candidate, nearest-train-crop similarity (classifier features), the
classical shape-overlap score (`ShapeKNN`), how often the sign occurs in
training (log), whether it has 1 or 0-4 training crops, and the context
association with the previous sign's best guess (`la.context`). A logistic
model (numpy, L2) learns which candidate is right.

Val tablets are split in two halves by a hash of the tablet ID: fit on one,
score the other, both ways, so the reported gain is out of sample.
Uses `runs/benchmark/tune_cache_yolo.npz` (from `benchmark.tune_hybrid`).
Writes runs/benchmark/tune_rerank.json.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "fraction-solver"))

from la import context, fetch, reader
from la.shapes import load_mask
from la.signboxes import DATASET_DIR
from la.signcrops import identified, sign_id

from benchmark import metrics as M
from benchmark.readers import ShapeKNN
from benchmark.run import train_counts
from benchmark.tune_context import half

FEATURES = ("p", "logp", "rank", "margin", "knn", "shape", "log_freq", "rare1", "rare4", "assoc")


def logistic(x: np.ndarray, y: np.ndarray, l2: float = 1.0, steps: int = 400, lr: float = 0.5) -> np.ndarray:
    """Weights (with bias last) by gradient descent on standardised features."""
    xb = np.hstack([x, np.ones((len(x), 1))])
    w = np.zeros(xb.shape[1])
    for _ in range(steps):
        p = 1 / (1 + np.exp(-(xb @ w)))
        grad = xb.T @ (p - y) / len(y) + l2 * np.r_[w[:-1], 0] / len(y)
        w -= lr * grad
    return w


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, default=DATASET_DIR)
    parser.add_argument("--cache", type=Path, default=ROOT / "runs" / "benchmark" / "tune_cache_yolo.npz")
    parser.add_argument("--topk", type=int, default=10)
    args = parser.parse_args(argv)

    annotations = json.loads((args.dataset / "annotations.json").read_text(encoding="utf-8"))
    seen = train_counts(annotations)
    c = np.load(args.cache, allow_pickle=False)
    names, probs = list(c["names"]), c["tta"]
    bank = reader.NeighbourBank(None, c["bank_signs"], c["bank_vectors"])
    knn = bank.scores(names, c["queries"])                       # best cosine per class
    docs = fetch.load_cached()
    splits = context.split_of_documents(docs, annotations)
    lm = context.PairModel.fit(context.train_lines(docs, {d for d, s in splits.items() if s == "train"}))
    shape = ShapeKNN("shape", dataset=args.dataset)
    shape_index = {s: i for i, s in enumerate(shape.classes)}

    rows = []
    for tablet in annotations:
        if tablet["split"] != "val":
            continue
        named = identified(tablet)
        ink = load_mask(args.dataset / tablet["image"])
        query = np.stack([shape._vector(ink, s["xyxy"]) for s in named]) if named else np.zeros((0, 1))
        inter = query @ shape.reference.T
        union = query.sum(axis=1)[:, None] + shape.reference_ink[None, :] - inter
        overlap = np.where(union > 0, inter / np.maximum(union, 1e-9), 0.0)
        per_class = np.full((len(named), len(shape.classes)), 0.0)
        for cls, members in shape.members.items():
            per_class[:, shape_index[cls]] = overlap[:, members].max(axis=1) if len(named) else 0
        for j, s in enumerate(named):
            rows.append({"tablet": tablet["tablet"], "position": s["position"], "sign": sign_id(s),
                         "role": s.get("role") or "unknown", "shape": per_class[j]})
    if len(rows) != len(probs):
        raise SystemExit("cache and val signs differ: rebuild the cache")

    previous_best = {}
    for i, r in enumerate(rows):
        previous_best[(r["tablet"], r["position"])] = names[int(np.argmax(probs[i]))]

    cand_feats, cand_signs, labels, groups = [], [], [], []
    for i, r in enumerate(rows):
        order = np.argsort(-probs[i])[: args.topk]
        best = probs[i][order[0]]
        prev = previous_best.get((r["tablet"], r["position"] - 1), context.START)
        feats, signs = [], []
        for rank, j in enumerate(order):
            s = names[int(j)]
            p = float(probs[i][j])
            n = seen[s]
            feats.append([p, math.log(max(p, 1e-6)), rank, best - p, float(knn[i][j]),
                          float(r["shape"][shape_index[s]]) if s in shape_index else 0.0,
                          math.log1p(n), float(n == 1), float(0 < n <= 4), lm.association(s, prev)])
            signs.append(s)
        cand_feats.append(np.array(feats))
        cand_signs.append(signs)
        labels.append(np.array([s == r["sign"] for s in signs], dtype=float))
        groups.append(half(r["tablet"]))

    def evaluate(w, mean, std, which):
        idents = []
        for f, signs, r, g in zip(cand_feats, cand_signs, rows, groups):
            if g != which:
                continue
            z = np.hstack([(f - mean) / std, np.ones((len(f), 1))]) @ w if w is not None else -np.arange(len(f))
            order = np.argsort(-z)
            idents.append(M.Identification(r["sign"], [signs[k] for k in order], [1.0] * len(order),
                                           r["role"], M.bucket_of(seen[r["sign"]])))
        return M.identification([M.TabletRecord("v", [], [], identifications=idents)])

    results = {}
    for fit_half, test_half in ((0, 1), (1, 0)):
        x = np.vstack([f for f, g in zip(cand_feats, groups) if g == fit_half])
        y = np.concatenate([l for l, g in zip(labels, groups) if g == fit_half])
        mean, std = x.mean(axis=0), x.std(axis=0) + 1e-9
        w = logistic((x - mean) / std, y)
        results[f"fit{fit_half}_test{test_half}"] = {
            "weights": dict(zip([*FEATURES, "bias"], np.round(w, 3).tolist())),
            "rerank": evaluate(w, mean, std, test_half), "baseline": evaluate(None, None, None, test_half)}
    out = ROOT / "runs" / "benchmark" / "tune_rerank.json"
    out.write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    for name, r in results.items():
        b, x = r["baseline"], r["rerank"]
        print(f"{name}: top1 {b['id_top1']:.3f} -> {x['id_top1']:.3f}   top3 {b['id_top3']:.3f} -> {x['id_top3']:.3f}   "
              f"logogram {b['id_top1_role_logogram']:.3f} -> {x['id_top1_role_logogram']:.3f}")
        print("   weights:", r["weights"])
    print(f"Written to {out}")


if __name__ == "__main__":
    main()
