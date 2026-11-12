import json
from base64 import b64decode
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from ultralytics.engine.results import Results
import cv2
from backend.app.main import app
from backend.app.tablet_demo import HT13_IMAGE, SIGN_IMGSZ, active_weights, annotate_ht13, ht13_result


@pytest.fixture(autouse=True)
def no_trained_detector(monkeypatch, tmp_path):
    # Tests describe the baseline unless they opt in, even where trained weights exist locally.
    monkeypatch.setattr("backend.app.tablet_demo.SIGN_WEIGHTS", tmp_path / "missing-signs.pt")
    monkeypatch.setattr("backend.app.tablet_demo.CLASSIFIER_WEIGHTS", tmp_path / "missing-classifier.pt")


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
        "trained": False,
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
    assert response.json() == {"width": 100, "height": 200, "trained": False, "predictions": []}


def test_trained_sign_weights_are_preferred_when_present(monkeypatch, tmp_path):
    trained = tmp_path / "linear_a_signs.pt"
    monkeypatch.setattr("backend.app.tablet_demo.SIGN_WEIGHTS", trained)
    assert active_weights()[2] is False
    trained.write_bytes(b"weights")
    assert active_weights() == (trained, SIGN_IMGSZ, True)


def test_only_fraction_boxes_from_the_trained_detector_get_shape_guesses(monkeypatch, tmp_path):
    from ultralytics.engine.results import Results

    trained = tmp_path / "linear_a_signs.pt"
    trained.write_bytes(b"weights")
    monkeypatch.setattr("backend.app.tablet_demo.SIGN_WEIGHTS", trained)
    image = np.full((200, 100, 3), 255, dtype=np.uint8)
    image[50:90, 20:30] = 0
    result = Results(image, path=str(HT13_IMAGE), names={0: "syllabogram", 2: "fraction"},
                     boxes=np.array([[10, 40, 40, 120, 0.9, 2], [50, 40, 90, 120, 0.8, 0]]))
    guesses = [{"sign": "A707", "label": "J", "distance": 4.0}]
    with patch("backend.app.tablet_demo.ht13_result", return_value=result), \
         patch("backend.app.reading.identify_mask", return_value=guesses) as identify:
        with TestClient(app) as client:
            data = client.get("/tablet-demo/ht13/predictions").json()
    assert data["trained"] is True
    fraction, syllabogram = data["predictions"]
    assert fraction["shapeGuesses"] == guesses
    assert "shapeGuesses" not in syllabogram
    identify.assert_called_once()


def test_predictions_endpoint_reports_unavailable_model():
    with patch("backend.app.tablet_demo.ht13_result", side_effect=FileNotFoundError("weights")):
        with TestClient(app) as client:
            response = client.get("/tablet-demo/ht13/predictions")
    assert response.status_code == 503
    assert response.json() == {"detail": "HT13 predictions are unavailable."}


@pytest.mark.parametrize("endpoint", ["/tablet-demo/ht13", "/tablet-demo/ht13/predictions"])
def test_prediction_routes_forward_confidence_and_handle_missing_weights(endpoint):
    with patch("backend.app.tablet_demo.ht13_result", side_effect=FileNotFoundError("weights")) as predict:
        with TestClient(app) as client:
            response = client.get(endpoint, params={"confidence": 0.1})
    assert response.status_code == 503
    assert predict.call_args.kwargs["confidence"] == 0.1


@pytest.mark.parametrize("endpoint", ["/tablet-demo/ht13", "/tablet-demo/ht13/predictions"])
@pytest.mark.parametrize("confidence", [0, -0.1, 1.1, "nan", "invalid"])
def test_prediction_routes_reject_invalid_confidence(endpoint, confidence):
    with patch("backend.app.tablet_demo.ht13_result") as predict:
        with TestClient(app) as client:
            response = client.get(endpoint, params={"confidence": confidence})
    assert response.status_code == 422
    predict.assert_not_called()


MODELS = Path(__file__).resolve().parents[2] / "models"


