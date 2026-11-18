import json
import re
from datetime import datetime, timezone
from typing import NamedTuple

from backend.app import tablet_demo
from backend.app.data_controller.data_controller import DataController
from backend.app.model.correction import (CatalogueSign, CorrectionCreate, CorrectionExportSign,
                                          CorrectionExportTablet, SignCorrection)
from backend.app.reading_pipeline.glyphs import _index, _key, glyph

COLUMNS = ("id, analysis_id, sign_id, created_at, box_x, box_y, box_w, box_h, original_sign, original_label, "
           "original_confidence, model_version, proposed_sign, uncertain, note, status")


class SavedSign(NamedTuple):
    """A detected sign as its analysis was saved, with what a correction records about the reading."""
    sign: dict
    model_version: str
    trained: bool
    width: int
    height: int


class ReviewConflict(Exception):
    """The correction was already reviewed."""


class OwnCorrection(Exception):
    """Reviewers cannot decide on their own corrections."""


def sign_key(sign: str) -> str:
    """One key per sign however it is written: AB01, ab001 and AB1 are all AB1."""
    sign = re.sub(r"^(ab|a)(?=\d)", lambda prefix: prefix.group().upper(), sign.strip(), flags=re.IGNORECASE)
    return _key(sign) or sign


def _sigla(key: str) -> str:
    """The dataset's spelling of a sign key: AB signs have two digits (AB1 -> AB01), A signs as they are."""
    return re.sub(r"^AB(\d)(?!\d)", r"AB0\1", key)


def _natural(sign: CatalogueSign) -> list:
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", sign.sign)]


def catalogue() -> list[CatalogueSign]:
    """Signs a correction may propose: the classifier's classes, plus every Unicode Linear A sign."""
    classifier = tablet_demo.active_classifier()
    named = tablet_demo.sign_catalogue(classifier) if classifier else {}
    signs = {sign_key(sign): CatalogueSign(sign=sign, name=entry.get("name") or sign, glyph=glyph(sign))
             for sign, entry in named.items() if sign != "unidentified"}
    for key, character in _index().items():
        signs.setdefault(key, CatalogueSign(sign=_sigla(key), name=_sigla(key), glyph=character))
    return sorted(signs.values(), key=_natural)


def catalogue_sign(proposed: str) -> str | None:
    """The catalogue's own spelling of `proposed` (AB01, ab001 and AB1 are one sign), or None."""
    key = sign_key(proposed)
    return next((sign.sign for sign in catalogue() if sign_key(sign.sign) == key), None)


def _correction(row: dict) -> SignCorrection:
    return SignCorrection(
        **{name: row[name] for name in ("id", "analysis_id", "sign_id", "original_sign", "original_label",
                                        "original_confidence", "model_version", "proposed_sign", "note", "status")},
        created_at=row["created_at"].replace(tzinfo=timezone.utc),
        box={"x": row["box_x"], "y": row["box_y"], "w": row["box_w"], "h": row["box_h"]},
        uncertain=bool(row["uncertain"]),
    )


def _xyxy(row: dict) -> list[int]:
    width, height = row["image_width"], row["image_height"]
    return [round(row["box_x"] * width), round(row["box_y"] * height),
            round((row["box_x"] + row["box_w"]) * width), round((row["box_y"] + row["box_h"]) * height)]


