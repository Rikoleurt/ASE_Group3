"""Fraction formulas found among detected signs, and whether their fractions balance.

A Linear A account lists entries, each a whole number followed by fraction
signs, and closes with KU-RO ("total") followed by the total. The detector
reads the fraction signs and KU-RO but not the tally strokes of the whole
numbers. So the check is on fractions alone, modulo 1: the entries' fractions
must add up to the total's fraction plus some number of whole units, which
carry into the whole numbers where they cannot be seen.

Example, HT 13: the entries carry J and J (1/2 + 1/2 = 1, so 0 modulo 1) and
KU-RO is followed by J (1/2). The fractions are off by 1/2, which is the
scribe's known error: the entries total 131, the total says 130 1/2.
"""

import sys
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Sequence

FRACTION_SOLVER = Path(__file__).resolve().parents[3] / "fraction-solver"
if str(FRACTION_SOLVER) not in sys.path:
    sys.path.insert(0, str(FRACTION_SOLVER))  # as backend.app.reading does: not an installed package
from la import values  # noqa: E402

KU, RO, PO, TO = "AB81", "AB02", "AB11", "AB05"
CARRY_NOTE = "Whole numbers (tally strokes) are not read, so the check is on fractions only."


@dataclass
class Term:
    id: int  # the detected sign's id
    sign: str
    label: str  # J, E, ...
    value: Fraction | None  # None for signs without an agreed value (W, X, Y, Ω, L)
    tentative: bool
    line: int


@dataclass
class Formula:
    kind: str  # "total" (KU-RO), "grand_total" (PO-TO-KU-RO) or "group" (fractions without a total)
    lines: list[int]
    sign_ids: list[int]  # every sign in the formula, for its bounding box
    entries: list[Term]
    total: list[Term] = field(default_factory=list)
    marker_ids: list[int] = field(default_factory=list)  # the KU-RO signs themselves

    @property
    def entries_sum(self) -> Fraction | None:
        return _sum(self.entries)

    @property
    def total_value(self) -> Fraction | None:
        return _sum(self.total) if self.kind != "group" else None

    @property
    def tentative(self) -> bool:
        return any(term.tentative for term in self.entries + self.total)

    @property
    def verdict(self) -> str | None:
        """balances, mismatch, incomplete (a sign without a value), no_fractions, or None for a group."""
        if self.kind == "group":
            return None
        if not self.entries and not self.total:
            return "no_fractions"
        if self.entries_sum is None or self.total_value is None:
            return "incomplete"
        return "balances" if (self.entries_sum - self.total_value) % 1 == 0 else "mismatch"

    @property
    def difference(self) -> Fraction | None:
        """How far the fractions are off, modulo 1, as the smaller of the two ways round."""
        if self.verdict not in ("balances", "mismatch"):
            return None
        off = (self.entries_sum - self.total_value) % 1
        return min(off, 1 - off)

    @property
    def carried(self) -> int:
        """Whole units the entries' fractions add beyond the total's, when they balance."""
        if self.verdict != "balances":
            return 0
        return int(self.entries_sum - self.total_value)

    def steps(self) -> list[str]:
        """The working, one line per step, for the page to reveal in turn."""
        shown = list(dict.fromkeys(f"{term.label} = {fmt(term.value)}" for term in self.entries + self.total))
        if self.kind == "group":
            return shown + [f"Sum: {_plus(self.entries)} = {fmt(self.entries_sum)}"]
        marker = "PO-TO-KU-RO" if self.kind == "grand_total" else "KU-RO"
        shown.append(f"Entries: {_plus(self.entries) or 'no fractions'} = {fmt(self.entries_sum or 0)}")
        shown.append(f"{marker} total: {_plus(self.total) or 'no fraction'} = {fmt(self.total_value or 0)}")
        if self.verdict == "balances":
            shown.append("The fractions balance" + (f" ({self.carried} whole carried)" if self.carried else ""))
        elif self.verdict == "mismatch":
            shown.append(f"The fractions are off by {fmt(self.difference)}")
        elif self.verdict == "incomplete":
            shown.append("A fraction sign has no agreed value, so the balance cannot be checked")
        return shown

    def note(self) -> str:
        notes = [CARRY_NOTE]
        if self.tentative:
            notes.append("Uses a tentative value (H = 1/16 or A = 1/24).")
        return " ".join(notes)