@pytest.mark.skipif(not (MODELS / "linear_a_signs.pt").is_file(), reason="trained weights are not installed")
def test_ht13_trained_model_predicts_and_reuses_weights_without_database(monkeypatch):
    from backend.app import tablet_demo

    weights = MODELS / "linear_a_signs.pt"
    classifier = MODELS / "linear_a_classifier.pt"
    monkeypatch.setattr(tablet_demo, "SIGN_WEIGHTS", weights)
    monkeypatch.setattr(tablet_demo, "CLASSIFIER_WEIGHTS", classifier)
    tablet_demo._load_model.cache_clear()
    with patch("mysql.connector.connect", side_effect=AssertionError("No DB for inference")),          patch.object(tablet_demo, "YOLO", wraps=tablet_demo.YOLO) as load:
        with TestClient(app) as client:
            response = client.get("/tablet-demo/ht13/predictions")
            annotated = client.get("/tablet-demo/ht13")
        loaded = sorted(call.args[0] for call in load.call_args_list)
        assert loaded == sorted(str(w.resolve()) for w in (weights, classifier) if w.is_file())

    assert response.status_code == annotated.status_code == 200
    data = response.json()
    assert data["trained"] is True
    assert (data["width"], data["height"]) == (1367, 2253)
    assert data["predictions"]  # Smoke test of the shipped checkpoint on HT13.
    for prediction in data["predictions"]:
        assert prediction["label"].startswith(("AB", "A", "unidentified"))
        assert 0 < prediction["confidence"] <= 100
        box = prediction["box"]
        assert 0 <= box["x"] < box["x"] + box["w"] <= 1.000001
        assert 0 <= box["y"] < box["y"] + box["h"] <= 1.000001
        with Image.open(BytesIO(b64decode(prediction["imageUrl"].split(",", 1)[1]))) as crop:
            assert crop.width > 0 and crop.height > 0
    assert annotated.headers["content-type"] == "image/png"
    with Image.open(BytesIO(annotated.content)) as image:
        assert image.size == (1367, 2253)


@pytest.fixture
def two_stage(monkeypatch, tmp_path):
    """A trained one-class detector and a classifier, with the classifier's model mocked."""
    import json

    detector, classifier = tmp_path / "linear_a_signs.pt", tmp_path / "linear_a_classifier.pt"
    detector.write_bytes(b"weights")
    classifier.write_bytes(b"weights")
    classifier.with_suffix(".json").write_text(json.dumps({
        "A707": {"name": "A707", "roles": ["fraction"]},
        "AB01": {"name": "AB01 (da)", "roles": ["syllabogram"]},
    }), encoding="utf-8")
    monkeypatch.setattr("backend.app.tablet_demo.SIGN_WEIGHTS", detector)
    monkeypatch.setattr("backend.app.tablet_demo.CLASSIFIER_WEIGHTS", classifier)
    monkeypatch.setattr("backend.app.tablet_demo._model", lambda weights: object())
    monkeypatch.setattr("backend.app.tablet_demo.READER_CONFIG", tmp_path / "linear_a_reader.json")  # none: plain
    image = np.full((200, 100, 3), 255, dtype=np.uint8)
    image[50:90, 20:30] = 0
    return Results(image, path=str(HT13_IMAGE), names={0: "sign"},
                   boxes=np.array([[10, 40, 40, 120, 0.9, 0], [50, 40, 90, 120, 0.5, 0]]))


def test_the_classifier_names_each_detected_sign_and_lists_candidates(two_stage):
    named = [[("A707", 0.8), ("AB01", 0.15), ("AB99", 0.05)], [("AB01", 0.6), ("A707", 0.4), ("AB99", 0.0)]]
    guesses = [{"sign": "A707", "label": "J", "distance": 4.0}]
    with patch("backend.app.tablet_demo.ht13_result", return_value=two_stage),          patch("la.reader.name_boxes", return_value=named) as name_boxes,          patch("backend.app.reading.identify_mask", return_value=guesses) as identify:
        with TestClient(app) as client:
            data = client.get("/tablet-demo/ht13/predictions").json()
    assert data["trained"] is True
    first, second = data["predictions"]
    assert first["label"] == "A707" and second["label"] == "AB01 (da)"
    assert first["confidence"] == pytest.approx(72.0) and first["detectionConfidence"] == pytest.approx(90.0)
    assert [c["sign"] for c in first["candidates"]] == ["A707", "AB01", "AB99"]
    assert first["candidates"][2]["label"] == "AB99"  # unknown to the catalogue: shown by ID
    assert first["shapeGuesses"] == guesses and "shapeGuesses" not in second
    identify.assert_called_once()
    boxes = name_boxes.call_args.args[2]
    assert boxes == [(10, 40, 40, 120), (50, 40, 90, 120)]


