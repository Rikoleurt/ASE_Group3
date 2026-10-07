"""HT13 Sprint 1 baseline using generic pretrained YOLO, not a Linear A model."""

from base64 import b64encode
from math import ceil
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


def ht13_predictions() -> dict:
    """Expose real detections with normalized boxes for the responsive demo UI."""
    result = ht13_result()
    height, width = result.orig_shape
    predictions = []
    for index, box in enumerate(result.boxes):
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        crop = result.orig_img[
            max(0, int(y1)):min(height, ceil(y2)),
            max(0, int(x1)):min(width, ceil(x2)),
        ]
        image_url = ""
        if crop.size:
            ok, png = cv2.imencode(".png", crop)
            if ok:
                image_url = "data:image/png;base64," + b64encode(png.tobytes()).decode("ascii")
        predictions.append({
            "id": index + 1,
            "label": result.names[int(box.cls.item())],
            "confidence": float(box.conf.item()) * 100,
            "imageUrl": image_url,
            "box": {
                "x": x1 / width,
                "y": y1 / height,
                "w": (x2 - x1) / width,
                "h": (y2 - y1) / height,
            },
        })
    return {"width": width, "height": height, "predictions": predictions}
