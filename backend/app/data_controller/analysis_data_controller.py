import time
import sys
import json
from datetime import datetime, timezone
from collections import Counter
from io import BytesIO

import numpy as np
from PIL import Image, UnidentifiedImageError

from backend.app import tablet_demo
from backend.app.image_store import StoredImage
from backend.app.data_controller.data_controller import DataController
from backend.app.model.analysis import (AnalysisResult, AnalysisMetadata, AnalysisHistoryDetail,
                                        Box, DetectedSign, FractionTerm, Line)
from backend.app.model.analysis import Formula as FormulaModel
from backend.app.reading_pipeline.formula import Formula, Term, find_formulas, fmt
from backend.app.reading_pipeline.glyphs import glyph
from backend.app.reading_pipeline.lines import group_lines
from backend.app.reading_pipeline.transliterate import line_text, meaning

if str(tablet_demo.ROOT / "fraction-solver") not in sys.path:
    sys.path.insert(0, str(tablet_demo.ROOT / "fraction-solver"))  # as backend.app.reading does
from la import values  # noqa: E402


class ImageTooLargeError(ValueError):
    """The image declares more pixels than it is safe to decode."""


class AnalysisDataController(DataController):
    def save_analysis(self, user_id: int, filename: str, format: str, size_bytes: int,
                      result: AnalysisResult, image: StoredImage | None = None) -> AnalysisMetadata:
        """Store an immutable result snapshot, and the stored image's record when there is one.

        The snapshot leaves out the sign crops; the image itself is on disk (image_store),
        so both rows are written in one transaction and neither exists without the other.
        """
        created_at = datetime.now(timezone.utc)
        stamp = created_at.replace(tzinfo=None)
        snapshot = result.model_dump(mode="json", exclude={"signs": {"__all__": {"crop"}}})
        with self.connection() as connection:
            cursor = connection.cursor()
            try:
                image_id = None
                if image is not None:
                    cursor.execute(
                        "INSERT INTO uploaded_image (owner_id, storage_key, sha256, format, size_bytes, width, height, "
                        "created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (user_id, image.key, image.sha256, image.format, image.size_bytes, result.width, result.height,
                         stamp),
                    )
                    image_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO analysis (user_id, created_at, filename, format, size_bytes, result_json, image_id) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (user_id, stamp, filename, format, size_bytes, json.dumps(snapshot), image_id),
                )
                analysis_id = cursor.lastrowid
            finally:
                cursor.close()
        return AnalysisMetadata(id=analysis_id, created_at=created_at, filename=filename,
                                format=format, size_bytes=size_bytes, has_image=image is not None)

    def stored_image(self, user_id: int, analysis_id: int) -> tuple[str, str] | None:
        """The storage key and format of the image of the user's own analysis, or None."""
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    "SELECT i.storage_key, i.format FROM analysis a JOIN uploaded_image i ON i.id = a.image_id "
                    "WHERE a.user_id = %s AND a.id = %s", (user_id, analysis_id),
                )
                row = cursor.fetchone()
            finally:
                cursor.close()
        return (row["storage_key"], row["format"]) if row else None

    def list_analyses(self, user_id: int, limit: int,
                      before: tuple[datetime, int] | None = None) -> list[AnalysisMetadata]:
        """Read one extra row to determine whether another page exists."""
        clause = ""
        params = [user_id]
        if before:
            clause = " AND (created_at < %s OR (created_at = %s AND id < %s))"
            params.extend([before[0], before[0], before[1]])
        params.append(limit + 1)
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    "SELECT id, created_at, filename, format, size_bytes, result_schema_version, "
                    "image_id IS NOT NULL AS has_image FROM analysis WHERE user_id = %s" + clause +
                    " ORDER BY created_at DESC, id DESC LIMIT %s", tuple(params),
                )
                rows = cursor.fetchall()
            finally:
                cursor.close()
        return [AnalysisMetadata(**_metadata(row)) for row in rows]

    def get_analysis(self, user_id: int, analysis_id: int) -> AnalysisHistoryDetail | None:
        """A foreign record is indistinguishable from a missing record."""
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    "SELECT id, created_at, filename, format, size_bytes, result_schema_version, result_json, "
                    "image_id IS NOT NULL AS has_image FROM analysis WHERE user_id = %s AND id = %s",
                    (user_id, analysis_id),
                )
                row = cursor.fetchone()
            finally:
                cursor.close()
        if row is None:
            return None
        result = json.loads(row.pop("result_json"))
        return AnalysisHistoryDetail(**_metadata(row), result=result)

    def analyze(self, image_bytes: bytes, filename: str | None = None) -> AnalysisResult | None:
        """Read the signs on an uploaded image; None if it is not an image.

        Raises ImageTooLargeError when the image declares more than
        Image.MAX_IMAGE_PIXELS pixels, and FileNotFoundError or RuntimeError
        when no model can run.
        """
        try:
            image = Image.open(BytesIO(image_bytes))
            # Pillow only warns between 1x and 2x MAX_IMAGE_PIXELS, so check before decoding.
            if image.width * image.height > Image.MAX_IMAGE_PIXELS:
                raise ImageTooLargeError
            image.load()
            image = image.convert("RGB")
        except Image.DecompressionBombError as error:
            raise ImageTooLargeError from error
        except (UnidentifiedImageError, OSError):
            return None

        started = time.perf_counter()
        bgr = np.ascontiguousarray(np.asarray(image)[:, :, ::-1])  # the reader expects OpenCV's BGR
        read = tablet_demo.predictions_for(tablet_demo.read_image(bgr))
        classifier = tablet_demo.active_classifier()
        catalogue = tablet_demo.sign_catalogue(classifier) if classifier else {}
        signs = [_sign(prediction, catalogue) for prediction in read["predictions"]]
        trained = read["trained"]
        return AnalysisResult(
            **read_signs(signs, trained),
            confidence=round(sum(sign.confidence for sign in signs) / len(signs)) if signs else 0,
            time_taken=round(time.perf_counter() - started, 2),
            width=read["width"],
            height=read["height"],
            trained=trained,
            model_version=tablet_demo.model_version(),
        )


