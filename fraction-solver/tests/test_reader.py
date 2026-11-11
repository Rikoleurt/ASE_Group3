"""la.reader: crops, test-time augmentation and the nearest-neighbour blend, with fake models."""

from types import SimpleNamespace

import numpy as np
import pytest
from la import reader


class FakeClassifier:
    """Two classes; the probability of class 'A' is the crop's ink share, so crops change answers."""
    names = {0: "A", 1: "B"}

    def __init__(self):
        self.calls = 0

    def predict(self, crops, device=None, verbose=False):
        self.calls += 1
        out = []
        for crop in crops:
            ink = float((crop[..., 0] < 128).mean())
            probs = np.array([ink, 1 - ink], dtype=np.float32)
            out.append(SimpleNamespace(probs=SimpleNamespace(data=_Tensor(probs))))
        return out


class _Tensor:
    def __init__(self, a):
        self.a = a

    def cpu(self):
        return self

    def numpy(self):
        return self.a


def drawing():
    ink = np.zeros((100, 100), dtype=bool)
    ink[20:40, 20:40] = True
    ink[60:80, 60:62] = True
    return ink


def test_name_boxes_returns_sorted_top_labels():
    tops = reader.name_boxes(FakeClassifier(), drawing(), [(20, 20, 40, 40), (55, 55, 85, 85)])
    assert [t[0][0] for t in tops] == ["A", "B"]
    assert all(t[0][1] >= t[1][1] for t in tops)
    assert reader.name_boxes(FakeClassifier(), drawing(), []) == []


def test_tta_boxes_keep_the_original_first_and_vary_the_rest():
    variants = reader.tta_boxes((10, 10, 30, 20))
    assert variants[0] == (10, 10, 30, 20)
    assert len(variants) == len(reader.TTA_VARIANTS) == len(set(variants))


def test_tta_averages_over_variants_in_one_batch():
    clf = FakeClassifier()
    names, probs = reader.boxed_probabilities(clf, drawing(), [(20, 20, 40, 40), (55, 55, 85, 85)], tta=True)
    assert clf.calls == 1
    assert probs.shape == (2, 2)
    assert np.allclose(probs.sum(axis=1), 1.0)


def unit(*rows):
    return np.array(rows, dtype=np.float32)


def bank(weight=0.5, temperature=0.05):
    # Reference crops: two of A pointing along x, one of B along y.
    vectors = unit([1, 0], [0.9, 0.1], [0, 1])
    return reader.NeighbourBank(lambda crops: vectors[: len(crops)], np.array(["A", "A", "B"]),
                                reader._unit(vectors), weight, temperature)


def test_scores_take_best_similarity_per_sign_and_mark_missing_signs():
    s = bank().scores(["A", "B", "C"], reader._unit(unit([0, 1])))
    assert s[0, 1] == pytest.approx(1.0)
    assert s[0, 0] == pytest.approx(reader._unit(unit([0.9, 0.1]))[0, 1])
    assert s[0, 2] == -1.0


def test_blend_moves_a_wrong_classifier_toward_the_neighbour_vote():
    probs = unit([0.9, 0.1])                    # classifier says A
    query = reader._unit(unit([0, 1]))          # looks exactly like the B reference
    assert bank(weight=0.0).blend(["A", "B"], probs, query)[0, 0] == pytest.approx(0.9)
    blended = bank(weight=0.8).blend(["A", "B"], probs, query)
    assert blended[0, 1] > blended[0, 0]
    assert blended.sum() == pytest.approx(1.0)


def test_prior_correction_restores_true_frequency_and_keeps_rows_normalised():
    # Trained on resampled copies: 1 real crop of R became 10, 100 of C stayed 100.
    probs = unit([0.5, 0.5])
    names = ["R", "C"]
    assert np.array_equal(reader.prior_correction(names, probs, {"R": 1, "C": 100}, 0.0), probs)
    corrected = reader.prior_correction(names, probs, {"R": 1, "C": 100}, 1.0)
    assert corrected[0, 1] > corrected[0, 0]
    assert corrected[0, 0] == pytest.approx(0.1 / 1.1)
    assert corrected.sum() == pytest.approx(1.0)
    unknown = reader.prior_correction(["X", "C"], probs, {"C": 100}, 1.0)
    assert unknown[0] == pytest.approx([0.5, 0.5])
