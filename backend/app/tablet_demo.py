"""HT13 demo: a trained Linear A sign reader when one exists, otherwise the
Sprint 1 baseline using generic pretrained YOLO, which is not a Linear A model.

The reader is either one detector that also names signs (361 classes), or a
detector that only finds signs plus a classifier that names each crop (`train.py
detect` and `train.py classify`). The classifier is used whenever its weights
are present next to a trained detector.
"""

import json
import os
import sys
from base64 import b64encode
from functools import lru_cache
from math import ceil
from pathlib import Path
from threading import Lock
from ultralytics import YOLO
from ultralytics.engine.results import Results
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HT13_IMAGE = Path(__file__).resolve().parent / "static" / "ht13.webp"
YOLO_WEIGHTS = ROOT / "yolo26n.pt"
SIGN_WEIGHTS = Path(os.getenv("SIGN_DETECTOR_WEIGHTS", ROOT / "models" / "linear_a_signs.pt"))
# Sign names and roles travel beside the weights, as `<weights>.json` (out/sign_crops/classes.json).
CLASSIFIER_WEIGHTS = Path(os.getenv("SIGN_CLASSIFIER_WEIGHTS", ROOT / "models" / "linear_a_classifier.pt"))

SIGN_IMGSZ = 1024
CANDIDATES = 3
INFERENCE_LOCK = Lock()


@lru_cache(maxsize=2)
def _load_model(weights: str, modified_ns: int) -> YOLO:
    """Reuse the models; the timestamp invalidates the cache after weight updates."""
    return YOLO(weights)


def _model(weights: Path) -> YOLO:
    return _load_model(str(weights.resolve()), weights.stat().st_mtime_ns)


def active_weights() -> tuple[Path, int, bool]:
    """(weights, imgsz, trained): the sign detector if present, else the baseline."""
    if SIGN_WEIGHTS.is_file():
        return SIGN_WEIGHTS, SIGN_IMGSZ, True
    if not YOLO_WEIGHTS.is_file():
        raise FileNotFoundError("Pretrained yolo26n.pt is required at the repository root.")
    return YOLO_WEIGHTS, 640, False


def active_classifier() -> Path | None:
    """The sign classifier, only ever used behind the trained detector."""
    return CLASSIFIER_WEIGHTS if SIGN_WEIGHTS.is_file() and CLASSIFIER_WEIGHTS.is_file() else None


@lru_cache(maxsize=2)
def _sign_catalogue(path: str, modified_ns: int) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sign_catalogue(weights: Path) -> dict:
    """Sign ID -> {name, roles, ...}; empty when the file is missing (IDs are shown as they are)."""
    path = weights.with_suffix(".json")
    return _sign_catalogue(str(path), path.stat().st_mtime_ns) if path.is_file() else {}


def read_image(source: Path | np.ndarray, confidence: float = 0.25):
    """
    Run the active model on an image file or a BGR array, including legitimate empty results
    """
    weights, imgsz, _trained = active_weights()
    # YOLO's predictor is mutable: serialize calls sharing the cached model.
    with INFERENCE_LOCK:
        model = _model(weights)
        return model.predict(
            source=source if isinstance(source, np.ndarray) else str(source), imgsz=imgsz,
            conf=confidence, device="cpu", save=False, verbose=False
        )[0]


def ht13_result(image_path: Path = HT13_IMAGE, confidence: float = 0.25):
    """
    Run the active model on the HT13 demo image
    """
    active_weights()
    if not image_path.is_file():
        raise FileNotFoundError(f"Cannot read HT13 image: {image_path}")
    return read_image(image_path, confidence=confidence)


