"""A second evidence channel: the order fractions are written in.

Linear A scribes appear to write fraction signs in decreasing order of value, so
a sequence `J E` says J > E without any arithmetic. Adjacent pairs therefore give
inequality constraints, and their transitive closure gives many more.

This matters because tablet arithmetic yields almost nothing: three usable
equations in the whole corpus. Ordering evidence is far more plentiful, and it
reaches signs that never appear on a tablet with a preserved total.

Everything here is measured, not assumed:
  * whether any pair is attested in both directions (which would break the rule);
  * whether the resulting graph is acyclic (a cycle would be a contradiction);
  * how likely both of those are by chance;
  * whether the published values actually respect the observed order.
"""

from __future__ import annotations

import itertools
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from fractions import Fraction


@dataclass
class OrderEvidence:
    runs: list[tuple[str, int, list[str]]] = field(default_factory=list)  # tablet, line, sign ids
    pairs: Counter = field(default_factory=Counter)  # (a, b) meaning a written before b
    sites: Counter = field(default_factory=Counter)

    @property
    def heterogeneous_pairs(self) -> Counter:
        """Pairs of *different* signs; a repeated sign says nothing about order."""
        return Counter({p: n for p, n in self.pairs.items() if p[0] != p[1]})

    def dominant_pairs(self, min_ratio: int = 3) -> tuple[Counter, list[dict]]:
        """Keep the majority direction of each pair; report what was overruled.

        Real corpora contain misreadings, so a single counter-example should not
        veto a direction attested thirty times. J before E is written 32 times
        and E before J once — at ZA 8 line 6, a reading Corazza et al. themselves
        call doubtful. Pairs that do not clear `min_ratio` are dropped entirely
        rather than guessed at.
        """
        kept: Counter = Counter()
        overruled: list[dict] = []
        seen: set[frozenset[str]] = set()
        for (a, b), n in self.heterogeneous_pairs.items():
            key = frozenset((a, b))
            if key in seen:
                continue
            seen.add(key)
            m = self.pairs.get((b, a), 0)
            if m == 0:
                kept[(a, b)] = n
            elif n >= max(1, m * min_ratio):
                kept[(a, b)] = n
                overruled.append({"kept": (a, b), "kept_count": n, "dropped": (b, a), "dropped_count": m})
            elif m >= max(1, n * min_ratio):
                kept[(b, a)] = m
                overruled.append({"kept": (b, a), "kept_count": m, "dropped": (a, b), "dropped_count": n})
            else:
                overruled.append({"kept": None, "dropped": (a, b), "dropped_count": n, "rival_count": m})
        return kept, overruled

    def contradictions(self) -> list[tuple[tuple[str, str], int, int]]:
        """Pairs attested in both directions — each one breaks the ordering rule."""
        out = []
        seen = set()
        for (a, b), n in self.heterogeneous_pairs.items():
            if (b, a) in seen or (a, b) in seen:
                continue
            m = self.pairs.get((b, a), 0)
            if m:
                out.append(((a, b), n, m))
            seen.add((a, b))
        return out


def collect(docs: dict[str, dict], decompose: bool = True) -> OrderEvidence:
    """Find runs of adjacent fraction signs, line by line.

    Compound signs are expanded into the marks they are written as (JE -> J E),
    because the corpus records the same thing both ways and SigLA's tracing shows
    two separate marks. Without this, 24 JE tokens hide 24 J-before-E sequences.
    Pass `decompose=False` to see the raw encoding.
    """
    from la.values import decompose_all

    ev = OrderEvidence()
    for doc in docs.values():
        tablet = doc.get("id", "?")
        site = doc.get("site") or "?"
        for line_no, line in enumerate(doc.get("lines") or [], 1):
            run: list[str] = []
            for token in line:
                if token.get("kind") == "fraction" and token.get("id"):
                    run.extend(decompose_all([token["id"]]) if decompose else [token["id"]])
                    continue
                if len(run) >= 2:
                    _record(ev, tablet, line_no, run, site)
                run = []
            if len(run) >= 2:
                _record(ev, tablet, line_no, run, site)
    return ev


