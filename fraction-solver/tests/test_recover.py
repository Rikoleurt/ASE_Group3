"""Recovery tests on synthetic notations whose answers are known in advance.

These run without any corpus data: they test the method, not Linear B. The taxonomy is
the contribution, so most of these tests are about the *boundary* between verdicts —
particularly that a single gap is never reported as a stronger result than it is.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from la import recover
from la.lb.metrology import DRY, LIQUID, Series


def gap(surviving, where="entry", line="1"):
    return recover.Gap(where=where, line=line, surviving=list(surviving))


LIQ = recover.MetricNotation(LIQUID)   # UNIT=72 Z, S=24, V=4, Z=1; caps 3, 6, 4
COUNT = recover.CountNotation()


class TestNotation:
    def test_metric_sizes_follow_the_ratio_chain(self):
        assert LIQ.size("UNIT") == 72   # 3 S x 6 V x 4 Z
        assert LIQ.size("S") == 24
        assert LIQ.size("V") == 4
        assert LIQ.size("Z") == 1

    def test_bundling_caps_come_from_the_series(self):
        assert LIQ.cap("UNIT") is None  # whole units are unbounded
        assert LIQ.cap("S") == 3
        assert LIQ.cap("V") == 6
        assert LIQ.cap("Z") == 4

    def test_dry_and_liquid_differ_only_in_the_major_unit(self):
        dry = recover.MetricNotation(DRY)
        assert dry.size("V") == LIQ.size("V")
        assert dry.size("UNIT") == 240 and LIQ.size("UNIT") == 72


class TestWritingOrder:
    def test_a_break_cannot_bring_back_a_larger_unit(self):
        # `S 1[` : only V and Z can follow, never another whole unit.
        found = recover.addenda_up_to([("S", 1)], LIQ, Fraction(72), strict=True)
        assert found, "expected some legal continuations"
        for a in found:
            assert all(u in {"V", "Z"} for u, _ in a.appended)

    def test_nothing_surviving_admits_any_unit(self):
        # `OLE [` : the amount is gone entirely, so any sign could have stood there.
        found = recover.legal_addenda([], LIQ, Fraction(72), strict=True)
        assert any(("UNIT", 1) in a.appended for a in found)

    def test_unknown_surviving_sign_yields_nothing(self):
        assert recover.legal_addenda([("Q", 1)], LIQ, Fraction(4)) == []


class TestBundling:
    def test_strict_search_respects_the_carry_rule(self):
        # 6 V make an S, so `V 6` is never written; 24 must be reached another way.
        found = recover.legal_addenda([("S", 1)], LIQ, Fraction(24), strict=True)
        for a in found:
            for unit, count in a.appended:
                assert count < LIQ.cap(unit)

    def test_relaxed_search_admits_more_than_strict(self):
        strict = recover.legal_addenda([("S", 1)], LIQ, Fraction(24), strict=True)
        relaxed = recover.legal_addenda([("S", 1)], LIQ, Fraction(24), strict=False)
        assert len(relaxed) >= len(strict)

    def test_extension_is_capped_by_the_carry_rule(self):
        # `S 1[` can become S 2 but not S 3, because 3 S is a whole unit.
        found = recover.addenda_up_to([("S", 1)], LIQ, Fraction(72), strict=True)
        assert max(a.extend for a in found) == 1


class TestVerdicts:
    def test_balanced_when_nothing_is_missing(self):
        r = recover.classify(Fraction(0), [gap([("S", 1)])], LIQ)
        assert r.verdict == recover.BALANCED

    def test_error_when_it_does_not_balance_and_nothing_is_broken(self):
        r = recover.classify(Fraction(5), [], LIQ)
        assert r.verdict == recover.ERROR_NO_DAMAGE

    def test_overfull_when_entries_exceed_an_intact_total(self):
        r = recover.classify(Fraction(-5), [gap([("S", 1)])], LIQ)
        assert r.verdict == recover.OVERFULL

    def test_a_broken_total_is_not_called_overfull(self):
        r = recover.classify(Fraction(-5), [gap([("S", 1)])], LIQ, total_damaged=True)
        assert r.verdict == recover.UNRESOLVED

    def test_unresolved_without_a_notation(self):
        assert recover.classify(Fraction(5), [gap([])], None).verdict == recover.UNRESOLVED

    def test_impossible_when_no_legal_amount_fits(self):
        # `Z 3[` can only gain more Z, and the carry rule stops at 3, so 100 is unreachable.
        r = recover.classify(Fraction(100), [gap([("Z", 3)])], LIQ, strict=True)
        assert r.verdict == recover.IMPOSSIBLE

    def test_counted_commodity_with_one_gap_is_uniquely_restored(self):
        # Any integer is writeable, so exactly one reading balances: the residual itself.
        r = recover.classify(Fraction(5), [gap([("UNIT", 1)])], COUNT)
        assert r.verdict == recover.UNIQUE
        assert r.candidates[0].value == 5
        assert r.is_determination

    def test_a_wholly_lost_headcount_is_recovered(self):
        r = recover.classify(Fraction(5), [gap([])], COUNT)
        assert r.verdict == recover.UNIQUE
        assert r.candidates[0].value == 5


class TestBundlingMakesRestorationUnique:
    """Why Linear B is recoverable and Linear A much less so.

    A carry rule makes the written form of a value essentially canonical, so where a
    single-gap restoration is possible at all it is usually the *only* one. Relaxing the
    rule — which is what a scribe violating it would amount to — immediately multiplies the
    readings. That contrast is the mechanism behind the whole result, so it is tested
    rather than asserted.
    """

    def test_strict_single_gap_is_unique_or_impossible(self):
        for residual in (1, 2, 3, 4, 5, 8, 12, 20, 24):
            r = recover.classify(Fraction(residual), [gap([("V", 1)])], LIQ, strict=True)
            assert r.verdict in {recover.UNIQUE, recover.IMPOSSIBLE}, (residual, r.verdict)

    def test_relaxing_the_carry_rule_multiplies_the_readings(self):
        strict = recover.classify(Fraction(8), [gap([("V", 1)])], LIQ, strict=True)
        relaxed = recover.classify(Fraction(8), [gap([("V", 1)])], LIQ, strict=False)
        assert strict.verdict == recover.UNIQUE
        assert relaxed.spellings > strict.spellings


class TestSingleGapIsNotOversold:
    """A lone gap's amount is arithmetic, not analysis, and must not be sold as more."""

    def test_several_spellings_is_amount_determined_not_unique(self):
        # No carry rule, so a half is J, or two E at a repeat limit of three.
        notation = recover.FractionNotation(
            {"J": Fraction(1, 2), "E": Fraction(1, 4), "D": Fraction(1, 6)}, repeat_limit=3
        )
        r = recover.classify(Fraction(1, 2), [gap([(recover.WHOLE, 1)])], notation, strict=True)
        assert r.verdict == recover.AMOUNT_DETERMINED
        assert r.spellings > 1
        assert r.distinct_distributions == 1
        assert r.is_determination is False  # must not count as a determination

    def test_the_meaning_string_says_so(self):
        text = recover.VERDICT_MEANING[recover.AMOUNT_DETERMINED]
        assert "arithmetic alone" in text


