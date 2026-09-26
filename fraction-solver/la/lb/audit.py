"""An arithmetic audit of Linear B, and the error rate it yields.

**Why this exists.** The Linear A half of this project found that a handful of
Haghia Triada tablets do not balance, and could say nothing about what that means.
"HT 9a is short by 3/4" is uninterpretable without a base rate: if competent
Mycenaean accountants failed to balance one tablet in seven, a few Linear A failures
are unremarkable; if they failed one in fifty, they are anomalies worth explaining.
A targeted literature search found no published systematic arithmetic audit of
Linear B and no published error rate for Mycenaean accounting, so the number does
not appear to exist. Linear B is the right place to get it: same administrative
tradition, same genre, roughly the same century — but deciphered, with published
metrology and a scribal hand attached to most documents.

**Three separations the audit keeps, because collapsing any of them inflates the
headline.**

1. *Damage is not error.* The error rate is measured only over sections with no
   break anywhere near a quantity. Damaged sections go to `la.recover` instead, where
   the question is whether the break is recoverable, not whether the scribe was wrong.
2. *Unresolved is not balanced.* A section whose commodity or units cannot be placed
   is excluded and counted, never scored as correct.
3. *Fitting is not testing.* `fit_sizes` derives the unit ratios from the corpus;
   the error rate uses ratios fixed in advance. Deriving ratios from totals and then
   scoring totals against them would guarantee a low error rate by construction, so
   the fit is reported as its own result and `--holdout` splits the data for anyone
   who wants the two provably disjoint.

The fit is worth having in its own right: it re-derives Linear B metrology from the
tablets using the same exact-rational identifiability analysis `la.solver` applies to
Linear A. Recovering the published ratios is the strongest single check that the
parser reads these documents correctly.
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from fractions import Fraction

from sympy import Matrix, Rational

from la import recover
from la.lb import metrology, parse
from la.lb.metrology import Series
from la.lb.parse import LBSection, LBTablet, Measure

# ---------------------------------------------------------------------------
# Which series each commodity is measured in, from corpus usage
# ---------------------------------------------------------------------------


@dataclass
class CommodityProfile:
    commodity: str
    occurrences: int = 0
    bare: int = 0  # written with a plain number and no subunit sign
    metrograms: Counter = field(default_factory=Counter)

    @property
    def inferred(self) -> str | None:
        """The series this commodity's own usage implies, or None for counted.

        Decided by which subunit signs ever follow it. `T` means dry, `S` liquid,
        and the weight letters mean weight; `V` and `Z` alone are ambiguous, since
        both capacity series share them, and are not enough on their own.
        """
        votes: Counter = Counter()
        for unit, n in self.metrograms.items():
            if unit == "T":
                votes["dry"] += n
            elif unit == "S":
                votes["liquid"] += n
            elif unit in {"L", "M", "N", "P", "Q"}:
                votes["weight"] += n
        if votes:
            return votes.most_common(1)[0][0]
        if self.metrograms:
            return None  # only V/Z seen: capacity, but which series is undetermined
        return None  # never subdivided: counted

    @property
    def ambiguous(self) -> bool:
        """True when the commodity's subunits point to more than one series."""
        votes = {"dry": 0, "liquid": 0, "weight": 0}
        for unit, n in self.metrograms.items():
            if unit == "T":
                votes["dry"] += n
            elif unit == "S":
                votes["liquid"] += n
            elif unit in {"L", "M", "N", "P", "Q"}:
                votes["weight"] += n
        return sum(1 for v in votes.values() if v) > 1

    @property
    def only_capacity_subunits(self) -> bool:
        """Subdivided by V/Z only, so it is a capacity commodity of unknown series."""
        return bool(self.metrograms) and self.inferred is None


def profile_commodities(tablets: list[LBTablet]) -> dict[str, CommodityProfile]:
    """How each commodity is actually written, across the corpus."""
    profiles: dict[str, CommodityProfile] = {}
    for tablet in tablets:
        for m in tablet.measures:
            if not m.commodity or m.inherited_commodity:
                continue  # an inherited commodity is our inference, not the scribe's
            p = profiles.setdefault(m.commodity, CommodityProfile(m.commodity))
            p.occurrences += 1
            subunits = [u for u, _ in m.terms if u != "UNIT"]
            if subunits:
                p.metrograms.update(subunits)
            else:
                p.bare += 1
    return profiles


