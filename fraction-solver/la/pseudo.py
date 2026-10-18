"""Self-training: let a trained detector point out the signs the labels miss.

Labels come from matching each lineara.eu crop onto its tracing (`la.signboxes`).
Where that fails (a crop that matches below 0.85, a crop that was never
published) the sign is still on the drawing but has no box. Training then
teaches the detector that such signs are background, and testing counts a
correct detection of one as a false positive.

A detector trained on the imperfect labels already finds many of these. This
module lists its confident detections that overlap no existing box, draws them
on contact sheets for review, and records the accepted ones in
`data/labels/extra_boxes.csv`, which `la.signboxes.build_dataset` merges on the
next build:

    python -m la.cli pseudo propose --weights best.pt --split train
    (review out/yolo_signs/pseudo/train/: sheets and candidates.csv)
    python -m la.cli pseudo accept out/yolo_signs/pseudo/train/candidates.csv

In `train`, candidates at or above `AUTO_ACCEPT` are pre-ticked (classic
pseudo-labelling). In `val` and `test` nothing is pre-ticked and only boxes a
person accepted (`--source reviewed`) are ever merged, so the scores stay honest.
Numerals have no class: reject candidates on tally strokes.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from la.evaluation import iou
from la.shapes import load_mask
from la.signboxes import DATASET_DIR, EXTRA_COLUMNS, EXTRA_LABELS, EXTRA_SOURCES

AUTO_ACCEPT = 0.8
MAX_OVERLAP = 0.3
CELL = 220
SHEET_COLUMNS, SHEET_ROWS = 6, 5
CANDIDATE_COLUMNS = ("id", "tablet", "split", "x0", "y0", "x1", "y1", "confidence", "accept", "sheet")


def unlabelled(boxes: list[tuple[float, float, float, float]], confidences: list[float],
               labelled: list[tuple[float, float, float, float]],
               max_overlap: float = MAX_OVERLAP) -> list[tuple[tuple[int, int, int, int], float]]:
    """Detections overlapping no labelled box (IoU below `max_overlap`), rounded to pixels."""
    out = []
    for box, confidence in zip(boxes, confidences):
        if all(iou(box, other) < max_overlap for other in labelled):
            out.append((tuple(int(round(v)) for v in box), confidence))
    return out


def propose(weights: Path, dataset: Path = DATASET_DIR, split: str = "train", conf: float = 0.4,
            imgsz: int = 1024, device: str | None = None) -> Path:
    """Write candidates.csv and contact sheets to `<dataset>/pseudo/<split>/`; returns the CSV path."""
    from ultralytics import YOLO

    model = YOLO(str(weights))
    annotations = json.loads((dataset / "annotations.json").read_text(encoding="utf-8"))
    out = dataset / "pseudo" / split
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("sheet_*.png"):
        old.unlink()

    candidates = []
    for tablet in (t for t in annotations if t["split"] == split):
        result = model.predict(str(dataset / tablet["image"]), imgsz=imgsz, conf=conf, device=device, verbose=False)[0]
        labelled = [tuple(s["xyxy"]) for s in tablet["signs"]]
        for box, confidence in unlabelled(result.boxes.xyxy.tolist(), result.boxes.conf.tolist(), labelled):
            candidates.append({"tablet": tablet["tablet"], "split": split, "image": tablet["image"],
                               "box": box, "confidence": confidence})
    candidates.sort(key=lambda c: -c["confidence"])

    per_sheet = SHEET_COLUMNS * SHEET_ROWS
    path = out / "candidates.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CANDIDATE_COLUMNS)
        for i, c in enumerate(candidates, 1):
            accept = 1 if split == "train" and c["confidence"] >= AUTO_ACCEPT else ""
            writer.writerow([i, c["tablet"], split, *c["box"], round(c["confidence"], 3), accept,
                             f"sheet_{(i - 1) // per_sheet + 1:03d}.png"])
    for start in range(0, len(candidates), per_sheet):
        contact_sheet(dataset, candidates[start:start + per_sheet], start + 1).save(
            out / f"sheet_{start // per_sheet + 1:03d}.png")
    return path


def contact_sheet(dataset: Path, candidates: list[dict], first_id: int) -> Image.Image:
    """A grid of candidates, each in context with its box drawn and its row id."""
    sheet = Image.new("RGB", (SHEET_COLUMNS * CELL, SHEET_ROWS * CELL), "white")
    draw = ImageDraw.Draw(sheet)
    inks: dict[str, np.ndarray] = {}
    for n, c in enumerate(candidates):
        ink = inks.setdefault(c["image"], load_mask(dataset / c["image"]))
        x0, y0, x1, y1 = c["box"]
        side = max(x1 - x0, y1 - y0)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        left, top = int(max(0, cx - side)), int(max(0, cy - side))
        window = ink[top:int(cy + side), left:int(cx + side)]
        cell = Image.fromarray(np.where(window, 0, 255).astype(np.uint8)).convert("RGB")
        scale = (CELL - 24) / max(cell.size)
        cell = cell.resize((max(1, round(cell.width * scale)), max(1, round(cell.height * scale))))
        ImageDraw.Draw(cell).rectangle([(x0 - left) * scale, (y0 - top) * scale,
                                        (x1 - left) * scale, (y1 - top) * scale], outline="red", width=2)
        col, row = n % SHEET_COLUMNS, n // SHEET_COLUMNS
        sheet.paste(cell, (col * CELL + 2, row * CELL + 22))
        draw.text((col * CELL + 4, row * CELL + 4), f"#{first_id + n}  {c['tablet']}  {c['confidence']:.2f}",
                  fill="black")
    return sheet


def accept(candidates: Path, source: str = "pseudo", extra: Path = EXTRA_LABELS) -> int:
    """Append the candidates marked `accept=1` to the extra-box file; returns how many were new."""
    if source not in EXTRA_SOURCES:
        raise ValueError(f"source must be one of {EXTRA_SOURCES}")
    with candidates.open(encoding="utf-8", newline="") as f:
        chosen = [r for r in csv.DictReader(f) if r["accept"].strip() == "1"]
    existing = set()
    if extra.exists():
        with extra.open(encoding="utf-8", newline="") as f:
            existing = {(r["tablet"], r["x0"], r["y0"], r["x1"], r["y1"]) for r in csv.DictReader(f)}
    extra.parent.mkdir(parents=True, exist_ok=True)
    new_file = not extra.exists()
    added = 0
    with extra.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(EXTRA_COLUMNS)
        for r in chosen:
            key = (r["tablet"], r["x0"], r["y0"], r["x1"], r["y1"])
            if key in existing:
                continue
            existing.add(key)
            writer.writerow([*key, source, r["confidence"]])
            added += 1
    return added
