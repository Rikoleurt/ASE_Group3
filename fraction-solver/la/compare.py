"""Stage B: score the competing published value systems against the corpus.

Four systems disagree about Linear A's fraction values — Corazza et al. 2021,
Younger, Schrijver 2014, Stoltenberg 1955 — and nobody has tested them against
the corpus systematically. Two evidence channels are available:

  * arithmetic — does a system make the exact equations balance?
  * ordering   — does it respect the observed decreasing writing order?

The interesting case is where the channels agree about which entries are weak.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from fractions import Fraction

from la import ordering, values as V
from la.parse import Section
from la.solver import build_equations


@dataclass
class SystemScore:
    name: str
    equations_total: int = 0
    equations_satisfied: int = 0
    pairs_checked: int = 0
    pairs_respected: int = 0
    violations: list[dict] = field(default_factory=list)
    impossible_values: dict[str, str] = field(default_factory=dict)
    differs_from_baseline: dict[str, tuple[str, str]] = field(default_factory=dict)

    @property
    def ordering_rate(self) -> float:
        return self.pairs_respected / self.pairs_checked if self.pairs_checked else 0.0


def system_values(name: str) -> dict[str, Fraction]:
    """A complete value table for a named system: the baseline with its overrides."""
    values = dict(V.KNOWN_VALUES)
    values.update(V.ALTERNATIVE_SYSTEMS.get(name, {}))
    return values


def all_systems() -> dict[str, dict[str, Fraction]]:
    systems = {"Corazza et al. 2021": dict(V.KNOWN_VALUES)}
    for name in V.ALTERNATIVE_SYSTEMS:
        systems[name] = system_values(name)
    return systems


def score_system(
    name: str,
    values: dict[str, Fraction],
    sections: list[tuple[str, Section]],
    pairs: Counter,
    min_attestations: int = 1,
    exclude_pairs: set[tuple[str, str]] | None = None,
) -> SystemScore:
    score = SystemScore(name=name)

    # Arithmetic: how many exact equations does this system satisfy?
    equations = [e for e in build_equations(sections, {}, include_damaged=True) if not e.is_bound]
    for eq in equations:
        score.equations_total += 1
        if eq.satisfied(values):
            score.equations_satisfied += 1

    # Ordering: how many attested pairs does it put in decreasing order?
    filtered = Counter({
        p: n for p, n in pairs.items()
        if n >= min_attestations and (not exclude_pairs or p not in exclude_pairs)
    })
    check = ordering.check_against_values(filtered, values)
    score.pairs_checked = check["checked"]
    score.pairs_respected = check["respected"]
    for v in check["violations"]:
        a, b = v["pair"]
        score.violations.append({
            "pair": f"{V.LABELS.get(a, a)} -> {V.LABELS.get(b, b)}",
            "values": v["values"],
            "attestations": v["count"],
        })

    # Any value outside (0, 1) cannot be a fraction sign.
    for sign, value in values.items():
        if not 0 < value < 1:
            score.impossible_values[V.LABELS.get(sign, sign)] = str(value)

    baseline = V.KNOWN_VALUES
    for sign, value in values.items():
        if sign in baseline and baseline[sign] != value:
            score.differs_from_baseline[V.LABELS.get(sign, sign)] = (str(baseline[sign]), str(value))

    return score


def discriminating_pairs(systems: dict[str, dict[str, Fraction]], pairs: Counter) -> list[dict]:
    """Attested pairs on which the systems disagree — what to re-examine on the clay."""
    out = []
    for (a, b), n in pairs.items():
        verdicts = {}
        for name, values in systems.items():
            if a in values and b in values:
                verdicts[name] = values[a] > values[b]
        if len(set(verdicts.values())) > 1:
            out.append({
                "pair": f"{V.LABELS.get(a, a)} -> {V.LABELS.get(b, b)}",
                "attestations": n,
                "respected_by": sorted(k for k, v in verdicts.items() if v),
                "violated_by": sorted(k for k, v in verdicts.items() if not v),
            })
    return sorted(out, key=lambda d: -d["attestations"])
