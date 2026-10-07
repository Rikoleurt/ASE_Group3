"""Train YOLO on the latest Label Studio export and score it on the test sheets."""

from __future__ import annotations

import argparse
import random
import re
import shutil
import statistics
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import torch
from PIL import Image, ImageDraw
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent.parent
EXPORTS_DIR = ROOT / "data" / "exports"
IMAGES_DIR = ROOT / "data" / "images"
DATASET_DIR = ROOT / "data" / "dataset"
CHECK_DIR = ROOT / "data" / "check"
RUNS_DIR = ROOT / "runs"
WEIGHTS = RUNS_DIR / "train" / "weights" / "best.pt"
PRETRAINED = "yolo26n.pt"
SPLITS = ("train", "val", "test")

KEEP_TRAIN = {"weights/best.pt", "args.yaml", "results.png"}
KEEP_EVAL_SUFFIX = "_pred.jpg"

NAME_PATTERN = re.compile(r"sheet\d{2}_\d{2}")
MAX_AREA_SHARE = 0.25
MIN_SIDE_PX = 4


def read_labels() -> tuple[str, dict[str, list[str]]]:
    zips = sorted(EXPORTS_DIR.glob("*.zip"), key=lambda p: p.stat().st_mtime)
    if not zips:
        sys.exit(f"No export found: put the Label Studio YOLO .zip in {EXPORTS_DIR}")
    labels: dict[str, list[str]] = {}
    with zipfile.ZipFile(zips[-1]) as archive:
        for name in archive.namelist():
            if not (name.startswith("labels/") and name.endswith(".txt")):
                continue
            match = NAME_PATTERN.search(Path(name).stem)
            if match is None:
                print(f"skipped {name}: no sheetNN_MM in its name")
                continue
            text = archive.read(name).decode()
            labels[match.group()] = [line for line in text.splitlines() if line.strip()]
    if not labels:
        sys.exit(f"No label files in {zips[-1].name}: was it exported in YOLO format?")
    missing = sorted(stem for stem in labels if not (IMAGES_DIR / f"{stem}.jpg").is_file())
    if missing:
        sys.exit(f"Labels without image in {IMAGES_DIR}: {', '.join(missing)}")
    return zips[-1].name, labels


def check(stem: str, lines: list[str], draw: bool) -> list[str]:
    warnings = []
    with Image.open(IMAGES_DIR / f"{stem}.jpg") as image:
        image = image.convert("RGB")
        pen = ImageDraw.Draw(image)
        for number, line in enumerate(lines, start=1):
            fields = line.split()
            if len(fields) != 5 or fields[0] != "0":
                warnings.append(f"line {number}: expected 'class cx cy w h' with class 0, got '{line}'")
                continue
            cx, cy, w, h = (float(v) for v in fields[1:])
            box_w, box_h = w * image.width, h * image.height
            left, top = cx * image.width - box_w / 2, cy * image.height - box_h / 2
            suspicious = (box_w * box_h > MAX_AREA_SHARE * image.width * image.height
                          or min(box_w, box_h) < MIN_SIDE_PX)
            if suspicious:
                warnings.append(f"box {number}: {box_w:.0f}x{box_h:.0f} px")
            pen.rectangle((left, top, left + box_w, top + box_h),
                          outline="red" if suspicious else "lime", width=2)
        if draw:
            image.save(CHECK_DIR / f"{stem}.jpg", "JPEG", quality=90)
    return warnings


def pick_sheets(by_sheet: dict[str, list[str]], rng: random.Random, taken: set[str]) -> list[str]:
    total = sum(len(stems) for stems in by_sheet.values())
    candidates = sorted(set(by_sheet) - taken)
    rng.shuffle(candidates)
    picked, count = [], 0
    for sheet in candidates:
        if count >= 0.15 * total:
            break
        picked.append(sheet)
        count += len(by_sheet[sheet])
    return picked


