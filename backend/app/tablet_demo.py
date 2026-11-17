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
import torch

ROOT = Path(__file__).resolve().parents[2]
HT13_IMAGE = Path(__file__).resolve().parent / "static" / "ht13.webp"
YOLO_WEIGHTS = ROOT / "yolo26n.pt"
SIGN_WEIGHTS = Path(os.getenv("SIGN_DETECTOR_WEIGHTS", ROOT / "models" / "linear_a_signs.pt"))
# Sign names and roles travel beside the weights, as `<weights>.json` (out/sign_crops/classes.json).
CLASSIFIER_WEIGHTS = Path(os.getenv("SIGN_CLASSIFIER_WEIGHTS", ROOT / "models" / "linear_a_classifier.pt"))
# Optional refinements of the classifier's naming, chosen with the benchmark (benchmark/models.yaml,
# signs-v1-tta-knn-comparer): written by scripts/build_reader.py. Without the file the plain classifier names.
READER_CONFIG = Path(os.getenv("SIGN_READER_CONFIG", ROOT / "models" / "linear_a_reader.json"))

SIGN_IMGSZ = 1024
CANDIDATES = 3
INFERENCE_LOCK = Lock()
# Calls are serialized by INFERENCE_LOCK, so more threads only contend: on a
# 16-CPU Windows laptop torch's default (8) made one HT13 reading take ~21 s
# instead of ~0.7 s with 2. Set in each inference call, not once: the thread
# count is per OS thread, and FastAPI runs routes in worker threads.
INFERENCE_THREADS = int(os.getenv("INFERENCE_THREADS", "2"))


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
        torch.set_num_threads(INFERENCE_THREADS)
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
        torch.set_num_threads(INFERENCE_THREADS)
        extra = refinements(weights)
        options = {} if extra is None else {"tta": extra["tta"], "bank": extra["bank"], "comparer": extra["comparer"],
                                            "real_counts": extra["counts"], "prior": extra["prior"]}
        named = reader.name_boxes(_model(weights), reader.ink_of(result.orig_img), boxes,
                                  top=CANDIDATES, device="cpu", **options)
    return [[{"sign": sign, "label": catalogue.get(sign, {}).get("name", sign),
              "roles": catalogue.get(sign, {}).get("roles", []), "probability": probability * 100}
             for sign, probability in top] for top in named]


@lru_cache(maxsize=2)
def _load_refinements(config_path: str, modified_ns: int, classifier_path: str) -> dict:
    """TTA flag, neighbour bank, comparer and frequency prior from `READER_CONFIG`.

    A refinement whose file is missing is left out (with a warning), so the
    reader degrades to what is installed instead of failing.
    """
    from collections import Counter

    from la import embeddings, reader

    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    folder = Path(config_path).parent
    out = {"version": config.get("version"), "tta": bool(config.get("tta")), "bank": None,
           "comparer": None, "prior": 0.0, "counts": {}}
    knn = config.get("knn")
    if knn and (folder / knn["bank"]).is_file():
        data = np.load(folder / knn["bank"], allow_pickle=False)
        embed = embeddings.embedder(knn.get("backbone", "yolo"), _model(Path(classifier_path)))
        out["bank"] = reader.NeighbourBank(embed, data["signs"], data["vectors"],
                                           weight=knn["weight"], temperature=knn["temperature"])
        if config.get("prior"):
            out["prior"], out["counts"] = float(config["prior"]), Counter(data["signs"].tolist())
    elif knn:
        print(f"Reader: neighbour bank {knn['bank']} missing, skipped", file=sys.stderr)
    comparer = config.get("comparer")
    if comparer and (folder / comparer["weights"]).is_file():
        from la.comparer import Comparer
        options = {k: v for k, v in comparer.items() if k != "weights"}
        out["comparer"] = Comparer.load(folder / comparer["weights"], device="cpu", **options)
    elif comparer:
        print(f"Reader: comparer {comparer['weights']} missing, skipped", file=sys.stderr)
    return out


def refinements(classifier: Path) -> dict | None:
    """The installed naming refinements, or None for the plain classifier."""
    if not READER_CONFIG.is_file():
        return None
    return _load_refinements(str(READER_CONFIG), READER_CONFIG.stat().st_mtime_ns, str(classifier.resolve()))


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


def warm_up() -> None:
    """Load every model once by reading HT13, so the first real request is fast."""
    try:
        ht13_predictions()
    except Exception as error:  # noqa: BLE001 - a failed warm-up only means a slower first request
        print(f"Model warm-up skipped: {error}", file=sys.stderr)


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
