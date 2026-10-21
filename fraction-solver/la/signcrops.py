"""A sign classification dataset, cut from the detection dataset's boxes.

Reading a tablet is two jobs: finding the signs and naming them. One 361-class
detector does both badly, because most classes have a handful of examples and
the box and the name are learnt together. Here the detector learns one class,
"sign" (`la.cli dataset --labels sign`), and a classifier names each crop.

Crops come from `annotations.json`, so they inherit the detection split: a
tablet's signs are never split between train and test. Folders are SigLA sign
IDs, which are plain alphanumerics and therefore safe on every filesystem; the
readable name and roles of each are in `classes.json`.

Rare classes are resampled in `train` only, with varied copies (`la.augment`).
Val and test hold one crop per real sign, so their scores stay honest. Signs
whose ID never occurs in train cannot be learnt; they are counted in
`report.json` and left out of val and test folders, where Ultralytics would
skip them anyway. `evaluate.py` still counts them as misses.
"""

from __future__ import annotations

import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

from la import augment, fetch
from la.shapes import load_mask
from la.signboxes import DATASET_DIR, LICENCE_NOTICE, SPLITS, UNKNOWN_SIGN

CROP_DIR = fetch.ROOT / "out" / "sign_crops"
RESAMPLE_TARGET = 100


def sign_id(sign: dict) -> str:
    return sign.get("sign") or UNKNOWN_SIGN


def identified(tablet: dict) -> list[dict]:
    """Signs with a known identity: matched crops, not boxes added by review."""
    return [s for s in tablet["signs"] if s.get("source", "matched") == "matched"]


def catalogue(annotations: list[dict]) -> dict[str, dict]:
    """Per sign ID: its readings, roles and display name, from the annotations."""
    readings: dict[str, set[str]] = defaultdict(set)
    roles: dict[str, set[str]] = defaultdict(set)
    for tablet in annotations:
        for sign in identified(tablet):
            key = sign_id(sign)
            roles[key].add(sign.get("role") or "unknown")
            if sign.get("reading"):
                readings[key].add(sign["reading"])
    out = {}
    for key in sorted(roles):
        variants = sorted(readings[key])
        reading = variants[0] if len(variants) == 1 else None
        out[key] = {"sign": None if key == UNKNOWN_SIGN else key, "reading": reading, "readings": variants,
                    "roles": sorted(roles[key]), "name": f"{key} ({reading})" if reading else key}
    return out


def build_crops(dataset: Path = DATASET_DIR, out: Path = CROP_DIR,
                target: int = RESAMPLE_TARGET, seed: int = 0) -> dict:
    """Write `{train,val,test}/<sign id>/*.png`, `classes.json` and `report.json`."""
    annotations_path = dataset / "annotations.json"
    if not annotations_path.exists():
        raise FileNotFoundError(f"{annotations_path} is missing; run `la.cli dataset` first")
    if target < 1:
        raise ValueError("target must be at least 1")
    annotations = json.loads(annotations_path.read_text(encoding="utf-8"))
    signs = catalogue(annotations)
    lowered = Counter(key.lower() for key in signs)
    clashes = [key for key in signs if lowered[key.lower()] > 1]
    if clashes:  # Windows and macOS folders ignore case
        raise ValueError(f"sign IDs differ only by case: {sorted(clashes)}")

    # (sign id, crop as the demo cuts it, the sign's own ink, file stem)
    real: dict[str, list[tuple[str, np.ndarray, np.ndarray, str]]] = {s: [] for s in SPLITS}
    for tablet in annotations:
        if tablet["split"] not in real:
            continue
        ink = load_mask(dataset / tablet["image"])
        stem = Path(tablet["image"]).stem
        for sign in identified(tablet):
            x0, y0, x1, y1 = sign["xyxy"]
            # Copy: a slice would keep the whole tablet's mask alive, ~2 GB over the corpus.
            real[tablet["split"]].append((sign_id(sign), augment.square_crop(ink, (x0, y0, x1, y1)),
                                          ink[y0:y1, x0:x1].copy(), f"{stem}_{sign['position']}"))

    learnable = {key for key, *_ in real["train"]}
    shutil.rmtree(out, ignore_errors=True)
    report: dict = {"target": target, "seed": seed, "real": {}, "written": {},
                    "unseen_in_train": {}, "train_counts": {}}
    rng = np.random.default_rng(seed)
    for split in SPLITS:
        per_class: dict[str, list[tuple[np.ndarray, np.ndarray, str]]] = defaultdict(list)
        for key, crop, mask, name in real[split]:
            per_class[key].append((crop, mask, name))
        written = 0
        for key, crops in sorted(per_class.items()):
            if key not in learnable:
                continue
            folder = out / split / key
            folder.mkdir(parents=True, exist_ok=True)
            for crop, _, name in crops:
                save(crop, folder / f"{name}.png")
            written += len(crops)
            if split == "train":
                extra = augment.resample_count(len(crops), target) - len(crops)
                for k in range(extra):
                    _, mask, name = crops[k % len(crops)]
                    varied = augment.vary(mask, rng)
                    save(augment.render(varied, margin=augment.CROP_MARGIN), folder / f"{name}_v{k}.png")
                written += extra
                report["train_counts"][key] = {"real": len(crops), "total": len(crops) + extra}
        report["real"][split] = len(real[split])
        report["written"][split] = written
        report["unseen_in_train"][split] = sum(1 for key, *_ in real[split] if key not in learnable)

    report["classes"] = len(learnable)
    report["classes_without_train"] = sorted(set(signs) - learnable)
    (out / "classes.json").write_text(json.dumps(
        {key: signs[key] for key in sorted(learnable)}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "LICENCE.txt").write_text(LICENCE_NOTICE, encoding="utf-8")
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def save(pixels: np.ndarray, path: Path) -> None:
    Image.fromarray(pixels).save(path)
