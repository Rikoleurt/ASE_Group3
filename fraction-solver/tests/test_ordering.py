"""Tests for the ordering evidence channel."""

from __future__ import annotations

from collections import Counter
from fractions import Fraction

from la import ordering


def make_pairs(*pairs: tuple[str, str]) -> Counter:
    c = Counter()
    for p in pairs:
        c[p] += 1
    return c


class TestGraph:
    def test_transitive_closure_follows_chains(self):
        closure = ordering.transitive_closure(make_pairs(("J", "E"), ("E", "F")))
        assert ("J", "F") in closure
        assert ("J", "E") in closure and ("E", "F") in closure

    def test_cycle_detected(self):
        assert ordering.has_cycle(make_pairs(("A", "B"), ("B", "C"), ("C", "A"))) is True
        assert ordering.has_cycle(make_pairs(("A", "B"), ("B", "C"))) is False

    def test_contradiction_is_reported(self):
        ev = ordering.OrderEvidence(pairs=make_pairs(("A", "B"), ("B", "A")))
        assert ev.contradictions() == [(("A", "B"), 1, 1)]

    def test_repeated_sign_is_not_evidence(self):
        ev = ordering.OrderEvidence(pairs=make_pairs(("B", "B")))
        assert sum(ev.heterogeneous_pairs.values()) == 0


class TestValueChecking:
    def test_respecting_and_violating_pairs(self):
        values = {"J": Fraction(1, 2), "E": Fraction(1, 4), "K": Fraction(1, 10)}
        result = ordering.check_against_values(make_pairs(("J", "E"), ("E", "K"), ("K", "J")), values)
        assert result["checked"] == 3
        assert result["respected"] == 2
        assert result["violations"][0]["pair"] == ("K", "J")


class TestBounds:
    def test_unknown_sign_is_bounded_from_both_sides(self):
        # J > X > K, so X lies strictly between 1/10 and 1/2.
        pairs = make_pairs(("J", "X"), ("X", "K"))
        values = {"J": Fraction(1, 2), "K": Fraction(1, 10)}
        candidates = [Fraction(n, 60) for n in range(1, 60)]
        bounds = ordering.bound_unknowns(pairs, values, candidates)
        assert bounds["X"]["upper_bound"] == "1/2"
        assert bounds["X"]["lower_bound"] == "1/10"
        remaining = bounds["X"]["candidates_remaining"]
        assert 0 < remaining < len(candidates)

    def test_run_extraction_from_documents(self):
        doc = {
            "id": "T 1",
            "site": "Test",
            "lines": [[
                {"kind": "number", "value": 5},
                {"kind": "fraction", "id": "J"},
                {"kind": "fraction", "id": "E"},
                {"kind": "divider"},
                {"kind": "fraction", "id": "K"},
            ]],
        }
        ev = ordering.collect({"T 1": doc})
        assert len(ev.runs) == 1  # the divider ends the run, so K is not part of it
        assert ev.runs[0][2] == ["J", "E"]
        assert ev.pairs[("J", "E")] == 1


class TestDecomposition:
    """Compound signs are written as their parts; the encoding must not hide that."""

    def _doc(self, frac_ids):
        return {"id": "T 1", "site": "Test",
                "lines": [[{"kind": "fraction", "id": f} for f in frac_ids]]}

    def test_compound_expands_into_its_parts(self):
        ev = ordering.collect({"T 1": self._doc(["A732"])})  # JE
        assert ev.runs[0][2] == ["A707", "A704"]             # J then E
        assert ev.pairs[("A707", "A704")] == 1

    def test_raw_encoding_can_still_be_inspected(self):
        ev = ordering.collect({"T 1": self._doc(["A732"])}, decompose=False)
        assert ev.runs == []  # a single token is not a run of two

    def test_both_encodings_of_DD_give_the_same_evidence(self):
        as_one = ordering.collect({"T 1": self._doc(["A717", "A7092"])})
        as_two = ordering.collect({"T 1": self._doc(["A703", "A703", "A7092"])})
        assert as_one.pairs == as_two.pairs


class TestDominantDirection:
    def test_overwhelming_majority_overrules_a_single_counterexample(self):
        ev = ordering.OrderEvidence(pairs=Counter({("J", "E"): 32, ("E", "J"): 1}))
        kept, overruled = ev.dominant_pairs()
        assert kept == Counter({("J", "E"): 32})
        assert overruled[0]["dropped"] == ("E", "J")
        assert overruled[0]["dropped_count"] == 1

    def test_a_close_call_is_dropped_rather_than_guessed(self):
        ev = ordering.OrderEvidence(pairs=Counter({("A", "B"): 3, ("B", "A"): 2}))
        kept, overruled = ev.dominant_pairs()
        assert kept == Counter()
        assert overruled[0]["kept"] is None

    def test_uncontested_pairs_pass_through(self):
        ev = ordering.OrderEvidence(pairs=Counter({("A", "B"): 1}))
        kept, _ = ev.dominant_pairs()
        assert kept == Counter({("A", "B"): 1})
