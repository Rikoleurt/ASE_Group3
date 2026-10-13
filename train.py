"""Entraîner YOLO26 sur les caractères annotés du corpus Linear A."""

from pathlib import Path

from ultralytics import YOLO


ROOT = Path(__file__).resolve().parent


def main() -> None:
    model = YOLO(str(ROOT / "yolo26n.pt"))
    model.train(
        data=str(ROOT / "fraction-solver" / "out" / "yolo_signs" / "data.yaml"),
        epochs=100,
        batch=8,
        imgsz=1024,
        patience=20,
        project=str(ROOT / "runs" / "detect"),
        name="linear_a_signs",
    )


if __name__ == "__main__":
    main()