class CorrectionDataController(DataController):
    def detected_sign(self, user_id: int, analysis_id: int, sign_id: int) -> SavedSign | None:
        """The sign as the model saved it in the user's own analysis; None if there is no such sign."""
        with self.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute("SELECT result_json FROM analysis WHERE user_id = %s AND id = %s",
                               (user_id, analysis_id))
                row = cursor.fetchone()
            finally:
                cursor.close()
        if row is None:
            return None
        result = json.loads(row[0])
        sign = next((sign for sign in result.get("signs", []) if sign.get("id") == sign_id), None)
        if sign is None:
            return None
        return SavedSign(sign, result.get("model_version") or "unknown", bool(result.get("trained")),
                         result["width"], result["height"])

    def create(self, user_id: int, analysis_id: int, request: CorrectionCreate, saved: SavedSign,
               proposed_sign: str | None) -> SignCorrection:
        """Store one submission; earlier ones for the same sign are kept for the reviewer to compare."""
        created_at = datetime.now(timezone.utc)
        sign, box = saved.sign, saved.sign["box"]
        with self.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "INSERT INTO sign_correction (analysis_id, author_id, created_at, sign_id, box_x, box_y, box_w, "
                    "box_h, original_sign, original_label, original_confidence, model_version, image_width, "
                    "image_height, proposed_sign, uncertain, note) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (analysis_id, user_id, created_at.replace(tzinfo=None), request.sign_id, box["x"], box["y"],
                     box["w"], box["h"], sign.get("sign"), sign["label"], sign["confidence"], saved.model_version,
                     saved.width, saved.height, proposed_sign, request.uncertain, request.note),
                )
                correction_id = cursor.lastrowid
            finally:
                cursor.close()
        return SignCorrection(id=correction_id, analysis_id=analysis_id, sign_id=request.sign_id,
                              created_at=created_at, box=box, original_sign=sign.get("sign"),
                              original_label=sign["label"], original_confidence=sign["confidence"],
                              model_version=saved.model_version, proposed_sign=proposed_sign,
                              uncertain=request.uncertain, note=request.note, status="pending")

    def list_for_analysis(self, user_id: int, analysis_id: int) -> list[SignCorrection]:
        """The user's own corrections of one analysis, oldest first."""
        return self._select(f"SELECT {COLUMNS} FROM sign_correction WHERE author_id = %s AND analysis_id = %s "
                            "ORDER BY created_at, id", (user_id, analysis_id))

    def list_by_status(self, status: str, limit: int) -> list[SignCorrection]:
        """The review queue, oldest first so nothing waits forever."""
        return self._select(f"SELECT {COLUMNS} FROM sign_correction WHERE status = %s "
                            "ORDER BY created_at, id LIMIT %s", (status, limit))

    def review(self, correction_id: int, reviewer_id: int, decision: str) -> SignCorrection | None:
        """Approve or reject someone else's pending correction; None if it does not exist."""
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    "UPDATE sign_correction SET status = %s, reviewer_id = %s, reviewed_at = %s "
                    "WHERE id = %s AND status = 'pending' AND author_id <> %s",
                    (decision, reviewer_id, datetime.now(timezone.utc).replace(tzinfo=None), correction_id,
                     reviewer_id),
                )
                updated = cursor.rowcount
                cursor.execute(f"SELECT {COLUMNS}, author_id FROM sign_correction WHERE id = %s", (correction_id,))
                row = cursor.fetchone()
            finally:
                cursor.close()
        if row is None:
            return None
        if not updated:
            raise OwnCorrection() if row["author_id"] == reviewer_id else ReviewConflict()
        return _correction(row)

    def export_approved(self) -> list[CorrectionExportTablet]:
        """Approved replacement signs, grouped by analysis; uncertainty flags carry no label to train on."""
        rows = self._rows(
            "SELECT c.id, c.analysis_id, a.filename, c.box_x, c.box_y, c.box_w, c.box_h, c.image_width, "
            "c.image_height, c.original_sign, c.model_version, c.proposed_sign FROM sign_correction c "
            "JOIN analysis a ON a.id = c.analysis_id "
            "WHERE c.status = 'approved' AND c.proposed_sign IS NOT NULL ORDER BY c.analysis_id, c.id", ())
        tablets: dict[int, CorrectionExportTablet] = {}
        for row in rows:
            tablet = tablets.setdefault(row["analysis_id"], CorrectionExportTablet(
                analysis_id=row["analysis_id"], filename=row["filename"], width=row["image_width"],
                height=row["image_height"], signs=[]))
            tablet.signs.append(CorrectionExportSign(
                sign=row["proposed_sign"], xyxy=_xyxy(row), original_sign=row["original_sign"],
                model_version=row["model_version"], correction_id=row["id"],
            ))
        return list(tablets.values())

    def _select(self, query: str, params: tuple) -> list[SignCorrection]:
        return [_correction(row) for row in self._rows(query, params)]

    def _rows(self, query: str, params: tuple) -> list[dict]:
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(query, params)
                return cursor.fetchall()
            finally:
                cursor.close()
