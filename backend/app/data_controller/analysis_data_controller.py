import time
import sys
import json
from datetime import datetime, timezone
from collections import Counter
from io import BytesIO

import numpy as np
from PIL import Image, UnidentifiedImageError

from backend.app import tablet_demo
from backend.app.data_controller.data_controller import DataController
from backend.app.model.analysis import (AnalysisResult, AnalysisMetadata, AnalysisHistoryDetail,
                                        Box, DetectedSign, FractionTerm, Line)
from backend.app.model.analysis import Formula as FormulaModel, AnalysisComment
from backend.app.reading_pipeline.formula import Formula, Term, find_formulas, fmt
from backend.app.reading_pipeline.glyphs import glyph
from backend.app.reading_pipeline.lines import group_lines
from backend.app.reading_pipeline.transliterate import line_text, meaning

if str(tablet_demo.ROOT / "fraction-solver") not in sys.path:
    sys.path.insert(0, str(tablet_demo.ROOT / "fraction-solver"))  # as backend.app.reading does
from la import values  # noqa: E402


class AnalysisDataController(DataController):
    def save_analysis(self, user_id: int, filename: str, format: str, size_bytes: int,
                      result: AnalysisResult) -> AnalysisMetadata:
        """Store an immutable result snapshot, excluding uploaded pixel data."""
        created_at = datetime.now(timezone.utc)
        snapshot = result.model_dump(mode="json", exclude={"signs": {"__all__": {"crop"}}})
        with self.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "INSERT INTO analysis (user_id, created_at, filename, format, size_bytes, result_json) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (user_id, created_at.replace(tzinfo=None), filename, format, size_bytes, json.dumps(snapshot)),
                )
                analysis_id = cursor.lastrowid
            finally:
                cursor.close()
        return AnalysisMetadata(id=analysis_id, created_at=created_at, filename=filename,
                                format=format, size_bytes=size_bytes)

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
                    "SELECT id, created_at, filename, format, size_bytes, result_schema_version "
                    "FROM analysis WHERE user_id = %s" + clause +
                    " ORDER BY created_at DESC, id DESC LIMIT %s", tuple(params),
                )
                rows = cursor.fetchall()
            finally:
                cursor.close()
        return [AnalysisMetadata(**{**row, "created_at": row["created_at"].replace(tzinfo=timezone.utc)}) for row in rows]

    def get_analysis(self, user_id: int, analysis_id: int) -> AnalysisHistoryDetail | None:
        """A foreign record is indistinguishable from a missing record."""
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    "SELECT id, created_at, filename, format, size_bytes, result_schema_version, result_json "
                    "FROM analysis WHERE user_id = %s AND id = %s", (user_id, analysis_id),
                )
                row = cursor.fetchone()
            finally:
                cursor.close()
        if row is None:
            return None
        result = json.loads(row.pop("result_json"))
        return AnalysisHistoryDetail(**{**row, "created_at": row["created_at"].replace(tzinfo=timezone.utc)}, result=result)

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
        trained = read["trained"]
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
        return AnalysisResult(
            symbol_interpretation=" / ".join(line.text for line in lines) or _fallback(signs),
            confidence=round(sum(sign.confidence for sign in signs) / len(signs)) if signs else 0,
            time_taken=round(time.perf_counter() - started, 2),
            summary=_summary(signs, trained, formulas),
            width=read["width"],
            height=read["height"],
            trained=trained,
            signs=[sign for line in grouped for sign in line],
            lines=lines,
            formulas=[_formula(formula, by_id) for formula in formulas],
        )
    
    def _owns_analysis(self, cursor, user_id: int, analysis_id: int) -> bool:
        cursor.execute("SELECT 1 FROM analysis WHERE id = %s AND user_id = %s", (analysis_id, user_id))
        return cursor.fetchone() is not None

    def list_comments(self, user_id: int, analysis_id: int) -> list[AnalysisComment] | None:
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                if not self._owns_analysis(cursor, user_id, analysis_id):
                    return None
                cursor.execute(
                    "SELECT id, analysis_id, author_id, created_at, body FROM analysis_comment "
                    "WHERE analysis_id = %s ORDER BY created_at, id LIMIT 500", (analysis_id,),
                )
                rows = cursor.fetchall()
            finally:
                cursor.close()
        return [AnalysisComment(**{**r, "created_at": r["created_at"].replace(tzinfo=timezone.utc)}) for r in rows]

    def add_comment(self, user_id: int, analysis_id: int, body: str) -> AnalysisComment | None:
        created_at = datetime.now(timezone.utc).replace(tzinfo=None)
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                if not self._owns_analysis(cursor, user_id, analysis_id):
                    return None
                cursor.execute(
                    "INSERT INTO analysis_comment (analysis_id, author_id, created_at, body) VALUES (%s, %s, %s, %s)",
                    (analysis_id, user_id, created_at, body),
                )
                comment_id = cursor.lastrowid
                connection.commit()
            finally:
                cursor.close()
        return AnalysisComment(id=comment_id, analysis_id=analysis_id, author_id=user_id,
                            created_at=created_at.replace(tzinfo=timezone.utc), body=body)

    def delete_comment(self, user_id: int, comment_id: int) -> bool:
        with self.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute("DELETE FROM analysis_comment WHERE id = %s AND author_id = %s", (comment_id, user_id))
                deleted = cursor.rowcount > 0
                connection.commit()
            finally:
                cursor.close()
        return deleted


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
