"""Boundary cases of the solver that the planted-value tests do not reach."""

from __future__ import annotations

from fractions import Fraction

import pytest

from la.solver import Equation, analyse


def eq(coeffs: dict[str, int], constant: Fraction, sense: str = "=") -> Equation:
    return Equation("T", 1, coeffs, constant, damaged=False, entry_count=2, sense=sense)


def test_empty_system_determines_nothing():
    ident = analyse([])
    assert ident.consistent
    assert (ident.rank, ident.free_dimensions, ident.determined) == (0, 0, {})


def test_bounds_alone_do_not_count_toward_rank():
    ident = analyse([eq({"X": 1}, Fraction(1, 2), "<="), eq({"X": 1}, Fraction(1, 3), ">=")])
    assert ident.unknowns == ["X"]
    assert ident.rank == 0
    assert ident.free_dimensions == 1
    assert ident.determined == {}


def test_trivial_equations_are_ignored_by_the_rank():
    ident = analyse([eq({}, Fraction(0)), eq({"X": 2}, Fraction(1))])
    assert ident.rank == 1
    assert ident.determined == {"X": Fraction(1, 2)}


def test_duplicate_equations_do_not_inflate_the_rank():
    ident = analyse([eq({"X": 1, "Y": 1}, Fraction(1, 2))] * 3)
    assert ident.rank == 1
    assert ident.free_dimensions == 1


@pytest.mark.parametrize("sense,constant,expected", [
    ("=", Fraction(2), False),    # reach of 2X is < 2, so it cannot balance
    ("=", Fraction(-2), False),
    ("=", Fraction(199, 100), True),
    ("<=", Fraction(-2), False),  # entries cannot sum below -reach
    ("<=", Fraction(-199, 100), True),
    (">=", Fraction(2), False),   # entries cannot reach a total of 2
    (">=", Fraction(199, 100), True),
])
def test_satisfiable_respects_the_reach_boundary(sense, constant, expected):
    assert eq({"X": 2}, constant, sense).satisfiable is expected


@pytest.mark.parametrize("constant,expected", [(Fraction(0), True), (Fraction(1, 2), False)])
def test_trivial_equation_is_satisfiable_only_when_it_balances(constant, expected):
    assert eq({}, constant).satisfiable is expected


def test_residual_is_unknown_when_a_value_is_missing():
    equation = eq({"X": 1, "Y": 1}, Fraction(1, 2))
    assert equation.residual({"X": Fraction(1, 4)}) is None
    assert equation.satisfied({"X": Fraction(1, 4)}) is None


@pytest.mark.parametrize("sense,value,expected", [
    ("=", Fraction(1, 2), True), ("=", Fraction(1, 3), False),
    ("<=", Fraction(1, 3), True), ("<=", Fraction(2, 3), False),
    (">=", Fraction(2, 3), True), (">=", Fraction(1, 3), False),
])
def test_satisfied_follows_the_sense(sense, value, expected):
    assert eq({"X": 1}, Fraction(1, 2), sense).satisfied({"X": value}) is expected
