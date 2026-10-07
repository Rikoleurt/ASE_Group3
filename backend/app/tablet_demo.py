"""HT13 Sprint 1 baseline using generic pretrained YOLO, not a Linear A model."""

from pathlib import Path
from ultralytics import YOLO
import cv2

HT13_IMAGE = Path(__file__).resolve().parent / "static" / "ht13.webp"
YOLO_WEIGHTS = Path(__file__).resolve().parents[2] / "yolo26n.pt"


def ht13_result(image_path: Path = HT13_IMAGE):
    """
    Run the local pretrained model, including legitimate empty results
    """
    if not YOLO_WEIGHTS.is_file():
        raise FileNotFoundError("Pretrained yolo26n.pt is required at the repository root.")
    if not image_path.is_file():
        raise FileNotFoundError(f"Cannot read HT13 image: {image_path}")


    model = YOLO(str(YOLO_WEIGHTS))
    return model.predict(
        source=str(image_path), imgsz=640, conf=0.25, device="cpu", save=False, verbose=False
    )[0]


def annotate_ht13(image_path: Path = HT13_IMAGE) -> bytes:
    """
    Render with Ultralytics and return a PNG in memory; no output files or DB
    """

    annotated = ht13_result(image_path).plot(labels=True, conf=True, line_width=3)
    ok, png = cv2.imencode(".png", annotated)
    if not ok:
        raise RuntimeError("Could not encode the HT13 annotation.")
    return png.tobytes()
