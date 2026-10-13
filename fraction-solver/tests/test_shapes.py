"""Shape pipeline tests, on synthetic glyphs whose answers are known.

These test the method, not Linear A: if a square does not normalise to the same
canonical form when rotated and rescaled, no result on real tracings means
anything.
"""

from __future__ import annotations

import numpy as np
import pytest

from la import shapes


def square(size=40, offset=(10, 10), canvas=100):
    m = np.zeros((canvas, canvas), dtype=bool)
    y, x = offset
    m[y:y + size, x:x + size] = True
    return m


def rectangle(w=60, h=20, canvas=100):
    m = np.zeros((canvas, canvas), dtype=bool)
    m[40:40 + h, 20:20 + w] = True
    return m


def glyph_from(mask, sign="X", tablet="T"):
    canon = shapes.normalise(mask)
    return shapes.Glyph(sign=sign, tablet=tablet, path=None, mask=canon,
                        hu=shapes.hu_moments(canon), contour=shapes.boundary(canon))


class TestNormalisation:
    def test_position_is_removed(self):
        a = shapes.normalise(square(offset=(5, 5)))
        b = shapes.normalise(square(offset=(50, 50)))
        assert np.array_equal(a, b)

    def test_scale_is_removed(self):
        a = shapes.normalise(square(size=20))
        b = shapes.normalise(square(size=60, canvas=200))
        overlap = np.logical_and(a, b).sum() / max(np.logical_or(a, b).sum(), 1)
        assert overlap > 0.9

    def test_empty_mask_is_handled(self):
        out = shapes.normalise(np.zeros((50, 50), dtype=bool))
        assert out.shape == (shapes.CANON, shapes.CANON)
        assert not out.any()


class TestDescriptors:
    def test_hu_moments_are_scale_invariant(self):
        a = shapes.hu_moments(shapes.normalise(square(size=20)))
        b = shapes.hu_moments(shapes.normalise(square(size=60, canvas=200)))
        assert np.allclose(a, b, atol=0.5)

    def test_different_shapes_differ(self):
        sq = glyph_from(square())
        rect = glyph_from(rectangle())
        assert shapes.distance(sq, rect) > 0.05

    def test_a_glyph_is_closest_to_itself(self):
        g = glyph_from(square())
        assert shapes.distance(g, g) == pytest.approx(0.0, abs=1e-9)

    def test_boundary_is_a_subset_of_the_ink(self):
        mask = shapes.normalise(square())
        b = shapes.boundary(mask)
        assert len(b) > 0
        assert len(b) < mask.sum()


class TestComponents:
    def test_one_blob_is_one_component(self):
        assert shapes._components(square()) == 1

    def test_two_separated_blobs_are_two_components(self):
        m = np.zeros((100, 100), dtype=bool)
        m[10:30, 10:30] = True
        m[60:80, 60:80] = True
        assert shapes._components(m) == 2


class TestRetrieval:
    def test_identical_shapes_retrieve_their_own_class(self):
        glyphs = [glyph_from(square(offset=(o, o)), sign="SQ") for o in (5, 10, 15)]
        glyphs += [glyph_from(rectangle(h=h), sign="RE") for h in (18, 20, 22)]
        result = shapes.retrieval_evaluation(glyphs)
        assert result["evaluated"] == 6
        assert result["top1"] == 1.0

    def test_singletons_are_excluded_from_scoring(self):
        glyphs = [glyph_from(square(), sign="SQ"), glyph_from(rectangle(), sign="ONLY")]
        assert shapes.retrieval_evaluation(glyphs)["evaluated"] == 0
