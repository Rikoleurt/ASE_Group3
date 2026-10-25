"""Worked examples for the reading pipeline: signs as the reader returns them,
laid out like a tablet (one row per line, left to right)."""

from fractions import Fraction
from types import SimpleNamespace

import pytest

from backend.app.reading_pipeline.formula import find_formulas, fmt, value_of
from backend.app.reading_pipeline.glyphs import glyph
from backend.app.reading_pipeline.lines import group_lines
from backend.app.reading_pipeline.transliterate import line_text

READINGS = {"AB81": "ku", "AB02": "ro", "AB11": "po", "AB05": "to", "AB59": "ta", "AB01": "da",
            "AB131a": "VIN", "A707": "J", "A704": "E", "A732": "JE", "A710": "W", "A706": "H"}
FRACTIONS = {"A707", "A704", "A732", "A710", "A706"}


def tablet(*rows: str):
    """Signs from rows of sign IDs: row r at y = r/10, each sign 0.08 wide with 0.02 gaps."""
    signs = []
    for row, text in enumerate(rows):
        for column, sign in enumerate(text.split()):
            signs.append(SimpleNamespace(
                id=len(signs) + 1, sign=sign, reading=READINGS.get(sign),
                role="fraction" if sign in FRACTIONS else "logogram" if sign == "AB131a" else "syllabogram",
                box=SimpleNamespace(x=column / 10, y=row / 10, w=0.08, h=0.06)))
    return signs


def formulas(*rows: str):
    return find_formulas(group_lines(tablet(*rows)))


def ids(lines):
    return [[sign.sign for sign in line] for line in lines]


# Lines


def test_signs_are_read_line_by_line_left_to_right():
    signs = tablet("AB59 AB01", "AB81 AB02")
    assert ids(group_lines(list(reversed(signs)))) == [["AB59", "AB01"], ["AB81", "AB02"]]


def test_a_slanting_line_stays_one_line():
    signs = tablet("AB59 AB01 AB81 AB02")
    for column, sign in enumerate(signs):
        sign.box.y += column * 0.01  # drifts down by 3/5 of a sign height over the line
    assert len(group_lines(signs)) == 1


def test_no_signs_no_lines():
    assert group_lines([]) == []


# Fraction formulas


def test_entries_that_add_up_to_the_total_balance():
    (formula,) = formulas("AB59 A707", "AB01 A704", "AB81 AB02 A732")  # J + E = JE
    assert formula.kind == "total"
    assert formula.verdict == "balances"
    assert (formula.entries_sum, formula.total_value) == (Fraction(3, 4), Fraction(3, 4))
    assert formula.lines == [0, 1, 2]
    assert formula.steps() == [
        "J = 1/2", "E = 1/4", "JE = 3/4",
        "Entries: J + E = 1/2 + 1/4 = 3/4", "KU-RO total: JE = 3/4", "The fractions balance",
    ]


def test_the_ht13_error_is_found():
    # HT 13: entries carry J and J, KU-RO says J. Younger: "KU-RO records 130.5, but the numbers total 131".
    (formula,) = formulas("AB59 A707", "AB01 A707", "AB81 AB02 A707")
    assert formula.verdict == "mismatch"
    assert formula.difference == Fraction(1, 2)
    assert formula.steps()[-1] == "The fractions are off by 1/2"


def test_whole_units_carried_into_the_numbers_still_balance():
    (formula,) = formulas("AB59 A707", "AB01 A707", "AB81 AB02")  # 1/2 + 1/2 = 1 whole, no fraction in the total
    assert formula.verdict == "balances"
    assert formula.carried == 1
    assert formula.steps()[-1] == "The fractions balance (1 whole carried)"


def test_a_sign_without_an_agreed_value_cannot_be_checked():
    (formula,) = formulas("AB59 A710", "AB81 AB02 A707")  # W has no agreed value
    assert formula.verdict == "incomplete"
    assert formula.difference is None
    assert formula.entries[0].label == "W"


