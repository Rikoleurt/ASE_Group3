"""Corrections as training data (#87): every corrected copy's boxes, plus #73's approved labels.

Two forms, both for admins:
- JSON, shaped like the training annotations (la.signboxes): per image its size and each
  sign's ID and pixel box (x0, y0, x1, y1), with where the box came from;
- a YOLO zip: images/, labels/ (one line per named box: class cx cy w h, as fractions),
  classes.txt, and the same JSON as corrections.json.

Boxes without a sign are left out of the YOLO labels (there is no class to give them) but kept
in the JSON, with sign null, so nothing the users drew is lost.
"""
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from backend.app import glyph_index, image_store
from backend.app.box_edits import GEOMETRY, same, state
from backend.app.data_controller.data_controller import DataController


class ExportDataController(DataController):
    def copies(self) -> list[dict]:
        """Every corrected copy with its image key, and its boxes that are not deleted."""
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    "SELECT s.id, s.owner_id, s.analysis_id, s.tablet_slug, s.start, s.width, s.height, s.version, "
                    "s.updated_at, a.filename, i.storage_key, i.format FROM box_set s "
                    "LEFT JOIN analysis a ON a.id = s.analysis_id LEFT JOIN uploaded_image i ON i.id = a.image_id "
                    "ORDER BY s.id")
                copies = cursor.fetchall()
                cursor.execute(
                    "SELECT set_id, id, x, y, w, h, sign, origin, original_x, original_y, original_w, original_h, "
                    "model_sign FROM box WHERE deleted = FALSE ORDER BY set_id, id")
                boxes = cursor.fetchall()
            finally:
                cursor.close()
        by_copy: dict[int, list[dict]] = {}
        for box in boxes:
            by_copy.setdefault(box["set_id"], []).append(box)
        for copy in copies:
            copy["boxes"] = by_copy.get(copy["id"], [])
        return copies


def _xyxy(box: dict, width: int, height: int) -> list[int]:
    return [round(box["x"] * width), round(box["y"] * height),
            round((box["x"] + box["w"]) * width), round((box["y"] + box["h"]) * height)]


def _changed(box: dict) -> bool:
    if box["original_x"] is None:
        return True
    original = state({name: box[f"original_{name}"] for name in GEOMETRY}, box["model_sign"])
    return not same(original, state(box, box["sign"]))


def _image_name(copy: dict) -> str:
    extension = image_store.EXTENSIONS.get(copy["format"] or "", ".png")
    return f"copy-{copy['id']}{extension}"


def corrections(copies: list[dict], label_corrections: list) -> dict:
    """The JSON export."""
    exported = []
    for copy in copies:
        exported.append({
            "copy_id": copy["id"],
            "owner_id": copy["owner_id"],
            "source": "analysis" if copy["analysis_id"] is not None else "tablet",
            "analysis_id": copy["analysis_id"],
            "filename": copy["filename"],
            "tablet": copy["tablet_slug"],
            "start": copy["start"],
            "version": copy["version"],
            "width": copy["width"],
            "height": copy["height"],
            "image": f"images/{_image_name(copy)}",
            "signs": [{"box_id": box["id"], "sign": box["sign"], "xyxy": _xyxy(box, copy["width"], copy["height"]),
                       "origin": box["origin"], "changed": _changed(box), "original_sign": box["model_sign"]}
                      for box in copy["boxes"]],
        })
    return {
        "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "copies": exported,
        "label_corrections": [item.model_dump(mode="json") for item in label_corrections],
    }


def _image_path(copy: dict) -> Path | None:
    if copy["tablet_slug"] is not None:
        try:
            return glyph_index.tracing_path(copy["tablet_slug"])
        except glyph_index.CorpusMissing:
            return None
    if copy["storage_key"] is None:
        return None
    return image_store.find(copy["storage_key"], copy["format"])


def yolo_zip(copies: list[dict], label_corrections: list) -> bytes:
    """The YOLO zip. Copies whose image is missing on this server are listed in corrections.json
    under "missing_images" and left out of images/ and labels/."""
    data = corrections(copies, label_corrections)
    classes = sorted({box["sign"] for copy in copies for box in copy["boxes"] if box["sign"]})
    index = {sign: number for number, sign in enumerate(classes)}
    missing = []
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for copy in copies:
            path = _image_path(copy)
            if path is None:
                missing.append(copy["id"])
                continue
            name = _image_name(copy)
            archive.write(path, f"images/{name}")
            lines = [f"{index[box['sign']]} {box['x'] + box['w'] / 2:.6f} {box['y'] + box['h'] / 2:.6f} "
                     f"{box['w']:.6f} {box['h']:.6f}" for box in copy["boxes"] if box["sign"]]
            archive.writestr(f"labels/{Path(name).stem}.txt", "\n".join(lines) + ("\n" if lines else ""))
        archive.writestr("classes.txt", "\n".join(classes) + "\n")
        data["missing_images"] = missing
        data["unnamed_boxes_left_out"] = sum(1 for copy in copies for box in copy["boxes"] if not box["sign"])
        archive.writestr("corrections.json", json.dumps(data, indent=2, ensure_ascii=False))
    return buffer.getvalue()
