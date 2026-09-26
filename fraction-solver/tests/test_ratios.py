"""Ration-ratio constraints: a headcount beside a commodity."""

from __future__ import annotations

from fractions import Fraction

from la import ratios


def sign(reading, sid=None):
    return {"kind": "sign", "id": sid or reading, "reading": reading}


NUM = lambda v: {"kind": "number", "value": v}
FRAC = lambda i: {"kind": "fraction", "id": i}
DMG = {"kind": "damage"}


def doc(lines, did="T 1"):
    return {"id": did, "lines": lines}


class TestDetection:
    def test_headcount_then_commodity_is_a_ration_statement(self):
        pairs = ratios.find_ration_pairs(doc([
            [sign("ku"), sign("VIR"), NUM(72)],
            [sign("GRA", "A574"), NUM(36)],
        ]))
        assert len(pairs) == 1
        assert pairs[0].people.integer == 72
        assert pairs[0].issued.integer == 36
        assert pairs[0].ration({}) == Fraction(1, 2)

    def test_only_the_immediately_following_line_counts(self):
        """Pairing across a gap invents ration statements that are not there."""
        pairs = ratios.find_ration_pairs(doc([
            [sign("VIR"), NUM(72)],
            [sign("ku"), sign("ro")],
            [sign("GRA", "A574"), NUM(36)],
        ]))
        assert pairs == []

    def test_a_break_beside_the_headcount_is_recorded(self):
        pairs = ratios.find_ration_pairs(doc([
            [sign("VIR"), NUM(50), DMG],
            [sign("GRA", "A574"), NUM(26), FRAC("A707")],
        ]))
        assert pairs[0].people.broken is True
        assert pairs[0].issued.fractions == ("A707",)
        assert pairs[0].complete is False


class TestPlausibility:
    def test_a_simple_ration_is_plausible(self):
        pairs = ratios.find_ration_pairs(doc([[sign("VIR"), NUM(9)], [sign("X", "A1"), NUM(3)]]))
        assert pairs[0].plausible({}) is True   # 1/3 per person

    def test_an_absurd_ratio_is_rejected(self):
        """335/42 per person is two unrelated lines, not a ration."""
        pairs = ratios.find_ration_pairs(doc([[sign("VIR"), NUM(42)], [sign("X", "A1"), NUM(335)]]))
        assert pairs[0].plausible({}) is False


class TestSolvingBrokenPairs:
    def test_properness_forces_a_unique_solution(self):
        """PE 1: 50[ people at 1/2 each = 26 + J has exactly one proper-fraction answer."""
        pair = ratios.find_ration_pairs(doc([
            [sign("VIR"), NUM(50), DMG],
            [sign("GRA", "A574"), NUM(26), FRAC("A707")],
        ]))[0]
        sols = ratios.solve_broken_pair(pair, Fraction(1, 2), "A707")
        assert sols == [(53, Fraction(1, 2))]

    def test_no_solution_when_the_ration_cannot_fit(self):
        pair = ratios.find_ration_pairs(doc([
            [sign("VIR"), NUM(50), DMG],
            [sign("GRA", "A574"), NUM(26), FRAC("A707")],
        ]))[0]
        assert ratios.solve_broken_pair(pair, Fraction(1, 100), "A707") == []

    def test_a_pair_without_the_unknown_sign_yields_nothing(self):
        pair = ratios.find_ration_pairs(doc([
            [sign("VIR"), NUM(50), DMG],
            [sign("GRA", "A574"), NUM(26)],
        ]))[0]
        assert ratios.solve_broken_pair(pair, Fraction(1, 2), "A707") == []
