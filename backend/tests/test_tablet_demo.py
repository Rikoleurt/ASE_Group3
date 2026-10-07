from io import BytesIO
from unittest.mock import patch
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from backend.app.main import app
from backend.app.tablet_demo import HT13_IMAGE, annotate_ht13, ht13_result


def test_ht13_endpoint_runs_pretrained_inference_without_database():
    # Exercise real local YOLO inference and Results.plot(), even with zero detections.
    with patch("mysql.connector.connect", side_effect=AssertionError("No DB in this demo")):
        with TestClient(app) as client:
            original = client.get("/tablet-demo/ht13?annotated=false")
            annotated = client.get("/tablet-demo/ht13")

    assert original.status_code == annotated.status_code == 200
    assert original.headers["content-type"] == "image/webp"
    assert original.content == HT13_IMAGE.read_bytes()
    assert annotated.headers["content-type"] == "image/png"
    with Image.open(BytesIO(original.content)) as image:
        source = np.array(image.convert("RGB"))
    with Image.open(BytesIO(annotated.content)) as image:
        rendered = np.array(image.convert("RGB"))
    assert rendered.shape == source.shape == (2253, 1367, 3)
    # No assertion about accuracy, box count or changed pixels: empty is valid.


def test_empty_predictions_do_not_add_synthetic_boxes():
    import cv2
    from ultralytics.engine.results import Results

    image = cv2.imread(str(HT13_IMAGE))
    empty = Results(image, path=str(HT13_IMAGE), names={0: "person"}, boxes=np.empty((0, 6)))
    with patch("backend.app.tablet_demo.ht13_result", return_value=empty):
        png = annotate_ht13()
    rendered = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert np.array_equal(rendered, image)


def test_missing_pretrained_weights_fail_instead_of_falling_back(monkeypatch, tmp_path):
    monkeypatch.setattr("backend.app.tablet_demo.YOLO_WEIGHTS", tmp_path / "missing.pt")
    with pytest.raises(FileNotFoundError, match="Pretrained yolo26n.pt"):
        ht13_result()
