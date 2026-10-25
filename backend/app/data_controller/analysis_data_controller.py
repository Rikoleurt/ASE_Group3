import sys
import time
from collections import Counter
from io import BytesIO

import numpy as np
from PIL import Image, UnidentifiedImageError

from backend.app import tablet_demo
from backend.app.model.analysis import AnalysisResult, DetectedSign

if str(tablet_demo.ROOT / "fraction-solver") not in sys.path:
    sys.path.insert(0, str(tablet_demo.ROOT / "fraction-solver"))  # as backend.app.reading does
from la import values  # noqa: E402


class AnalysisDataController:
    def analyze(self, image_bytes: bytes, filename: str | None = None) -> AnalysisResult | None:
        """Read the signs on an uploaded image; None if it is not an image.

        Raises FileNotFoundError or RuntimeError when no model can run.
        """
        try:
            image = Image.open(BytesIO(image_bytes))
            image.load()
            image = image.convert("RGB")
        except (UnidentifiedImageError, OSError):
            return None

        started = time.perf_counter()
        bgr = np.ascontiguousarray(np.asarray(image)[:, :, ::-1])  # the reader expects OpenCV's BGR
        read = tablet_demo.predictions_for(tablet_demo.read_image(bgr))
        classifier = tablet_demo.active_classifier()
        catalogue = tablet_demo.sign_catalogue(classifier) if classifier else {}
        signs = [_sign(prediction, catalogue) for prediction in read["predictions"]]
        best = max(signs, key=lambda sign: sign.confidence, default=None)
        return AnalysisResult(
            symbol_interpretation=best.label if best else "No signs found",
            confidence=round(best.confidence) if best else 0,
            time_taken=round(time.perf_counter() - started, 2),
            summary=_summary(signs, read["trained"]),
            width=read["width"],
            height=read["height"],
            trained=read["trained"],
            signs=signs,
        )


def _summary(signs: list[DetectedSign], trained: bool) -> str:
    if not trained:
        return (f"{len(signs)} objects found by a generic model: "
                "the Linear A sign reader is not installed (python scripts/fetch_models.py).")
    if not signs:
        return "No signs found on this image."
    roles = Counter(sign.role or "unknown" for sign in signs)
    parts = ", ".join(f"{count} {role}{'s' if count > 1 else ''}" for role, count in roles.most_common())
    return f"{len(signs)} sign{'s' if len(signs) > 1 else ''} found: {parts}."


def _sign(prediction: dict, catalogue: dict) -> DetectedSign:
    candidates = prediction.get("candidates") or []
    top = candidates[0] if candidates else None
    entry = catalogue.get(top["sign"], {}) if top else {}
    return DetectedSign(
        id=prediction["id"],
        sign=top["sign"] if top else None,
        label=prediction["label"],
        reading=entry.get("reading"),
        role=role_of(top["sign"], entry.get("reading"), top["roles"]) if top else None,
        confidence=prediction["confidence"],
        detection_confidence=prediction.get("detectionConfidence", prediction["confidence"]),
        box=prediction["box"],
        candidates=candidates,
        crop=prediction["imageUrl"],
        shape_guesses=prediction.get("shapeGuesses"),
    )


def role_of(sign: str | None, reading: str | None, roles: list[str]) -> str:
    """One role per sign. The catalogue lists every role a sign has had in the corpus
    (most syllabograms are also listed as logograms), so the sign itself decides."""
    if sign in values.KNOWN_VALUES or sign in values.OPEN_SIGNS:
        return "fraction"  # including combinations such as A717 (DD), catalogued as a syllabogram
    if reading:
        return "syllabogram" if reading.islower() else "logogram"  # ku, pa3 / VIN, qi OVIS
    for role in ("fraction", "transaction", "logogram", "syllabogram"):
        if role in roles:
            return role
    return "unknown"
