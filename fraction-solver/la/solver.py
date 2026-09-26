"""Phase 2: recover fraction values from tablet arithmetic, exactly.

Each section that balances gives one linear equation over the fraction values:

    sum(entry integers) + sum(entry fractions)  ==  total integer + total fractions

Rearranged, with c_f = (times f appears on entries) - (times f appears on the total):

    sum_f c_f * v_f  ==  total_integer - entry_integer

Known values move to the right-hand side, leaving a linear system over the
unknown ones. Everything is exact rational arithmetic; nothing here uses floats.

Three things this module deliberately reports rather than hides:
  * identifiability - which values the corpus pins down, and which it only
    constrains to a family;
  * consensus - the best assignment may satisfy most equations, not all, because
    tablets contain scribal errors and damaged signs;
  * a null model - with few equations, assignments satisfy some by chance.
"""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, field
from fractions import Fraction

from sympy import Matrix, Rational, nsimplify  # noqa: F401  (Rational used via conversion)

from la.parse import Section, fraction_counts, integer_sum

# Denominators that appear in Aegean metrology and in the published values.
# Deliberately generous; the solver reports what survives the constraints.
DEFAULT_DENOMINATORS = (2, 3, 4, 5, 6, 8, 10, 12, 15, 16, 20, 24, 30, 32, 60)


@dataclass
class Equation:
    """One section's arithmetic, as a linear constraint over fraction values.

    `sense` records what the section can actually assert, which depends on *which
    side* of it is damaged:

    * "="  — nothing missing; entries and total are both complete.
    * "<=" — an **entry** is broken, so what survives understates the true sum:
             surviving entries ≤ total.
    * ">=" — the **total** is broken (e.g. HT 116b's `KU-RO GRA 100[`), so the
             surviving total understates the true one: entries ≥ surviving total.

    When both sides are broken the section asserts nothing and is dropped. Getting
    this direction wrong silently inverts the constraint.
    """

    tablet: str
    total_line: int
    coefficients: dict[str, int]  # unknown sign id -> coefficient
    constant: Fraction  # right-hand side after moving known values across
    damaged: bool
    entry_count: int
    sense: str = "="  # "=" or "<="

    @property
    def is_bound(self) -> bool:
        return self.sense in {"<=", ">="}

    @property
    def is_trivial(self) -> bool:
        """No unknowns left: the equation only tests values we already have."""
        return not self.coefficients

    @property
    def reach(self) -> Fraction:
        """The largest magnitude the unknown side can take, since every value < 1."""
        return Fraction(sum(abs(c) for c in self.coefficients.values()))

    @property
    def satisfiable(self) -> bool:
        """Can any assignment of proper fractions satisfy this equation?

        Fraction values lie strictly between 0 and 1, so the unknown side cannot
        exceed the sum of |coefficients|. When the constant is outside that
        reach, the section's integers do not balance and it constrains nothing —
        it is a damaged or incomplete tablet, not evidence about fraction values.
        """
        if self.sense == "<=":
            return self.constant > -self.reach
        if self.sense == ">=":
            return self.constant < self.reach
        if self.is_trivial:
            return self.constant == 0
        return abs(self.constant) < self.reach

    def residual(self, assignment: dict[str, Fraction]) -> Fraction | None:
        """LHS - RHS under an assignment, or None if a value is missing."""
        total = Fraction(0)
        for sign, coeff in self.coefficients.items():
            if sign not in assignment:
                return None
            total += coeff * assignment[sign]
        return total - self.constant

    def satisfied(self, assignment: dict[str, Fraction]) -> bool | None:
        residual = self.residual(assignment)
        if residual is None:
            return None
        if self.sense == "<=":
            return residual <= 0
        if self.sense == ">=":
            return residual >= 0
        return residual == 0


