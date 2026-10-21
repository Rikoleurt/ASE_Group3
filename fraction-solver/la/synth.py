"""Synthetic training tablets: real signs pasted into the empty space of real tracings.

The detector has 500 training tablets. More can be composed from what they hold:
take a train tracing, keep its signs and their boxes, and paste further train
signs where the tablet is blank. The host keeps everything that makes a tracing
look like one, including the unlabelled numerals and ruling the detector has to
learn to ignore; only the arrangement is new.

Nothing from val or test is used, as host or as sign, and that includes other
faces and joined fragments of those tablets (they share a split already).
Pasted signs carry their own label in whatever mode the dataset was built
(`sign`, `role` or `identity`), so this works for any of them.

A sign ID with n crops is drawn in proportion to sqrt(n), not n, so rare forms
are pasted more often than they occur without swamping the common ones. Output goes to `images/synth` and `labels/synth`, and
`train.txt` lists real and synthetic training images for `data.yaml`.
"""

from __future__ import annotations

import json
import shutil
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from la import augment
from la.shapes import load_mask
from la.signboxes import DATASET_DIR, LICENCE_NOTICE, SignBox, yolo_line

SIGN_SIZE_JITTER = 0.15
MAX_TRIES = 60           # random positions tried per pasted sign
MIN_SIGNS, MAX_SIGNS = 2, 10


def sign_bank(dataset: Path, annotations: list[dict]) -> list[dict]:
    """Every train sign's ink, with its class in the dataset's label mode."""
    bank = []
    for tablet in annotations:
        if tablet["split"] != "train":
            continue
        ink = load_mask(dataset / tablet["image"])
        for sign in tablet["signs"]:
            if sign.get("source") == "pseudo":  # a reviewed box, but its sign is unknown
                continue
            x0, y0, x1, y1 = sign["xyxy"]
            bank.append({"mask": ink[y0:y1, x0:x1].copy(), "class_id": sign["class_id"],
                         "key": sign.get("sign") or "unidentified", "tablet": tablet["tablet"]})
    return bank


def sampling_weights(bank: list[dict]) -> np.ndarray:
    """Each sign weighted n^-1/2, so a sign ID with n crops is drawn in proportion to sqrt(n)."""
    counts = Counter(s["key"] for s in bank)
    weights = np.array([counts[s["key"]] ** -0.5 for s in bank])
    return weights / weights.sum()


def free_space(ink: np.ndarray, boxes: list[tuple[int, int, int, int]], gap: int) -> np.ndarray:
    """Where nothing is: no ink and no labelled box within `gap` pixels."""
    taken = ink.copy()
    for x0, y0, x1, y1 in boxes:
        taken[y0:y1, x0:x1] = True
    if gap > 0:
        taken = ndimage.binary_dilation(taken, iterations=gap)
    return ~taken