def infer_commodity_series(tablets: list[LBTablet], min_occurrences: int = 1) -> dict[str, str]:
    """Commodity to series name, derived from which subunits the corpus attaches.

    Preferred over the hand-written convention in `metrology`, because the corpus is
    the better witness. A commodity the corpus never subdivides maps to `""`, meaning
    counted — which is what stops `*146 28` on a Pylos Ma tablet being read as 28
    whole units of a weighed commodity.
    """
    out: dict[str, str] = {}
    for name, p in profile_commodities(tablets).items():
        if p.occurrences < min_occurrences:
            continue
        inferred = p.inferred
        out[name] = inferred or ""
    return out


def compare_with_convention(tablets: list[LBTablet]) -> dict:
    """Where corpus usage and the hand-written convention disagree.

    A disagreement is a bug in one of the two, and which one is worth knowing.
    """
    profiles = profile_commodities(tablets)
    agree, differ, only_corpus, only_convention = [], [], [], []
    for name, p in sorted(profiles.items()):
        corpus = p.inferred
        declared = metrology.series_for(name)
        declared_name = declared.name if declared else (None if metrology.is_counted(name) else "unlisted")
        if corpus and declared_name == corpus:
            agree.append(name)
        elif corpus and declared_name in {None, "unlisted"}:
            only_corpus.append({"commodity": name, "corpus": corpus, "convention": declared_name})
        elif corpus and declared_name != corpus:
            differ.append({"commodity": name, "corpus": corpus, "convention": declared_name})
        elif not corpus and declared_name not in {None, "unlisted"}:
            only_convention.append({"commodity": name, "convention": declared_name, "bare": p.bare})
    return {
        "commodities": len(profiles),
        "agree": len(agree),
        "disagree": differ,
        "corpus_only": only_corpus,
        "convention_only_never_subdivided": only_convention[:25],
        "ambiguous": [n for n, p in sorted(profiles.items()) if p.ambiguous],
        "capacity_series_undetermined": [
            n for n, p in sorted(profiles.items()) if p.only_capacity_subunits
        ],
    }


# ---------------------------------------------------------------------------
# Fitting the unit ratios from the corpus
# ---------------------------------------------------------------------------


@dataclass
class SizeFit:
    series: str
    equations: int
    unknowns: list[str]
    best: dict[str, Fraction] = field(default_factory=dict)
    satisfied: int = 0
    published: dict[str, int] = field(default_factory=dict)
    published_satisfied: int = 0
    agrees_with_published: bool = False
    rank: int = 0
    consistent: bool = False

    def to_dict(self) -> dict:
        return {
            "series": self.series,
            "equations": self.equations,
            "unknowns": self.unknowns,
            "fitted_sizes": {k: str(v) for k, v in self.best.items()},
            "fitted_satisfies": self.satisfied,
            "published_sizes": self.published,
            "published_satisfies": self.published_satisfied,
            "agrees_with_published": self.agrees_with_published,
            "rank_of_full_system": self.rank,
            "full_system_consistent": self.consistent,
            "fitted_ratios": self.ratios(),
        }

    def ratios(self) -> dict[str, str]:
        """Consecutive ratios implied by the fitted sizes, which is the citable form."""
        if not self.best:
            return {}
        order = sorted(self.best, key=lambda u: -self.best[u])
        out: dict[str, str] = {}
        for a, b in zip(order, order[1:]):
            if self.best[b]:
                out[f"{a}:{b}"] = str(self.best[a] / self.best[b])
        return out


def _size_equation(section: LBSection, series_map: dict[str, str]) -> dict[str, int] | None:
    """One balanced section as a linear equation over unit sizes.

    Coefficient of each unit is (times it appears on the entries) minus (times on the
    total), counted with multiplicity. The equation is homogeneous — it says the two
    sides are equal — so sizes are determined only up to scale, and the smallest unit
    is pinned to 1 by the caller.
    """
    coeffs: Counter = Counter()
    for m in section.entries:
        for unit, count in m.terms:
            coeffs[unit] += count
    for unit, count in section.total.terms:
        coeffs[unit] -= count
    return {u: c for u, c in coeffs.items() if c} or None