def build_equations(
    sections: list[tuple[str, Section]],
    known: dict[str, Fraction],
    include_damaged: bool = False,
    open_as_bounds: bool = True,
) -> list[Equation]:
    """One constraint per section that carries fraction signs.

    Sections with nothing missing give equalities. Sections where a break may
    have swallowed part of an entry give `<=` bounds instead, unless
    `open_as_bounds` is False (kept for comparison with the earlier behaviour).
    Sections whose entry list is physically incomplete — *supra mutila* tablets
    such as HT 46a, where the top of the tablet is gone — are excluded outright:
    what survives cannot constrain anything.
    """
    equations: list[Equation] = []
    for tablet_id, section in sections:
        if not section.entries:
            continue
        if section.entries_incomplete:
            continue  # the entry list itself is lost; nothing to constrain with
        entry_fracs = fraction_counts([e.quantity for e in section.entries])
        total_fracs = fraction_counts([section.total.quantity])
        if not entry_fracs and not total_fracs:
            continue  # integers only: tells us nothing about fraction values

        entries_open = any(e.quantity.open for e in section.entries)
        total_open = section.total.quantity.open
        damaged = entries_open or total_open
        if damaged and not include_damaged:
            continue
        if entries_open and total_open and open_as_bounds:
            continue  # both sides incomplete: the section asserts nothing
        if not open_as_bounds or not damaged:
            sense = "="
        elif entries_open:
            sense = "<="   # surviving entries understate the true sum
        else:
            sense = ">="   # surviving total understates the true total

        signs = set(entry_fracs) | set(total_fracs)
        coefficients: dict[str, int] = {}
        known_contribution = Fraction(0)
        for sign in signs:
            coeff = entry_fracs.get(sign, 0) - total_fracs.get(sign, 0)
            if coeff == 0:
                continue  # cancels out: appears equally on both sides
            if sign in known:
                known_contribution += coeff * known[sign]
            else:
                coefficients[sign] = coeff

        constant = Fraction(section.total.quantity.integer or 0) - Fraction(integer_sum(section)) - known_contribution

        equations.append(
            Equation(
                tablet=tablet_id,
                total_line=section.total.line_no,
                coefficients=coefficients,
                constant=constant,
                damaged=damaged,
                entry_count=len(section.entries),
                sense=sense,
            )
        )
    return equations


@dataclass
class Identifiability:
    unknowns: list[str]
    rank: int
    consistent: bool
    determined: dict[str, Fraction] = field(default_factory=dict)
    free_dimensions: int = 0
    particular: dict[str, Fraction] = field(default_factory=dict)
    nullspace: list[dict[str, Fraction]] = field(default_factory=list)


def analyse(equations: list[Equation]) -> Identifiability:
    """Exact rank/identifiability analysis of the system."""
    unknowns = sorted({s for eq in equations for s in eq.coefficients})
    # Bounds constrain but do not determine; rank and identifiability are about
    # equalities only, and pooling the two would overstate what is pinned down.
    live = [eq for eq in equations if eq.coefficients and not eq.is_bound]
    if not unknowns or not live:
        return Identifiability(unknowns=unknowns, rank=0, consistent=True, free_dimensions=len(unknowns))

    A = Matrix([[eq.coefficients.get(s, 0) for s in unknowns] for eq in live])
    b = Matrix([[Rational(eq.constant.numerator, eq.constant.denominator)] for eq in live])

    rank_A = A.rank()
    rank_Ab = A.row_join(b).rank()
    consistent = rank_A == rank_Ab

    result = Identifiability(
        unknowns=unknowns,
        rank=rank_A,
        consistent=consistent,
        free_dimensions=len(unknowns) - rank_A,
    )
    if not consistent:
        return result

    solution, params = A.gauss_jordan_solve(b)
    zeroed = solution.subs({p: 0 for p in params})
    result.particular = {
        s: Fraction(int(zeroed[i].p), int(zeroed[i].q)) for i, s in enumerate(unknowns)
    }

    basis = []
    for p in params:
        vec = solution.subs({q: (1 if q == p else 0) for q in params}) - zeroed
        basis.append({s: Fraction(int(vec[i].p), int(vec[i].q)) for i, s in enumerate(unknowns)})
    result.nullspace = basis

    # A value is determined when every null-space direction leaves it unchanged.
    for i, sign in enumerate(unknowns):
        if all(vec[sign] == 0 for vec in basis):
            result.determined[sign] = result.particular[sign]
    return result