def _record(ev: OrderEvidence, tablet: str, line_no: int, run: list[str], site: str) -> None:
    ev.runs.append((tablet, line_no, list(run)))
    ev.sites[site] += 1
    for a, b in zip(run, run[1:]):
        ev.pairs[(a, b)] += 1


def transitive_closure(pairs: Counter) -> set[tuple[str, str]]:
    """All implied 'greater than' relations, following edges as far as they go."""
    adjacency: dict[str, set[str]] = defaultdict(set)
    for (a, b) in pairs:
        if a != b:
            adjacency[a].add(b)
    nodes = set(adjacency) | {b for bs in adjacency.values() for b in bs}
    closure: set[tuple[str, str]] = set()
    for start in nodes:
        stack = list(adjacency[start])
        seen: set[str] = set()
        while stack:
            node = stack.pop()
            if node in seen or node == start:
                continue
            seen.add(node)
            closure.add((start, node))
            stack.extend(adjacency[node])
    return closure


def has_cycle(pairs: Counter) -> bool:
    closure = transitive_closure(pairs)
    return any((b, a) in closure for (a, b) in closure)


def check_against_values(pairs: Counter, values: dict[str, Fraction]) -> dict:
    """Do the published values respect the observed writing order?"""
    checked, respected, violations = 0, 0, []
    for (a, b), n in pairs.items():
        if a == b or a not in values or b not in values:
            continue
        checked += 1
        if values[a] > values[b]:
            respected += 1
        else:
            violations.append({"pair": (a, b), "count": n, "values": (str(values[a]), str(values[b]))})
    return {"checked": checked, "respected": respected, "violations": violations}


def null_model(pairs: Counter, trials: int = 20000, seed: int = 20260923) -> dict:
    """If each observed pair had a random direction, how often would we see this?

    Two questions: would every pair be unidirectional, and would the graph be
    acyclic? Both are properties the real data has, and both could occur by luck.
    """
    unordered = {tuple(sorted(p)) for p in pairs if p[0] != p[1]}
    rng = random.Random(seed)
    acyclic_hits = 0
    for _ in range(trials):
        oriented = Counter()
        for a, b in unordered:
            if rng.random() < 0.5:
                oriented[(a, b)] = 1
            else:
                oriented[(b, a)] = 1
        if not has_cycle(oriented):
            acyclic_hits += 1
    return {
        "distinct_unordered_pairs": len(unordered),
        "trials": trials,
        "p_acyclic_by_chance": acyclic_hits / trials,
    }


def bound_unknowns(
    pairs: Counter,
    values: dict[str, Fraction],
    candidates: list[Fraction],
) -> dict[str, dict]:
    """Narrow each unvalued sign using the signs above and below it in the order."""
    closure = transitive_closure(pairs)
    signs = {s for p in pairs for s in p}
    out: dict[str, dict] = {}
    for sign in sorted(signs - set(values)):
        # sign < value of anything known that is written before it
        upper = [values[a] for (a, b) in closure if b == sign and a in values]
        # sign > value of anything known that is written after it
        lower = [values[b] for (a, b) in closure if a == sign and b in values]
        upper_bound = min(upper) if upper else None
        lower_bound = max(lower) if lower else None
        viable = [
            c for c in candidates
            if (upper_bound is None or c < upper_bound) and (lower_bound is None or c > lower_bound)
        ]
        out[sign] = {
            "upper_bound": str(upper_bound) if upper_bound else None,
            "lower_bound": str(lower_bound) if lower_bound else None,
            "candidates_remaining": len(viable),
            "candidates_total": len(candidates),
            "examples": [str(v) for v in viable[:6]],
        }
    return out