def read_signs(signs: list[DetectedSign], trained: bool = True) -> dict:
    """Reading order, lines, transliteration and fraction formulas for a tablet's signs.

    Used for the model's signs and for corrected boxes (#83). Fills in each sign's line,
    order and meaning, and returns the AnalysisResult fields that depend on the signs."""
    # Reading order, transliteration and fractions only mean something for Linear A signs.
    grouped = group_lines(signs) if trained else [signs] if signs else []
    for number, line in enumerate(grouped):
        for position, sign in enumerate(line):
            sign.line, sign.order = number, position
    lines = [_line(number, line) for number, line in enumerate(grouped)] if trained else []
    formulas = find_formulas(grouped) if trained else []
    by_id = {sign.id: sign for sign in signs}
    if trained:
        for sign in signs:
            sign.meaning = meaning(sign)
        for formula in formulas:
            word = "grand total (PO-TO-KU-RO)" if formula.kind == "grand_total" else "total (KU-RO)"
            for sign_id in formula.marker_ids:
                by_id[sign_id].meaning = word
    return dict(
        symbol_interpretation=" / ".join(line.text for line in lines) or _fallback(signs),
        summary=_summary(signs, trained, formulas),
        signs=[sign for line in grouped for sign in line],
        lines=lines,
        formulas=[_formula(formula, by_id) for formula in formulas],
    )


def describe_sign(sign: str | None, catalogue: dict) -> dict:
    """Label, reading, role and glyph of a sign ID, as the reader names it; for corrected boxes."""
    if sign is None:
        return dict(sign=None, label="Unnamed sign", reading=None, role="unknown", glyph=None)
    entry = catalogue.get(sign, {})
    return dict(sign=sign, label=entry.get("name") or sign, reading=entry.get("reading"),
                role=role_of(sign, entry.get("reading"), entry.get("roles") or []), glyph=glyph(sign))


