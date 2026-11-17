"""Embed every corpus sign crop and write models/glyph_embeddings.npz.

    python scripts/build_glyph_embeddings.py [--out models/glyph_embeddings.npz]

Keys: tablet (corpus id, e.g. "HT 13"), position, sign (SigLA ID), vectors
(float32, raw), model (backbone name) and weights_sha256 (of the weights used).
Crops are read from fraction-solver/data/images (never written). The output is
gitignored. Refuses to overwrite an existing file unless --force is given.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "fraction-solver"))

from la import fetch, glyphembed, signboxes  # noqa: E402
from la.shapes import load_mask  # noqa: E402


def corpus_crops() -> list[tuple[str, int, str, Path]]:
    """(tablet id, position, sign ID, crop path) for every cached sign crop on disk."""
    rows = []
    for tablet, doc in fetch.load_cached().items():
        for sign in doc.get("signs") or []:
            if not (sign.get("image") and sign.get("sign")):
                continue
            path = signboxes.image_path(doc, sign["image"])
            if path.exists():
                rows.append((tablet, int(sign["position"]), sign["sign"], path))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "models" / "glyph_embeddings.npz")
    parser.add_argument("--backbone", choices=glyphembed.BACKBONES, default=glyphembed.DEFAULT_BACKBONE)
    parser.add_argument("--weights", type=Path, default=ROOT / "models" / "linear_a_classifier.pt")
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.out.exists() and not args.force:
        print(f"{args.out} exists; pass --force to replace it.", file=sys.stderr)
        return 1
    import torch
    from ultralytics import YOLO

    torch.set_num_threads(args.threads)
    rows = corpus_crops()
    if not rows:
        print("No cached sign crops found (python -m la.cli images).", file=sys.stderr)
        return 1
    model = YOLO(str(args.weights))
    print(f"embedding {len(rows)} crops with {args.backbone} ({args.weights.name})", flush=True)
    chunks, started = [], time.perf_counter()
    for start in range(0, len(rows), 512):  # bound memory: masks are loaded 512 at a time
        part = rows[start:start + 512]
        chunks.append(glyphembed.embed_inks(model, [load_mask(row[3]) for row in part], args.batch))
        print(f"  {start + len(part)}/{len(rows)}  {time.perf_counter() - started:.0f}s", flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.out,
        tablet=np.array([row[0] for row in rows]),
        position=np.array([row[1] for row in rows], dtype=np.int32),
        sign=np.array([row[2] for row in rows]),
        vectors=np.concatenate(chunks),
        model=np.array(args.backbone),
        weights_sha256=np.array(glyphembed.weights_sha256(args.weights)),
    )
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