def candidate_values(denominators=DEFAULT_DENOMINATORS, unit_only: bool = True) -> list[Fraction]:
    """Plausible fraction values.

    The published Linear A values are all unit fractions (1/2, 1/4, 1/5, 1/6,
    1/10), which is also what a metrological subunit system implies, so unit
    fractions are the default hypothesis space. `unit_only=False` widens it to
    every proper fraction over the same denominators, at the cost of a much
    larger search.
    """
    if unit_only:
        return sorted(Fraction(1, d) for d in denominators)
    values = set()
    for d in denominators:
        for n in range(1, d):
            f = Fraction(n, d)
            if f < 1:
                values.add(f)
    return sorted(values)


def enumerate_assignments(
    equations: list[Equation],
    unknowns: list[str],
    grid: list[Fraction] | None = None,
    max_combinations: int = 5_000_000,
    distinct: bool = True,
) -> list[tuple[dict[str, Fraction], int]]:
    """Score every plausible assignment by how many equations it satisfies.

    Returns assignments sorted by satisfied count, best first. Exhaustive over the
    grid, which is feasible because the unknown count is small.
    """
    grid = grid or candidate_values()
    live = [eq for eq in equations if eq.coefficients]
    if not unknowns or not live:
        return []
    if len(grid) ** len(unknowns) > max_combinations:
        raise ValueError(
            f"grid too large: {len(grid)}^{len(unknowns)} combinations; "
            "narrow the denominators or the unknown set"
        )

    scored: list[tuple[dict[str, Fraction], int]] = []
    for combo in itertools.product(grid, repeat=len(unknowns)):
        if distinct and len(set(combo)) != len(combo):
            continue
        assignment = dict(zip(unknowns, combo))
        hits = sum(1 for eq in live if eq.satisfied(assignment))
        if hits:
            scored.append((assignment, hits))
    scored.sort(key=lambda pair: -pair[1])
    return scored


def null_model(
    equations: list[Equation],
    unknowns: list[str],
    trials: int = 2000,
    grid: list[Fraction] | None = None,
    seed: int = 20260923,
) -> dict:
    """How many equations does a random assignment satisfy by chance?

    Without this, 'our values explain 4 tablets' is not interpretable.
    """
    grid = grid or candidate_values()
    live = [eq for eq in equations if eq.coefficients]
    rng = random.Random(seed)
    counts: list[int] = []
    for _ in range(trials):
        assignment = {s: rng.choice(grid) for s in unknowns}
        counts.append(sum(1 for eq in live if eq.satisfied(assignment)))
    counts.sort()
    n = len(counts)
    return {
        "trials": trials,
        "mean": sum(counts) / n if n else 0,
        "p50": counts[n // 2] if n else 0,
        "p95": counts[int(n * 0.95)] if n else 0,
        "p99": counts[int(n * 0.99)] if n else 0,
        "max": counts[-1] if n else 0,
    }


def leave_one_out(
    sections: list[tuple[str, Section]],
    known: dict[str, Fraction],
    grid: list[Fraction] | None = None,
) -> dict[str, dict]:
    """Hide each known value in turn and try to recover it from the corpus.

    This is the method's own validation: if it cannot re-derive values that are
    already published, its answers for the unsolved signs mean nothing.
    """
    results: dict[str, dict] = {}
    for hidden in sorted(known):
        reduced = {k: v for k, v in known.items() if k != hidden}
        equations = build_equations(sections, reduced)
        ident = analyse(equations)
        entry = {
            "true_value": str(known[hidden]),
            "equations": len([e for e in equations if e.coefficients]),
            "appears_in_system": hidden in ident.unknowns,
            "consistent": ident.consistent,
            "determined": hidden in ident.determined,
            "recovered": str(ident.determined.get(hidden)) if hidden in ident.determined else None,
        }
        entry["correct"] = entry["determined"] and ident.determined[hidden] == known[hidden]
        results[hidden] = entry
    return results
