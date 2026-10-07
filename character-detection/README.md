# Character detection

First step towards tablet analysis: **draw a bounding box around each printed character** (digits and Latin letters) in a photo.

The model is a pretrained YOLO detector, fine-tuned on our own photos annotated in Label Studio with a single class, `character`. Recognising *which* character it is comes later.

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd character-detection
uv sync                          # Python 3.13, ultralytics, pillow
uv tool install label-studio     # annotation tool, kept in its own environment
```

## Prepare photos

Put photos in `data/originals/`, named after [ANNOTATION_GUIDE.md](ANNOTATION_GUIDE.md):
`sheetNN` for a whole page, which is cut into a 3 × 4 grid of tiles, or `sheetNN_MM` for a framed zone, kept whole.

```bash
uv run python scripts/prepare_images.py --overview --all   # -> data/images/ + data/overview/ (numbered grids)
```

Look at `data/overview/`, list the tiles worth annotating in `data/keep.txt` (one name per line, e.g. `sheet02_06`), then run the script again without options: only the listed tiles are kept. Every image is upright, at most 1280 px and without metadata.

## Annotate

Annotate `data/images/` in Label Studio (`label-studio start`, then http://localhost:8080) following [ANNOTATION_GUIDE.md](ANNOTATION_GUIDE.md), and export in **YOLO** format into `data/exports/`.

## Train and evaluate

```bash
uv run python scripts/train.py --check     # check the latest export, draw every box in data/check/
uv run python scripts/train.py --val-sheets sheet13 --test-sheets sheet16
uv run python scripts/predict.py data/images/sheet02_06.jpg   # -> data/predictions/
uv run python scripts/predict.py --page data/originals/sheet05.HEIC
```

`--page` runs the model on whole-page photos. The model learnt on tiles, so the page is fed at the scale of its training tiles (2560 px for a 4284 × 5712 photo) instead of being shrunk to 640 px, where characters become too small to be found. Pages 01–11 were never annotated: they are the fair ones to test on.

`train.py` uses the latest export in `data/exports/`: it reports suspicious boxes, splits the images by sheet, fine-tunes YOLO (about 5 min on an M2) and prints precision, recall and mAP on the test sheets, never seen during training.
Each run **replaces** the model in `runs/train/weights/best.pt`.
Without `--val-sheets` / `--test-sheets`, sheets are drawn at random (about 15% of images each).

## Layout

```
scripts/
  prepare_images.py   photos -> images to annotate
  train.py            Label Studio export -> checked dataset -> model -> test scores
  predict.py          any image or whole page -> data/predictions/ with the boxes drawn
data/                 gitignored
  originals/          the photos, source of everything else
  keep.txt            tiles kept for annotation
  images/             images annotated in Label Studio
  exports/            Label Studio YOLO exports
  predictions/        images with predicted boxes
  dataset/            train/val/test split of the last training, described by data.yaml
  check/, overview/   drawn on request (--check, --overview), safe to delete
runs/                 gitignored
  train/              weights/best.pt, results.png (scores per epoch), args.yaml (settings)
  eval-test/          predictions on the test sheets
```

## Status

- [x] Project setup
- [x] Annotation guide
- [x] Photo collection (18 pages of one printed catalogue, cut into tiles)
- [x] Annotation in Label Studio (20 tiles, 787 boxes)
- [x] Dataset split
- [x] Training (YOLO26n fine-tuned, 15 training tiles, ~4 min on an M2)
- [x] Evaluation: on the test sheet, precision 0.89, recall 0.93, mAP50 0.94, mAP50-95 0.49
- [ ] Light text on coloured backgrounds: mostly missed, needs a few annotated examples

Test scores come from 3 tiles of one sheet: read them as an indication, not a measurement.