def fit_sizes(
    sections: list[LBSection],
    series: Series,
    series_map: dict[str, str],
    trials: int = 4000,
    seed: int = 20260924,
) -> SizeFit:
    """Derive unit sizes from sections that ought to balance.

    Scribal errors make the full system inconsistent, so the fit is a consensus:
    sample just enough equations to determine the unknowns, solve exactly, and keep
    whichever solution satisfies the most equations overall. That is deliberately
    robust rather than least-squares — these are exact rational identities, and an
    approximate answer to "is 1 T six V" is not useful.
    """
    smallest = series.smallest
    unknowns = [u for u in series.units if u != smallest]
    equations: list[dict[str, int]] = []
    for section in sections:
        if section.series is not series or not section.yields_equation:
            continue
        eq = _size_equation(section, series_map)
        if eq and any(u in series.units for u in eq) and all(u in series.units for u in eq):
            equations.append(eq)

    fit = SizeFit(series=series.name, equations=len(equations), unknowns=unknowns)
    fit.published = {u: series.in_smallest(u) for u in series.units}
    if not equations:
        return fit

    def score(sizes: dict[str, Fraction]) -> int:
        hits = 0
        for eq in equations:
            total = sum(c * sizes.get(u, Fraction(1) if u == smallest else Fraction(0))
                        for u, c in eq.items())
            if total == 0:
                hits += 1
        return hits

    published_sizes = {u: Fraction(series.in_smallest(u)) for u in series.units}
    fit.published_satisfied = score(published_sizes)

    # Exact rank of the whole system, for the identifiability story.
    all_units = unknowns
    A = Matrix([[eq.get(u, 0) for u in all_units] for eq in equations])
    b = Matrix([[-eq.get(smallest, 0)] for eq in equations])
    fit.rank = A.rank()
    fit.consistent = A.rank() == A.row_join(b).rank()

    rng = random.Random(seed)
    best: dict[str, Fraction] = {}
    best_score = -1
    k = len(unknowns)
    for _ in range(trials):
        if len(equations) < k:
            break
        sample = rng.sample(equations, k)
        M = Matrix([[eq.get(u, 0) for u in unknowns] for eq in sample])
        rhs = Matrix([[-eq.get(smallest, 0)] for eq in sample])
        if M.rank() < k:
            continue
        try:
            sol = M.solve(rhs)
        except Exception:  # noqa: BLE001 - singular sample, skip
            continue
        sizes = {smallest: Fraction(1)}
        ok = True
        for i, u in enumerate(unknowns):
            val = sol[i]
            if not getattr(val, "is_Rational", False):
                ok = False
                break
            f = Fraction(int(Rational(val).p), int(Rational(val).q))
            if f <= 0:
                ok = False
                break
            sizes[u] = f
        if not ok:
            continue
        # Sizes must descend in the series' declared order to be a unit system at all.
        ordered = [sizes[u] for u in series.units]
        if any(a <= b for a, b in zip(ordered, ordered[1:])):
            continue
        s = score(sizes)
        if s > best_score:
            best_score, best = s, sizes

    fit.best = best
    fit.satisfied = max(best_score, 0)
    fit.agrees_with_published = bool(best) and all(
        best.get(u) == Fraction(series.in_smallest(u)) for u in series.units
    )
    return fit


# ---------------------------------------------------------------------------
# The audit itself
# ---------------------------------------------------------------------------


@dataclass
class SectionAudit:
    tablet: str
    commodity: str | None
    series: str | None
    hand: str | None
    site: str | None
    series_code: str | None
    entries: int
    residual: int | None
    tier: str             # clean | edge | broken
    open_quantity: bool   # a break may have shortened an amount
    resolved: bool        # every quantity could be valued
    restored: bool        # an editor supplied part of the arithmetic
    balances: bool | None
    counted: bool
    rendered_total: str = ""

    @property
    def auditable(self) -> bool:
        """Complete as written, valued, and not editorially repaired.

        Deliberately excludes `restored`: a total that balances only because an editor
        supplied the numeral that makes it balance tests the editor, not the scribe.
        """
        return (
            self.tier != "broken"
            and not self.open_quantity
            and self.resolved
            and not self.restored
        )

    @property
    def scorable(self) -> bool:
        """The headline population: auditable *and* free of edge damage."""
        return self.auditable and self.tier == "clean"

    def to_dict(self) -> dict:
        return {
            "tablet": self.tablet,
            "commodity": self.commodity,
            "series": self.series or ("counted" if self.counted else None),
            "hand": self.hand,
            "site": self.site,
            "series_code": self.series_code,
            "entries": self.entries,
            "residual": self.residual,
            "tier": self.tier,
            "restored": self.restored,
            "balances": self.balances,
            "total_as_written": self.rendered_total,
        }