class TestDistributionAcrossGaps:
    """Two broken entries can *share* the shortfall; assuming one took it all is wrong."""

    def test_shortfall_may_be_split_between_two_gaps(self):
        r = recover.classify(Fraction(24), [gap([("S", 1)], "a"), gap([("S", 1)], "b")], LIQ)
        assert r.verdict == recover.AMBIGUOUS
        assert r.distinct_distributions > 1
        # One gap taking all 24 is present, but so is a genuine split.
        tuples = {c.value_tuple for c in r.candidates}
        assert (("a", "24"),) in tuples
        assert any(len(t) == 2 for t in tuples), "expected a split across both gaps"

    def test_a_gap_may_receive_nothing(self):
        # A break can fall beside a quantity without removing any of it.
        r = recover.classify(Fraction(5), [gap([("UNIT", 1)], "a"), gap([("UNIT", 1)], "b")], COUNT)
        tuples = {c.value_tuple for c in r.candidates}
        assert (("a", "5"),) in tuples  # all of it in one gap, the other untouched
        assert (("b", "5"),) in tuples
        assert (("a", "2"), ("b", "3")) in tuples  # or shared

    def test_placement_is_part_of_the_distribution(self):
        # 1 Z is the smallest unit, so exactly one gap holds it — but either one could.
        r = recover.classify(Fraction(1), [gap([("Z", 1)], "a"), gap([("Z", 1)], "b")], LIQ)
        assert all(c.value == 1 for c in r.candidates)
        assert r.distinct_distributions == 2, "which gap it sits in must distinguish them"
        assert r.verdict == recover.AMBIGUOUS


