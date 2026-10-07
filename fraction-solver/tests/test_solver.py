"""Solver tests on synthetic systems whose answers are known in advance.

These run without any corpus data: they test the method, not Linear A. If the
solver cannot recover planted values here, no result it produces on the real
corpus can be trusted.
"""

from __future__ import annotations

from fractions import Fraction

from la.solver import (
    Equation,
    analyse,
    build_equations,
    candidate_values,
    enumerate_assignments,
    null_model,
)
from la.parse import Entry, Quantity, Section, Total


def eq(name: str, coeffs: dict[str, int], constant: Fraction) -> Equation:
    return Equation(name, 1, coeffs, constant, damaged=False, entry_count=3)


class TestIdentifiability:
    def test_recovers_planted_values(self):
        # X = 1/3, Y = 1/5
        system = [
            eq("T1", {"X": 3}, Fraction(1)),
            eq("T2", {"Y": 5}, Fraction(1)),
            eq("T3", {"X": 3, "Y": 5}, Fraction(2)),
        ]
        ident = analyse(system)
        assert ident.consistent
        assert ident.rank == 2
        assert ident.free_dimensions == 0
        assert ident.determined == {"X": Fraction(1, 3), "Y": Fraction(1, 5)}

    def test_reports_underdetermination_instead_of_guessing(self):
        ident = analyse([eq("T", {"X": 1, "Y": 1}, Fraction(1, 2))])
        assert ident.consistent
        assert ident.determined == {}
        assert ident.free_dimensions == 1
        assert len(ident.nullspace) == 1

    def test_detects_inconsistency(self):
        ident = analyse([eq("a", {"X": 1}, Fraction(1, 2)), eq("b", {"X": 1}, Fraction(1, 3))])
        assert ident.consistent is False
        assert ident.determined == {}

    def test_partial_identifiability(self):
        """One value pinned down, another only constrained."""
        system = [
            eq("T1", {"X": 2}, Fraction(1)),
            eq("T2", {"Y": 1, "Z": 1}, Fraction(1, 2)),
        ]
        ident = analyse(system)
        assert ident.determined == {"X": Fraction(1, 2)}
        assert "Y" not in ident.determined and "Z" not in ident.determined
        assert ident.free_dimensions == 1


class TestEnumeration:
    def test_best_assignment_is_the_planted_one(self):
        system = [
            eq("T1", {"X": 3}, Fraction(1)),
            eq("T2", {"Y": 5}, Fraction(1)),
            eq("T3", {"X": 3, "Y": 5}, Fraction(2)),
        ]
        grid = [Fraction(1, 2), Fraction(1, 3), Fraction(1, 4), Fraction(1, 5), Fraction(1, 6)]
        ranked = enumerate_assignments(system, ["X", "Y"], grid=grid)
        best, hits = ranked[0]
        assert hits == 3
        assert best == {"X": Fraction(1, 3), "Y": Fraction(1, 5)}

    def test_candidate_grid_defaults_to_unit_fractions(self):
        """The published values are all unit fractions, so that is the default space."""
        values = candidate_values((2, 3, 4))
        assert values == [Fraction(1, 4), Fraction(1, 3), Fraction(1, 2)]

    def test_candidate_grid_can_widen_to_all_proper_fractions(self):
        values = candidate_values((2, 3, 4), unit_only=False)
        assert all(0 < v < 1 for v in values)
        assert Fraction(2, 3) in values and Fraction(3, 4) in values


class TestNullModel:
    def test_random_assignments_sometimes_satisfy_equations(self):
        """The point of the null model: chance agreement is not zero."""
        system = [eq("T1", {"X": 1}, Fraction(1, 2))]
        grid = [Fraction(1, 2), Fraction(1, 3), Fraction(1, 4)]
        stats = null_model(system, ["X"], trials=300, grid=grid)
        assert stats["trials"] == 300
        assert 0 < stats["mean"] < 1  # roughly 1 in 3 by chance
        assert stats["max"] == 1


class TestEquationBuilding:
    def _section(self, entry_specs, total_spec):
        entries = [
            Entry(line_no=i + 1, quantity=Quantity(integer=n, fractions=list(f)))
            for i, (n, f) in enumerate(entry_specs)
        ]
        n, f = total_spec
        total = Total(
            line_no=len(entries) + 1,
            kind="total",
            marker="ku-ro",
            quantity=Quantity(integer=n, fractions=list(f)),
        )
        return Section(entries=entries, total=total)

    def test_known_values_move_to_the_constant(self):
        # entries 10 + F, total 10; F known = 1/2  ->  no unknowns, constant -1/2
        section = self._section([(10, ["F"]), (0, [])], (10, []))
        equations = build_equations([("T", section)], {"F": Fraction(1, 2)})
        assert len(equations) == 1
        assert equations[0].is_trivial
        assert equations[0].constant == Fraction(-1, 2)

    def test_signs_cancelling_on_both_sides_are_dropped(self):
        section = self._section([(5, ["F"]), (5, [])], (10, ["F"]))
        equations = build_equations([("T", section)], {})
        assert equations[0].coefficients == {}
        assert equations[0].constant == 0

    def test_damaged_sections_excluded_by_default(self):
        section = self._section([(5, ["F"]), (5, [])], (10, []))
        section.entries[0].quantity.damaged = True
        assert build_equations([("T", section)], {}) == []
        assert len(build_equations([("T", section)], {}, include_damaged=True)) == 1

    def test_integer_only_sections_produce_no_equation(self):
        section = self._section([(5, []), (5, [])], (10, []))
        assert build_equations([("T", section)], {}) == []
