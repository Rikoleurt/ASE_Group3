import numpy as np

from backend.app.glyph_index import GlyphIndex
from backend.tests.glyph_fixtures import DOCS, embeddings, index


def test_occurrences_grouped_by_sign_with_boxes_and_safe_slugs_only():
    idx = index()
    assert idx.counts() == {"AB01": 1, "AB77": 7}  # the "a b" slug is not a valid tablet id
    assert [(o.slug, o.position) for o in idx.by_sign["AB77"]][:3] == [("HT-1", 1), ("HT-2", 1), ("HT-2", 4)]
    first = idx.lookup("HT-1", 1)
    assert first.tablet == "HT 1" and first.has_crop and first.box == (0.1, 0.1, 0.1, 0.2)
    assert idx.lookup("HT-2", 4).has_crop is False and idx.lookup("HT-2", 4).box is None
    assert idx.lookup("HT-1", 99) is None


def test_without_embeddings_corpus_order_and_no_similarity():
    idx = index(with_embeddings=False)
    mode, ranked = idx.ranked("AB77")
    assert mode == "none" and all(score is None for _o, score in ranked)
    assert not idx.has_embeddings() and not idx.is_outlier(idx.lookup("HT-1", 1))


def test_similarity_orders_by_cosine_and_missing_vectors_come_last():
    idx = index()
    mode, ranked = idx.ranked("AB77", idx.vector_of("HT-1", 1))
    assert mode == "glyph"
    scores = [s for _o, s in ranked]
    assert ranked[0][0].slug == "HT-1" and abs(scores[0] - 1) < 1e-5
    assert scores[-1] is None and ranked[-1][0].position == 4  # HT 2 #4 has no vector
    present = [s for s in scores if s is not None]
    assert present == sorted(present, reverse=True)
    # The odd one out is the least similar glyph that has a vector.
    assert ranked[-2][0].slug == "KN-Zb-5" and ranked[-2][0].position == 11


def test_default_order_is_typical_first_and_far_glyph_is_flagged():
    idx = index()
    mode, ranked = idx.ranked("AB77")
    assert mode == "centre"
    assert ranked[-2][0].position == 11
    assert idx.is_outlier(idx.lookup("KN-Zb-5", 11))
    assert not idx.is_outlier(idx.lookup("HT-1", 1))


def test_vector_for_a_different_sign_is_ignored():
    data = embeddings()
    data["sign"] = np.array(["AB01"] * len(data["sign"]))  # a stale file whose labels no longer match
    idx = GlyphIndex(DOCS, [], data)
    assert idx.vector_of("HT-1", 1) is None
    assert idx.vector_of("HT-1", 2) is not None
