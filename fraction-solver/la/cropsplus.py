"""More training crops for rare signs: unplaced drawings and font-rendered signs.

`la.signcrops` cuts its crops from the boxes found on tablet tracings, so a sign
drawing that could not be located on its tablet never reaches the classifier.
The classifier does not need the location, only the drawing, so this adds:

* **Unplaced drawings**: SigLA sign drawings (`data/cache/allcrops`, named
  `<sign>__<role>__<tablet>__<position>.png`) with no box in the detection
  dataset, from train tablets or from tablets outside the dataset whose group
  would fall in train. Erasures are skipped. Val and test tablets, and every
  face or joined fragment of them, are never used.
* **Font signs**: the sign drawn by Noto Sans Linear A (SIL OFL 1.1), thinned
  to the stroke width of a tracing, then varied like any rare crop (tilt,
  stretch, stroke weight, chipped edge). Only for signs with at most
  `FONT_MAX_REAL` real training crops, including signs with none: those become
  classes the classifier can now answer. The font is an idealised hand, so this
  is an experiment the benchmark decides on, not a given.

Val and test folders are unchanged, so scores stay comparable with `sign_crops`.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

from la import augment, fetch, signcrops
from la.shapes import load_mask
from la.signboxes import DATASET_DIR, split_for, tablet_groups

ROOT = fetch.ROOT
ALLCROPS = ROOT / "data" / "cache" / "allcrops"
FONT = ROOT.parent / "frontend" / "src" / "assets" / "fonts" / "NotoSansLinearA.woff2"
PLUS_DIR = ROOT / "out" / "sign_crops_plus"
FONT_MAX_REAL = 4          # signs with more real crops than this get no font copies
FONT_COPIES = 12           # varied font copies per eligible sign
FONT_PX = 200              # render size before thinning and framing
FONT_THIN = 6              # erosion steps: font strokes are ~3x a tracing's
SKIP_ROLES = {"erasure"}


def font_mask(char: str, font: ImageFont.FreeTypeFont) -> np.ndarray | None:
    canvas = Image.new("L", (FONT_PX * 2, FONT_PX * 2), 255)
    ImageDraw.Draw(canvas).text((FONT_PX // 4, FONT_PX // 8), char, font=font, fill=0)
    mask = np.asarray(canvas) < 128
    if not mask.any():
        return None
    thin = mask
    for _ in range(FONT_THIN):
        eroded = ndimage.binary_erosion(thin)
        if eroded.sum() < 0.25 * thin.sum():   # never erode a fine stroke away
            break
        thin = eroded
    return augment.trim(thin)


def unplaced_drawings(annotations: list[dict]) -> list[tuple[str, Path]]:
    """(sign ID, drawing) for drawings with no box whose tablet belongs to train."""
    placed = {(t["tablet"].replace(" ", "_"), s["position"]) for t in annotations for s in t["signs"]}
    split = {t["tablet"].replace(" ", "_"): t["split"] for t in annotations}
    docs = fetch.load_cached()
    groups = {doc_id.replace(" ", "_"): group for doc_id, group in tablet_groups(docs).items()}
    # A tablet outside the dataset is placed where its group would go, so faces and joins stay together.
    group_split = {t["group"]: t["split"] for t in annotations}
    out = []
    for path in sorted(ALLCROPS.glob("*.png")):
        try:
            sign, role, tablet, position = path.stem.split("__")
            position = int(position)
        except ValueError:
            continue
        if role in SKIP_ROLES or (tablet, position) in placed:
            continue
        where = split.get(tablet)
        if where is None:
            group = groups.get(tablet, tablet)
            where = group_split.get(group) or split_for(group, 0.15, 0.15)
        if where == "train":
            out.append((sign, path))
    return out


def build_crops_plus(glyph, dataset: Path = DATASET_DIR, out: Path = PLUS_DIR, seed: int = 0,
                     drawings: bool = True, font: bool = True) -> dict:
    """`la.signcrops.build_crops`, then the extra train crops above. Returns the report.

    `glyph(sign_id)` gives the sign's Unicode character or None (the app's
    `backend.app.reading_pipeline.glyphs.glyph`); it is passed in so `la` does
    not depend on the backend.
    """
    report = signcrops.build_crops(dataset, out, seed=seed)
    annotations = json.loads((dataset / "annotations.json").read_text(encoding="utf-8"))
    real = Counter(signcrops.sign_id(s) for t in annotations if t["split"] == "train"
                   for s in signcrops.identified(t))
    catalogue = signcrops.catalogue(annotations)
    classes = json.loads((out / "classes.json").read_text(encoding="utf-8"))
    rng = np.random.default_rng(seed + 1)
    added = {"drawings": Counter(), "font": Counter()}

    if drawings:
        for sign, path in unplaced_drawings(annotations):
            if sign not in catalogue or sign == signcrops.UNKNOWN_SIGN:
                continue
            mask = augment.trim(load_mask(path))
            if not mask.any():
                continue
            folder = out / "train" / sign
            folder.mkdir(parents=True, exist_ok=True)
            signcrops.save(augment.render(mask, margin=augment.CROP_MARGIN), folder / f"drawing_{path.stem}.png")
            added["drawings"][sign] += 1
            classes.setdefault(sign, catalogue[sign])

    if font:
        face = ImageFont.truetype(str(FONT), FONT_PX)
        for sign in sorted(catalogue):
            have = real[sign] + added["drawings"][sign]
            char = glyph(sign)
            if sign == signcrops.UNKNOWN_SIGN or have > FONT_MAX_REAL or not char:
                continue
            mask = font_mask(char, face)
            if mask is None:
                continue
            folder = out / "train" / sign
            folder.mkdir(parents=True, exist_ok=True)
            for k in range(FONT_COPIES):
                varied = augment.vary(mask, rng) if k else mask
                signcrops.save(augment.render(varied, margin=augment.CROP_MARGIN), folder / f"font_{sign}_{k}.png")
            added["font"][sign] += FONT_COPIES
            classes.setdefault(sign, catalogue[sign])

    (out / "classes.json").write_text(json.dumps(dict(sorted(classes.items())), indent=2, ensure_ascii=False)
                                      + "\n", encoding="utf-8")
    report["plus"] = {
        "drawings": sum(added["drawings"].values()), "drawing_signs": len(added["drawings"]),
        "font_crops": sum(added["font"].values()), "font_signs": len(added["font"]),
        "new_classes": sorted(s for s in added["font"] | added["drawings"] if real[s] == 0),
        "classes": len(classes),
    }
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
