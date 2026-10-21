"""End-to-end scoring: found, named, and how sure we can be with a hundred tablets."""

from __future__ import annotations

import math

import pytest

from la.evaluation import Prediction, TabletScore, Truth, bootstrap, iou, match, rates, report, score_tablet


def test_iou_of_identical_disjoint_and_half_overlapping_boxes():
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1
    assert iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0
    assert iou((0, 0, 10, 10), (5, 0, 15, 10)) == pytest.approx(1 / 3)


def test_each_truth_is_matched_once_by_the_most_confident_prediction():
    truths = [Truth((0, 0, 10, 10), "AB01")]
    predictions = [Prediction((0, 0, 10, 10), 0.6, ["AB02"]), Prediction((1, 0, 10, 10), 0.9, ["AB01"])]
    assert match(predictions, truths) == {0: 1}


def test_a_sign_is_read_only_when_found_and_named():
    truths = [Truth((0, 0, 10, 10), "AB01"), Truth((20, 0, 30, 10), "AB02"),
              Truth((40, 0, 50, 10), "A707", learnable=False), Truth((60, 0, 70, 10), None)]
    predictions = [Prediction((0, 0, 10, 10), 0.9, ["AB01", "AB02"]),
                   Prediction((20, 0, 30, 10), 0.8, ["AB59", "AB28", "AB02"]),
                   Prediction((40, 0, 50, 10), 0.7, ["AB01"]),
                   Prediction((61, 0, 70, 10), 0.6, []),
                   Prediction((90, 90, 99, 99), 0.5, ["AB01"])]
    s = score_tablet("HT 1", predictions, truths)
    assert (s.truths, s.predictions, s.found, s.found_named, s.named, s.named_learnable) == (4, 5, 4, 3, 3, 2)
    assert (s.read_top1, s.read_top3, s.read_top1_learnable) == (1, 2, 1)
    r = rates([s])
    assert r["precision"] == 4 / 5 and r["recall"] == 1
    assert r["read_top1"] == pytest.approx(1 / 3) and r["read_top3"] == pytest.approx(2 / 3)
    assert r["read_top1_learnable"] == 0.5 and r["named_given_found"] == pytest.approx(1 / 3)


def test_a_detector_that_names_nothing_reads_nothing():
    s = score_tablet("HT 1", [Prediction((0, 0, 10, 10), 0.9, [])], [Truth((0, 0, 10, 10), "AB01")])
    assert rates([s])["recall"] == 1 and rates([s])["read_top1"] == 0


def tablet(read: int, of: int) -> TabletScore:
    return TabletScore("t", truths=of, predictions=of, found=of, found_named=of, named=of,
                       named_learnable=of, read_top1=read, read_top3=read, read_top1_learnable=read)


def test_bootstrap_interval_contains_the_estimate_and_narrows_with_more_tablets():
    few = [tablet(3, 10), tablet(7, 10)] * 5
    many = few * 10
    lo_few, hi_few = bootstrap(few, resamples=400)["read_top1"]
    lo_many, hi_many = bootstrap(many, resamples=400)["read_top1"]
    assert lo_few <= 0.5 <= hi_few and lo_many <= 0.5 <= hi_many
    assert hi_many - lo_many < hi_few - lo_few


def test_report_is_reproducible_and_handles_no_tablets():
    scores = [tablet(1, 4), tablet(2, 4), tablet(4, 4)]
    assert report(scores, resamples=50, seed=1) == report(scores, resamples=50, seed=1)
    empty = report([], resamples=10)
    assert empty["tablets"] == 0 and math.isnan(empty["rates"]["recall"])
