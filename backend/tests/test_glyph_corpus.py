"""The real corpus, when it is installed (the dataset is gitignored and absent in CI)."""
import pytest

from backend.app import glyph_index

pytestmark = pytest.mark.skipif(not glyph_index.ANNOTATIONS.is_file(), reason="corpus not installed")


def test_real_corpus_index_is_consistent():
    index = glyph_index.get_index()
    assert len(index.counts()) > 300 and sum(index.counts().values()) > 4000
    ka = index.by_sign["AB77"]
    assert all(o.sign == "AB77" and index.lookup(o.slug, o.position) is o for o in ka)
    assert any(o.box for o in ka)
    for o in ka:
        if o.box:
            x, y, w, h = o.box
            assert 0 <= x < 1 and 0 <= y < 1 and 0 < w <= 1 and 0 < h <= 1 and x + w <= 1.01 and y + h <= 1.01
    mode, ranked = index.ranked("AB77")
    assert mode in {"centre", "none"} and len(ranked) == len(ka)
