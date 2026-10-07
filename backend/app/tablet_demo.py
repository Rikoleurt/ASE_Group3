"""HT13 demo: a trained Linear A sign detector when one exists, otherwise the
Sprint 1 baseline using generic pretrained YOLO, which is not a Linear A model."""

import os
from base64 import b64encode
from math import ceil
from pathlib import Path
from ultralytics import YOLO
import cv2

HT13_IMAGE = Path(__file__).resolve().parent / "static" / "ht13.webp"
YOLO_WEIGHTS = Path(__file__).resolve().parents[2] / "yolo26n.pt"
# Trained on the lineara.eu dataset; see "Training data for a sign detector" in the README.
SIGN_WEIGHTS = Path(os.getenv(
    "SIGN_DETECTOR_WEIGHTS", Path(__file__).resolve().parents[2] / "models" / "linear_a_signs.pt"
))
# Must match the imgsz the sign detector was trained with (the README command uses 1024).
SIGN_IMGSZ = 1024


def active_weights() -> tuple[Path, int, bool]:
    """(weights, imgsz, trained): the sign detector if present, else the baseline."""
    if SIGN_WEIGHTS.is_file():
        return SIGN_WEIGHTS, SIGN_IMGSZ, True
    if not YOLO_WEIGHTS.is_file():
        raise FileNotFoundError("Pretrained yolo26n.pt is required at the repository root.")
    return YOLO_WEIGHTS, 640, False


def ht13_result(image_path: Path = HT13_IMAGE):
    """
    Run the active model, including legitimate empty results
    """
    weights, imgsz, _trained = active_weights()
    if not image_path.is_file():
        raise FileNotFoundError(f"Cannot read HT13 image: {image_path}")


    model = YOLO(str(weights))
    return model.predict(
        source=str(image_path), imgsz=imgsz, conf=0.25, device="cpu", save=False, verbose=False
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
    """Expose real detections with normalized boxes for the responsive demo UI.

    With the trained detector, boxes it labels "fraction" (train with
    `la.cli dataset --labels role`) also get shape-matched guesses for which
    fraction sign they are. Nothing else is shape-matched: the method was only
    measured to work on fraction signs.
    """
    result = ht13_result()
    _weights, _imgsz, trained = active_weights()
    height, width = result.orig_shape
    predictions = []
    for index, box in enumerate(result.boxes):
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        crop = result.orig_img[
            max(0, int(y1)):min(height, ceil(y2)),
            max(0, int(x1)):min(width, ceil(x2)),
        ]
        label = result.names[int(box.cls.item())]
        image_url = ""
        if crop.size:
            ok, png = cv2.imencode(".png", crop)
            if ok:
                image_url = "data:image/png;base64," + b64encode(png.tobytes()).decode("ascii")
        prediction = {
            "id": index + 1,
            "label": label,
            "confidence": float(box.conf.item()) * 100,
            "imageUrl": image_url,
            "box": {
                "x": x1 / width,
                "y": y1 / height,
                "w": (x2 - x1) / width,
                "h": (y2 - y1) / height,
            },
        }
        if trained and label == "fraction" and crop.size:
            from backend.app.reading import identify_mask

            prediction["shapeGuesses"] = identify_mask(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) < 128, tablet="HT 13")
        predictions.append(prediction)
    return {"width": width, "height": height, "trained": trained, "predictions": predictions}
