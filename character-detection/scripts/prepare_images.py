"""Cut the original photos into images to annotate."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from pillow_heif import register_heif_opener

ROOT = Path(__file__).resolve().parent.parent
ORIGINALS_DIR = ROOT / "data" / "originals"
IMAGES_DIR = ROOT / "data" / "images"
OVERVIEW_DIR = ROOT / "data" / "overview"
KEEP_FILE = ROOT / "data" / "keep.txt"

EXTENSIONS = {".heic", ".heif", ".jpg", ".jpeg", ".png"}
PAGE_PATTERN = re.compile(r"sheet\d{2}")
ZONE_PATTERN = re.compile(r"sheet\d{2}_\d{2}")
OVERVIEW_SIZE = 1600
MAX_SIZE = 1280
COLS, ROWS = 3, 4

Box = tuple[int, int, int, int]


def find_photos(src: Path) -> list[Path]:
    photos = sorted(p for p in src.iterdir() if p.suffix.lower() in EXTENSIONS)
    errors = []
    seen: dict[str, Path] = {}
    for photo in photos:
        if not (PAGE_PATTERN.fullmatch(photo.stem) or ZONE_PATTERN.fullmatch(photo.stem)):
            errors.append(f"{photo.name}: name must look like sheet07 (page) or sheet07_03 (zone)")
        elif photo.stem in seen:
            errors.append(f"{photo.name}: same name as {seen[photo.stem].name}")
        seen.setdefault(photo.stem, photo)
    if errors:
        sys.exit("Fix these files before preparing:\n  " + "\n  ".join(errors))
    return photos


def tile_boxes(width: int, height: int, cols: int, rows: int) -> list[Box]:
    xs = [width * i // cols for i in range(cols + 1)]
    ys = [height * j // rows for j in range(rows + 1)]
    return [(xs[i], ys[j], xs[i + 1], ys[j + 1]) for j in range(rows) for i in range(cols)]


def draw_overview(image: Image.Image, boxes: list[Box]) -> Image.Image:
    scale = OVERVIEW_SIZE / max(image.size)
    overview = image.resize((round(image.width * scale), round(image.height * scale)))
    draw = ImageDraw.Draw(overview)
    font = ImageFont.load_default(size=48)
    for number, box in enumerate(boxes, start=1):
        left, top, right, bottom = (round(v * scale) for v in box)
        draw.rectangle((left, top, right, bottom), outline="red", width=3)
        draw.text((left + 10, top + 6), f"{number:02d}", fill="red", font=font,
                  stroke_width=3, stroke_fill="white")
    return overview


def prepare(photo: Path, overview: bool, keep: set[str] | None) -> list[str]:
    with Image.open(photo) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        if ZONE_PATTERN.fullmatch(photo.stem):
            named = {photo.stem: (0, 0, image.width, image.height)}
        else:
            boxes = tile_boxes(image.width, image.height, COLS, ROWS)
            named = {f"{photo.stem}_{n:02d}": box for n, box in enumerate(boxes, start=1)}
            if overview:
                draw_overview(image, boxes).save(OVERVIEW_DIR / f"{photo.stem}.jpg", "JPEG", quality=85)

        written = []
        for name, box in named.items():
            if keep is not None and name not in keep:
                continue
            tile = image.crop(box)
            tile.thumbnail((MAX_SIZE, MAX_SIZE), Image.Resampling.LANCZOS)
            tile.save(IMAGES_DIR / f"{name}.jpg", "JPEG", quality=95)
            written.append(name)
        return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--overview", action="store_true", help="draw the numbered grids in data/overview/")
    parser.add_argument("--all", action="store_true", help="ignore data/keep.txt and write every tile")
    args = parser.parse_args()

    if not ORIGINALS_DIR.is_dir():
        sys.exit(f"No original photos: {ORIGINALS_DIR} does not exist")
    keep = None
    if KEEP_FILE.is_file() and not args.all:
        keep = set(KEEP_FILE.read_text().split())
    register_heif_opener()
    photos = find_photos(ORIGINALS_DIR)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    if args.overview:
        OVERVIEW_DIR.mkdir(parents=True, exist_ok=True)

    seen: dict[str, str] = {}
    for photo in photos:
        written = prepare(photo, args.overview, keep)
        clashes = [name for name in written if name in seen]
        if clashes:
            sys.exit(f"{photo.name} and {seen[clashes[0]]} both produce {clashes[0]}.jpg: rename one of them")
        seen.update({name: photo.name for name in written})
        print(f"{photo.name:<16} -> {len(written):>2} images")

    sheets = {name.split("_")[0] for name in seen}
    print(f"\n{len(seen)} images from {len(sheets)} sheets written to {IMAGES_DIR}")
    if keep is not None:
        print(f"Filtered by {KEEP_FILE.name}; use --all to write every tile")
    if args.overview:
        print(f"Grids to choose from: {OVERVIEW_DIR}")


if __name__ == "__main__":
    main()