def _metadata(row: dict) -> dict:
    """A history row as AnalysisMetadata fields: UTC time, and MySQL's 0/1 as a bool."""
    return {**row, "created_at": row["created_at"].replace(tzinfo=timezone.utc), "has_image": bool(row.get("has_image"))}


def _fallback(signs: list[DetectedSign]) -> str:
    return ", ".join(sign.label for sign in signs) or "No signs found"


def _line(number: int, line: list[DetectedSign]) -> Line:
    text, gloss = line_text(line)
    return Line(index=number, sign_ids=[sign.id for sign in line], text=text, gloss=gloss)


def _formula(formula: Formula, by_id: dict[int, DetectedSign]) -> FormulaModel:
    boxes = [by_id[sign_id].box for sign_id in formula.sign_ids]
    left, top = min(b.x for b in boxes), min(b.y for b in boxes)
    right, bottom = max(b.x + b.w for b in boxes), max(b.y + b.h for b in boxes)
    total = formula.total_value
    return FormulaModel(
        kind=formula.kind,
        lines=formula.lines,
        sign_ids=formula.sign_ids,
        marker_ids=formula.marker_ids,
        box=Box(x=left, y=top, w=right - left, h=bottom - top),
        entries=[_term(term) for term in formula.entries],
        total=[_term(term) for term in formula.total],
        entries_sum=fmt(formula.entries_sum),
        total_value=fmt(total) if formula.kind != "group" else None,
        verdict=formula.verdict,
        difference=fmt(formula.difference) if formula.difference is not None else None,
        carried=formula.carried,
        tentative=formula.tentative,
        steps=formula.steps(),
        note=formula.note(),
    )


def _term(term: Term) -> FractionTerm:
    return FractionTerm(id=term.id, sign=term.sign, label=term.label, glyph=glyph(term.sign),
                        value=fmt(term.value), tentative=term.tentative, line=term.line)


def _summary(signs: list[DetectedSign], trained: bool, formulas: list[Formula]) -> str:
    if not trained:
        return (f"{len(signs)} objects found by a generic model: "
                "the Linear A sign reader is not installed (python scripts/fetch_models.py).")
    if not signs:
        return "No signs found on this image."
    roles = Counter(sign.role or "unknown" for sign in signs)
    parts = ", ".join(f"{count} {role}{'s' if count > 1 else ''}" for role, count in roles.most_common())
    found = f"{len(signs)} sign{'s' if len(signs) > 1 else ''} found: {parts}."
    checks = {
        "balances": "the fractions balance",
        "mismatch": "the fractions are off by {difference}",
        "incomplete": "a fraction sign has no agreed value, so it cannot be checked",
        "no_fractions": "it has no fractions to check",
    }
    for formula in formulas:
        if formula.kind != "group":
            check = checks[formula.verdict].format(difference=fmt(formula.difference))
            found += f" KU-RO total found: {check}."
    return found


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
        glyph=glyph(top["sign"]) if top else None,
    )


def role_of(sign: str | None, reading: str | None, roles: list[str]) -> str:
    """One role per sign. The catalogue lists every role a sign has had in the corpus
    (most syllabograms are also listed as logograms), so the sign itself decides."""
    if sign in values.KNOWN_VALUES or sign in values.OPEN_SIGNS:
        return "fraction"  # including combinations such as A717 (DD), catalogued as a syllabogram
    if reading:
        # ku, pa3 / VIN; a mixed reading (ni FIC) is a syllable where the catalogue allows it.
        syllable = any(word.islower() for word in reading.split())
        logogram = any(not word.islower() for word in reading.split())
        return "syllabogram" if syllable and (not logogram or "syllabogram" in roles) else "logogram"
    for role in ("fraction", "transaction", "logogram", "syllabogram"):
        if role in roles:
            return role
    return "unknown"
