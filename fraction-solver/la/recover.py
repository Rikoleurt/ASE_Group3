"""Which damaged numerals are *uniquely* recoverable from surviving arithmetic?

When a break has swallowed part of a quantity, the tablet's own total sometimes
forces exactly one reading. That is a different kind of claim from anything the
restoration literature currently makes, and the distinction is the point of this
module:

* **Ithaca** (Assael et al., *Nature* 603, 2022) restores Greek inscriptions
  probabilistically, ranking a top-20 from a 35,884-word vocabulary. It handles no
  numerals at all.
* **Born, Monroe, Kelley & Sarkar** (CAWL 2023) come closest: a subset-sum solver
  over proto-Elamite summary tablets, used to *disambiguate* which metrological
  reading an intact numeral carries. They explicitly discard damaged numerals.
  Arithmetic disambiguates there; it never restores.
* Nobody, as far as a targeted search could establish, separates *uniquely
  determined* from *probabilistically suggested* for a numeral. There is no term for
  it in the literature.

So the output here is not a ranking. It is a verdict per damaged quantity, and the
verdict that matters is `UNIQUE`: given the total, the writing conventions, and where
the break falls, only one amount can ever have stood there.

**What makes uniqueness possible** is that an amount is not a free number — it is a
sequence of signs obeying two conventions, which together make most values
unwriteable in a given gap:

1. **Writing order.** Units descend. A break after `S 2` can hide more S strokes, or
   V and Z after them, but never a whole unit, because that would have been written
   first.
2. **Bundling.** Six V make a T, so a scribe writes `T 1 V 1`, not `V 7`. Counts stay
   below the bundling cap. Born et al. treat violations of exactly this as scribal
   error.

Both conventions are reported twice — `strict` (canonical, counts under the cap) and
`relaxed` (bundling violations permitted) — because a conclusion that holds only
under the strict reading is a weaker conclusion, and saying so is cheaper than being
caught.

The same machinery runs on Linear A through `FractionNotation`, where the "units" are
fraction signs and the ordering convention is the decreasing-value rule established
in `la.ordering`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Protocol

# ---------------------------------------------------------------------------
# Notation: what counts as a legal amount
# ---------------------------------------------------------------------------


class Notation(Protocol):
    """A way of writing amounts as an ordered sequence of (sign, count) terms."""

    def units(self) -> tuple[str, ...]:
        """Signs in writing order, largest value first."""

    def size(self, unit: str) -> Fraction:
        """The value of one of `unit`."""

    def cap(self, unit: str) -> int | None:
        """The count at which a scribe carries to the next unit up, or None."""


@dataclass(frozen=True)
class MetricNotation:
    """Linear B: a `metrology.Series` of units with bundling caps."""

    series: object  # la.lb.metrology.Series

    def units(self) -> tuple[str, ...]:
        return tuple(self.series.units)  # type: ignore[attr-defined]

    def size(self, unit: str) -> Fraction:
        return Fraction(self.series.in_smallest(unit))  # type: ignore[attr-defined]

    def cap(self, unit: str) -> int | None:
        return self.series.bundling_cap(unit)  # type: ignore[attr-defined]


@dataclass(frozen=True)
class CountNotation:
    """A counted commodity — sheep, men, cloth — with no subunits at all.

    Every positive integer is a legal amount, so exactly one reading balances any
    given shortfall. That makes lost headcounts the easiest recoverable class in the
    corpus and worth separating in the results: "the lost entry recorded five men" is
    a determination, but a cheap one, and pooling it with the metrological cases would
    flatter the method.
    """

    unit: str = "UNIT"

    def units(self) -> tuple[str, ...]:
        return (self.unit,)

    def size(self, unit: str) -> Fraction:
        return Fraction(1)

    def cap(self, unit: str) -> int | None:
        return None


WHOLE = "UNIT"  # the whole commodity unit, written as an ordinary numeral


@dataclass(frozen=True)
class FractionNotation:
    """Linear A: a whole-unit numeral followed by fraction signs in decreasing value.

    Two conventions carry the constraint here, and neither is as strong as Linear B's
    bundling rule, so Linear A results are correspondingly weaker:

    * **Order.** Fractions are written in decreasing value, which is the convention
      established from the corpus in `la.ordering` (25 checkable sign pairs, none
      attested in both directions). A break at the end of a quantity can therefore hide
      only signs *smaller* than the last one still visible — which is what makes some
      gaps uniquely fillable.
    * **Repetition.** There is no carrying rule: a scribe may write `D D` for a third.
      `repeat_limit` is therefore a declared assumption, not a metrological fact, and any
      count that depends on it has to be reported against it. Two is the usual observed
      maximum (`D D`, `B B`, `J J`).

    The whole unit heads the chain with no cap, so a break after a bare integer can hide
    both further units and any fraction, while a break after a fraction sign cannot bring
    back a whole unit.
    """

    values: dict[str, Fraction]
    repeat_limit: int = 2

    def units(self) -> tuple[str, ...]:
        return (WHOLE,) + tuple(sorted(self.values, key=lambda s: -self.values[s]))

    def size(self, unit: str) -> Fraction:
        return Fraction(1) if unit == WHOLE else self.values[unit]

    def cap(self, unit: str) -> int | None:
        return None if unit == WHOLE else self.repeat_limit


# ---------------------------------------------------------------------------
# Addenda: what a break can legally hide
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Addendum:
    """One legal way the missing text could have read.

    `extend` is extra count on the last surviving sign — strokes lost inside the
    numeral itself. `appended` is whole new terms after it. Both are needed: a break
    after `S 1` can hide `S 2` (extend) or `S 1 V 3` (append) or `S 2 V 3` (both),
    and these are different claims about the clay.
    """

    extend: int = 0
    appended: tuple[tuple[str, int], ...] = ()
    value: Fraction = Fraction(0)
    canonical: bool = True

    def describe(self, last_unit: str | None) -> str:
        parts = []
        if self.extend and last_unit:
            parts.append(f"+{self.extend} {last_unit}")
        parts += [f"{u} {c}" for u, c in self.appended]
        return " ".join(parts) or "nothing"


MAX_ADDENDA = 20_000  # a safety bound; exceeding it is reported, never silently truncated

#: How often one sign may repeat once the carry rule is switched off.
#:
#: Relaxing the rule is the sensitivity check — a scribe who violated bundling would write
#: `V 7` — but with no cap at all the search is unbounded: sixteen Linear A fraction signs
#: down to 1/60 admit astronomically many ways to make up a shortfall, and the enumeration
#: does not terminate in useful time. Six is well past anything attested (two is the
#: observed maximum) while keeping the relaxed figure computable, and it is a declared
#: assumption rather than a fact about the script.
RELAXED_MAX_COUNT = 6


def addenda_up_to(
    surviving: list[tuple[str, int]],
    notation: Notation,
    limit: Fraction,
    strict: bool = True,
    max_new_terms: int = 3,
) -> list[Addendum]:
    """Every legal continuation of `surviving` whose value is at most `limit`.

    The break falls at the *end* of what survives, which is what `1[` records, so only
    signs at or below the last surviving sign may appear: anything larger would have been
    written earlier and would therefore have survived.

    Values up to a bound rather than one exact target, because a section with two broken
    entries can have the missing amount *split* between them. Enumerating only the exact
    residual per gap silently assumes one gap absorbed all of it — which on KN Fp 1 gave
    "one S, in one of two gaps" and missed that three V in each gap balances just as well.
    """
    if limit <= 0:
        return []
    units = notation.units()
    last_unit = surviving[-1][0] if surviving else None
    last_count = surviving[-1][1] if surviving else 0

    if last_unit is None:
        start = -1  # nothing survives: any sign could have stood there
    elif last_unit not in units:
        return []
    else:
        start = units.index(last_unit)

    found: list[Addendum] = []

    if last_unit is None:
        extend_options = [0]
    else:
        size = notation.size(last_unit)
        cap = notation.cap(last_unit)
        top = int(limit / size) if size else 0
        if strict and cap is not None:
            top = min(top, max(cap - 1 - last_count, 0))
        extend_options = list(range(0, top + 1))

    for extend in extend_options:
        consumed = extend * notation.size(last_unit) if last_unit else Fraction(0)
        if consumed > limit:
            continue
        for terms, value in _append_combinations(
            units, start + 1, limit - consumed, notation, strict, max_new_terms
        ):
            if extend == 0 and not terms:
                continue  # the empty addendum adds nothing
            found.append(
                Addendum(
                    extend=extend,
                    appended=tuple(terms),
                    value=consumed + value,
                    canonical=_is_canonical(last_unit, last_count + extend, terms, notation),
                )
            )
            if len(found) > MAX_ADDENDA:
                return found
    return found


def legal_addenda(
    surviving: list[tuple[str, int]],
    notation: Notation,
    target: Fraction,
    strict: bool = True,
    max_new_terms: int = 3,
) -> list[Addendum]:
    """Legal continuations of `surviving` worth exactly `target`."""
    return [
        a for a in addenda_up_to(surviving, notation, target, strict, max_new_terms)
        if a.value == target
    ]


def _append_combinations(
    units: tuple[str, ...],
    index: int,
    remaining: Fraction,
    notation: Notation,
    strict: bool,
    budget: int,
) -> list[tuple[list[tuple[str, int]], Fraction]]:
    """Descending-unit search for term lists worth at most `remaining`, with their values.

    Pruned on value, so the search stays small even with generous caps.
    """
    if remaining < 0 or index >= len(units) or budget == 0:
        return [([], Fraction(0))]

    out: list[tuple[list[tuple[str, int]], Fraction]] = []
    unit = units[index]
    size = notation.size(unit)
    cap = notation.cap(unit)
    max_count = int(remaining / size) if size else 0
    if strict and cap is not None:
        max_count = min(max_count, cap - 1)
    else:
        max_count = min(max_count, RELAXED_MAX_COUNT)

    for count in range(0, max_count + 1):
        spent = count * size
        if spent > remaining:
            break
        sub_budget = budget - 1 if count else budget
        for tail, tail_value in _append_combinations(
            units, index + 1, remaining - spent, notation, strict, sub_budget
        ):
            out.append((([(unit, count)] if count else []) + tail, spent + tail_value))
    return out


def _is_canonical(
    last_unit: str | None,
    last_total: int,
    terms: list[tuple[str, int]],
    notation: Notation,
) -> bool:
    """Would a scribe have written it this way, or carried to a larger unit?"""
    if last_unit is not None:
        cap = notation.cap(last_unit)
        if cap is not None and last_total >= cap:
            return False
    for unit, count in terms:
        cap = notation.cap(unit)
        if cap is not None and count >= cap:
            return False
    return True


# ---------------------------------------------------------------------------
# Verdicts
# ---------------------------------------------------------------------------

BALANCED = "BALANCED"
UNIQUE = "UNIQUE"
AMOUNT_DETERMINED = "AMOUNT_DETERMINED"
AMBIGUOUS = "AMBIGUOUS"
IMPOSSIBLE = "IMPOSSIBLE"
ERROR_NO_DAMAGE = "ERROR_NO_DAMAGE"
OVERFULL = "OVERFULL"
UNRESOLVED = "UNRESOLVED"

#: What each verdict licenses a reader to say. Printed with every result, because the
#: distinction between a determination and a suggestion is the whole contribution, and it
#: is exactly what a summary table loses.
#:
#: `AMOUNT_DETERMINED` is stated carefully on purpose. Where a section has a single gap,
#: the missing amount follows from the arithmetic alone and is therefore *trivially*
#: determined — no notation needed. Calling that a "uniquely recoverable numeral" would be
#: an overclaim. What the notation contributes is narrower and real: it says whether the
#: amount is writeable in that gap at all (`IMPOSSIBLE` when not), which signs can have
#: expressed it (`UNIQUE` when only one spelling works), and, with several gaps, how the
#: shortfall can be divided between them.
VERDICT_MEANING: dict[str, str] = {
    BALANCED: "Arithmetic already balances; the break hid nothing countable.",
    UNIQUE: (
        "Exactly one legal restoration: one amount, one place, one spelling. "
        "The signs that stood in the gap are determined."
    ),
    AMOUNT_DETERMINED: (
        "Every gap's amount is fixed, but more than one set of signs could express it. "
        "With a single gap this follows from the arithmetic alone and is not a "
        "contribution of the notation."
    ),
    AMBIGUOUS: (
        "The shortfall can be divided between the gaps in more than one way, so no gap's "
        "amount is determined. A constraint, not a restoration."
    ),
    IMPOSSIBLE: (
        "No legal amount balances this section, so the break cannot explain it: "
        "either the scribe erred or a reading is wrong."
    ),
    ERROR_NO_DAMAGE: "Nothing is broken and it still does not balance: a scribal error.",
    OVERFULL: "Entries exceed an intact total; a break cannot subtract.",
    UNRESOLVED: "Units or commodity could not be resolved; no claim made.",
}


@dataclass
class Candidate:
    """One restoration hypothesis: what each gap gained, across the whole section."""

    parts: tuple[tuple[str, str | None, Addendum], ...] = ()  # (where, line, addendum)

    @property
    def value(self) -> Fraction:
        return sum((a.value for _w, _l, a in self.parts), Fraction(0))

    @property
    def value_tuple(self) -> tuple[tuple[str, str], ...]:
        """Which gap receives how much — the identity of this distribution.

        The gap has to be part of the key. Keyed on amounts alone, "1 Z in gap a" and
        "1 Z in gap b" collapse into one distribution and a section with two equally
        possible placements is reported as determined.
        """
        return tuple(sorted((w, str(a.value)) for w, _l, a in self.parts))

    @property
    def canonical(self) -> bool:
        return all(a.canonical for _w, _l, a in self.parts)

    def render(self, gaps: list["Gap"]) -> str:
        by_where = {g.where: g for g in gaps}
        bits = []
        for where, _line, addendum in self.parts:
            gap = by_where.get(where)
            last = gap.surviving[-1][0] if gap and gap.surviving else None
            bits.append(f"{where}: {addendum.describe(last)}")
        return "; ".join(bits)

    def to_dict(self, gaps: list["Gap"]) -> dict:
        return {
            "restoration": self.render(gaps),
            "value": str(self.value),
            "per_gap": [
                {"where": w, "line": ln, "value": str(a.value)} for w, ln, a in self.parts
            ],
            "canonical": self.canonical,
        }


@dataclass
class Gap:
    """A damaged quantity: what survives of it, and where."""

    where: str
    line: str | None
    surviving: list[tuple[str, int]]

    def to_dict(self) -> dict:
        return {
            "where": self.where,
            "line": self.line,
            "surviving": [[u, c] for u, c in self.surviving],
        }


@dataclass
class Recovery:
    """The verdict for one section, with every hypothesis that survives."""

    tablet: str
    commodity: str | None
    verdict: str = UNRESOLVED
    residual: Fraction | None = None
    gaps: list[Gap] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)
    strict: bool = True
    note: str | None = None
    truncated: bool = False  # the hypothesis space hit its safety bound

    @property
    def open_quantities(self) -> int:
        return len(self.gaps)

    @property
    def is_determination(self) -> bool:
        """Only a single legal restoration counts. See `VERDICT_MEANING[AMOUNT_DETERMINED]`."""
        return self.verdict == UNIQUE

    @property
    def distinct_distributions(self) -> int:
        return len({c.value_tuple for c in self.candidates})

    @property
    def spellings(self) -> int:
        return len(self.candidates)

    def to_dict(self) -> dict:
        return {
            "tablet": self.tablet,
            "commodity": self.commodity,
            "verdict": self.verdict,
            "means": VERDICT_MEANING[self.verdict],
            "residual": str(self.residual) if self.residual is not None else None,
            "gaps": [g.to_dict() for g in self.gaps],
            "distinct_distributions": self.distinct_distributions,
            "spellings": self.spellings,
            "candidates": [c.to_dict(self.gaps) for c in self.candidates[:40]],
            "strict": self.strict,
            "truncated": self.truncated,
            "note": self.note,
        }


MAX_DISTRIBUTIONS = 5_000


def _distribute(
    gaps: list[Gap],
    per_gap: list[list[Addendum]],
    index: int,
    remaining: Fraction,
    chosen: list[tuple[str, str | None, Addendum]],
    out: list[Candidate],
) -> bool:
    """Find every way the shortfall divides across the gaps. False if the bound was hit.

    A gap may legitimately receive nothing — a break can fall beside a quantity without
    removing any of it — so the empty choice is always available.
    """
    if len(out) >= MAX_DISTRIBUTIONS:
        return False
    if index == len(gaps):
        if remaining == 0 and chosen:
            out.append(Candidate(parts=tuple(chosen)))
        return True
    ok = True
    gap = gaps[index]
    # This gap takes nothing.
    ok &= _distribute(gaps, per_gap, index + 1, remaining, chosen, out)
    for addendum in per_gap[index]:
        if addendum.value > remaining:
            continue
        chosen.append((gap.where, gap.line, addendum))
        ok &= _distribute(gaps, per_gap, index + 1, remaining - addendum.value, chosen, out)
        chosen.pop()
        if len(out) >= MAX_DISTRIBUTIONS:
            return False
    return ok


def classify(
    residual: Fraction | None,
    gaps: list[Gap],
    notation: Notation | None,
    tablet: str = "?",
    commodity: str | None = None,
    strict: bool = True,
    total_damaged: bool = False,
) -> Recovery:
    """Turn a residual plus a list of gaps into a verdict.

    `residual` is recorded total minus summed entries, so a positive value is what the
    break must supply. Breaks only ever add, which is what makes the *sign* of the
    residual decisive rather than incidental: a negative residual cannot be explained by
    damage to an entry at all.
    """
    base = Recovery(
        tablet=tablet,
        commodity=commodity,
        residual=residual,
        gaps=list(gaps),
        strict=strict,
    )
    if residual is None or notation is None:
        base.verdict = UNRESOLVED
        return base

    if residual == 0:
        base.verdict = BALANCED
        if gaps:
            base.note = "Balances as written; the break apparently hid nothing countable."
        return base

    if residual < 0:
        if total_damaged:
            base.verdict = UNRESOLVED
            base.note = (
                "The total is broken and the entries exceed it, so the true total was larger. "
                "Recovering totals rather than entries is a separate problem, not attempted here."
            )
        else:
            base.verdict = OVERFULL
        return base

    if not gaps:
        base.verdict = ERROR_NO_DAMAGE
        return base

    per_gap = [addenda_up_to(g.surviving, notation, residual, strict=strict) for g in gaps]
    # A search that hit its own bound has not proved anything. Reporting that as
    # IMPOSSIBLE inverts the result — the relaxed pass, which admits strictly *more*
    # readings than the strict one, came back with six times as many "no legal amount"
    # verdicts purely because its enumeration was cut short.
    hit_bound = any(len(a) > MAX_ADDENDA for a in per_gap)
    complete = _distribute(gaps, per_gap, 0, residual, [], base.candidates)
    base.truncated = hit_bound or not complete

    if base.truncated and not base.candidates:
        base.verdict = UNRESOLVED
        base.note = (
            "The hypothesis space exceeded its safety bound before any restoration was "
            "found, so nothing is claimed either way."
        )
        return base

    if not base.candidates:
        base.verdict = IMPOSSIBLE
    elif base.truncated:
        # More readings may exist beyond the bound, so uniqueness cannot be asserted.
        base.verdict = AMBIGUOUS
        base.note = (
            f"{len(base.candidates)} restorations found before the search bound; there may "
            "be more, so this is a lower bound on the ambiguity, not a determination."
        )
    elif len(base.candidates) == 1:
        base.verdict = UNIQUE
    elif base.distinct_distributions == 1:
        base.verdict = AMOUNT_DETERMINED
        if len(gaps) == 1:
            base.note = (
                f"One gap, so the missing {residual} follows from the arithmetic alone; "
                f"{base.spellings} sign sequences could express it."
            )
        else:
            base.note = (
                f"All {base.spellings} restorations divide the shortfall the same way "
                f"across {len(gaps)} gaps."
            )
    else:
        base.verdict = AMBIGUOUS
        base.note = (
            f"{base.distinct_distributions} ways to divide {residual} across {len(gaps)} gaps."
        )
    return base


def summarise(recoveries: list[Recovery]) -> dict:
    """Counts by verdict, plus the numbers that matter for a headline claim."""
    counts: dict[str, int] = {}
    for r in recoveries:
        counts[r.verdict] = counts.get(r.verdict, 0) + 1
    attempted = sum(
        counts.get(k, 0) for k in (UNIQUE, AMOUNT_DETERMINED, AMBIGUOUS, IMPOSSIBLE)
    )
    single_gap = [r for r in recoveries if r.open_quantities == 1]
    return {
        "sections": len(recoveries),
        "by_verdict": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
        "verdict_meanings": VERDICT_MEANING,
        "gaps_with_a_restoration_attempt": attempted,
        "uniquely_restored": counts.get(UNIQUE, 0),
        "amount_determined_spelling_open": counts.get(AMOUNT_DETERMINED, 0),
        "unique_share_of_attempts": counts.get(UNIQUE, 0) / attempted if attempted else None,
        "impossible_share_of_attempts": (
            counts.get(IMPOSSIBLE, 0) / attempted if attempted else None
        ),
        # Stated so no reader mistakes the trivial case for the interesting one.
        "single_gap_sections": len(single_gap),
        "single_gap_note": (
            "In a single-gap section the missing amount is fixed by arithmetic alone. Only "
            "UNIQUE (one possible spelling) and IMPOSSIBLE (no legal spelling) say anything "
            "the notation contributes."
        ),
        "truncated": sum(1 for r in recoveries if r.truncated),
    }