class TestFractionNotation:
    VALUES = {"J": Fraction(1, 2), "E": Fraction(1, 4), "D": Fraction(1, 6)}

    def test_whole_unit_heads_the_chain(self):
        n = recover.FractionNotation(self.VALUES)
        assert n.units()[0] == recover.WHOLE
        assert n.size(recover.WHOLE) == 1
        assert n.cap(recover.WHOLE) is None

    def test_signs_are_ordered_by_decreasing_value(self):
        n = recover.FractionNotation(self.VALUES)
        sizes = [n.size(u) for u in n.units()]
        assert sizes == sorted(sizes, reverse=True)

    def test_a_break_after_a_fraction_cannot_restore_a_whole_unit(self):
        n = recover.FractionNotation(self.VALUES)
        found = recover.addenda_up_to([("J", 1)], n, Fraction(2))
        for a in found:
            assert recover.WHOLE not in {u for u, _ in a.appended}

    def test_repeat_limit_is_honoured_and_reported(self):
        n = recover.FractionNotation(self.VALUES, repeat_limit=2)
        found = recover.addenda_up_to([(recover.WHOLE, 1)], n, Fraction(1), strict=True)
        for a in found:
            for unit, count in a.appended:
                if unit != recover.WHOLE:
                    assert count < 2


class TestSummary:
    def test_summary_separates_unique_from_amount_determined(self):
        loose = recover.FractionNotation({"J": Fraction(1, 2), "E": Fraction(1, 4)}, repeat_limit=3)
        results = [
            recover.classify(Fraction(5), [gap([("UNIT", 1)])], COUNT),                  # UNIQUE
            recover.classify(Fraction(1, 2), [gap([(recover.WHOLE, 1)])], loose),        # AMOUNT_DETERMINED
        ]
        s = recover.summarise(results)
        assert s["uniquely_restored"] == 1
        assert s["amount_determined_spelling_open"] == 1
        assert s["gaps_with_a_restoration_attempt"] == 2

    def test_summary_warns_about_single_gap_sections(self):
        s = recover.summarise([recover.classify(Fraction(5), [gap([("UNIT", 1)])], COUNT)])
        assert s["single_gap_sections"] == 1
        assert "arithmetic alone" in s["single_gap_note"]

    def test_every_verdict_has_a_stated_meaning(self):
        for name in (
            recover.BALANCED, recover.UNIQUE, recover.AMOUNT_DETERMINED, recover.AMBIGUOUS,
            recover.IMPOSSIBLE, recover.ERROR_NO_DAMAGE, recover.OVERFULL, recover.UNRESOLVED,
        ):
            assert recover.VERDICT_MEANING[name]


class TestSeriesInvariants:
    def test_a_series_needs_one_fewer_ratio_than_units(self):
        with pytest.raises(ValueError):
            Series(name="bad", units=("A", "B", "C"), ratios=(2,), source="test")
