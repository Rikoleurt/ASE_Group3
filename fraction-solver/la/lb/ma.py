"""The Pylos Ma series: a fixed-ratio invariant, and what it can restore.

**Read this first.** Everything this module computes turned out to be already published,
and one of its outputs is mislabelled. The proportion was identified by **Bennett in
1951**, not by Palaima 2004 as an earlier version of this file claimed. The coarse
rounding of `ME` is quantified by Shelmerdine. The anomaly the audit flags on PY Ma 225 is
Wyatt's, from 1962. Several of the restorations are in *PTT I* and in de Fidio 1982.

Most importantly, **deviation from the ratio is not scribal error.** de Fidio's thesis is
that the extant figures "reflect systematic reductions of a larger assessment", and the
tablets record exemptions and arrears explicitly, so a district assessed below the ratio
is one granted relief. `deviations()` therefore measures a real quantity under a wrong
name: it is deviation from Bennett's ratio, not an accounting error rate, and it cannot
calibrate a Linear A mismatch. See `FINDINGS.md` §7 and `docs/sources.md`.

The module is kept because it validates the parser — four independent agreements with the
literature — and because the ratio genuinely does restore damaged figures. It is not kept
as a source of new claims.

Every Pylos Ma district tablet assesses six commodities in the fixed proportion
**7 : 7 : 2 : 3 : 1.5 : 150**, a machine-checkable invariant across eighteen tablets in a
*deciphered* script. It supports three things the rest of this project cannot:

1. **A second, independent arithmetic channel.** Within-tablet totals are scarce at
   Knossos and most surviving ones are fragmentary. A fixed ratio constrains every
   assessment line whether or not the tablet carries a total at all.
2. **Restoration without a total.** PY Ma 397 reads `KE M 2[` and PY Ma 365 reads
   `RI M 14[`. Neither tablet's total survives, but the ratio predicts what each value
   must have been, so the break is recoverable from the series rather than the tablet.
   That is a different constraint from the one `la.recover` uses on totals, and the two
   agree or disagree independently.
3. **A test of the invariant itself.** The ratio is taken from a secondary source, so it
   is fitted here from the tablets rather than assumed, and the fitted proportion is
   reported against the published one.

**What the data shows, and why the scale factor matters.** The assessment scale is
`*146 / 7`. Where that is a whole number the six values can all be integers; where it is
not, the scribe had to round, and rounding is not error. Separating the two is the
difference between "Mycenaean scribes made mistakes" and "Mycenaean scribes rounded",
so deviations are reported against the nearest *writeable* value, not the exact real
number.

Commodity order follows the tablets: `*146`, `RI`, `KE`, `*152`, `O`, `ME`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from statistics import median

from la.lb.parse import LBTablet

#: The six commodities, in the order they are written on the assessment line.
COMMODITIES: tuple[str, ...] = ("*146", "RI", "KE", "*152", "O", "ME")

#: First identified by Bennett (1951); "usually cited as 7 : 7 : 2 : 3 : 1.5 : 150"
#: (Shelmerdine, "Mycenaean Taxation", read). The literature labels the six commodities
#: A-F, matching this order: A = *146 (textiles), B = RI, C = KE, D = *152 (oxhides),
#: E = O, F = ME.
PUBLISHED_RATIO: tuple[Fraction, ...] = (
    Fraction(7), Fraction(7), Fraction(2), Fraction(3), Fraction(3, 2), Fraction(150),
)
PUBLISHED_SOURCE = (
    "Bennett 1951, via Shelmerdine, 'Mycenaean Taxation' (Read); "
    "foundational study Wyatt, AJA 66 (1962) 21-41"
)


@dataclass
class Assessment:
    """One district's assessment line: six written numbers, some possibly broken."""

    tablet: str
    damos_id: int
    place: str | None
    values: dict[str, int] = field(default_factory=dict)
    damaged: set[str] = field(default_factory=set)
    restored: set[str] = field(default_factory=set)

    @property
    def complete(self) -> bool:
        return all(c in self.values for c in COMMODITIES) and not self.damaged

    @property
    def scale(self) -> Fraction | None:
        """The assessment's multiplier, from the anchor commodity `*146`."""
        anchor = self.values.get("*146")
        if anchor is None or "*146" in self.damaged:
            return None
        return Fraction(anchor, 7)

    def to_dict(self) -> dict:
        return {
            "tablet": self.tablet,
            "place": self.place,
            "values": {c: self.values.get(c) for c in COMMODITIES},
            "damaged": sorted(self.damaged),
            "restored": sorted(self.restored),
            "scale": str(self.scale) if self.scale is not None else None,
        }


