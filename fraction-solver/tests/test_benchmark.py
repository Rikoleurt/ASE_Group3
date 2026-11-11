"""Benchmark metrics (benchmark/metrics.py): no models needed, hand-checked numbers."""

import math

import numpy as np
import pytest

from benchmark import metrics as M


def det(conf, labels=(), truth=-1):
    return M.Detection(conf, list(labels), [1.0] * len(labels), truth)


def ident(sign, labels, p=0.9, bucket="5+", role="syllabogram"):
    return M.Identification(sign, list(labels), [p] + [0.0] * (len(labels) - 1), role, bucket)


@pytest.mark.parametrize("n,bucket", [(0, "unseen"), (1, "1"), (2, "2-4"), (4, "2-4"), (5, "5+"), (90, "5+")])
def test_bucket_of(n, bucket):
    assert M.bucket_of(n) == bucket


def tablet():
    # Three truths; the third has no known identity (a box added by review).
    return M.TabletRecord("T1", ["AB01", "AB02", None], [True, False, True], detections=[
        det(0.9, ["AB01", "AB09"], truth=0),     # found, read
        det(0.3, ["AB09", "AB02"], truth=1),     # found, top-3 only
        det(0.2, ["AB01"], truth=2),             # found, identity unknown
        det(0.6, ["AB05"]),                       # false positive
    ])


def test_end_to_end_matches_evaluate_rates():
    r = M.end_to_end([tablet()], conf=0.25)
    assert r["precision"] == pytest.approx(2 / 3)
    assert r["recall"] == pytest.approx(2 / 3)
    assert r["read_top1"] == pytest.approx(1 / 2)
    assert r["read_top3"] == pytest.approx(2 / 2)
    assert r["read_top1_learnable"] == pytest.approx(1 / 1)
    assert r["named_given_found"] == pytest.approx(1 / 2)


def test_lower_threshold_keeps_more_boxes():
    low = M.end_to_end([tablet()], conf=0.1)
    assert low["recall"] == pytest.approx(1.0)
    assert low["precision"] == pytest.approx(3 / 4)


def test_average_precision_perfect_and_partial():
    perfect = M.TabletRecord("P", ["A", "B"], [True, True], [det(0.9, truth=0), det(0.8, truth=1)])
    assert M.average_precision([perfect]) == pytest.approx(1.0)
    # Ranked: hit, miss, hit -> precision 1, 1/2, 2/3 at recall 0.5, 0.5, 1.0; envelope gives 0.5*1 + 0.5*2/3.
    mixed = M.TabletRecord("M", ["A", "B"], [True, True], [det(0.9, truth=0), det(0.8), det(0.7, truth=1)])
    assert M.average_precision([mixed]) == pytest.approx(0.5 + 0.5 * 2 / 3)
    assert M.average_precision([M.TabletRecord("E", ["A"], [True])]) == 0.0


def test_identification_rates_and_macro():
    rec = M.TabletRecord("T", [], [], identifications=[
        ident("A", ["A", "B"]), ident("A", ["A"]), ident("A", ["B", "A"]),   # sign A: 2/3
        ident("B", ["C", "D", "E", "F", "B"], bucket="1"),                     # sign B: 0/1, in top 5
    ])
    r = M.identification([rec])
    assert r["id_top1"] == pytest.approx(2 / 4)
    assert r["id_top3"] == pytest.approx(3 / 4)
    assert r["id_top5"] == pytest.approx(4 / 4)
    assert r["id_macro_top1"] == pytest.approx((2 / 3 + 0) / 2)
    assert r["id_top1_bucket_1"] == 0.0
    assert r["id_top1_bucket_5+"] == pytest.approx(2 / 3)
    assert math.isnan(r["id_top1_bucket_unseen"])


def test_selective_accuracy_answers_most_confident_first():
    idents = [ident("A", ["A"], p=0.9), ident("B", ["X"], p=0.2), ident("C", ["C"], p=0.8), ident("D", ["X"], p=0.1)]
    assert M.selective(idents, 0.5) == 1.0
    assert M.selective(idents, 1.0) == 0.5


def test_ece_zero_when_calibrated_and_positive_when_overconfident():
    calibrated = [ident("A", ["A"], p=1.0)] * 4
    assert M.ece(calibrated) == pytest.approx(0.0)
    over = [ident("A", ["B"], p=0.95)] * 4
    assert M.ece(over) == pytest.approx(0.95)


def records(n_good):
    out = []
    for i in range(10):
        hit = i < n_good
        out.append(M.TabletRecord(f"T{i}", ["A"], [True], [det(0.9, ["A" if hit else "B"], truth=0)],
                                  [ident("A", ["A" if hit else "B"])]))
    return out


def test_bootstrap_interval_contains_point_estimate():
    rs = records(6)
    draws = M.resample_indices(len(rs), 200, seed=1)
    ci = M.bootstrap(rs, M.identification, draws)
    lo, hi = ci["id_top1"]
    assert lo <= 0.6 <= hi
    assert 0 <= lo < hi <= 1


def test_paired_difference_identical_models_tie_and_better_model_wins():
    rs = records(5)
    draws = M.resample_indices(len(rs), 300, seed=2)
    same = M.paired_difference(rs, rs, M.identification, draws)["id_top1"]
    assert same["diff"] == 0 and same["lo"] == 0 and same["hi"] == 0 and same["verdict"] == "tie"
    better = M.paired_difference(records(10), records(2), M.identification, draws)["id_top1"]
    assert better["diff"] == pytest.approx(0.8) and better["verdict"] == "better"


def test_paired_difference_flips_verdict_for_calibration_error():
    good = [M.TabletRecord(f"T{i}", [], [], identifications=[ident("A", ["A"], p=1.0)]) for i in range(8)]
    bad = [M.TabletRecord(f"T{i}", [], [], identifications=[ident("A", ["B"], p=0.95)]) for i in range(8)]
    d = M.paired_difference(good, bad, M.identification, M.resample_indices(8, 100))["id_ece"]
    assert d["diff"] < 0 and d["verdict"] == "better"


def test_paired_difference_needs_same_tablets():
    with pytest.raises(ValueError):
        M.paired_difference(records(5), records(5)[::-1], M.identification, M.resample_indices(10, 5))


def test_resample_indices_are_reproducible():
    assert np.array_equal(M.resample_indices(7, 4, seed=3), M.resample_indices(7, 4, seed=3))


def test_macro_interval_contains_estimate_despite_resampling_bias():
    # Many tablets of one well-read sign, and a few rare signs that are always missed:
    # resampling drops the rare signs often, which pushes a percentile interval above the estimate.
    rs = [M.TabletRecord(f"C{i}", [], [], identifications=[ident("A", ["A"])]) for i in range(30)]
    rs += [M.TabletRecord(f"R{i}", [], [], identifications=[ident(f"R{i}", ["A"])]) for i in range(3)]
    point = M.identification(rs)["id_macro_top1"]
    lo, hi = M.bootstrap(rs, M.identification, M.resample_indices(len(rs), 400, seed=4))["id_macro_top1"]
    assert lo <= point <= hi
