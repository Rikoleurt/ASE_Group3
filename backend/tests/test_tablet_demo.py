from base64 import b64decode
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


def test_predictions_endpoint_serializes_real_boxes_as_normalized_coordinates():
    from ultralytics.engine.results import Results

    result = Results(
        np.zeros((200, 100, 3), dtype=np.uint8),
        path=str(HT13_IMAGE),
        names={0: "object"},
        boxes=np.array([[10, 40, 40, 120, 0.75, 0]]),
    )
    with patch("backend.app.tablet_demo.ht13_result", return_value=result):
        with TestClient(app) as client:
            response = client.get("/tablet-demo/ht13/predictions")
    assert response.status_code == 200
    data = response.json()
    image_url = data['predictions'][0].pop('imageUrl')
    assert image_url.startswith('data:image/png;base64,')
    with Image.open(BytesIO(b64decode(image_url.split(',', 1)[1]))) as crop:
        assert crop.size == (30, 80)
    assert data == {
        "width": 100,
        "height": 200,
        "predictions": [{
            "id": 1,
            "label": "object",
            "confidence": 75.0,
            "box": {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4},
        }],
    }


def test_predictions_endpoint_preserves_empty_results():
    from ultralytics.engine.results import Results

    result = Results(
        np.zeros((200, 100, 3), dtype=np.uint8),
        path=str(HT13_IMAGE), names={0: "object"}, boxes=np.empty((0, 6)),
    )
    with patch("backend.app.tablet_demo.ht13_result", return_value=result):
        with TestClient(app) as client:
            response = client.get("/tablet-demo/ht13/predictions")
    assert response.status_code == 200
    assert response.json() == {"width": 100, "height": 200, "predictions": []}


def test_predictions_endpoint_reports_unavailable_model():
    with patch("backend.app.tablet_demo.ht13_result", side_effect=FileNotFoundError("weights")):
        with TestClient(app) as client:
            response = client.get("/tablet-demo/ht13/predictions")
    assert response.status_code == 503
    assert response.json() == {"detail": "HT13 predictions are unavailable."}