def audit_sections(
    tablets: list[LBTablet],
    series_map: dict[str, str],
) -> list[SectionAudit]:
    """Every section, scored for whether the scribe's own total matches their entries."""
    out: list[SectionAudit] = []
    for tablet in tablets:
        for section in tablet.sections:
            residual = section.residual(series_map)
            series = section.series
            out.append(
                SectionAudit(
                    tablet=tablet.id,
                    commodity=section.commodity,
                    series=series.name if series else None,
                    hand=tablet.hand,
                    site=tablet.site,
                    series_code=tablet.series_code,
                    entries=len(section.entries),
                    residual=residual,
                    tier=section.tier,
                    open_quantity=section.has_open_quantity,
                    resolved=residual is not None,
                    restored=section.has_restored,
                    balances=(residual == 0) if residual is not None else None,
                    counted=series is None and residual is not None,
                    rendered_total=section.total.render(),
                )
            )
    return out


def error_rate(audits: list[SectionAudit], min_group: int = 5) -> dict:
    """The headline: how often an intact, fully resolved Linear B section fails to balance.

    Broken down by scribal hand, site and tablet series, because a single corpus-wide
    figure hides the thing a reader most wants — whether error is a property of the
    administration or of particular scribes.

    Four exclusions, each counted rather than quietly dropped: sections with a break or
    a gap (damage is not error), sections whose units could not be placed (unresolved is
    not balanced), sections an editor part-restored (scoring those would be circular),
    and totals covering fewer than two entries (no arithmetic to check).
    """
    scored = [a for a in audits if a.scorable]
    auditable = [a for a in audits if a.auditable]
    failures = [a for a in scored if not a.balances]

    def breakdown(key, population: list[SectionAudit] | None = None) -> list[dict]:
        groups: dict[str, list[SectionAudit]] = defaultdict(list)
        for a in population if population is not None else scored:
            value = key(a)
            if value:
                groups[str(value)].append(a)
        rows = []
        for name, items in groups.items():
            if len(items) < min_group:
                continue
            bad = [i for i in items if not i.balances]
            rows.append({
                "group": name,
                "sections": len(items),
                "failures": len(bad),
                "error_rate": len(bad) / len(items),
            })
        rows.sort(key=lambda r: (-r["error_rate"], -r["sections"]))
        return rows

    restored_only = [
        a for a in audits
        if a.tier != "broken" and not a.open_quantity and a.resolved and a.restored
    ]
    edge = [a for a in auditable if a.tier == "edge"]
    return {
        "sections_total": len(audits),
        "excluded_content_missing": sum(1 for a in audits if a.tier == "broken"),
        "excluded_open_quantity": sum(
            1 for a in audits if a.tier != "broken" and a.open_quantity
        ),
        "excluded_unresolved": sum(
            1 for a in audits
            if a.tier != "broken" and not a.open_quantity and not a.resolved
        ),
        "excluded_editorially_restored": len(restored_only),
        "scored": len(scored),
        "failures": len(failures),
        "error_rate": len(failures) / len(scored) if scored else None,
        # The sensitivity that matters: edge-damaged sections may be missing an entry, so
        # a failure there is ambiguous between scribal error and lost text. If the two
        # tiers disagree sharply, the headline is about damage, not arithmetic.
        "by_tier": [
            {
                "tier": name,
                "sections": len(items),
                "failures": sum(1 for a in items if not a.balances),
                "error_rate": (
                    sum(1 for a in items if not a.balances) / len(items) if items else None
                ),
            }
            for name, items in (("clean", scored), ("edge", edge))
            if items
        ],
        "error_rate_including_edge": (
            sum(1 for a in auditable if not a.balances) / len(auditable) if auditable else None
        ),
        # The comparison that shows why restored sections are excluded: an editor who
        # restores a numeral to make a total work will balance far more often than a
        # scribe did.
        "restored_error_rate": (
            sum(1 for a in restored_only if not a.balances) / len(restored_only)
            if restored_only else None
        ),
        "counted_vs_measured": [
            {
                "kind": kind,
                "sections": len(items),
                "failures": sum(1 for a in items if not a.balances),
                "error_rate": sum(1 for a in items if not a.balances) / len(items) if items else None,
            }
            for kind, items in (
                ("counted", [a for a in scored if a.counted]),
                ("measured", [a for a in scored if not a.counted]),
            )
            if items
        ],
        "by_hand": breakdown(lambda a: a.hand),
        "by_site": breakdown(lambda a: a.site),
        "by_series": breakdown(lambda a: a.series_code),
        "by_unit_series": breakdown(lambda a: a.series or ("counted" if a.counted else None)),
        "worst_examples": [a.to_dict() for a in sorted(
            failures, key=lambda a: -abs(a.residual or 0)
        )[:20]],
        "all_failures": [a.to_dict() for a in failures],
    }