def extract(tablets: list[LBTablet]) -> list[Assessment]:
    """The assessment line of every Ma tablet.

    The assessment is the first line carrying measures; later lines are deliveries
    (`a-pu-do-si`), deficits (`o-pe-ro`) and exemptions (`o-u-di-do-si`), which record
    what happened to the assessment rather than the assessment itself and must not be
    mixed into it.
    """
    out: list[Assessment] = []
    for tablet in tablets:
        if tablet.series_code != "M" or tablet.subseries != "a":
            continue
        entries = [m for m in tablet.measures if m.role == "entry"]
        if not entries:
            continue
        first_line = min(m.line_no for m in entries)
        row = [m for m in entries if m.line_no == first_line]
        assessment = Assessment(tablet=tablet.id, damos_id=tablet.damos_id, place=None)
        for m in row:
            if m.commodity not in COMMODITIES:
                continue
            # The written number, ignoring which metrogram carries it: the ratio is a
            # proportion between the numerals as written, not between absolute weights.
            total = sum(count for _unit, count in m.terms)
            assessment.values[m.commodity] = total
            if m.damaged:
                assessment.damaged.add(m.commodity)
            if m.restored:
                assessment.restored.add(m.commodity)
        if assessment.values:
            out.append(assessment)
    return sorted(out, key=lambda a: a.damos_id)


# ---------------------------------------------------------------------------
# Fitting the ratio
# ---------------------------------------------------------------------------


def fit_ratio(
    assessments: list[Assessment],
    anchor: str = "*146",
    granularity: dict[str, int] | None = None,
) -> dict:
    """Derive the proportion from the tablets, and compare with the published one.

    **Consensus, not average.** Each commodity's candidate ratios are the per-tablet
    observed ratios themselves (plus the published value), and the winner is whichever
    one the most tablets match *exactly*, ties going to the simplest fraction. This
    matters: an earlier version took the median, which on an even-sized sample averages
    the two middle observations and returned `O = 35/23` — a number no scribe ever used,
    manufactured by the estimator rather than found in the corpus, and which then looked
    like a disagreement with Palaima. Consensus scoring cannot invent a value that no
    tablet exhibits.

    The median is still reported, because the gap between the two is a useful warning
    about how thin the sample is.
    """
    granularity = granularity or {}
    per_commodity: dict[str, list[Fraction]] = {c: [] for c in COMMODITIES}
    observations: dict[str, list[tuple[int, int]]] = {c: [] for c in COMMODITIES}
    used = 0
    for a in assessments:
        base = a.values.get(anchor)
        if not base or anchor in a.damaged:
            continue
        used += 1
        for c in COMMODITIES:
            v = a.values.get(c)
            if v is None or c in a.damaged:
                continue
            per_commodity[c].append(Fraction(v, base))
            observations[c].append((base, v))

    anchor_published = PUBLISHED_RATIO[COMMODITIES.index(anchor)]
    published = dict(zip(COMMODITIES, PUBLISHED_RATIO))
    fitted: dict[str, Fraction] = {}
    scores: dict[str, int] = {}

    for c in COMMODITIES:
        obs = observations[c]
        if not obs:
            continue
        candidates = _simple_candidates(published[c])
        best, best_score = None, -1
        # The published ratio is the hypothesis under test, so it is tried first and only
        # displaced by a candidate that fits *strictly better*. Ordering by simplicity
        # alone let `ME = 148` beat `150` on an exact tie, which is a worse answer
        # reported with the same confidence.
        target = published[c]
        for cand in sorted(
            candidates, key=lambda f: (f != target, f.denominator, abs(f - target))
        ):
            g = granularity.get(c, 1)
            hits = sum(
                1 for base, written in obs
                if _nearest_multiple(Fraction(base) * cand / anchor_published, g) == written
            )
            if hits > best_score:
                best, best_score = cand, hits
        fitted[c] = best  # type: ignore[assignment]
        scores[c] = best_score

    medians = {
        c: (Fraction(median(sorted(v))) * anchor_published if v else None)
        for c, v in per_commodity.items()
    }
    return {
        "anchor": anchor,
        "tablets_used": used,
        "method": "consensus: the candidate ratio matching the most tablets exactly",
        "fitted_ratio": {c: str(v) for c, v in fitted.items()},
        "fitted_exact_matches": scores,
        "median_ratio_for_comparison": {
            c: (str(v) if v is not None else None) for c, v in medians.items()
        },
        "published_ratio": {c: str(v) for c, v in published.items()},
        "published_source": PUBLISHED_SOURCE,
        "matches_published": {
            c: (c in fitted and fitted[c] == published[c]) for c in COMMODITIES
        },
        "agrees_on_all_six": all(
            c in fitted and fitted[c] == published[c] for c in COMMODITIES
        ),
        "observations_per_commodity": {c: len(v) for c, v in per_commodity.items()},
    }


