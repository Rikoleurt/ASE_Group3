"""The readers a benchmark can compare, behind one small interface.

A reader may detect (find sign boxes on a tablet drawing), identify (name the
sign in a given box), or both. The benchmark scores each stage it supports:

* `detect(image)` -> list of (box, confidence, labels, probs), boxes in pixels.
* `identify(ink, boxes)` -> per box, a list of (sign ID, probability), best first.

Kinds are registered in `KINDS` and built from `benchmark/models.yaml` entries,
so a new technique only needs a class and a line there. Ultralytics is imported
lazily: the metrics and their tests do not need it.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import numpy as np
from la import augment, reader
from la.shapes import CANON, load_mask, normalise
from la.signcrops import identified, sign_id

DETECT_CONF = 0.01        # low floor so AP and the confidence sweep see every useful box
NAME_CONF = 0.05          # boxes below the lowest sweep threshold are never scored, so not named
TOP = 5
ROLE_NAMES = ("sign", "syllabogram", "logogram", "fraction", "transaction")


def _yolo(path: str | Path):
    from ultralytics import YOLO
    return YOLO(str(path))


class Reader:
    """Base reader: subclasses set `detects` / `identifies` and implement the stages."""
    detects = False
    identifies = False

    def __init__(self, name: str, imgsz: int = 1024, device: str = "cpu", **_):
        self.name, self.imgsz, self.device = name, imgsz, device

    def detect(self, image: Path) -> list[tuple[tuple, float, list[str], list[float]]]:
        raise NotImplementedError

    def identify(self, ink: np.ndarray, boxes: list[tuple]) -> list[list[tuple[str, float]]]:
        raise NotImplementedError

    def weights(self) -> list[Path]:
        return []

    def time_app(self, image: Path, conf: float = 0.25) -> float:
        """Seconds to read one tablet the way the app does (detect at `conf`, name the boxes)."""
        started = time.perf_counter()
        self._app_read(image, conf)
        return time.perf_counter() - started

    def _app_read(self, image: Path, conf: float) -> None:
        if self.detects:
            boxes = [b for b, c, _, _ in self.detect(image) if c >= conf]
            if self.identifies and boxes and not isinstance(self, OneStage):
                self.identify(load_mask(image), boxes)
        elif self.identifies:
            self.identify(load_mask(image), [])


class _Detector(Reader):
    detects = True

    def __init__(self, name: str, detector: str, **kw):
        super().__init__(name, **kw)
        self.detector_path = Path(detector)
        self.detector = _yolo(detector)

    def weights(self) -> list[Path]:
        return [self.detector_path]

    def _raw(self, image: Path, conf: float = DETECT_CONF):
        result = self.detector.predict(str(image), imgsz=self.imgsz, conf=conf, device=self.device,
                                       verbose=False, max_det=1000)[0]
        return result, [tuple(b) for b in result.boxes.xyxy.tolist()], result.boxes.conf.tolist()


class Generic(_Detector):
    """A detector that does not know Linear A signs (e.g. the stock yolo26n.pt): boxes only."""

    def detect(self, image):
        _, boxes, confs = self._raw(image)
        return [(b, c, [], []) for b, c in zip(boxes, confs)]


class OneStage(_Detector):
    """An identity detector: one class per sign ID, so it names what it finds."""
    def detect(self, image):
        result, boxes, confs = self._raw(image)
        out = []
        for b, c, k in zip(boxes, confs, result.boxes.cls.tolist()):
            name = result.names[int(k)]
            sign = None if name in ROLE_NAMES else name.split(" ")[0]
            out.append((b, c, [sign] if sign else [], [c] if sign else []))
        return out


class TwoStage(_Detector):
    """The app's reader: a one-class detector, then a classifier on each crop."""
    identifies = True

    def __init__(self, name: str, detector: str, classifier: str, **kw):
        super().__init__(name, detector, **kw)
        self.classifier_path = Path(classifier)
        self.classifier = _yolo(classifier)

    def weights(self):
        return [self.detector_path, self.classifier_path]

    def detect(self, image):
        _, boxes, confs = self._raw(image)
        named = [i for i, c in enumerate(confs) if c >= NAME_CONF]
        tops = self.identify(load_mask(image), [boxes[i] for i in named]) if named else []
        labels: dict[int, list[tuple[str, float]]] = dict(zip(named, tops))
        return [(b, c, [s for s, _ in labels.get(i, [])], [p for _, p in labels.get(i, [])])
                for i, (b, c) in enumerate(zip(boxes, confs))]

    def identify(self, ink, boxes):
        return reader.name_boxes(self.classifier, ink, boxes, top=TOP, device=self.device)