# ---------------------------------------------------------------------------
# Bridge to la.recover
# ---------------------------------------------------------------------------


def gaps_for(section: LBSection) -> list[recover.Gap]:
    """The damaged entry quantities in a section, as recovery gaps."""
    gaps: list[recover.Gap] = []
    for m in section.entries:
        if m.open:
            gaps.append(
                recover.Gap(
                    where=m.render(),
                    line=m.line_label,
                    surviving=list(m.terms),
                )
            )
    return gaps


def notation_for(section: LBSection, series_map: dict[str, str]) -> recover.Notation | None:
    """The writing system this section's amounts obey.

    A measured commodity gets its unit chain with bundling caps; a counted one gets
    plain integers, where every value is legal. Returning None means the units could
    not be placed, and no recovery claim is made.
    """
    if section.series is not None:
        return recover.MetricNotation(section.series)
    if section.residual(series_map) is not None:
        return recover.CountNotation()
    return None


def recover_section(
    section: LBSection,
    series_map: dict[str, str],
    strict: bool = True,
) -> recover.Recovery:
    """Ask whether a damaged section's missing amount is uniquely determined."""
    residual = section.residual(series_map)
    result = recover.classify(
        residual=Fraction(residual) if residual is not None else None,
        gaps=gaps_for(section),
        notation=notation_for(section, series_map),
        tablet=section.tablet,
        commodity=section.commodity,
        strict=strict,
        total_damaged=section.total.open,
    )
    if section.series is None and result.verdict != recover.UNRESOLVED:
        result.note = ((result.note + " ") if result.note else "") + (
            "Counted commodity: any integer is writeable, so uniqueness here is "
            "arithmetic alone, not a constraint from the notation."
        )
    return result


def recover_all(
    tablets: list[LBTablet],
    series_map: dict[str, str],
    strict: bool = True,
) -> list[recover.Recovery]:
    """Recovery verdicts for every section where a break touches a quantity.

    Sections with a *gap* rather than a break are skipped: when whole entries may be
    missing, the residual measures the lost entries, not the lost part of a surviving
    amount, and treating the two alike is what produced Linear A's spurious 42.5
    "shortfall" on the *supra mutila* HT 46a.
    """
    out: list[recover.Recovery] = []
    for tablet in tablets:
        for section in tablet.sections:
            if not section.has_open_quantity or section.entries_incomplete:
                continue
            out.append(recover_section(section, series_map, strict=strict))
    return out


# ---------------------------------------------------------------------------
# Held-out corruption: the only honest accuracy figure
# ---------------------------------------------------------------------------


def _prefix_value(terms: list[tuple[str, int]], series: Series | None) -> int:
    """Value of a partial quantity, for both measured and counted commodities."""
    if series is None:
        return sum(c for u, c in terms if u == "UNIT")
    return metrology.value_in_smallest(terms, series)


