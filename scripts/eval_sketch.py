"""How well would sketch search find a sign? Run before building its UI (the sketch-search gate).

    python scripts/eval_sketch.py                # both proxies, all methods
    python scripts/eval_sketch.py --out reports/sketch_eval.json

No team sketches exist yet, so two proxies stand in for a scholar's drawing:

* sketch-like tracings: drawings from the dataset's *test* tablets (never trained on), reduced
  to a one-pixel skeleton, redrawn with an even pen, and jittered (rotation, scale, shear), as
  a mouse or finger sketch would be;
* font characters: each sign's Unicode character (Noto Sans Linear A), the standard form a
  scholar would draw from memory, redrawn with the same pen.

Each query is scored by the classifier alone, by the neighbour bank alone (best cosine to the
training crops, `la.reader.NeighbourBank`), and by their blend (the reader's own weights), with
and without the pen normalisation. Reports top-1/5/12 over all signs and over the 20 signs
with most training examples.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "fraction-solver"))

from backend.app import glyph_index, reading, sketch_search, tablet_demo  # noqa: E402
from backend.app.reading_pipeline.glyphs import glyph as unicode_glyph  # noqa: E402
from la import glyphembed  # noqa: E402

KS = (1, 5, 12)
TOP_SIGNS = 20


def jitter(ink: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """A small random rotation, scale and shear, as a hand-drawn copy would have."""
    height, width = ink.shape
    pad = max(height, width) // 4
    canvas = np.pad(ink.astype(np.uint8) * 255, pad)
    angle, scale, shear = rng.uniform(-6, 6), rng.uniform(0.9, 1.1), rng.uniform(-0.08, 0.08)
    centre = (canvas.shape[1] / 2, canvas.shape[0] / 2)
    matrix = cv2.getRotationMatrix2D(centre, angle, scale)
    matrix[0, 1] += shear
    warped = cv2.warpAffine(
        canvas, matrix, (canvas.shape[1], canvas.shape[0]), flags=cv2.INTER_NEAREST
    )
    return warped > 127


def test_queries(
    index: glyph_index.GlyphIndex, rng: np.random.Generator
) -> list[tuple[str, np.ndarray]]:
    """(sign, sketch-like ink) for every test-split drawing whose crop is downloaded."""
    annotations = json.loads(glyph_index.ANNOTATIONS.read_text(encoding="utf-8"))
    slug_of = {tablet: slug for slug, tablet in index.slugs.items()}
    queries = []
    for tablet in annotations:
        if tablet.get("split") != "test" or tablet["tablet"] not in slug_of:
            continue
        for sign in tablet["signs"]:
            path = reading.sign_image(slug_of[tablet["tablet"]], int(sign["position"]))
            if path is None or not sign.get("sign"):
                continue
            try:
                ink = glyphembed.ink_from_png_bytes(path.read_bytes())
            except glyphembed.BadCrop:
                continue
            if ink.sum() < 20:
                continue
            queries.append((sign["sign"], jitter(sketch_search.even_pen(ink), rng)))
    return queries


def font_queries(names: list[str]) -> list[tuple[str, np.ndarray]]:
    from PIL import ImageFont

    from la import cropsplus

    face = ImageFont.truetype(str(cropsplus.FONT), cropsplus.FONT_PX)
    out = []
    for sign in names:
        character = unicode_glyph(sign)
        mask = cropsplus.font_mask(character, face) if character else None
        if mask is not None and mask.any():
            out.append((sign, sketch_search.even_pen(mask)))
    return out


def ranks(scores: np.ndarray, names: list[str], truth: list[str]) -> np.ndarray:
    order = np.argsort(-scores, axis=1)
    position = {name: i for i, name in enumerate(names)}
    out = []
    for row, sign in zip(order, truth):
        hit = np.where(row == position.get(sign, -1))[0]
        out.append(int(hit[0]) + 1 if len(hit) else 10**6)
    return np.array(out)


def summary(rank: np.ndarray, truth: list[str], top: set[str]) -> dict:
    chosen = np.array([sign in top for sign in truth])

    def at(mask):
        return {
            f"top{k}": round(float((rank[mask] <= k).mean()) * 100, 1) if mask.any() else None
            for k in KS
        }

    return {
        "queries": int(len(rank)),
        "all": at(np.ones(len(rank), bool)),
        "top20_signs": {**at(chosen), "queries": int(chosen.sum())},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    scorer = sketch_search.scorer()
    if scorer is None:
        print(
            "The classifier or the neighbour bank is not installed (python scripts/fetch_models.py).",
            file=sys.stderr,
        )
        return 1
    index = glyph_index.get_index()
    rng = np.random.default_rng(args.seed)
    counts = Counter(sign for sign in scorer.bank.signs.tolist() if sign != "unidentified")
    top = {sign for sign, _ in counts.most_common(TOP_SIGNS)}
    report = {
        "model": tablet_demo.CLASSIFIER_WEIGHTS.name,
        "top20_signs": sorted(top),
        "proxies": {},
    }
    for proxy, queries in (
        ("sketch-like test tracings", test_queries(index, rng)),
        ("font characters", font_queries(scorer.names)),
    ):
        truth = [sign for sign, _ in queries]
        inks = [ink for _, ink in queries]
        classifier, neighbours, blend = scorer.scores(inks)
        report["proxies"][proxy] = {
            method: summary(ranks(matrix, scorer.names, truth), truth, top)
            for method, matrix in (
                ("classifier", classifier),
                ("neighbours", neighbours),
                ("blend", blend),
            )
        }
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
