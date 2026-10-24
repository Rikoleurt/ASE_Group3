"""Sign variations and crops: plausible, never mirrored, and framed as the demo frames them."""

from __future__ import annotations

import numpy as np
import pytest

from la import augment
from test_signboxes import big_sign, stroke_sign


def test_square_crop_keeps_proportions_and_centres_the_sign():
    ink = np.zeros((300, 300), dtype=bool)
    ink[100:200, 140:160] = True                      # a tall bar
    crop = augment.square_crop(ink, (140, 100, 160, 200), margin=0, size=100)
    assert crop.shape == (100, 100) and crop.dtype == np.uint8
    dark = crop < 128
    ys, xs = np.nonzero(dark)
    assert ys.min() == 0 and ys.max() == 99           # full height
    assert 35 <= xs.min() and xs.max() <= 64          # 1/5 of the width, centred


def test_square_crop_margin_adds_context_and_stays_inside_the_image():
    ink = np.zeros((50, 50), dtype=bool)
    ink[0:10, 0:10] = True
    neighbour = (15, 0, 35, 10)                       # 5 px from the sign; the margin is 10 px
    crop = augment.square_crop(ink, neighbour, margin=0.5, size=64)
    assert (crop < 128).any()                         # the margin reaches the sign next door
    assert augment.square_crop(ink, (0, 0, 10, 10), margin=2.0).shape == (augment.CROP_SIZE,) * 2


def test_variations_are_deterministic_for_a_seed_and_differ_between_draws():
    sign = big_sign(3)
    a = [augment.vary(sign, np.random.default_rng(7)) for _ in range(2)]
    assert np.array_equal(a[0], a[1])
    rng = np.random.default_rng(7)
    draws = [augment.vary(sign, rng) for _ in range(5)]
    assert len({d.tobytes() + bytes(d.shape) for d in draws}) > 1


def test_variations_keep_most_of_the_sign_and_never_mirror_it():
    sign = np.zeros((60, 40), dtype=bool)
    sign[:, :6] = True                                # an L: a stem on the left...
    sign[-6:, :] = True                               # ...and a foot along the bottom
    rng = np.random.default_rng(0)
    smallest_area = (1 - augment.MAX_STRETCH) ** 2    # shrinking in both directions
    for _ in range(50):
        v = augment.vary(sign, rng)
        assert v.any() and v.sum() >= augment.MIN_INK_KEPT * smallest_area * 0.95 * sign.sum()
        h, w = v.shape
        left, right = v[:, : w // 3].sum(), v[:, -(w // 3):].sum()
        assert left > right                           # the stem is still on the left


def test_chipping_never_removes_too_much():
    sign = stroke_sign(5, size=(60, 60))
    rng = np.random.default_rng(1)
    for _ in range(100):
        assert augment.chip(sign, rng).sum() >= augment.MIN_INK_KEPT * sign.sum()


def test_vary_returns_an_empty_sign_unchanged():
    assert not augment.vary(np.zeros((10, 10), dtype=bool), np.random.default_rng(0)).any()


@pytest.mark.parametrize("n, expected", [(0, 0), (1, 10), (4, 20), (25, 50), (100, 100), (400, 400)])
def test_resampling_lifts_rare_classes_towards_the_target_without_shrinking_any(n, expected):
    assert augment.resample_count(n, 100) == expected
