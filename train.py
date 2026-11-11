"""Entraîner YOLO26 sur les caractères annotés du corpus Linear A.

Two models read a tablet: a detector that finds signs and a classifier that names
each one. Train both from the repository root:

    python train.py detect      # data: la.cli dataset --labels sign [then la.cli synth]
    python train.py classify    # data: la.cli crops

Signs are never mirrored (orientation is part of a sign's identity), and the
classifier's crops are only cropped gently: a sign cut in half is another sign.
"""

import argparse
from pathlib import Path

from ultralytics import YOLO


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "fraction-solver" / "out"


def detect(args: argparse.Namespace) -> None:
    model = YOLO(args.model or str(ROOT / "yolo26n.pt"))
    model.train(
        data=str(args.data or DATA / "yolo_signs" / "data.yaml"),
        epochs=args.epochs or 150,
        patience=30,
        batch=args.batch or 8,
        imgsz=args.imgsz or 1024,  # the web demo predicts at this size
        fliplr=0.0,
        degrees=3.0,
        seed=args.seed,
        workers=args.workers,
        project=str(ROOT / "runs" / "detect"),
        name=args.name or "linear_a_signs",
    )


def classify(args: argparse.Namespace) -> None:
    model = YOLO(args.model or "yolo26n-cls.pt")
    model.train(
        data=str(args.data or DATA / "sign_crops"),
        epochs=args.epochs or 100,
        patience=25,
        batch=args.batch or 64,
        imgsz=args.imgsz or 128,
        fliplr=0.0,
        scale=0.1,          # random crops keep 90-100% of the sign
        auto_augment=None,  # varied copies come from la.augment instead
        hsv_h=0.0, hsv_s=0.0, hsv_v=0.2,
        erasing=0.1,
        seed=args.seed,
        workers=args.workers,
        project=str(ROOT / "runs" / "classify"),
        name=args.name or "linear_a_signs",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("task", choices=["detect", "classify"])
    parser.add_argument("--data", type=Path, help="data.yaml (detect) or crop folder (classify)")
    parser.add_argument("--model", help="starting weights (default yolo26n.pt / yolo26n-cls.pt)")
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--batch", type=int)
    parser.add_argument("--imgsz", type=int, help="image size (default 1024 detect / 128 classify)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--workers", type=int, default=2, help="dataloader processes (each holds images in RAM)")
    parser.add_argument("--name", help="run name under runs/<task>/")
    args = parser.parse_args()
    {"detect": detect, "classify": classify}[args.task](args)


if __name__ == "__main__":
    main()