def test_a_total_on_the_next_line_is_found():
    (formula,) = formulas("AB59 A707", "AB81 AB02", "A707")
    assert formula.verdict == "balances"
    assert formula.lines == [0, 1, 2]
    assert [term.line for term in formula.total] == [2]


def test_po_to_ku_ro_is_a_grand_total():
    (formula,) = formulas("AB59 A707", "AB11 AB05 AB81 AB02 A707")
    assert formula.kind == "grand_total"
    assert len(formula.marker_ids) == 4
    assert formula.steps()[-2] == "PO-TO-KU-RO total: J = 1/2"


def test_a_section_without_fractions_has_nothing_to_check():
    (formula,) = formulas("AB59 AB01", "AB81 AB02")
    assert formula.verdict == "no_fractions"


def test_each_ku_ro_closes_its_own_section():
    first, second = formulas("AB59 A707", "AB81 AB02 A707", "AB01 A704", "AB81 AB02 A707")
    assert (first.lines, first.verdict) == ([0, 1], "balances")
    assert (second.lines, second.verdict) == ([2, 3], "mismatch")
    assert second.difference == Fraction(1, 4)


def test_fractions_without_a_total_are_summed_as_a_group():
    (group,) = formulas("AB59 A707 A704")
    assert group.kind == "group"
    assert group.verdict is None
    assert group.entries_sum == Fraction(3, 4)
    assert group.steps()[-1] == "Sum: J + E = 1/2 + 1/4 = 3/4"


def test_a_tentative_value_is_flagged():
    (formula,) = formulas("AB59 A706", "AB81 AB02 A706")  # H = 1/16 is tentative
    assert formula.verdict == "balances"
    assert formula.tentative
    assert "tentative" in formula.note()


@pytest.mark.parametrize(("sign", "value"), [
    ("A707", Fraction(1, 2)), ("A732", Fraction(3, 4)), ("A717", Fraction(1, 3)), ("A710", None),
])
def test_fraction_values_come_from_the_published_table(sign, value):
    assert value_of(sign)[0] == value


@pytest.mark.parametrize(("value", "shown"), [
    (Fraction(1, 2), "1/2"), (Fraction(1), "1"), (Fraction(3, 2), "1 1/2"), (Fraction(0), "0"), (None, "?"),
])
def test_values_are_shown_as_mixed_numbers(value, shown):
    assert fmt(value) == shown


# Transliteration and glyphs


def test_syllables_close_together_form_one_word_and_known_words_are_glossed():
    (line,) = group_lines(tablet("AB131a AB81 AB02 A707"))
    assert line_text(line) == ("VIN ku-ro J", "wine total 1/2")


def test_a_wide_gap_ends_a_word():
    signs = tablet("AB59 AB01 AB81 AB02")
    for sign in signs[2:]:
        sign.box.x += 0.2  # the numerals of an entry sit here, unread
    assert line_text(group_lines(signs)[0])[0] == "ta-da ku-ro"


def test_a_mixed_reading_is_written_by_its_role():
    sign = SimpleNamespace(sign="AB30", reading="ni FIC", role="logogram",
                           box=SimpleNamespace(x=0, y=0, w=0.1, h=0.1))
    assert line_text([sign]) == ("FIC", "figs")
    sign.role = "syllabogram"
    assert line_text([sign])[0] == "ni"


@pytest.mark.parametrize(("sign", "codepoint"), [
    ("AB01", 0x10600), ("AB81", 0x10642), ("AB131a", 0x1064D), ("A707", 0x10746), ("A7092", 0x10749),
    ("A732", 0x10755), ("A400", 0x106A0),
])
def test_signs_have_their_unicode_glyph(sign, codepoint):
    assert glyph(sign) == chr(codepoint)


@pytest.mark.parametrize("sign", ["N800", "A517", "unidentified", None])
def test_signs_outside_unicode_have_no_glyph(sign):
    assert glyph(sign) is None
