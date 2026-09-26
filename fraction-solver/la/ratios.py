"""A third evidence channel: ration ratios.

Some tablets record a headcount and the commodity issued to them. The ratio is a
ration, and it constrains fraction values without any total:

    PE 1   VIR 72  ...  A574 36        ->  ration = 1/2 per person
           VIR 50[ ...  A574 26 J      ->  (50 or more) x 1/2 = 26 + J

Corazza et al. use this tablet as one of three props for J = 1/2, restoring the
broken headcount as 53 on the editors' conjecture. We do better: leave the
headcount unknown, solve for it jointly with the fraction, and see whether the
requirement that a fraction be proper (strictly between 0 and 1) forces a unique
answer. It does — which turns an assumed restoration into a derived one.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

# Logogram readings that denote people, and so a headcount.
PERSON_READINGS = {"VIR", "MUL", "VIR+KA", "VIR+[?]"}


@dataclass
class Quantity:
    integer: int | None
    fractions: tuple[str, ...]
    broken: bool

    def value(self, values: dict[str, Fraction]) -> Fraction | None:
        total = Fraction(self.integer or 0)
        for f in self.fractions:
            if f not in values:
                return None
            total += values[f]
        return total


@dataclass
class RationPair:
    tablet: str
    headcount_line: int
    commodity_line: int
    commodity: str | None
    people: Quantity
    issued: Quantity

    @property
    def complete(self) -> bool:
        return not self.people.broken and not self.issued.broken and not self.issued.fractions

    def plausible(self, values: dict[str, Fraction], max_denominator: int = 12) -> bool | None:
        """Is the implied ration a simple amount a scribe would issue?

        Pairing a headcount line with the line below it is a guess about layout,
        and most guesses are wrong: a ration of 335/42 per person is not a ration,
        it is two unrelated lines. Requiring a small denominator filters those out
        without hand-picking tablets.
        """
        r = self.ration(values)
        if r is None:
            return None
        return 0 < r <= 10 and r.denominator <= max_denominator

    def ration(self, values: dict[str, Fraction]) -> Fraction | None:
        """Commodity per person, when everything is known and nothing is broken."""
        issued = self.issued.value(values)
        if issued is None or not self.people.integer:
            return None
        return issued / self.people.integer


def _scan_line(line: list[dict]) -> tuple[str | None, Quantity | None, bool]:
    """Return (logogram reading or id, quantity, is_person_line) for one line."""
    logogram = None
    integer: int | None = None
    fractions: list[str] = []
    broken = False
    is_person = False
    for i, token in enumerate(line):
        kind = token.get("kind")
        if kind == "sign":
            reading = (token.get("reading") or "").strip()
            if reading.upper() in PERSON_READINGS:
                is_person = True
                logogram = reading.upper()
            elif reading and not reading.islower():
                logogram = token.get("id") or reading
            elif token.get("id", "").startswith("A") and not reading:
                logogram = token.get("id")
        elif kind == "number":
            v = token.get("value")
            if isinstance(v, int):
                integer = v if integer is None else integer + v
        elif kind == "fraction" and token.get("id"):
            fractions.append(token["id"])
        elif kind == "damage":
            neighbours = line[max(0, i - 1): i + 2]
            if any(n.get("kind") in {"number", "fraction"} for n in neighbours):
                broken = True
    if integer is None and not fractions:
        return logogram, None, is_person
    return logogram, Quantity(integer, tuple(fractions), broken), is_person


def find_ration_pairs(doc: dict) -> list[RationPair]:
    """A headcount line followed by a commodity line is a ration statement."""
    lines = doc.get("lines") or []
    scanned = [_scan_line(line) for line in lines]
    pairs: list[RationPair] = []
    for i, (logo, qty, is_person) in enumerate(scanned):
        if not (is_person and qty and qty.integer):
            continue
        for j in range(i + 1, min(i + 2, len(scanned))):  # the very next line only
            logo2, qty2, is_person2 = scanned[j]
            if is_person2 or not qty2:
                continue
            pairs.append(
                RationPair(
                    tablet=doc.get("id", "?"),
                    headcount_line=i + 1,
                    commodity_line=j + 1,
                    commodity=logo2,
                    people=qty,
                    issued=qty2,
                )
            )
            break
    return pairs


def solve_broken_pair(
    pair: RationPair,
    ration: Fraction,
    unknown_sign: str,
    max_extra: int = 40,
) -> list[tuple[int, Fraction]]:
    """Given a known ration, find (headcount, fraction value) pairs that fit.

    The headcount is broken, so its surviving digits are a lower bound: `50[`
    means at least 50. Only solutions where the fraction is a *proper* fraction
    count, which is what makes the answer unique on PE 1.
    """
    solutions: list[tuple[int, Fraction]] = []
    base = pair.people.integer or 0
    issued_int = Fraction(pair.issued.integer or 0)
    n_unknown = sum(1 for f in pair.issued.fractions if f == unknown_sign)
    if not n_unknown:
        return solutions
    for people in range(base, base + max_extra + 1):
        # people * ration = issued_int + n_unknown * value
        value = (ration * people - issued_int) / n_unknown
        if 0 < value < 1:
            solutions.append((people, value))
    return solutions