def _truncations(terms: list[tuple[str, int]]) -> list[list[tuple[str, int]]]:
    """Every prefix a break could have left of this quantity.

    A break at the right-hand edge does two things: it drops trailing terms, and it
    cuts strokes off the last numeral still visible. Both leave a prefix of the truth,
    which is exactly what `1[` records. The empty prefix is included because a break
    can remove the amount entirely, as in KN As 40's `ko-no-so VIR [`.
    """
    out: list[list[tuple[str, int]]] = []
    for keep in range(len(terms), 0, -1):
        prefix = terms[:keep]
        if keep < len(terms):
            out.append(list(prefix))       # whole terms lost, last numeral intact
        unit, count = prefix[-1]
        for reduced in range(1, count):    # last numeral cut short
            out.append(prefix[:-1] + [(unit, reduced)])
    out.append([])                          # the amount is gone entirely
    return out


def holdout_corruption(
    tablets: list[LBTablet],
    series_map: dict[str, str],
    strict: bool = True,
    trials_per_section: int = 50,
    seed: int = 20260924,
) -> dict:
    """Break numerals we already know the answer to, and see if recovery finds it.

    Only sections that balance exactly and carry no damage are used, so the truth is
    known. This is the Ithaca held-out-corruption protocol applied to numerals, which
    is the part no published work appears to do.

    Accuracy is reported *per verdict*, because the whole claim is that `UNIQUE`
    means something stronger than `AMBIGUOUS`. If `UNIQUE` restorations were not
    almost always right, the taxonomy would be worthless.
    """
    rng = random.Random(seed)
    per_verdict: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "correct": 0, "exact": 0})
    by_kind: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "determined": 0, "correct": 0})
    attempts = 0
    usable_sections = 0

    for tablet in tablets:
        for section in tablet.sections:
            if not section.yields_equation or section.has_restored:
                continue
            if section.residual(series_map) != 0:
                continue
            notation = notation_for(section, series_map)
            if notation is None:
                continue
            series = section.series
            kind = series.name if series else "counted"
            usable_sections += 1

            options: list[tuple[int, list[tuple[str, int]], int]] = []
            for i, m in enumerate(section.entries):
                if not m.terms:
                    continue
                true_value = m.value(series_map)
                if true_value is None:
                    continue
                for prefix in _truncations(list(m.terms)):
                    lost = true_value - _prefix_value(prefix, series)
                    if lost > 0:
                        options.append((i, prefix, lost))
            if not options:
                continue
            rng.shuffle(options)
            for index, prefix, lost in options[:trials_per_section]:
                attempts += 1
                entry = section.entries[index]
                result = recover.classify(
                    residual=Fraction(lost),
                    gaps=[recover.Gap(where=entry.render(), line=entry.line_label, surviving=prefix)],
                    notation=notation,
                    tablet=section.tablet,
                    commodity=section.commodity,
                    strict=strict,
                )
                bucket = per_verdict[result.verdict]
                bucket["n"] += 1
                # With one gap the amount is `lost` by construction, so what is under test
                # is whether the notation admits it at all and whether it admits anything
                # else. Reconstructing the exact signs is the strong outcome, counted apart.
                if any(c.value == lost for c in result.candidates):
                    bucket["correct"] += 1
                truth = _addendum_terms(list(entry.terms), prefix)
                if len(result.candidates) == 1 and _matches(result.candidates[0], truth):
                    bucket["exact"] += 1

                k = by_kind[kind]
                k["n"] += 1
                if result.is_determination:
                    k["determined"] += 1
                    if _matches(result.candidates[0], truth):
                        k["correct"] += 1

    rows = []
    for verdict, counts in sorted(per_verdict.items(), key=lambda kv: -kv[1]["n"]):
        rows.append({
            "verdict": verdict,
            "means": recover.VERDICT_MEANING[verdict],
            "n": counts["n"],
            "amount_among_candidates": counts["correct"],
            "reconstructs_exact_terms": counts["exact"],
            "accuracy": counts["correct"] / counts["n"] if counts["n"] else None,
        })
    # Only UNIQUE counts. AMOUNT_DETERMINED on a single gap is arithmetic, not restoration.
    determinations = [r for r in rows if r["verdict"] == recover.UNIQUE]
    det_n = sum(r["n"] for r in determinations)
    return {
        "protocol": (
            "Sections that balance exactly, carry no damage and contain nothing the editor "
            "restored are truncated at a legal break point; recovery is then asked to "
            "restore the amount it cannot see. The true answer is known by construction, "
            "which is the only way to get an accuracy figure when the real lost text is gone."
        ),
        "strict": strict,
        "usable_sections": usable_sections,
        "attempts": attempts,
        # Stated in the result itself, because the attempt count is the number that gets
        # quoted and it overstates the evidence badly. Many truncations of one section are
        # many views of one tablet, not independent samples, and the Linear B corpus
        # supplies exactly one section that both balances and is complete enough to corrupt.
        "independence_warning": (
            f"{attempts} truncations drawn from {usable_sections} section(s). Truncations of "
            "the same section are not independent; read `usable_sections`, not `attempts`."
        ),
        "by_verdict": rows,
        "by_commodity_kind": [
            {
                "kind": kind,
                "n": c["n"],
                "determined": c["determined"],
                "determination_rate": c["determined"] / c["n"] if c["n"] else None,
                "correct_when_determined": c["correct"] / c["determined"] if c["determined"] else None,
            }
            for kind, c in sorted(by_kind.items(), key=lambda kv: -kv[1]["n"])
        ],
        "determination_n": det_n,
        "determination_rate": det_n / attempts if attempts else None,
        "determination_accuracy": (
            sum(r["amount_among_candidates"] for r in determinations) / det_n if det_n else None
        ),
    }