class ShapeKNN(Reader):
    """Classical baseline, no training (FINDINGS.md section 4): nearest train crops by mask overlap.

    Each crop is cut exactly like the classifier's (`augment.square_crop`), then
    trimmed, scaled and centred (`la.shapes.normalise`). The score of a sign is
    its best IoU with any train attestation; the scores are reported as
    "probabilities" so the same metrics apply, though they are not calibrated.
    """
    identifies = True

    def __init__(self, name: str, dataset: Path, size: int = 64, **kw):
        super().__init__(name, **kw)
        self.size = size
        signs, vectors = [], []
        for tablet in _annotations(dataset):
            if tablet["split"] != "train":
                continue
            ink = load_mask(dataset / tablet["image"])
            for s in identified(tablet):
                signs.append(sign_id(s))
                vectors.append(self._vector(ink, s["xyxy"]))
        self.signs = np.array(signs)
        self.reference = np.stack(vectors) if vectors else np.zeros((0, size * size), np.float32)
        self.reference_ink = self.reference.sum(axis=1)
        self.classes = sorted(set(signs))
        self.members = {c: np.flatnonzero(self.signs == c) for c in self.classes}

    def _vector(self, ink, box) -> np.ndarray:
        crop = augment.square_crop(ink, tuple(box)) < 128
        mask = normalise(crop, size=CANON)
        small = mask.reshape(self.size, CANON // self.size, self.size, CANON // self.size).mean(axis=(1, 3)) > 0.25
        return small.ravel().astype(np.float32)

    def identify(self, ink, boxes):
        if not boxes or not len(self.reference):
            return [[] for _ in boxes]
        query = np.stack([self._vector(ink, b) for b in boxes])
        inter = query @ self.reference.T
        union = query.sum(axis=1)[:, None] + self.reference_ink[None, :] - inter
        overlap = np.where(union > 0, inter / np.maximum(union, 1e-9), 0.0)
        out = []
        for row in overlap:
            best = sorted(((float(row[m].max()), c) for c, m in self.members.items()), reverse=True)[:TOP]
            out.append([(c, s) for s, c in best])
        return out


_ANNOTATIONS: dict[Path, list[dict]] = {}


def _annotations(dataset: Path) -> list[dict]:
    import json
    dataset = Path(dataset)
    if dataset not in _ANNOTATIONS:
        _ANNOTATIONS[dataset] = json.loads((dataset / "annotations.json").read_text(encoding="utf-8"))
    return _ANNOTATIONS[dataset]


KINDS: dict[str, Callable[..., Reader]] = {
    "generic": Generic,
    "one_stage": OneStage,
    "two_stage": TwoStage,
    "shape_knn": ShapeKNN,
}


def build(entry: dict, root: Path, dataset: Path, device: str = "cpu") -> Reader:
    """A reader from one `models.yaml` entry; relative weight paths are taken from the repo root."""
    entry = dict(entry)
    kind = entry.pop("kind")
    if kind not in KINDS:
        raise ValueError(f"unknown reader kind {kind!r}; known: {sorted(KINDS)}")
    for key in ("detector", "classifier"):
        if key in entry:
            path = Path(entry[key])
            entry[key] = str(path if path.is_absolute() else root / path)
    entry.pop("description", None)
    entry.pop("train_run", None)
    return KINDS[kind](dataset=dataset, device=device, **entry)