def place(free: np.ndarray, h: int, w: int, rng: np.random.Generator) -> tuple[int, int] | None:
    """A random top-left (x, y) whose h x w window is entirely free, or None."""
    height, width = free.shape
    if h >= height or w >= width:
        return None
    blocked = np.pad((~free).cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    for _ in range(MAX_TRIES):
        y, x = int(rng.integers(0, height - h)), int(rng.integers(0, width - w))
        if blocked[y + h, x + w] - blocked[y, x + w] - blocked[y + h, x] + blocked[y, x] == 0:
            return x, y
    return None


def resize(mask: np.ndarray, height: int) -> np.ndarray:
    h, w = mask.shape
    size = (max(1, round(w * height / h)), max(1, height))
    return np.asarray(Image.fromarray(mask.astype(np.uint8) * 255).resize(size, Image.LANCZOS)) >= 128


def compose(host_ink: np.ndarray, host_rows: list[tuple[int, tuple[int, int, int, int]]],
            bank: list[dict], weights: np.ndarray, rng: np.random.Generator,
            blank: bool = False) -> tuple[np.ndarray, list[tuple[int, tuple[int, int, int, int]]], list[str]]:
    """One synthetic tablet: (ink, [(class, xyxy)], pasted sign keys).

    Pasted signs are scaled to the host's typical sign height, so a tablet keeps
    one hand's proportions. `blank` starts from an empty tablet of the host's size.
    """
    ink = np.zeros_like(host_ink) if blank else host_ink.copy()
    rows = [] if blank else list(host_rows)
    heights = [y1 - y0 for _, (_, y0, _, y1) in host_rows]
    typical = int(np.median(heights)) if heights else max(16, ink.shape[0] // 12)
    free = free_space(ink, [box for _, box in rows], gap=max(2, typical // 6))
    pasted = []
    for _ in range(int(rng.integers(MIN_SIGNS, MAX_SIGNS + 1))):
        sign = bank[int(rng.choice(len(bank), p=weights))]
        mask = augment.vary(sign["mask"], rng)
        target = round(typical * (1 + rng.uniform(-SIGN_SIZE_JITTER, SIGN_SIZE_JITTER)))
        if not mask.any() or target < 8:
            continue
        mask = augment.trim(resize(mask, target))
        if not mask.any():
            continue
        h, w = mask.shape
        spot = place(free, h, w, rng)
        if spot is None:
            continue
        x, y = spot
        ink[y:y + h, x:x + w] |= mask
        rows.append((sign["class_id"], (x, y, x + w, y + h)))
        gap = max(2, typical // 6)
        free[max(0, y - gap):y + h + gap, max(0, x - gap):x + w + gap] = False
        pasted.append(sign["key"])
    return ink, rows, pasted


def build_synth(dataset: Path = DATASET_DIR, count: int = 1000, seed: int = 0,
                blank_ratio: float = 0.1) -> dict:
    """Write `count` synthetic tablets and a `train.txt` of real plus synthetic images."""
    if count < 0 or not 0 <= blank_ratio <= 1:
        raise ValueError("count must be nonnegative and blank_ratio between 0 and 1")
    annotations = json.loads((dataset / "annotations.json").read_text(encoding="utf-8"))
    hosts = [t for t in annotations if t["split"] == "train"]
    bank = sign_bank(dataset, annotations)
    if not hosts or not bank:
        raise ValueError("the dataset has no training tablets to compose from")
    weights = sampling_weights(bank)
    rng = np.random.default_rng(seed)
    for kind in ("images", "labels"):
        shutil.rmtree(dataset / kind / "synth", ignore_errors=True)
        (dataset / kind / "synth").mkdir(parents=True)

    report = {"count": count, "seed": seed, "blank_ratio": blank_ratio, "hosts": Counter(),
              "pasted": Counter(), "boxes": 0, "pasted_boxes": 0}
    for i in range(count):
        host = hosts[int(rng.integers(len(hosts)))]
        ink = load_mask(dataset / host["image"])
        rows = [(s["class_id"], tuple(s["xyxy"])) for s in host["signs"]]
        blank = bool(rng.random() < blank_ratio)
        ink, rows, pasted = compose(ink, rows, bank, weights, rng, blank=blank)
        stem = f"synth_{i:05d}"
        Image.fromarray(np.where(ink, 0, 255).astype(np.uint8)).save(dataset / "images" / "synth" / f"{stem}.png")
        height, width = ink.shape
        lines = [yolo_line(c, SignBox("", "", 0, *box, 1.0), width, height) for c, box in rows]
        (dataset / "labels" / "synth" / f"{stem}.txt").write_text("\n".join(lines) + "\n" if lines else "",
                                                                   encoding="utf-8")
        report["hosts"][host["tablet"]] += 1
        report["pasted"].update(pasted)
        report["boxes"] += len(rows)
        report["pasted_boxes"] += len(pasted)

    write_train_list(dataset)
    (dataset / "images" / "synth" / "LICENCE.txt").write_text(LICENCE_NOTICE, encoding="utf-8")
    report["pasted_sign_ids"] = len(report["pasted"])
    (dataset / "synth_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def write_train_list(dataset: Path) -> Path:
    """`train.txt` with the real and synthetic training images; `data.yaml` points at it."""
    images = sorted((dataset / "images" / "train").glob("*.png")) + sorted((dataset / "images" / "synth").glob("*.png"))
    listing = dataset / "train.txt"
    listing.write_text("".join(f"./{p.relative_to(dataset).as_posix()}\n" for p in images), encoding="utf-8")
    data = dataset / "data.yaml"
    data.write_text(data.read_text(encoding="utf-8").replace("train: images/train\n", "train: train.txt\n"),
                    encoding="utf-8")
    return listing
