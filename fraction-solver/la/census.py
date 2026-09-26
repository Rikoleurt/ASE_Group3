"""Phase 0: count what the corpus can actually support.

This answers the question the whole project hinges on: how many tablets carry a
total, fractions, and intact entries — and which fraction signs ever appear in a
position where their value could be constrained.

Output is a summary to stdout plus CSVs under out/.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

from la.fetch import load_cached
from la.parse import Tablet, evaluate_section, fraction_counts, parse_document
from la import values as values_mod
from la.values import KNOWN_VALUES


def fraction_readings(docs: dict[str, dict]) -> dict[str, str]:
    """Map fraction sign id -> its letter reading, as the corpus spells it."""
    mapping: dict[str, str] = {}
    for doc in docs.values():
        for line in doc.get("lines") or []:
            for token in line:
                if token.get("kind") == "fraction" and token.get("id"):
                    reading = token.get("reading")
                    if reading:
                        mapping.setdefault(token["id"], reading)
    return mapping

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"


def build(docs: dict[str, dict]) -> list[Tablet]:
    return [parse_document(doc) for doc in docs.values()]


def census(tablets: list[Tablet]) -> dict:
    stats: dict = {
        "documents": len(tablets),
        "with_lines": 0,
        "unread": 0,
        "with_any_quantity": 0,
        "with_total": 0,
        "with_fractions": 0,
        "with_total_and_fractions": 0,
        "layouts": Counter(),
        "fraction_occurrences": Counter(),
        "fraction_on_entries": Counter(),
        "fraction_on_totals": Counter(),
        "fraction_tablets": defaultdict(set),
        "constrainable_tablets": 0,
        "constrainable_undamaged": 0,
        "fraction_signs_constrainable": Counter(),
        "integer_check": Counter(),
        "upstream_agreement": Counter(),
    }

    rows_sections: list[dict] = []

    for t in tablets:
        has_lines = bool(t.sections or t.trailing_entries or t.deficits)
        if has_lines:
            stats["with_lines"] += 1
        if t.unread:
            stats["unread"] += 1
        stats["layouts"][t.layout] += 1

        all_quantities = [e.quantity for s in t.sections for e in s.entries]
        all_quantities += [s.total.quantity for s in t.sections]
        all_quantities += [e.quantity for e in t.trailing_entries]
        all_quantities += [e.quantity for e in t.deficits]

        if any(q.has_value for q in all_quantities):
            stats["with_any_quantity"] += 1
        if t.sections:
            stats["with_total"] += 1

        doc_fracs = fraction_counts(all_quantities)
        if doc_fracs:
            stats["with_fractions"] += 1
            for fid, n in doc_fracs.items():
                stats["fraction_occurrences"][fid] += n
                stats["fraction_tablets"][fid].add(t.id)
        if doc_fracs and t.sections:
            stats["with_total_and_fractions"] += 1

        for s in t.sections:
            entry_fracs = fraction_counts([e.quantity for e in s.entries])
            total_fracs = fraction_counts([s.total.quantity])
            for fid, n in entry_fracs.items():
                stats["fraction_on_entries"][fid] += n
            for fid, n in total_fracs.items():
                stats["fraction_on_totals"][fid] += n

            ev = evaluate_section(s, KNOWN_VALUES)

            # Match the solver's definition exactly, so the two commands cannot
            # report different counts for the same corpus: a section constrains
            # fraction values only if it yields an exact equation (nothing broken,
            # entry list complete) and carries a fraction sign.
            constrains = (
                len(s.entries) >= 2
                and bool(entry_fracs or total_fracs)
                and s.yields_equation
            )
            if constrains:
                stats["constrainable_tablets"] += 1
                if not ev["damaged"]:
                    stats["constrainable_undamaged"] += 1
                for fid in set(entry_fracs) | set(total_fracs):
                    stats["fraction_signs_constrainable"][fid] += 1

            if s.entries:
                stats["integer_check"]["balances" if ev["integer_balances"] else "mismatch"] += 1

            rows_sections.append(
                {
                    "tablet": t.id,
                    "site": t.site or "",
                    "support": t.support or "",
                    "period": t.period or "",
                    "scribe": t.scribe or "",
                    "layout": t.layout,
                    "total_line": s.total.line_no,
                    "total_kind": s.total.kind,
                    "entries": len(s.entries),
                    "entry_integer_sum": sum(e.quantity.integer or 0 for e in s.entries),
                    "total_integer": s.total.quantity.integer or 0,
                    "integer_balances": ev["integer_balances"],
                    "integer_delta": ev["integer_delta"],
                    "entry_fractions": ";".join(f"{k}x{v}" for k, v in sorted(entry_fracs.items())),
                    "total_fractions": ";".join(f"{k}x{v}" for k, v in sorted(total_fracs.items())),
                    "unknown_fraction_signs": ";".join(ev["unknown_fraction_signs"]),
                    "fraction_delta": str(ev["fraction_delta"]) if ev["fraction_delta"] is not None else "",
                    "balances_with_known_values": ev["balances"] if ev["balances"] is not None else "",
                    "damaged": ev["damaged"],
                    "constrains_fractions": constrains,
                    "upstream_status": (t.upstream_arithmetic or {}).get("status", ""),
                }
            )

        # Compare our integer verdict with lineara.eu's own, for whole tablets
        # with exactly one section (where the comparison is unambiguous).
        upstream = (t.upstream_arithmetic or {}).get("status")
        if upstream and len(t.sections) == 1 and t.sections[0].entries:
            ours = "balances" if evaluate_section(t.sections[0], KNOWN_VALUES)["integer_balances"] else "mismatch"
            key = f"upstream={upstream} ours={ours}"
            stats["upstream_agreement"][key] += 1

    stats["fraction_tablets"] = {k: len(v) for k, v in stats["fraction_tablets"].items()}
    return stats, rows_sections


def report(stats: dict, rows: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("CENSUS — Linear A fraction evidence")
    print("=" * 72)
    print(f"Documents parsed            : {stats['documents']}")
    print(f"  with any quantity         : {stats['with_any_quantity']}")
    print(f"  with a total (ku-ro etc.) : {stats['with_total']}")
    print(f"  with fraction signs       : {stats['with_fractions']}")
    print(f"  with BOTH total+fractions : {stats['with_total_and_fractions']}")
    print(f"  marked unread             : {stats['unread']}")
    print()
    print(f"Sections that constrain fraction values : {stats['constrainable_tablets']}")
    print(f"  of those, undamaged                   : {stats['constrainable_undamaged']}")
    print()
    print("Integer arithmetic on sections with entries:")
    for k, v in stats["integer_check"].most_common():
        print(f"  {k:10s} {v}")
    print()
    print("Agreement with lineara.eu's own arithmetic status (single-section tablets):")
    for k, v in stats["upstream_agreement"].most_common():
        print(f"  {k:40s} {v}")
    print()
    print("Layouts:")
    for k, v in stats["layouts"].most_common():
        print(f"  {k:36s} {v}")
    print()
    print("Fraction signs — occurrences / tablets / on entries / on totals / constraining sections / known value")
    all_fracs = sorted(
        stats["fraction_occurrences"],
        key=lambda f: -stats["fraction_occurrences"][f],
    )
    for fid in all_fracs:
        known = KNOWN_VALUES.get(fid)
        print(
            f"  {fid:8s} {stats['fraction_occurrences'][fid]:5d} "
            f"{stats['fraction_tablets'].get(fid, 0):5d} "
            f"{stats['fraction_on_entries'].get(fid, 0):5d} "
            f"{stats['fraction_on_totals'].get(fid, 0):5d} "
            f"{stats['fraction_signs_constrainable'].get(fid, 0):5d}  "
            f"{values_mod.describe(fid)}"
        )

    with (OUT_DIR / "sections.csv").open("w", newline="", encoding="utf-8") as fh:
        if rows:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    summary = {k: (dict(v) if isinstance(v, Counter) else v) for k, v in stats.items()}
    (OUT_DIR / "census.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print()
    print(f"Wrote {OUT_DIR / 'sections.csv'} ({len(rows)} sections) and {OUT_DIR / 'census.json'}")


def main() -> None:
    docs = load_cached()
    print(f"Loaded {len(docs)} cached documents")

    tentative = values_mod.tentative_signs()
    print(f"Published values loaded: {len(values_mod.KNOWN_VALUES)} signs "
          f"(Corazza et al. 2021, Tables 8-9); tentative: {', '.join(tentative)}")
    print()

    tablets = build(docs)
    stats, rows = census(tablets)
    report(stats, rows)


if __name__ == "__main__":
    main()