#: The largest denominator a candidate ratio may have. Administrative proportions are
#: simple — Palaima's six are 7, 7, 2, 3, 3/2 and 150, none worse than a half — and
#: without this bound the fit chases the sample: an unbounded search returned `*152 =
#: 70/23`, which matched one more tablet than 3 does and is otherwise meaningless. The
#: prior that real unit ratios are simple does more work here than one extra data point.
MAX_RATIO_DENOMINATOR = 4


def _simple_candidates(published: Fraction) -> set[Fraction]:
    """Simple fractions within a factor of two of the published ratio, as the search space."""
    low, high = published / 2, published * 2
    out: set[Fraction] = {published}
    for q in range(1, MAX_RATIO_DENOMINATOR + 1):
        for p in range(1, int(high * q) + 1):
            f = Fraction(p, q)
            if low <= f <= high:
                out.add(f)
    return out


def rounding_direction(
    assessments: list[Assessment],
    ratio: dict[str, Fraction] | None = None,
    anchor: str = "*146",
) -> dict:
    """When the exact assessment was not a whole number, did the scribe round up or down?

    Reported as a description, not fitted as a parameter: with a dozen observations per
    commodity, adding a rounding *mode* to the model would explain the residue by
    construction. The asymmetry is worth seeing, but it is a hypothesis for a larger
    corpus, not a result from this one.
    """
    ratio = ratio or dict(zip(COMMODITIES, PUBLISHED_RATIO))
    anchor_ratio = ratio[anchor]
    up = down = exact_int = 0
    for a in assessments:
        base = a.values.get(anchor)
        if not base or anchor in a.damaged:
            continue
        scale = Fraction(base) / anchor_ratio
        for c in COMMODITIES:
            written = a.values.get(c)
            if written is None or c in a.damaged or c == anchor:
                continue
            exact = scale * ratio[c]
            if exact.denominator == 1:
                exact_int += 1
            elif written > exact:
                up += 1
            elif written < exact:
                down += 1
    total = up + down
    return {
        "exact_integer_predictions": exact_int,
        "fractional_predictions": total,
        "rounded_up": up,
        "rounded_down": down,
        "down_share": down / total if total else None,
        "note": (
            "Descriptive only. A consistent preference would be a real finding about "
            "Mycenaean practice, but this sample cannot establish one."
        ),
    }


# ---------------------------------------------------------------------------
# Deviation, separating rounding from error
# ---------------------------------------------------------------------------


@dataclass
class Deviation:
    tablet: str
    commodity: str
    written: int
    exact: Fraction
    nearest_writeable: int
    deviation: int           # written minus nearest writeable integer
    rounding_only: bool      # the exact value was not an integer and this is a rounding

    def to_dict(self) -> dict:
        return {
            "tablet": self.tablet,
            "commodity": self.commodity,
            "written": self.written,
            "exact": str(self.exact),
            "nearest_writeable": self.nearest_writeable,
            "deviation": self.deviation,
            "rounding_only": self.rounding_only,
        }