def build_dataset(labels: dict[str, list[str]], val: list[str] | None, test: list[str] | None) -> Path:
    by_sheet: dict[str, list[str]] = defaultdict(list)
    for stem in sorted(labels):
        by_sheet[stem.split("_")[0]].append(stem)
    if len(by_sheet) < 3:
        sys.exit(f"Need at least 3 annotated sheets to split by sheet, found {len(by_sheet)}")

    rng = random.Random(0)
    test = test if test is not None else pick_sheets(by_sheet, rng, set())
    val = val if val is not None else pick_sheets(by_sheet, rng, set(test))
    unknown = (set(test) | set(val)) - set(by_sheet)
    if unknown:
        sys.exit(f"Not annotated: {', '.join(sorted(unknown))}")
    if set(test) & set(val):
        sys.exit("A sheet cannot be in both val and test")
    split_of = {sheet: "train" for sheet in by_sheet}
    split_of.update({sheet: "val" for sheet in val})
    split_of.update({sheet: "test" for sheet in test})

    shutil.rmtree(DATASET_DIR, ignore_errors=True)
    for split in SPLITS:
        (DATASET_DIR / "images" / split).mkdir(parents=True)
        (DATASET_DIR / "labels" / split).mkdir(parents=True)

    summary = {split: [0, 0, []] for split in SPLITS}
    for sheet, stems in sorted(by_sheet.items()):
        split = split_of[sheet]
        summary[split][2].append(sheet)
        for stem in stems:
            shutil.copy(IMAGES_DIR / f"{stem}.jpg", DATASET_DIR / "images" / split / f"{stem}.jpg")
            lines = labels[stem]
            (DATASET_DIR / "labels" / split / f"{stem}.txt").write_text("".join(f"{line}\n" for line in lines))
            summary[split][0] += 1
            summary[split][1] += len(lines)
    for split in SPLITS:
        images, boxes, sheets = summary[split]
        print(f"{split:<5} {images:>3} images {boxes:>5} boxes  {' '.join(sheets)}")

    data_yaml = DATASET_DIR / "data.yaml"
    data_yaml.write_text(
        f"path: {DATASET_DIR}\n"
        "train: images/train\n"
        "val: images/val\n"
        "test: images/test\n"
        "names:\n"
        "  0: character\n"
    )
    return data_yaml


def keep_only(folder: Path, wanted) -> None:
    for path in folder.rglob("*"):
        if path.is_file() and not wanted(path.relative_to(folder).as_posix()):
            path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--val-sheets", nargs="*", help="e.g. sheet13 (default: random, ~15%% of images)")
    parser.add_argument("--test-sheets", nargs="*", help="e.g. sheet16 (default: random, ~15%% of images)")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--check", action="store_true", help="only check the export and draw the boxes in data/check/")
    args = parser.parse_args()

    export, labels = read_labels()
    if args.check:
        shutil.rmtree(CHECK_DIR, ignore_errors=True)
        CHECK_DIR.mkdir(parents=True)
    for stem in sorted(labels):
        for warning in check(stem, labels[stem], draw=args.check):
            print(f"{stem}: {warning}")

    counts = [len(lines) for lines in labels.values()]
    empty = sorted(stem for stem, lines in labels.items() if not lines)
    print(f"\nExport  : {export}")
    print(f"Boxes   : {sum(counts)} in {len(counts)} images"
          f"  (per image: min {min(counts)}, median {statistics.median(counts):.0f}, max {max(counts)})")
    if empty:
        print(f"No boxes: {', '.join(empty)}")
    if args.check:
        print(f"Boxes drawn in {CHECK_DIR}  (green = ok, red = suspicious)")
        return

    print()
    data_yaml = build_dataset(labels, args.val_sheets, args.test_sheets)
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    downloaded = not Path(PRETRAINED).exists()

    for name in ("train", "eval-test"):
        shutil.rmtree(RUNS_DIR / name, ignore_errors=True)
    YOLO(PRETRAINED).train(
        data=str(data_yaml), epochs=args.epochs, patience=30, imgsz=640, batch=8,
        device=device, workers=2, project=str(RUNS_DIR), name="train", exist_ok=True, seed=0,
    )
    metrics = YOLO(str(WEIGHTS)).val(
        data=str(data_yaml), split="test", imgsz=640, device=device,
        project=str(RUNS_DIR), name="eval-test", exist_ok=True, plots=True,
    )

    keep_only(RUNS_DIR / "train", lambda name: name in KEEP_TRAIN)
    keep_only(RUNS_DIR / "eval-test", lambda name: name.endswith(KEEP_EVAL_SUFFIX))
    if downloaded:
        Path(PRETRAINED).unlink(missing_ok=True)

    box = metrics.box
    print(f"\nWeights   : {WEIGHTS}")
    print("Scores on the test sheets, never seen during training:")
    print(f"Precision : {box.mp:.3f}   share of predicted boxes that are real characters")
    print(f"Recall    : {box.mr:.3f}   share of real characters that were found")
    print(f"mAP50     : {box.map50:.3f}")
    print(f"mAP50-95  : {box.map:.3f}   stricter: also rewards tight boxes")


if __name__ == "__main__":
    main()
