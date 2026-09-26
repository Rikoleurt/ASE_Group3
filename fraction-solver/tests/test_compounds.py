"""Compound-sign tests, on synthetic glyphs with known answers."""

from __future__ import annotations

import numpy as np
import pytest

from la import compounds, shapes


def glyph(mask, sign="S", tablet="T", tmp_path=None):
    """A Glyph backed by a real file, since compose() re-reads from disk."""
    from PIL import Image
    path = tmp_path / f"{sign}_{tablet}_{abs(hash(mask.tobytes())) % 9999}.png"
    Image.fromarray((~mask * 255).astype(np.uint8)).convert("RGBA").save(path)
    canon = shapes.normalise(mask)
    return shapes.Glyph(sign=sign, tablet=tablet, path=path, mask=canon,
                        hu=shapes.hu_moments(canon), contour=shapes.boundary(canon))


def bar(canvas=60, thickness=6):
    m = np.zeros((canvas, canvas), dtype=bool)
    m[10:50, 25:25 + thickness] = True
    return m


def ell(canvas=60):
    m = np.zeros((canvas, canvas), dtype=bool)
    m[10:50, 20:26] = True
    m[44:50, 20:45] = True
    return m


class TestCompose:
    def test_side_by_side_widens_the_result(self, tmp_path):
        a = glyph(bar(), tmp_path=tmp_path)
        out = compounds.compose(a, a, "side")
        assert out.mask.any()

    def test_every_geometry_produces_ink(self, tmp_path):
        a = glyph(bar(), "A", tmp_path=tmp_path)
        b = glyph(ell(), "B", tmp_path=tmp_path)
        for geometry in compounds.GEOMETRIES:
            assert compounds.compose(a, b, geometry).mask.any(), geometry

    def test_unknown_geometry_is_rejected(self, tmp_path):
        a = glyph(bar(), tmp_path=tmp_path)
        with pytest.raises(ValueError):
            compounds.compose(a, a, "spiral")


class TestScoring:
    def test_candidates_below_the_attestation_floor_are_skipped(self, tmp_path):
        by_sign = {
            "RARE": [glyph(bar(), "RARE", "T1", tmp_path), glyph(bar(), "RARE", "T2", tmp_path)],
            "COMMON": [glyph(ell(), "COMMON", f"T{i}", tmp_path) for i in range(4)],
        }
        target = [glyph(ell(), "TARGET", "TX", tmp_path)]
        scored = compounds.score_candidates(target, by_sign, exclude_tablets=set())
        assert [s for s, _ in scored] == ["COMMON"]  # RARE has only 2 attestations

    def test_same_tablet_glyphs_are_excluded(self, tmp_path):
        """A scribe's own hand must not be allowed to match itself."""
        by_sign = {"S": [glyph(ell(), "S", "SAME", tmp_path) for _ in range(4)]}
        target = [glyph(ell(), "S", "SAME", tmp_path)]
        assert compounds.score_candidates(target, by_sign, exclude_tablets={"SAME"}) == []

    def test_hypothesis_rank_is_reported(self, tmp_path):
        by_sign = {
            "W": [glyph(bar(), "W", "TW", tmp_path)],
            "B": [glyph(ell(), "B", f"T{i}", tmp_path) for i in range(4)],
        }
        result = compounds.test_hypothesis("W", "B", by_sign)
        assert result.attestations == 1
        assert result.hypothesis == "B"
        assert result.hypothesis_rank == 1
        assert result.hypothesis_distance is not None

    def test_missing_target_is_handled(self):
        result = compounds.test_hypothesis("NOPE", "B", {})
        assert result.attestations == 0
        assert result.ranked == []


class TestRealDoublingDetection:
    def test_adjacent_identical_fractions_are_found(self, tmp_path):
        docs = {"T 1": {"id": "T 1", "lines": [[
            {"kind": "fraction", "id": "A703"},
            {"kind": "fraction", "id": "A703"},
        ]]}}
        by_sign = {"A703": [glyph(ell(), "A703", "T 1", tmp_path) for _ in range(2)]}
        found = compounds.find_real_doublings(docs, by_sign)
        assert len(found) == 1
        assert found[0][0] == "T 1" and found[0][1] == "A703"

    def test_different_adjacent_signs_are_not_a_doubling(self, tmp_path):
        docs = {"T 1": {"id": "T 1", "lines": [[
            {"kind": "fraction", "id": "A703"},
            {"kind": "fraction", "id": "A707"},
        ]]}}
        assert compounds.find_real_doublings(docs, {}) == []