def _nearest_int(value: Fraction) -> int:
    """Round half away from zero, which is what a scribe writing strokes would do."""
    floor = value.numerator // value.denominator
    frac = value - floor
    return floor + 1 if frac >= Fraction(1, 2) else floor


def _nearest_multiple(value: Fraction, granularity: int) -> int:
    """The nearest multiple of `granularity`."""
    if granularity <= 1:
        return _nearest_int(value)
    return _nearest_int(value / granularity) * granularity


#: Rounding granularities to test. A scribe assessing 514.3 units of a bulk commodity may
#: well have written 500; one assessing 6.86 of a countable one had no such latitude.
GRANULARITIES: tuple[int, ...] = (1, 5, 10, 25, 50, 100)


def rounding_granularity(
    assessments: list[Assessment],
    ratio: dict[str, Fraction] | None = None,
    anchor: str = "*146",
) -> dict:
    """At what granularity was each commodity assessed?

    This exists because the first run of `deviations` made the Ma scribes look careless
    about `ME`: it matched the ratio only 42% of the time, against 70-89% for the other
    five. But every `ME` deviation was a multiple of 7 — the signature of dividing by 7
    and then writing a round number. `ME` values are 400, 500, 600, 900, 1000, 1350,
    1500. The scribe was not miscalculating; they were rounding to the nearest hundred.

    Fitting the granularity rather than assuming it turns 22 apparent errors into a
    statement about Mycenaean practice, and leaves behind the deviations that a coarser
    rounding cannot explain — which are the ones worth an epigrapher's time.
    """
    ratio = ratio or dict(zip(COMMODITIES, PUBLISHED_RATIO))
    anchor_ratio = ratio[anchor]
    rows = []
    for c in COMMODITIES:
        if c == anchor:
            continue
        observed: list[tuple[Fraction, int]] = []
        for a in assessments:
            base = a.values.get(anchor)
            written = a.values.get(c)
            if not base or anchor in a.damaged or written is None or c in a.damaged:
                continue
            observed.append(((Fraction(base) / anchor_ratio) * ratio[c], written))
        if not observed:
            continue
        scores = {
            g: sum(1 for exact, written in observed if _nearest_multiple(exact, g) == written)
            for g in GRANULARITIES
        }
        # Prefer the finest granularity that explains the most: a coarse one can only
        # ever fit more, so ties must go to the more constrained explanation.
        best = max(GRANULARITIES, key=lambda g: (scores[g], -g))
        rows.append({
            "commodity": c,
            "n": len(observed),
            "best_granularity": best,
            "matches_at_best": scores[best],
            "rate_at_best": scores[best] / len(observed),
            "matches_at_unit": scores[1],
            "rate_at_unit": scores[1] / len(observed),
            "scores": scores,
        })
    return {
        "granularities_tested": list(GRANULARITIES),
        "by_commodity": rows,
        "summary": {
            r["commodity"]: r["best_granularity"] for r in rows
        },
    }


