"""Worked examples for the reading pipeline: signs as the reader returns them,
laid out like a tablet (one row per line, left to right)."""

from types import SimpleNamespace

import pytest

from backend.app.reading_pipeline.glyphs import glyph
from backend.app.reading_pipeline.lines import group_lines

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


# Glyphs


@pytest.mark.parametrize(("sign", "codepoint"), [
    ("AB01", 0x10600), ("AB81", 0x10642), ("AB131a", 0x1064D), ("A707", 0x10746), ("A7092", 0x10749),
    ("A732", 0x10755), ("A400", 0x106A0),
])
def test_signs_have_their_unicode_glyph(sign, codepoint):
    assert glyph(sign) == chr(codepoint)


@pytest.mark.parametrize("sign", ["N800", "A517", "unidentified", None])
def test_signs_outside_unicode_have_no_glyph(sign):
    assert glyph(sign) is None