def _addendum_terms(
    truth: list[tuple[str, int]],
    prefix: list[tuple[str, int]],
) -> tuple[int, list[tuple[str, int]]]:
    """What the break removed, split into extra count on the last sign and whole terms."""
    if not prefix:
        return 0, truth
    last_unit, last_count = prefix[-1]
    matching = next((c for u, c in truth[:len(prefix)] if u == last_unit), last_count)
    return matching - last_count, truth[len(prefix):]


def _matches(candidate: recover.Candidate, truth: tuple[int, list[tuple[str, int]]]) -> bool:
    """Whether a hypothesis reconstructs the exact signs, not merely the right total."""
    if len(candidate.parts) != 1:
        return False
    addendum = candidate.parts[0][2]
    extend, appended = truth
    return addendum.extend == extend and list(addendum.appended) == appended


def accounting_baseline(tablets: list[LBTablet], series_map: dict[str, str]) -> dict:
    """The Mycenaean accounting error rate, from whichever channels can supply one.

    The point of the whole Linear B exercise: a base rate against which "HT 9a does not
    balance" can be read. Two channels contribute, and they are reported separately because
    their units of analysis differ — a `to-so` section is one summation, a Ma assessment
    value is one number — and pooling them would produce a figure that means nothing.

    **The first channel is nearly empty, and that is a finding.** Of roughly 5,900 DAMOS
    documents only about 120 carry a parsed total at all, and almost all of those are
    fragmentary: entries lost above a total make its sum unauditable, however legible the
    total itself is. It explains why no such rate appears in the literature — not oversight
    but scarcity. Anyone repeating this should not expect within-tablet totals to deliver it.

    **The second channel measures the wrong thing, and the label is kept only to match the
    output.** The Pylos Ma ratio does constrain every value on eighteen tablets, but the
    literature reads deviation from it as deliberate tax reduction, not scribal error (de
    Fidio 1982; see `la.lb.ma`). So no accounting error rate is obtained here. The figure
    below is deviation from Bennett's 1951 ratio, which is a real measurement under a name
    it does not deserve, and it cannot calibrate a Linear A mismatch.
    """
    from la.lb import ma as ma_module

    audits = audit_sections(tablets, series_map)
    totals_channel = error_rate(audits)

    assessments = ma_module.extract(tablets)
    grain = ma_module.rounding_granularity(assessments)
    ma_deviations = ma_module.deviations(
        assessments, granularity=grain["summary"]
    )

    return {
        "question": (
            "How often did a competent Mycenaean accountant record a figure that does not "
            "follow from the others on the same tablet?"
        ),
        "why_it_matters": (
            "A Linear A mismatch is uninterpretable without it. At a 15% base rate a handful "
            "of Linear A failures is unremarkable; at 2% they are anomalies needing explanation."
        ),
        "channels": [
            {
                "channel": "within-tablet totals (to-so / ku-su-to-ro-qa)",
                "unit_of_analysis": "one summation closed by a total",
                "sections_found": totals_channel["sections_total"],
                "scored": totals_channel["scored"],
                "failures": totals_channel["failures"],
                "error_rate": totals_channel["error_rate"],
                "error_rate_including_edge_damage": totals_channel["error_rate_including_edge"],
                "limitation": (
                    "Almost every surviving total sits on a tablet with content missing above "
                    "it, so the entries it summed cannot be reconstructed. This channel is too "
                    "scarce to carry an estimate."
                ),
            },
            {
                "channel": "Pylos Ma fixed assessment ratio (7:7:2:3:1.5:150)",
                "unit_of_analysis": "one assessed value",
                "tablets": ma_deviations["tablets_checked"],
                "values_checked": ma_deviations["values_checked"],
                "deviations": ma_deviations["values_off"],
                "deviation_rate": ma_deviations["value_error_rate"],
                "mean_absolute_deviation": ma_deviations["mean_absolute_deviation"],
                "limitation": (
                    "Not an error rate. Deviation from the ratio is read in the literature as "
                    "deliberate tax reduction (de Fidio 1982), and the tablets record exemptions "
                    "and arrears explicitly. `ME` is also rounded coarsely, which Shelmerdine "
                    "already quantifies; scoring it at unit precision inflates the figure by half "
                    "again, so rounding is modelled before anything is counted."
                ),
            },
        ],
        "outcome": "NO BASE RATE OBTAINED",
        "headline": {
            "measures": "deviation from Bennett's 1951 assessment ratio",
            "does_not_measure": "scribal arithmetic error",
            "source": "Pylos Ma assessment values",
            "n": ma_deviations["values_checked"],
            "deviations": ma_deviations["values_off"],
            "rate": ma_deviations["value_error_rate"],
            "anomalies_beyond_rounding": [
                r for r in ma_deviations["outliers"] if abs(r["deviation"]) >= 2
            ],
        },
        "caveats": [
            "The headline rate is NOT an accounting error rate. de Fidio 1982 reads the extant "
            "Ma figures as systematic reductions of a larger assessment, and the tablets record "
            "exemptions and arrears explicitly, so a district below the ratio was granted relief. "
            "Of the deviations flagged here the literature calls exactly one a scribal error: "
            "PY Ma 225's 22 for 12, per Wyatt 1962, 25 n. 41.",
            "One series, one site, one scribal hand (Pylos Hand 2), one archive moment.",
            "The ratio is Bennett's (1951) and standard; reproducing it validates the parser "
            "rather than establishing anything.",
        ],
        "if_a_base_rate_is_still_wanted": (
            "Use a channel where deviation cannot be policy. Judson, 'Scribes as Editors', "
            "AJA 124.4 (2020), catalogues scribal corrections corpus-wide: an error the scribe "
            "caught and fixed is unambiguously an error."
        ),
    }


