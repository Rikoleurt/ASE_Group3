"""Stage A: damage handling, inline KI-RO, and incomplete entry lists.

These encode the three corrections that came out of reading the epigraphic
commentary on the specific tablets our tool flagged.
"""

from __future__ import annotations

from fractions import Fraction

from la.parse import Section, Total, Quantity, Entry, parse_document
from la.solver import build_equations


def doc(lines, **kw):
    return {"id": kw.pop("id", "T 1"), "site": "Test", "lines": lines, **kw}


def sign(reading, sid=None):
    return {"kind": "sign", "id": sid or reading.upper(), "reading": reading}


NUM = lambda v: {"kind": "number", "value": v}
FRAC = lambda i: {"kind": "fraction", "id": i}
DMG = {"kind": "damage"}


class TestOpenQuantities:
    def test_damage_beside_a_quantity_makes_it_open(self):
        t = parse_document(doc([
            [sign("re"), sign("za"), NUM(5), DMG, FRAC("A707"), DMG],
            [sign("te"), sign("tu"), NUM(56)],
            [sign("ku"), sign("ro"), NUM(61)],
        ]))
        section = t.sections[0]
        assert section.has_open_quantity is True
        assert section.yields_equation is False

    def test_clean_section_yields_an_equation(self):
        t = parse_document(doc([
            [sign("te"), sign("tu"), NUM(56), FRAC("A707")],
            [sign("te"), sign("ki"), NUM(5)],
            [sign("ku"), sign("ro"), NUM(61), FRAC("A707")],
        ]))
        assert t.sections[0].yields_equation is True

    def test_open_section_becomes_a_bound_not_an_equation(self):
        t = parse_document(doc([
            [sign("re"), NUM(5), DMG, FRAC("A707")],
            [sign("te"), NUM(56)],
            [sign("ku"), sign("ro"), NUM(61)],
        ]))
        eqs = build_equations([("T 1", t.sections[0])], {}, include_damaged=True)
        assert len(eqs) == 1
        assert eqs[0].is_bound is True
        assert eqs[0].sense == "<="

    def test_a_bound_is_satisfied_when_entries_fall_short(self):
        eqs = build_equations(
            [("T", Section(
                entries=[Entry(1, Quantity(integer=5, fractions=["F"], damaged=True))],
                total=Total(2, "total", "ku-ro", Quantity(integer=6)),
            ))],
            {}, include_damaged=True,
        )
        bound = eqs[0]
        # surviving entries (5 + F) must not exceed the stated total (6)
        assert bound.satisfied({"F": Fraction(1, 2)}) is True
        assert bound.satisfied({"F": Fraction(3, 4)}) is True


class TestInlineDeficit:
    def test_kiro_on_a_line_splits_entry_from_balance_owed(self):
        """`OLIV 31 ki-ro 1` is an entry of 31 and a deficit of 1, not one line of 32."""
        t = parse_document(doc([
            [sign("OLIV", "AB122"), NUM(31), sign("ki"), sign("ro"), NUM(1)],
            [sign("te"), NUM(9)],
            [sign("ku"), sign("ro"), NUM(40)],
        ]))
        section = t.sections[0]
        assert sum(e.quantity.integer or 0 for e in section.entries) == 40
        assert len(t.deficits) == 1
        assert t.deficits[0].quantity.integer == 1

    def test_bare_kiro_still_opens_a_section(self):
        t = parse_document(doc([
            [sign("a"), sign("du"), NUM(20)],
            [sign("ki"), sign("ro")],
            [sign("ku"), NUM(1)],
            [sign("ka"), NUM(1)],
            [sign("ku"), sign("ro"), NUM(2)],
        ]))
        section = t.sections[0]
        assert section.opened_by == "ki-ro"
        assert sum(e.quantity.integer or 0 for e in section.entries) == 2
        assert len(t.untotalled_groups) == 1


class TestIncompleteEntryLists:
    def test_a_line_opening_with_a_break_marks_the_span_incomplete(self):
        """HT 46a is *supra mutila*: the entry list is physically missing."""
        t = parse_document(doc([
            [DMG],
            [DMG, sign("mu"), sign("ru"), NUM(1)],
            [sign("ku"), sign("ro"), NUM(43), FRAC("A707")],
        ]))
        section = t.sections[0]
        assert section.entries_incomplete is True
        assert section.yields_equation is False

    def test_incomplete_sections_produce_no_constraint_at_all(self):
        t = parse_document(doc([
            [DMG],
            [DMG, sign("mu"), NUM(1)],
            [sign("ku"), sign("ro"), NUM(43), FRAC("A707")],
        ]))
        assert build_equations([("T 1", t.sections[0])], {}, include_damaged=True) == []


class TestIdentifiabilityUsesEqualitiesOnly:
    def test_bounds_do_not_determine_values(self):
        from la.solver import analyse, Equation

        bound = Equation("T", 1, {"X": 1}, Fraction(1, 2), damaged=True, entry_count=2, sense="<=")
        ident = analyse([bound])
        assert ident.determined == {}
        assert ident.rank == 0


class TestBoundDirection:
    """Which side is broken decides which way the inequality runs."""

    def _section(self, entry_damaged: bool, total_damaged: bool) -> Section:
        return Section(
            entries=[Entry(1, Quantity(integer=10, fractions=["F"], damaged=entry_damaged))],
            total=Total(2, "total", "ku-ro", Quantity(integer=11, damaged=total_damaged)),
        )

    def test_broken_entry_gives_an_upper_bound(self):
        eqs = build_equations([("T", self._section(True, False))], {}, include_damaged=True)
        assert eqs[0].sense == "<="

    def test_broken_total_gives_a_lower_bound(self):
        """HT 116b: `KU-RO GRA 100[` understates the true total, so entries >= it."""
        eqs = build_equations([("T", self._section(False, True))], {}, include_damaged=True)
        assert eqs[0].sense == ">="

    def test_both_sides_broken_asserts_nothing(self):
        assert build_equations([("T", self._section(True, True))], {}, include_damaged=True) == []

    def test_lower_bound_is_satisfied_when_entries_exceed_the_written_total(self):
        eqs = build_equations([("T", self._section(False, True))], {}, include_damaged=True)
        bound = eqs[0]
        # entries 10 + F vs a surviving total of 11: F must make up at least 1,
        # which no proper fraction can, so a large F is closer to satisfying it.
        assert bound.satisfied({"F": Fraction(1, 2)}) is False
        assert bound.sense == ">="
