"""Uniquely recoverable numerals in Linear A.

`la.recover` was written script-agnostic so the same question could be asked of the
corpus that prompted it: given a tablet's total, the writing conventions, and where the
break falls, is a damaged Linear A quantity uniquely determined?

**This is a weaker instrument on Linear A than on Linear B, for three reasons that must
travel with every number it produces.**

1. **The values are hypotheses.** Linear B's metrology is solved, so a recovered amount
   there is a claim about the clay. Linear A's fraction values come from Corazza et al.
   2021, two of them (H, A) printed with "(?)", and this project already showed the
   corpus cannot determine them. A recovery here is conditional on that value system, so
   it is reported per system rather than absolutely.
2. **There is no bundling rule.** Linear B's `6 V = 1 T` forbids most amounts in a given
   gap, which is what makes uniqueness common there. Linear A merely writes fractions in
   decreasing order and permits repetition, so gaps admit more readings.
3. **The arithmetic is scarce.** Two exact equations and one bound in 1,883 documents.

So the expected finding is a small number of determinations and an honest count of the
ambiguous ones — and, more usefully, a check on whether the machinery reproduces
restorations scholars have already published. Younger's proposal that the missing amount
on HT 9a b.1 is **JE** is the test case: our residual computed 3/4 independently, and JE
is the sign for 3/4.
"""

from __future__ import annotations

import random
from collections import defaultdict
from fractions import Fraction

from la import recover, values
from la.parse import Quantity, Section, Tablet, fraction_counts, integer_sum


def quantity_terms(quantity: Quantity, decompose: bool = True) -> list[tuple[str, int]]:
    """A quantity as ordered `(sign, count)` terms, whole units first.

    Compound signs are decomposed by default (`JE` to `J E`), because SigLA's tracings
    show the scribe wrote two marks, and the recovery search needs the marks the scribe
    actually made, not the transcription's shorthand.
    """
    terms: list[tuple[str, int]] = []
    if quantity.integer:
        terms.append((recover.WHOLE, quantity.integer))
    signs = values.decompose_all(quantity.fractions) if decompose else list(quantity.fractions)
    # Runs of the same sign collapse into one term with a count, which is how the
    # notation model expects repetition.
    for sign in signs:
        if terms and terms[-1][0] == sign:
            terms[-1] = (sign, terms[-1][1] + 1)
        else:
            terms.append((sign, 1))
    return terms


def quantity_value(quantity: Quantity, system: dict[str, Fraction]) -> Fraction | None:
    """Exact value of a quantity, or None if it uses a sign the system does not value."""
    total = Fraction(quantity.integer or 0)
    for sign, count in fraction_counts([quantity]).items():
        parts = values.decompose_all([sign])
        for part in parts:
            if part not in system:
                return None
        total += count * sum(system[p] for p in parts)
    return total


def section_residual(section: Section, system: dict[str, Fraction]) -> Fraction | None:
    """Recorded total minus summed entries, exactly."""
    total = quantity_value(section.total.quantity, system)
    if total is None:
        return None
    running = Fraction(0)
    for entry in section.entries:
        value = quantity_value(entry.quantity, system)
        if value is None:
            return None
        running += value
    return total - running


def gaps_for(section: Section, decompose: bool = True) -> list[recover.Gap]:
    """The damaged entry quantities in a section, as recovery gaps."""
    out: list[recover.Gap] = []
    for entry in section.entries:
        if entry.quantity.open:
            out.append(
                recover.Gap(
                    where=f"line {entry.line_no}"
                    + (f" ({entry.word})" if entry.word else ""),
                    line=str(entry.line_no),
                    surviving=quantity_terms(entry.quantity, decompose=decompose),
                )
            )
    return out


def recover_section(
    tablet_id: str,
    section: Section,
    system: dict[str, Fraction],
    strict: bool = True,
    repeat_limit: int = 2,
) -> recover.Recovery:
    residual = section_residual(section, system)
    notation = recover.FractionNotation(values=system, repeat_limit=repeat_limit)
    result = recover.classify(
        residual=residual,
        gaps=gaps_for(section),
        notation=notation,
        tablet=tablet_id,
        commodity=section.entries[0].commodity if section.entries else None,
        strict=strict,
        total_damaged=section.total.quantity.open,
    )
    return result


def recover_all(
    docs: dict[str, dict],
    system: dict[str, Fraction] | None = None,
    strict: bool = True,
    repeat_limit: int = 2,
) -> list[recover.Recovery]:
    """Recovery verdicts for every Linear A section where a break touches a quantity."""
    from la.parse import parse_document

    system = system or values.KNOWN_VALUES
    out: list[recover.Recovery] = []
    for doc_id, doc in docs.items():
        tablet: Tablet = parse_document(doc)
        for section in tablet.sections:
            if section.entries_incomplete or len(section.entries) < 2:
                continue
            if not fraction_counts([e.quantity for e in section.entries]) and not fraction_counts(
                [section.total.quantity]
            ):
                continue  # integers only: no fraction evidence either way
            residual = section_residual(section, system)
            # Sections that fail to balance with *nothing* broken are kept, not skipped.
            # They are the whole reason the `ERROR_NO_DAMAGE` verdict exists, and HT 9a is
            # one of them: it is short by exactly 3/4 with every entry on side a intact.
            # Younger places the missing amount on side b, which this corpus stores as a
            # separate document, so no single section can hold both halves of his proposal.
            if not section.has_open_quantity and residual == 0:
                continue
            out.append(recover_section(doc_id, section, system, strict, repeat_limit))
    return out