def infer_counted_nouns(docs: dict[str, dict], min_tablets: int = 5) -> frozenset[str]:
    """Words that count themselves rather than labelling the commodity in force.

    Linear B writes `MUL 1 ko-wa 2` for one woman and two girls, so `ko-wa` is a counted
    category in its own right. But the Knossos As tablets write `a-ma-no 1` for one *man*,
    the `VIR` being understood from the surrounding lines — there the bare number belongs to
    the logogram, not the name.

    Nothing in the spelling separates the two, so frequency does: a counted category recurs
    across the corpus (`ko-wa` and `ko-wo` on roughly fifty documents each) while a personal
    name takes a bare number on one or two. Getting this wrong is not a small error — it
    detaches every unlabelled entry from its total and leaves almost no auditable arithmetic.
    """
    tally: Counter = Counter()
    for doc in docs.values():
        content = ((doc.get("item") or {}).get("content")) or ""
        tally.update(parse.counted_noun_candidates(content))
    return frozenset(word for word, n in tally.items() if n >= min_tablets)


def load_tablets(min_tablets: int = 5) -> list[LBTablet]:
    """Parse every cached DAMOS document, in two passes.

    The first pass only counts which words take bare numbers, so the second can tell a
    counted category from a personal name. Two passes are needed because the distinction is
    a property of the corpus, not of any one document.
    """
    from la.lb import fetch

    docs = fetch.load_cached()
    nouns = infer_counted_nouns(docs, min_tablets=min_tablets)
    return [parse.parse_document(doc, counted_nouns=nouns) for doc in docs.values()]