def name_signs(result) -> list[list[dict]] | None:
    """The classifier's best `CANDIDATES` signs for every box, or None without a classifier."""
    weights = active_classifier()
    if weights is None:
        return None
    fraction_solver = str(ROOT / "fraction-solver")
    if fraction_solver not in sys.path:
        sys.path.insert(0, fraction_solver)  # as backend.app.reading does: not an installed package
    from la import reader

    boxes = [tuple(b) for b in result.boxes.xyxy.tolist()]
    catalogue = sign_catalogue(weights)
    with INFERENCE_LOCK:
        named = reader.name_boxes(_model(weights), reader.ink_of(result.orig_img), boxes,
                                  top=CANDIDATES, device="cpu")
    return [[{"sign": sign, "label": catalogue.get(sign, {}).get("name", sign),
              "roles": catalogue.get(sign, {}).get("roles", []), "probability": probability * 100}
             for sign, probability in top] for top in named]


def annotate_ht13(image_path: Path = HT13_IMAGE, confidence: float = 0.25) -> bytes:
    """
    Render with Ultralytics and return a PNG in memory; no output files or DB
    """
    result = ht13_result(image_path, confidence=confidence)
    candidates = name_signs(result) if len(result.boxes) else None
    if candidates:
        # Redraw with the classifier's names: one class per box, scored as in the JSON.
        rows = [[*box, conf * top[0]["probability"] / 100, i] for i, (box, conf, top) in
                enumerate(zip(result.boxes.xyxy.tolist(), result.boxes.conf.tolist(), candidates))]
        result = Results(result.orig_img, path=result.path, names={i: top[0]["label"] for i, top in
                                                                   enumerate(candidates)}, boxes=np.array(rows))
    annotated = result.plot(labels=True, conf=True, line_width=3)
    ok, png = cv2.imencode(".png", annotated)
    if not ok:
        raise RuntimeError("Could not encode the HT13 annotation.")
    return png.tobytes()


def ht13_predictions(confidence: float = 0.25) -> dict:
    """Expose real detections on HT13 with normalized boxes for the responsive demo UI."""
    return predictions_for(ht13_result(confidence=confidence), tablet="HT 13")


def predictions_for(result, tablet: str = "") -> dict:
    """Serialize one model result: normalized boxes, crops and, with a classifier, sign names.

    With a classifier, each box is labelled with its most likely sign and lists
    the top candidates; `confidence` is then the detector's confidence that a
    sign is there times the classifier's probability for that sign.

    Boxes labelled "fraction" by a role-trained detector, or whose most likely
    sign is a fraction, also get shape-matched guesses for which fraction sign
    they are. Nothing else is shape-matched: the method was only measured to
    work on fraction signs. `tablet` keeps that tablet's own drawings out of
    the shape references; "" excludes nothing.
    """
    _weights, _imgsz, trained = active_weights()
    candidates = name_signs(result) if len(result.boxes) else None
    height, width = result.orig_shape
    predictions = []
    for index, box in enumerate(result.boxes):
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        crop = result.orig_img[
            max(0, int(y1)):min(height, ceil(y2)),
            max(0, int(x1)):min(width, ceil(x2)),
        ]
        label = result.names[int(box.cls.item())]
        detected = float(box.conf.item()) * 100
        image_url = ""
        if crop.size:
            ok, png = cv2.imencode(".png", crop)
            if ok:
                image_url = "data:image/png;base64," + b64encode(png.tobytes()).decode("ascii")
        prediction = {
            "id": index + 1,
            "label": label,
            "confidence": detected,
            "imageUrl": image_url,
            "box": {
                "x": x1 / width,
                "y": y1 / height,
                "w": (x2 - x1) / width,
                "h": (y2 - y1) / height,
            },
        }
        fraction = label == "fraction"
        if candidates:
            top = candidates[index]
            prediction.update(label=top[0]["label"], confidence=detected * top[0]["probability"] / 100,
                              detectionConfidence=detected, candidates=top)
            fraction = "fraction" in top[0]["roles"]
        if trained and fraction and crop.size:
            from backend.app.reading import identify_mask

            prediction["shapeGuesses"] = identify_mask(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) < 128, tablet=tablet)
        predictions.append(prediction)
    return {"width": width, "height": height, "trained": trained, "predictions": predictions}
