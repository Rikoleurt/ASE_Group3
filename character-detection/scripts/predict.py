"""Draw the predicted boxes on images or whole pages."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pillow_heif import register_heif_opener
from ultralytics import YOLO

from prepare_images import COLS, EXTENSIONS, ROWS

ROOT = Path(__file__).resolve().parent.parent
WEIGHTS = ROOT / "runs" / "train" / "weights" / "best.pt"
PREDICTIONS_DIR = ROOT / "data" / "predictions"
IMGSZ = 640
MAX_DETECTIONS = 5000
MAX_OUTPUT_SIZE = 2560


def collect(sources: list[Path]) -> list[Path]:
    images = []
    for source in sources:
        if source.is_dir():
            images += sorted(p for p in source.iterdir() if p.suffix.lower() in EXTENSIONS)
        else:
            images.append(source)
    return images


def page_imgsz(width: int, height: int) -> int:
    tile_side = max(width / COLS, height / ROWS)
    size = max(width, height) * IMGSZ / tile_side
    return max(IMGSZ, round(size / 32) * 32)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sources", type=Path, nargs="+", help="image files or folders")
    parser.add_argument("--page", action="store_true", help="the images are whole pages, not tiles")
    parser.add_argument("--conf", type=float, default=0.25, help="minimum confidence to keep a box")
    args = parser.parse_args()

    if not WEIGHTS.is_file():
        sys.exit(f"No trained model: run scripts/train.py first ({WEIGHTS} missing)")
    register_heif_opener()
    model = YOLO(str(WEIGHTS))
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)

    for path in collect(args.sources):
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
        imgsz = page_imgsz(*image.size) if args.page else IMGSZ
        result = model.predict(image, imgsz=imgsz, conf=args.conf, max_det=MAX_DETECTIONS,
                               device=device, verbose=False)[0]
        boxes = result.boxes.xyxy.tolist()

        full_width = image.width
        image.thumbnail((MAX_OUTPUT_SIZE, MAX_OUTPUT_SIZE), Image.Resampling.LANCZOS)
        ratio = image.width / full_width
        draw = ImageDraw.Draw(image)
        for box in boxes:
            draw.rectangle([v * ratio for v in box], outline="lime", width=2)
        draw.text((10, 10), f"{len(boxes)} characters", fill="lime",
                  font=ImageFont.load_default(size=max(28, image.width // 40)),
                  stroke_width=3, stroke_fill="black")
        image.save(PREDICTIONS_DIR / f"{path.stem}.jpg", "JPEG", quality=90)
        print(f"{path.name:<24} {len(boxes):>5} boxes  (model input {imgsz} px)")

    print(f"\nDrawn images: {PREDICTIONS_DIR}")


if __name__ == "__main__":
    main()