def error_rate(
    docs: dict[str, dict],
    system: dict[str, Fraction] | None = None,
) -> dict:
    """How often does an intact Linear A section fail to balance?

    The figure the Linear B audit exists to calibrate. It is reported with its own
    denominator in plain sight, because that denominator is the real finding: a rate over
    a handful of sections carries almost no information, and quoting it without the count
    would be the single most misleading thing this project could do.
    """
    from la.parse import parse_document

    system = system or values.KNOWN_VALUES
    scored: list[dict] = []
    for doc_id, doc in docs.items():
        tablet: Tablet = parse_document(doc)
        for section in tablet.sections:
            if len(section.entries) < 2 or not section.yields_equation:
                continue
            residual = section_residual(section, system)
            if residual is None:
                continue
            has_fractions = bool(
                fraction_counts([e.quantity for e in section.entries])
                or fraction_counts([section.total.quantity])
            )
            scored.append({
                "tablet": doc_id,
                "site": tablet.site,
                "entries": len(section.entries),
                "residual": str(residual),
                "balances": residual == 0,
                "has_fractions": has_fractions,
            })
    with_fr = [s for s in scored if s["has_fractions"]]
    integers_only = [s for s in scored if not s["has_fractions"]]
    return {
        "value_system": {k: str(v) for k, v in sorted(system.items())},
        "sections_scored": len(scored),
        "failures": sum(1 for s in scored if not s["balances"]),
        "error_rate": (
            sum(1 for s in scored if not s["balances"]) / len(scored) if scored else None
        ),
        "fraction_bearing": {
            "sections": len(with_fr),
            "failures": sum(1 for s in with_fr if not s["balances"]),
            "error_rate": (
                sum(1 for s in with_fr if not s["balances"]) / len(with_fr) if with_fr else None
            ),
        },
        "integers_only": {
            "sections": len(integers_only),
            "failures": sum(1 for s in integers_only if not s["balances"]),
            "error_rate": (
                sum(1 for s in integers_only if not s["balances"]) / len(integers_only)
                if integers_only else None
            ),
        },
        "caveat": (
            "Fraction-bearing sections are scored against an assumed value system, so a "
            "failure there may indict the values rather than the scribe. Integer-only "
            "sections need no such assumption and are the cleaner comparison with Linear B."
        ),
        "sections": sorted(scored, key=lambda s: (s["balances"], s["tablet"])),
    }


def compare_systems(
    docs: dict[str, dict],
    strict: bool = True,
) -> dict:
    """Do competing published value systems disagree about what is recoverable?

    A restoration that every system agrees on is a claim about the tablet; one that only
    Corazza's values support is a claim about Corazza's values. Keeping them apart is the
    same discipline `la.compare` applies to the arithmetic.
    """
    systems: dict[str, dict[str, Fraction]] = {"Corazza et al. 2021": dict(values.KNOWN_VALUES)}
    for name, overrides in values.ALTERNATIVE_SYSTEMS.items():
        merged = dict(values.KNOWN_VALUES)
        merged.update(overrides)
        systems[name] = merged

    per_system: dict[str, dict] = {}
    determinations: dict[str, set[str]] = {}
    for name, system in systems.items():
        results = recover_all(docs, system, strict=strict)
        per_system[name] = recover.summarise(results)
        determinations[name] = {
            f"{r.tablet}|{c.render(r.gaps)}"
            for r in results
            if r.is_determination
            for c in r.candidates
        }

    all_names = list(systems)
    shared = set.intersection(*determinations.values()) if determinations else set()
    return {
        "systems": per_system,
        "restorations_all_systems_agree_on": sorted(shared),
        "system_specific": {
            name: sorted(determinations[name] - shared) for name in all_names
        },
    }


