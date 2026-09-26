"""Full-inventory retrieval: the scoring must not be fooled by same-tablet neighbours."""

from __future__ import annotations

import numpy as np
from PIL import Image

from la import inventory


def write_glyph(tmp_path, sign, role, tablet, pos, mask):
    path = tmp_path / f"{sign}__{role}__{tablet}__{pos}.png"
    Image.fromarray((~mask * 255).astype(np.uint8)).convert("RGBA").save(path)
    return path


def bar(canvas=40, x=18, w=4):
    m = np.zeros((canvas, canvas), dtype=bool)
    m[8:32, x:x + w] = True
    return m


def block(canvas=40):
    m = np.zeros((canvas, canvas), dtype=bool)
    m[10:30, 10:30] = True
    return m


class TestScanning:
    def test_filename_fields_are_parsed(self, tmp_path):
        write_glyph(tmp_path, "AB01", "syllabogram", "HT_13", 4, bar())
        entries = inventory.scan(tmp_path)
        assert len(entries) == 1
        e = entries[0]
        assert (e.sign, e.role, e.tablet) == ("AB01", "syllabogram", "HT 13")


class TestDistances:
    def test_identical_shapes_are_zero_apart(self):
        rows = np.array([[1, 1, 0, 0], [1, 1, 0, 0]], dtype=np.float32)
        d = inventory.iou_distances(rows)
        assert d[0, 1] == 0.0

    def test_disjoint_shapes_are_one_apart(self):
        rows = np.array([[1, 1, 0, 0], [0, 0, 1, 1]], dtype=np.float32)
        assert inventory.iou_distances(rows)[0, 1] == 1.0

    def test_self_distance_is_excluded(self):
        rows = np.array([[1, 0], [0, 1]], dtype=np.float32)
        assert np.isinf(inventory.iou_distances(rows)[0, 0])


class TestSameTabletExclusion:
    def _entries_and_dist(self, tmp_path):
        # Two identical 'A' glyphs on one tablet, and one 'B' elsewhere.
        # Without exclusion, each A trivially finds its twin.
        write_glyph(tmp_path, "A", "syllabogram", "T1", 1, bar())
        write_glyph(tmp_path, "A", "syllabogram", "T1", 2, bar())
        write_glyph(tmp_path, "B", "syllabogram", "T2", 1, block())
        entries = inventory.scan(tmp_path)
        rows = inventory.build_matrix(entries, size=32)
        return entries, inventory.iou_distances(rows)

    def test_same_tablet_neighbours_are_ignored(self, tmp_path):
        entries, dist = self._entries_and_dist(tmp_path)
        result = inventory.evaluate(entries, dist, exclude_same_tablet=True)
        # Neither A has an A on another tablet, so neither is scorable.
        assert result["scored"] == 0

    def test_without_exclusion_the_twins_inflate_the_score(self, tmp_path):
        entries, dist = self._entries_and_dist(tmp_path)
        result = inventory.evaluate(entries, dist, exclude_same_tablet=False)
        assert result["scored"] == 2
        assert result["top1"] == 1.0


class TestReporting:
    def test_coverage_thresholds_shrink_monotonically(self):
        from collections import Counter
        table = inventory.coverage_table(Counter({"a": 50, "b": 10, "c": 3, "d": 1}))
        shares = [row["share_of_corpus"] for row in table]
        assert shares == sorted(shares, reverse=True)
        assert table[0]["threshold"] == 2

    def test_frequency_bins_are_reported(self, tmp_path):
        for i in range(4):
            write_glyph(tmp_path, "A", "syllabogram", f"T{i}", 1, bar())
        write_glyph(tmp_path, "Z", "logogram", "T9", 1, block())
        entries = inventory.scan(tmp_path)
        dist = inventory.iou_distances(inventory.build_matrix(entries, size=32))
        result = inventory.evaluate(entries, dist)
        assert result["sign_types"] == 2
        assert any(b["glyphs_scored"] for b in result["by_frequency"])
