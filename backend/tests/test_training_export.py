"""Training export (#87): the JSON, the YOLO zip, and that only admins get either."""
import io
import json
import zipfile
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from mysql.connector import Error as DatabaseError

from backend.app import glyph_index
from backend.app.image_storage import store_image
from backend.app.main import app
from backend.app.model.correction import CorrectionExportSign, CorrectionExportTablet
from backend.app.routes.admin_routes import get_correction_controller, get_export_data_controller
from backend.tests.test_admin import logged_in
from backend.tests.test_history import png


def box(box_id, x, sign, origin="model", original=True, model_sign=None):
    geometry = {"x": x, "y": 0.1, "w": 0.1, "h": 0.2}
    return {"set_id": 0, "id": box_id, **geometry, "sign": sign, "origin": origin,
            **({f"original_{k}": v for k, v in geometry.items()} if original else
               {f"original_{k}": None for k in geometry}), "model_sign": model_sign if model_sign is not None else sign}


def copies(upload_key):
    return [
        {"id": 1, "owner_id": 7, "analysis_id": 12, "tablet_slug": None, "start": "model", "width": 1000, "height": 500,
         "version": 3, "updated_at": datetime(2026, 11, 18), "filename": "tablet.png", "storage_key": upload_key, "format": "PNG",
         "boxes": [box(1, 0.1, "AB81"), box(2, 0.3, "AB02", model_sign="AB59"), box(3, 0.5, None, "user", original=False)]},
        {"id": 2, "owner_id": 8, "analysis_id": None, "tablet_slug": "HT-1", "start": "scholar", "width": 1000, "height": 500,
         "version": 0, "updated_at": datetime(2026, 11, 18), "filename": None, "storage_key": None, "format": None,
         "boxes": [box(4, 0.2, "AB81", "scholar")]},
    ]


APPROVED = [CorrectionExportTablet(analysis_id=12, filename="tablet.png", width=1000, height=500, signs=[
    CorrectionExportSign(sign="AB02", xyxy=[300, 50, 400, 150], original_sign="AB59", model_version="v1", correction_id=9)])]


@pytest.fixture
def stores(monkeypatch, tmp_path):
    stored_key = store_image(png(), "PNG")
    tracing = tmp_path / "HT-1.png"
    tracing.write_bytes(png())
    monkeypatch.setattr(glyph_index, "tracing_path", lambda slug: tracing if slug == "HT-1" else None)
    exports, corrections = MagicMock(), MagicMock()
    exports.copies.return_value = copies(stored_key)
    corrections.export_approved.return_value = APPROVED
    app.dependency_overrides[get_export_data_controller] = lambda: exports
    app.dependency_overrides[get_correction_controller] = lambda: corrections
    yield exports, corrections
    app.dependency_overrides.clear()


@pytest.fixture
def admin(monkeypatch, stores):
    with logged_in(monkeypatch, admin=True) as client:
        yield client


def test_json_has_every_copy_in_pixels_with_where_each_box_came_from(admin):
    body = admin.get("/admin/export/corrections").json()
    first, tablet = body["copies"]
    assert {k: first[k] for k in ("copy_id", "source", "analysis_id", "width", "height", "image")} == {
        "copy_id": 1, "source": "analysis", "analysis_id": 12, "width": 1000, "height": 500, "image": "images/copy-1.png"}
    assert first["signs"] == [
        {"box_id": 1, "sign": "AB81", "xyxy": [100, 50, 200, 150], "origin": "model", "changed": False, "original_sign": "AB81"},
        {"box_id": 2, "sign": "AB02", "xyxy": [300, 50, 400, 150], "origin": "model", "changed": True, "original_sign": "AB59"},
        {"box_id": 3, "sign": None, "xyxy": [500, 50, 600, 150], "origin": "user", "changed": True, "original_sign": None},
    ]
    assert (tablet["source"], tablet["tablet"], tablet["start"]) == ("tablet", "HT-1", "scholar")
    assert body["label_corrections"][0]["signs"][0]["correction_id"] == 9


def test_yolo_zip_has_images_labels_and_classes(admin):
    response = admin.get("/admin/export/corrections.zip")
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["content-disposition"].startswith('attachment; filename="corrections-')
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert sorted(archive.namelist()) == ["classes.txt", "corrections.json", "images/copy-1.png", "images/copy-2.png",
                                          "labels/copy-1.txt", "labels/copy-2.txt"]
    assert archive.read("classes.txt").decode() == "AB02\nAB81\n"
    # The unnamed box has no class, so it is left out of the labels.
    assert archive.read("labels/copy-1.txt").decode().splitlines() == [
        "1 0.150000 0.200000 0.100000 0.200000", "0 0.350000 0.200000 0.100000 0.200000"]
    assert archive.read("images/copy-1.png") == png()
    manifest = json.loads(archive.read("corrections.json"))
    assert (manifest["missing_images"], manifest["unnamed_boxes_left_out"]) == ([], 1)


def test_copies_whose_image_is_gone_are_listed_not_zipped(admin, stores):
    exports, _ = stores
    exports.copies.return_value[0]["storage_key"] = "f" * 32 + ".png"
    archive = zipfile.ZipFile(io.BytesIO(admin.get("/admin/export/corrections.zip").content))
    assert "images/copy-1.png" not in archive.namelist()
    assert json.loads(archive.read("corrections.json"))["missing_images"] == [1]


def test_only_admins_export(monkeypatch, stores):
    monkeypatch.setenv("SIGN_REVIEWERS", "boss")
    with logged_in(monkeypatch, reviewer=True) as reviewer:
        assert reviewer.get("/admin/export/corrections").status_code == 403
        assert reviewer.get("/admin/export/corrections.zip").status_code == 403
    stores[0].copies.assert_not_called()


def test_storage_errors_are_503(admin, stores):
    stores[0].copies.side_effect = DatabaseError()
    assert admin.get("/admin/export/corrections").status_code == 503


def test_the_query_leaves_deleted_boxes_out(monkeypatch):
    from backend.app.training_export import ExportDataController
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchall.side_effect = [[{"id": 1}], [{"set_id": 1, "id": 5}]]
    monkeypatch.setattr("mysql.connector.connect", lambda **kwargs: connection)
    (copy,) = ExportDataController().copies()
    assert copy["boxes"] == [{"set_id": 1, "id": 5}]
    assert "deleted = FALSE" in cursor.execute.call_args_list[1].args[0]
