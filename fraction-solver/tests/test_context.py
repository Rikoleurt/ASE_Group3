"""la.context: the sign-pair model and joint line decoding."""

import pytest
from la import context


def model():
    return context.PairModel.fit([["KU", "RO"], ["KU", "RO"], ["KU", "RO"], ["SA", "RA"], ["KU", "PA"]])


def test_pair_probabilities_are_normalised_and_prefer_seen_pairs():
    m = model()
    assert sum(m.prob(s, "KU") for s in m.vocabulary) + m.prob("<unseen>", "KU") == pytest.approx(1.0)
    assert m.prob("RO", "KU") > m.prob("RA", "KU")
    assert m.association("RO", "KU") > 0 > m.association("RA", "KU")


def test_decode_uses_context_to_break_a_near_tie():
    cands = [[("KU", 0.9), ("SA", 0.1)], [("RA", 0.51), ("RO", 0.49)]]
    assert context.decode_line(cands, model(), 0.0) == cands
    out = context.decode_line(cands, model(), 1.0)
    assert out[1][0][0] == "RO"
    assert sum(p for _, p in out[1]) == pytest.approx(1.0)


def test_decode_keeps_a_confident_reading():
    cands = [[("KU", 0.9), ("SA", 0.1)], [("RA", 0.99), ("RO", 0.01)]]
    assert context.decode_line(cands, model(), 0.3)[1][0][0] == "RA"


def test_doc_lines_keep_signs_and_fractions_only():
    doc = {"lines": [[{"kind": "sign", "id": "AB81"}, {"kind": "number", "value": 3}, {"kind": "fraction", "id": "A707"}],
                     [{"kind": "divider"}]]}
    assert context.doc_lines(doc) == [["AB81", "A707"]]