def holdout_corruption(
    docs: dict[str, dict],
    system: dict[str, Fraction] | None = None,
    strict: bool = True,
    repeat_limit: int = 2,
    trials_per_section: int = 50,
    seed: int = 20260924,
) -> dict:
    """Break Linear A quantities we know the answer to, and see whether recovery finds it.

    The same protocol as the Linear B side, and the comparison between the two is the
    point: it shows how much of the Linear B result came from bundling constraints that
    Linear A does not have.
    """
    from la.parse import parse_document

    system = system or values.KNOWN_VALUES
    rng = random.Random(seed)
    notation = recover.FractionNotation(values=system, repeat_limit=repeat_limit)
    per_verdict: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "correct": 0})
    attempts = 0
    usable = 0

    for doc_id, doc in docs.items():
        tablet: Tablet = parse_document(doc)
        for section in tablet.sections:
            if not section.yields_equation or len(section.entries) < 2:
                continue
            if section_residual(section, system) != 0:
                continue
            usable += 1
            options: list[tuple[int, list[tuple[str, int]], Fraction]] = []
            for i, entry in enumerate(section.entries):
                terms = quantity_terms(entry.quantity)
                if not terms:
                    continue
                true_value = quantity_value(entry.quantity, system)
                if true_value is None:
                    continue
                for prefix in _truncations(terms):
                    lost = true_value - _terms_value(prefix, notation)
                    if lost > 0:
                        options.append((i, prefix, lost))
            if not options:
                continue
            rng.shuffle(options)
            for index, prefix, lost in options[:trials_per_section]:
                attempts += 1
                entry = section.entries[index]
                result = recover.classify(
                    residual=lost,
                    gaps=[recover.Gap(where=f"line {entry.line_no}", line=str(entry.line_no), surviving=prefix)],
                    notation=notation,
                    tablet=doc_id,
                    strict=strict,
                )
                bucket = per_verdict[result.verdict]
                bucket["n"] += 1
                if any(c.value == lost for c in result.candidates):
                    bucket["correct"] += 1

    rows = [
        {
            "verdict": v,
            "means": recover.VERDICT_MEANING[v],
            "n": c["n"],
            "correct": c["correct"],
            "accuracy": c["correct"] / c["n"] if c["n"] else None,
        }
        for v, c in sorted(per_verdict.items(), key=lambda kv: -kv[1]["n"])
    ]
    det = [r for r in rows if r["verdict"] == recover.UNIQUE]
    det_n = sum(r["n"] for r in det)
    return {
        "protocol": (
            "Linear A sections that balance exactly under the assumed value system and carry "
            "no damage are truncated at a legal break point; recovery then restores what it "
            "cannot see."
        ),
        "value_system": {k: str(v) for k, v in sorted(system.items())},
        "repeat_limit": repeat_limit,
        "strict": strict,
        "usable_sections": usable,
        "attempts": attempts,
        "independence_warning": (
            f"{attempts} truncations drawn from {usable} section(s). Truncations of the same "
            "section are not independent; read `usable_sections`, not `attempts`."
        ),
        "by_verdict": rows,
        "determination_n": det_n,
        "determination_rate": det_n / attempts if attempts else None,
        "determination_accuracy": (
            sum(r["correct"] for r in det) / det_n if det_n else None
        ),
    }


def _terms_value(terms: list[tuple[str, int]], notation: recover.Notation) -> Fraction:
    return sum((notation.size(u) * c for u, c in terms), Fraction(0))


def _truncations(terms: list[tuple[str, int]]) -> list[list[tuple[str, int]]]:
    """Every prefix a break could have left of this quantity."""
    out: list[list[tuple[str, int]]] = []
    for keep in range(len(terms), 0, -1):
        prefix = terms[:keep]
        if keep < len(terms):
            out.append(list(prefix))
        unit, count = prefix[-1]
        for reduced in range(1, count):
            out.append(prefix[:-1] + [(unit, reduced)])
    out.append([])
    return out


#: Restorations already proposed in the literature, as targets the search must reproduce.
#: A method that cannot recover a published hypothesis has no standing to propose new ones.
PUBLISHED_HYPOTHESES: dict[str, dict] = {
    "HT 9a": {
        "claim": "the missing amount is JE (3/4) in the broken entry at side b.1",
        "source": "Younger, Linear A Texts, HT commentary (Secondary; site offline, via Wayback)",
        "expected_value": Fraction(3, 4),
    },
    "HT 13": {
        "claim": "KU-RO records 130.5 but the entries total 131: an excess of 1/2",
        "source": "Younger, Linear A Texts, HT commentary (Secondary)",
        "expected_value": Fraction(-1, 2),
    },
    "HT 116b": {
        "claim": "the last stroke of the number 6 in a.3 OLE+MI 6 may be a slip",
        "source": "Younger, Linear A Texts, HT commentary (Secondary)",
        "expected_value": None,  # a numeral-misreading hypothesis, not a lost amount
    },
}


def check_published(
    docs: dict[str, dict],
    system: dict[str, Fraction] | None = None,
    strict: bool = True,
) -> list[dict]:
    """Does the search reproduce restorations scholars have already published?"""
    system = system or values.KNOWN_VALUES
    results = {r.tablet: r for r in recover_all(docs, system, strict=strict)}
    out = []
    for tablet, spec in PUBLISHED_HYPOTHESES.items():
        found = results.get(tablet)
        expected = spec["expected_value"]
        row = {
            "tablet": tablet,
            "published_claim": spec["claim"],
            "source": spec["source"],
            "expected_value": str(expected) if expected is not None else None,
            "reached_by_pipeline": found is not None,
            "verdict": found.verdict if found else None,
            "residual": str(found.residual) if found and found.residual is not None else None,
            "candidates": [c.to_dict(found.gaps) for c in found.candidates[:8]] if found else [],
        }
        if found is not None and expected is not None:
            row["residual_matches_published"] = found.residual == expected
            row["published_value_among_candidates"] = any(
                c.value == expected for c in found.candidates
            )
        out.append(row)
    return out