def deviations(
    assessments: list[Assessment],
    ratio: dict[str, Fraction] | None = None,
    anchor: str = "*146",
    granularity: dict[str, int] | None = None,
) -> dict:
    """Per-value deviation from the ratio, with rounding separated from real error.

    A value is `rounding_only` when the exact prediction was not a whole number and the
    scribe wrote the nearest writeable one. Anything else is a deviation the ratio
    cannot explain, and those are the cases worth an epigrapher's attention.

    `granularity` sets how coarsely each commodity was rounded; pass the fitted values
    from `rounding_granularity` rather than assuming unit precision, or `ME`'s round
    hundreds will be scored as two dozen arithmetic errors.
    """
    ratio = ratio or dict(zip(COMMODITIES, PUBLISHED_RATIO))
    granularity = granularity or {}
    anchor_ratio = ratio[anchor]
    rows: list[Deviation] = []
    exact_tablets = 0
    checked_tablets = 0

    for a in assessments:
        base = a.values.get(anchor)
        if not base or anchor in a.damaged:
            continue
        checked_tablets += 1
        scale = Fraction(base) / anchor_ratio
        tablet_exact = True
        for c in COMMODITIES:
            written = a.values.get(c)
            if written is None or c in a.damaged or c == anchor:
                continue
            exact = scale * ratio[c]
            nearest = _nearest_multiple(exact, granularity.get(c, 1))
            delta = written - nearest
            row = Deviation(
                tablet=a.tablet,
                commodity=c,
                written=written,
                exact=exact,
                nearest_writeable=nearest,
                deviation=delta,
                rounding_only=delta == 0 and exact != nearest,
            )
            rows.append(row)
            if delta != 0:
                tablet_exact = False
        if tablet_exact:
            exact_tablets += 1

    off = [r for r in rows if r.deviation != 0]
    integral_scale = [
        a.tablet for a in assessments
        if a.scale is not None and a.scale.denominator == 1
    ]
    return {
        "ratio_used": {c: str(v) for c, v in ratio.items()},
        "tablets_checked": checked_tablets,
        "tablets_matching_exactly": exact_tablets,
        "values_checked": len(rows),
        "values_off": len(off),
        "value_error_rate": len(off) / len(rows) if rows else None,
        "mean_absolute_deviation": (
            sum(abs(r.deviation) for r in rows) / len(rows) if rows else None
        ),
        "pure_roundings": sum(1 for r in rows if r.rounding_only),
        "tablets_with_integral_scale": integral_scale,
        # The substantive question: is deviation concentrated where the scribe had no
        # whole number to write? If so, this is rounding practice, not incompetence.
        "by_scale_kind": [
            {
                "scale": kind,
                "values": len(items),
                "off": sum(1 for r in items if r.deviation != 0),
                "rate": (
                    sum(1 for r in items if r.deviation != 0) / len(items) if items else None
                ),
            }
            for kind, items in (
                ("integral", [r for r in rows if r.exact.denominator == 1]),
                ("fractional", [r for r in rows if r.exact.denominator != 1]),
            )
            if items
        ],
        "by_commodity": [
            {
                "commodity": c,
                "values": sum(1 for r in rows if r.commodity == c),
                "off": sum(1 for r in rows if r.commodity == c and r.deviation != 0),
                "mean_deviation": (
                    sum(r.deviation for r in rows if r.commodity == c)
                    / max(sum(1 for r in rows if r.commodity == c), 1)
                ),
            }
            for c in COMMODITIES
        ],
        "outliers": [r.to_dict() for r in sorted(off, key=lambda r: -abs(r.deviation))[:15]],
    }


# ---------------------------------------------------------------------------
# Restoration from the ratio
# ---------------------------------------------------------------------------


@dataclass
class RatioRestoration:
    tablet: str
    commodity: str
    surviving: int | None
    predicted: int
    consistent_with_break: bool
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "tablet": self.tablet,
            "commodity": self.commodity,
            "surviving": self.surviving,
            "predicted": self.predicted,
            "consistent_with_break": self.consistent_with_break,
            "note": self.note,
        }


def restore_damaged(
    assessments: list[Assessment],
    ratio: dict[str, Fraction] | None = None,
    anchor: str = "*146",
    granularity: dict[str, int] | None = None,
) -> list[RatioRestoration]:
    """Predict each broken assessment value from the ratio.

    A prediction is only admissible if the break can actually accommodate it: a numeral
    cut short can only have been *larger*, never smaller, so a prediction below what
    survives refutes itself rather than the reading. That check is what stops this being
    a machine for confirming whatever the ratio says.
    """
    ratio = ratio or dict(zip(COMMODITIES, PUBLISHED_RATIO))
    granularity = granularity or {}
    anchor_ratio = ratio[anchor]
    out: list[RatioRestoration] = []
    for a in assessments:
        base = a.values.get(anchor)
        if not base or anchor in a.damaged:
            continue
        scale = Fraction(base) / anchor_ratio
        for c in sorted(a.damaged):
            if c == anchor:
                continue
            surviving = a.values.get(c)
            predicted = _nearest_multiple(scale * ratio[c], granularity.get(c, 1))
            ok = surviving is None or predicted >= surviving
            note = ""
            if surviving is not None and not ok:
                note = (
                    f"Ratio predicts {predicted} but {surviving} already survives; a break "
                    "cannot reduce a numeral, so either the reading or the ratio is wrong here."
                )
            elif surviving is not None and predicted == surviving:
                note = "The break apparently hid nothing: the surviving value already fits."
            out.append(
                RatioRestoration(
                    tablet=a.tablet,
                    commodity=c,
                    surviving=surviving,
                    predicted=predicted,
                    consistent_with_break=ok,
                    note=note,
                )
            )
    return out


