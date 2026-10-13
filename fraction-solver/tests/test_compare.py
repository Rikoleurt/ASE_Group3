"""Stage B: scoring competing value systems."""

from __future__ import annotations

from collections import Counter
from fractions import Fraction

from la import compare, values as V
from la.parse import Entry, Quantity, Section, Total


def section(entry_specs, total_spec):
    entries = [
        Entry(line_no=i + 1, quantity=Quantity(integer=n, fractions=list(f)))
        for i, (n, f) in enumerate(entry_specs)
    ]
    n, f = total_spec
    return Section(
        entries=entries,
        total=Total(len(entries) + 1, "total", "ku-ro", Quantity(integer=n, fractions=list(f))),
    )


class TestScoring:
    def test_a_system_that_balances_the_arithmetic_scores_it(self):
        # entries 10 + X + X, total 11  ->  2X = 1, so X = 1/2 balances
        sec = section([(10, ["X"]), (0, ["X"])], (11, []))
        good = compare.score_system("good", {"X": Fraction(1, 2)}, [("T", sec)], Counter())
        bad = compare.score_system("bad", {"X": Fraction(1, 4)}, [("T", sec)], Counter())
        assert good.equations_satisfied == 1
        assert bad.equations_satisfied == 0

    def test_ordering_violations_are_reported_with_counts(self):
        pairs = Counter({("A707", "A704"): 5, ("A704", "A707"): 1})
        score = compare.score_system("v", V.KNOWN_VALUES, [], pairs)
        assert score.pairs_checked == 2
        assert score.pairs_respected == 1
        assert score.violations[0]["attestations"] == 1

    def test_min_attestations_filters_thin_evidence(self):
        pairs = Counter({("A704", "A707"): 1})  # E before J: violates every system
        loose = compare.score_system("v", V.KNOWN_VALUES, [], pairs, min_attestations=1)
        strict = compare.score_system("v", V.KNOWN_VALUES, [], pairs, min_attestations=2)
        assert loose.pairs_checked == 1 and loose.pairs_respected == 0
        assert strict.pairs_checked == 0  # nothing survives the threshold

    def test_excluded_pairs_are_dropped(self):
        pairs = Counter({("A704", "A707"): 1})
        score = compare.score_system("v", V.KNOWN_VALUES, [], pairs, exclude_pairs={("A704", "A707")})
        assert score.pairs_checked == 0

    def test_values_outside_zero_to_one_are_flagged(self):
        score = compare.score_system("v", {"A707": Fraction(3, 2)}, [], Counter())
        assert "J" in score.impossible_values


class TestDiscrimination:
    def test_only_pairs_where_systems_disagree_are_returned(self):
        systems = {
            "one": {"X": Fraction(1, 2), "Y": Fraction(1, 4)},
            "two": {"X": Fraction(1, 4), "Y": Fraction(1, 2)},
        }
        pairs = Counter({("X", "Y"): 3})
        out = compare.discriminating_pairs(systems, pairs)
        assert len(out) == 1
        assert out[0]["respected_by"] == ["one"]
        assert out[0]["violated_by"] == ["two"]

    def test_agreement_is_not_reported(self):
        systems = {
            "one": {"X": Fraction(1, 2), "Y": Fraction(1, 4)},
            "two": {"X": Fraction(1, 3), "Y": Fraction(1, 5)},
        }
        assert compare.discriminating_pairs(systems, Counter({("X", "Y"): 2})) == []


class TestSystemTables:
    def test_alternatives_inherit_the_baseline_where_they_are_silent(self):
        younger = compare.system_values("Younger 2000-2020")
        assert younger["A707"] == V.KNOWN_VALUES["A707"]      # J: not disputed
        assert younger["A706"] != V.KNOWN_VALUES["A706"]      # H: overridden