def find_formulas(lines: Sequence[Sequence]) -> list[Formula]:
    """KU-RO sections, then any other line with fraction signs as a group.

    `lines` are signs in reading order (see lines.group_lines); each sign has
    `id`, `sign`, `reading` and `role`. A section runs from the line after the
    previous total to the KU-RO line. Its total is the fraction signs after
    KU-RO on that line, or the next line if that line holds only fractions.
    """
    formulas: list[Formula] = []
    start = 0
    index = 0
    while index < len(lines):
        found = _ku_ro(lines[index])
        if found is None:
            index += 1
            continue
        at, kind, markers = found
        line = lines[index]
        total_line = [sign for sign in line[at + 2:] if sign.role == "fraction"]
        last = index
        if not total_line and index + 1 < len(lines) and all(s.role == "fraction" for s in lines[index + 1]):
            last = index + 1
            total_line = list(lines[last])
        entries = [sign for number in range(start, index) for sign in lines[number] if sign.role == "fraction"]
        entries += [sign for sign in line[:at] if sign.role == "fraction"]
        formulas.append(Formula(
            kind=kind,
            lines=list(range(start, last + 1)),
            sign_ids=[sign.id for number in range(start, last + 1) for sign in lines[number]],
            entries=[_term(sign, lines) for sign in entries],
            total=[_term(sign, lines) for sign in total_line],
            marker_ids=[sign.id for sign in markers],
        ))
        start = index = last + 1
    covered = {number for formula in formulas for number in formula.lines}
    for number, line in enumerate(lines):
        fractions = [sign for sign in line if sign.role == "fraction"]
        if number not in covered and fractions:
            formulas.append(Formula(kind="group", lines=[number], sign_ids=[sign.id for sign in line],
                                    entries=[_term(sign, lines) for sign in fractions]))
    return formulas


def value_of(sign: str) -> tuple[Fraction | None, bool]:
    """(value, tentative) of a fraction sign; combinations such as JE add up their parts."""
    parts = values.decompose(sign)
    if sign in values.KNOWN_VALUES:
        value = values.KNOWN_VALUES[sign]
    elif all(part in values.KNOWN_VALUES for part in parts):
        value = sum((values.KNOWN_VALUES[part] for part in parts), Fraction(0))
    else:
        value = None
    tentative = bool({sign, *parts} & set(values.tentative_signs()))
    return value, tentative


def fmt(value: Fraction | None) -> str:
    """1/2, 3/4, 1, 1 1/2; '?' when unknown."""
    if value is None:
        return "?"
    whole, part = divmod(value, 1)
    if not part:
        return str(int(whole))
    return f"{int(whole)} {part}" if whole else str(part)


def _ku_ro(line: Sequence) -> tuple[int, str, list] | None:
    """(index of KU, kind, marker signs) for the first KU-RO in a line."""
    ids = [sign.sign for sign in line]
    for at in range(len(ids) - 1):
        if ids[at] == KU and ids[at + 1] == RO:
            if at >= 2 and ids[at - 2:at] == [PO, TO]:
                return at, "grand_total", list(line[at - 2:at + 2])
            return at, "total", list(line[at:at + 2])
    return None


def _term(sign, lines: Sequence[Sequence]) -> Term:
    value, tentative = value_of(sign.sign)
    line = next(number for number, signs in enumerate(lines) if sign in signs)
    label = values.LABELS.get(sign.sign) or values.OPEN_SIGNS.get(sign.sign) or sign.reading or sign.sign
    return Term(id=sign.id, sign=sign.sign, label=label, value=value, tentative=tentative, line=line)


def _sum(terms: list[Term]) -> Fraction | None:
    if any(term.value is None for term in terms):
        return None
    return sum((term.value for term in terms), Fraction(0))


def _plus(terms: list[Term]) -> str:
    """"J + E = 1/2 + 1/4" (one sign: "J"), or "" with no terms."""
    if not terms:
        return ""
    labels = " + ".join(term.label for term in terms)
    return labels if len(terms) == 1 else f"{labels} = {' + '.join(fmt(term.value) for term in terms)}"