def test_the_annotated_image_shows_the_classifier_names(two_stage):
    with patch("backend.app.tablet_demo.ht13_result", return_value=two_stage),          patch("la.reader.name_boxes", return_value=[[("A707", 0.8)], [("AB01", 0.6)]]),          patch.object(Results, "plot", autospec=True, side_effect=lambda self, **kw: self.orig_img) as plot:
        png = annotate_ht13()
    drawn = plot.call_args.args[0]
    assert drawn.names == {0: "A707", 1: "AB01 (da)"}
    assert drawn.boxes.conf.tolist() == pytest.approx([0.72, 0.3])
    assert cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR).shape == (200, 100, 3)


def test_the_classifier_is_ignored_without_a_trained_detector(monkeypatch, tmp_path):
    from backend.app import tablet_demo

    classifier = tmp_path / "linear_a_classifier.pt"
    classifier.write_bytes(b"weights")
    monkeypatch.setattr(tablet_demo, "CLASSIFIER_WEIGHTS", classifier)
    assert tablet_demo.active_classifier() is None


def test_inference_sets_its_thread_count_in_the_calling_thread():
    # The count is per OS thread and routes run in worker threads, so read_image sets it on every call.
    from backend.app import tablet_demo

    model = type("Model", (), {"predict": lambda self, **kwargs: ["result"]})()
    with patch.object(tablet_demo, "_model", return_value=model), \
         patch.object(tablet_demo.torch, "set_num_threads") as set_threads:
        assert tablet_demo.read_image(np.zeros((4, 4, 3), dtype=np.uint8)) == "result"
    set_threads.assert_called_once_with(tablet_demo.INFERENCE_THREADS)


@pytest.mark.parametrize(("setting", "warmed"), [("1", True), ("0", False)])
def test_models_are_warmed_at_startup_unless_turned_off(monkeypatch, setting, warmed):
    monkeypatch.setenv("PRELOAD_MODELS", setting)
    with patch("backend.app.tablet_demo.warm_up") as warm_up:
        with TestClient(app):
            pass
    assert warm_up.called is warmed


def test_a_failed_warm_up_does_not_stop_the_app(capsys):
    from backend.app import tablet_demo

    with patch.object(tablet_demo, "ht13_predictions", side_effect=FileNotFoundError("weights")):
        tablet_demo.warm_up()
    assert "warm-up skipped" in capsys.readouterr().err


def test_the_installed_reader_refinements_are_passed_to_the_classifier(two_stage, tmp_path):
    from backend.app import tablet_demo

    np.savez(tmp_path / "linear_a_bank.npz", signs=np.array(["A707", "A707", "AB01"]), vectors=np.eye(3, 4))
    (tmp_path / "linear_a_reader.json").write_text(json.dumps({
        "version": "test", "tta": True, "prior": 0.25,
        "knn": {"bank": "linear_a_bank.npz", "backbone": "yolo", "weight": 0.35, "temperature": 0.02},
        "comparer": {"weights": "missing_comparer.pt", "weight": 0.5}}), encoding="utf-8")
    tablet_demo._load_refinements.cache_clear()
    with patch("la.embeddings.embedder", return_value=lambda crops: np.zeros((len(crops), 4))),          patch("la.reader.name_boxes", return_value=[[("A707", 0.8)], [("AB01", 0.6)]]) as name_boxes:
        tablet_demo.name_signs(two_stage)
    options = name_boxes.call_args.kwargs
    assert options["tta"] is True and options["prior"] == 0.25
    assert options["real_counts"] == {"A707": 2, "AB01": 1}
    assert options["bank"].weight == 0.35 and len(options["bank"].signs) == 3
    assert options["comparer"] is None  # its file is missing: skipped, not an error


def test_without_a_reader_config_the_plain_classifier_names(two_stage):
    from backend.app import tablet_demo

    with patch("la.reader.name_boxes", return_value=[[("A707", 0.8)], [("AB01", 0.6)]]) as name_boxes:
        tablet_demo.name_signs(two_stage)
    assert not {"tta", "bank", "comparer", "prior"} & set(name_boxes.call_args.kwargs)
