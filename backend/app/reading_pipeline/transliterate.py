"""Transliteration of detected signs, line by line, with a gloss of the words whose
meaning is agreed. Linear A is undeciphered: most words stay transliterated."""

from statistics import median
from typing import Sequence

from backend.app.reading_pipeline.formula import fmt, value_of

# Accounting words and commodity logograms whose meaning is agreed (read
# through Linear B); every other word is left as it is.
GLOSSES = {
    "ku-ro": "total", "po-to-ku-ro": "grand total", "ki-ro": "deficit",
    "VIN": "wine", "OLIV": "olives", "OLE": "oil", "FIC": "figs", "GRA": "grain",
    "OVIS": "sheep", "CAP": "goats", "SUS": "pigs", "BOS": "cattle", "VIR": "men",
    "TELA": "cloth", "AROM": "aromatics",
}

# A gap wider than this fraction of a typical sign's width ends a word: it is
# where a word divider or the (undetected) numerals of an entry sit.
WORD_GAP = 0.8


def token(sign) -> str:
    """How one sign is written: its syllable (ku), logogram (VIN) or fraction label (J)."""
    words = (sign.reading or "").split()
    if sign.role == "syllabogram":
        return next((word for word in words if word.islower()), sign.reading or sign.sign or "?")
    if sign.role == "logogram":
        return next((word for word in words if not word.islower()), sign.reading or sign.sign or "?")
    return sign.reading or sign.sign or "?"


def line_text(line: Sequence) -> tuple[str, str]:
    """(transliteration, gloss) of one line: syllables joined by hyphens into words."""
    words: list[tuple[str, str, object]] = []  # (word, role, its first sign)
    for previous, sign in zip([None, *line], line):
        if previous is not None and _joins(previous, sign, line):
            word, role, first = words[-1]
            words[-1] = (f"{word}-{token(sign)}", role, first)
        else:
            words.append((token(sign), sign.role, sign))
    text = " ".join(word for word, _, _ in words)
    gloss = " ".join(_gloss(word, role, first) for word, role, first in words)
    return text, gloss


def _joins(previous, sign, line: Sequence) -> bool:
    """Whether `sign` continues the word `previous` ends: two syllables close together."""
    if previous.role != "syllabogram" or sign.role != "syllabogram":
        return False
    gap = sign.box.x - (previous.box.x + previous.box.w)
    return gap <= WORD_GAP * median(s.box.w for s in line)


def _gloss(word: str, role: str, sign) -> str:
    if role == "fraction":
        value, _ = value_of(sign.sign)
        return fmt(value) if value is not None else word
    return GLOSSES.get(word, word)