def holdout(
    assessments: list[Assessment],
    ratio: dict[str, Fraction] | None = None,
    anchor: str = "*146",
    granularity: dict[str, int] | None = None,
) -> dict:
    """Hide each intact value in turn and predict it from the other five.

    The only honest accuracy figure for the restorations above: if the ratio cannot
    re-predict values that survive, its predictions for values that do not are worthless.
    """
    ratio = ratio or dict(zip(COMMODITIES, PUBLISHED_RATIO))
    granularity = granularity or {}
    anchor_ratio = ratio[anchor]
    per_commodity: dict[str, dict[str, int]] = {}
    for a in assessments:
        base = a.values.get(anchor)
        if not base or anchor in a.damaged:
            continue
        scale = Fraction(base) / anchor_ratio
        for c in COMMODITIES:
            if c == anchor or c in a.damaged or c not in a.values:
                continue
            predicted = _nearest_multiple(scale * ratio[c], granularity.get(c, 1))
            bucket = per_commodity.setdefault(c, {"n": 0, "exact": 0, "within_1": 0})
            bucket["n"] += 1
            if predicted == a.values[c]:
                bucket["exact"] += 1
            if abs(predicted - a.values[c]) <= 1:
                bucket["within_1"] += 1
    rows = [
        {
            "commodity": c,
            "n": b["n"],
            "exact": b["exact"],
            "within_1": b["within_1"],
            "exact_rate": b["exact"] / b["n"] if b["n"] else None,
            "within_1_rate": b["within_1"] / b["n"] if b["n"] else None,
        }
        for c, b in per_commodity.items()
    ]
    total_n = sum(r["n"] for r in rows)
    return {
        "protocol": (
            f"Each surviving value is predicted from {anchor} alone via the ratio, and "
            "compared with what the scribe wrote."
        ),
        "by_commodity": rows,
        "n": total_n,
        "exact": sum(r["exact"] for r in rows),
        "exact_rate": sum(r["exact"] for r in rows) / total_n if total_n else None,
        "within_1_rate": sum(r["within_1"] for r in rows) / total_n if total_n else None,
    }


def report(tablets: list[LBTablet]) -> dict:
    """The whole Ma pilot: invariant, rounding, deviations, restorations, validation.

    Deviations are reported twice — at unit precision and at the fitted granularity —
    because the difference between the two *is* the finding. At unit precision the series
    looks error-strewn; at the fitted granularity most of that resolves into a rounding
    convention, and what survives is a much shorter list of real anomalies.
    """
    assessments = extract(tablets)
    published = dict(zip(COMMODITIES, PUBLISHED_RATIO))
    grain = rounding_granularity(assessments, published)
    fitted_grain = grain["summary"]
    return {
        "commodities": list(COMMODITIES),
        "tablets": len(assessments),
        "complete_assessments": sum(1 for a in assessments if a.complete),
        "assessments": [a.to_dict() for a in assessments],
        "ratio_fit": fit_ratio(assessments, granularity=fitted_grain),
        "rounding": grain,
        "rounding_direction": rounding_direction(assessments, published),
        "deviations_at_unit_precision": deviations(assessments, published),
        "deviations": deviations(assessments, published, granularity=fitted_grain),
        "restorations": [
            r.to_dict() for r in restore_damaged(assessments, published, granularity=fitted_grain)
        ],
        "holdout": holdout(assessments, published, granularity=fitted_grain),
    }
