"""Measure context re-ranking (la.context) on the val split, honestly.

    python -m benchmark.tune_context [--base tta-knn|tta|plain]

Uses the cached classifier outputs of `benchmark.tune_hybrid --backbone yolo`
(true val boxes), so it runs in seconds. The sign-pair model is fitted on the
transcriptions of training-group documents only. Val tablets are split in two
halves (by a hash of the tablet ID): the settings chosen on one half are scored
on the other, both ways, so the reported gain was never tuned on the signs it is
measured on. Line breaks and reading order come from the corpus transcription,
as the app's line grouping would give them; sign identities never do.
Writes runs/benchmark/tune_context.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "fraction-solver"))

from la import context, fetch, reader
from la.signboxes import DATASET_DIR
from la.signcrops import identified, sign_id

from benchmark import metrics as M
from benchmark.run import train_counts

WEIGHTS = (0.0, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0)
TOPK = (5, 10, 20)


def half(tablet: str) -> int:
    return hashlib.sha256(tablet.encode("utf-8")).digest()[0] % 2


def base_probs(cache: Path, which: str, seen: Counter):
    c = np.load(cache, allow_pickle=False)
    names = list(c["names"])
    if which == "plain":
        return names, c["plain"]
    probs = c["tta"]
    if which == "tta-knn":
        bank = reader.NeighbourBank(None, c["bank_signs"], c["bank_vectors"], weight=0.35, temperature=0.02)
        probs = reader.prior_correction(names, bank.blend(names, probs, c["queries"]), seen, 0.25)
    return names, probs


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", choices=["tta-knn", "tta", "plain"], default="tta-knn")
    parser.add_argument("--dataset", type=Path, default=DATASET_DIR)
    parser.add_argument("--cache", type=Path, default=ROOT / "runs" / "benchmark" / "tune_cache_yolo.npz")
    args = parser.parse_args(argv)

    annotations = json.loads((args.dataset / "annotations.json").read_text(encoding="utf-8"))
    seen = train_counts(annotations)
    docs = fetch.load_cached()
    splits = context.split_of_documents(docs, annotations)
    train_docs = {d for d, s in splits.items() if s == "train"}
    lines = context.train_lines(docs, train_docs)
    model = context.PairModel.fit(lines)
    print(f"pair model: {len(train_docs)} training documents, {len(lines)} lines, "
          f"{sum(map(len, lines))} signs, {len(model.vocabulary)} sign IDs")

    names, probs = base_probs(args.cache, args.base, seen)
    # Val signs in the cache's order (tune_hybrid: annotations order, identified signs).
    rows, k = [], 0
    for tablet in annotations:
        if tablet["split"] != "val":
            continue
        doc = docs.get(tablet["tablet"]) or {}
        line_of = {}
        position = 0
        for li, line in enumerate(doc.get("lines", [])):
            for tok in line:
                if tok.get("kind") in context.SIGN_KINDS:
                    position += 1
                    line_of[position] = li
        for s in identified(tablet):
            rows.append({"tablet": tablet["tablet"], "position": s["position"], "line": line_of.get(s["position"], -1),
                         "sign": sign_id(s), "role": s.get("role") or "unknown", "row": k})
            k += 1
    if k != len(probs):
        raise SystemExit(f"cache has {len(probs)} rows but val has {k} signs: rebuild the cache")

    def rerank(topk: int, weight: float) -> list[list[tuple[str, float]]]:
        out = [None] * len(rows)
        groups: dict[tuple, list] = {}
        for r in rows:
            groups.setdefault((r["tablet"], r["line"]), []).append(r)
        for members in groups.values():
            members.sort(key=lambda r: r["position"])
            cands = [reader.top_labels(names, probs[r["row"]][None, :], topk)[0] for r in members]
            for r, c in zip(members, context.decode_line(cands, model, weight)):
                out[r["row"]] = c
        return out

    def score(ranked, which_half=None) -> dict:
        idents = [M.Identification(r["sign"], [s for s, _ in c], [p for _, p in c], r["role"],
                                   M.bucket_of(seen[r["sign"]]))
                  for r, c in zip(rows, ranked) if which_half is None or half(r["tablet"]) == which_half]
        return M.identification([M.TabletRecord("val", [], [], identifications=idents)])

    grid = []
    for topk in TOPK:
        for w in WEIGHTS:
            ranked = rerank(topk, w)
            grid.append({"topk": topk, "weight": w, "all": score(ranked), "half0": score(ranked, 0),
                         "half1": score(ranked, 1)})
    base = next(g for g in grid if g["weight"] == 0 and g["topk"] == 20)

    def pick(h):
        return max(grid, key=lambda g: (g[f"half{h}"]["id_top1"], -g["weight"]))
    cross = {}
    for tune, test in ((0, 1), (1, 0)):
        g = pick(tune)
        cross[f"tuned_on_half{tune}"] = {"topk": g["topk"], "weight": g["weight"],
                                         "test_half": test, "id_top1": g[f"half{test}"]["id_top1"],
                                         "baseline_id_top1": base[f"half{test}"]["id_top1"],
                                         "id_top3": g[f"half{test}"]["id_top3"],
                                         "baseline_id_top3": base[f"half{test}"]["id_top3"]}
    out = ROOT / "runs" / "benchmark" / "tune_context.json"
    out.write_text(json.dumps({"base": args.base, "lm_documents": len(train_docs), "cross": cross,
                               "grid": grid}, indent=1) + "\n", encoding="utf-8")
    keys = ("id_top1", "id_top3", "id_top1_role_syllabogram", "id_top1_role_logogram", "id_top1_role_fraction")
    print("baseline: " + "  ".join(f"{k} {base['all'].get(k, float('nan')):.3f}" for k in keys))
    for g in sorted(grid, key=lambda g: -g["all"]["id_top1"])[:6]:
        print(f"top{g['topk']:<2} w {g['weight']:.2f}: " + "  ".join(f"{k} {g['all'].get(k, float('nan')):.3f}" for k in keys))
    for name, c in cross.items():
        print(f"{name}: k {c['topk']} w {c['weight']} -> half{c['test_half']} top1 {c['id_top1']:.3f} "
              f"(baseline {c['baseline_id_top1']:.3f}), top3 {c['id_top3']:.3f} (baseline {c['baseline_id_top3']:.3f})")
    print(f"Written to {out}")


if __name__ == "__main__":
    main()
