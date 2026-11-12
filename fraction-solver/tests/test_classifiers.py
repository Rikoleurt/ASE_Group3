import numpy as np
import pytest

torch = pytest.importorskip("torch")
torchvision = pytest.importorskip("torchvision")

from la import classifiers


@pytest.fixture
def tv_checkpoint(tmp_path):
    """A tiny untrained torchvision classifier saved as PR #67 saves them."""
    classes = ["A301", "AB01", "AB77"]
    model = classifiers._replace_head(torchvision.models.resnet18(weights=None), "resnet18", len(classes))
    path = tmp_path / "anywhere" / "best.pt"  # no 'bench_tv-' folder: recognised by contents
    path.parent.mkdir()
    torch.save({"arch": "resnet18", "classes": classes, "state": model.state_dict()}, path)
    return path, classes


def test_torchvision_checkpoints_are_recognised_by_contents(tv_checkpoint, tmp_path):
    path, _ = tv_checkpoint
    assert classifiers.is_torchvision(path)
    other = tmp_path / "not_a_model.pt"
    other.write_bytes(b"not a checkpoint")
    assert not classifiers.is_torchvision(other)


def test_torchvision_classifier_works_with_the_reader(tv_checkpoint):
    path, classes = tv_checkpoint
    clf = classifiers.load_classifier(path)
    assert isinstance(clf, classifiers.TorchvisionClassifier)
    crops = [np.full((128, 128, 3), v, dtype=np.uint8) for v in (0, 128, 255)]
    results = clf.predict(crops)  # the interface la.reader uses for Ultralytics classifiers
    assert [clf.names[i] for i in range(len(clf.names))] == classes
    probs = np.stack([r.probs.data.cpu().numpy() for r in results])
    assert probs.shape == (3, 3)
    np.testing.assert_allclose(probs.sum(axis=1), 1.0, rtol=1e-5)
