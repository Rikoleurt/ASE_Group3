"""Command line entry point.

Linear A: fetch, census, solve, validate, order, compare, ratios, recover.
Linear B: lb-fetch, lb-audit, lb-ma — the deciphered control corpus that calibrates
what a Linear A mismatch means.
"""

from __future__ import annotations

import argparse
import json
from fractions import Fraction
from pathlib import Path

from la import values as values_mod
from la.census import fraction_readings, main as census_main
from la.fetch import load_cached, main as fetch_main
from la.parse import Section, parse_document
from la import ordering
from la import compare
from la import ratios
from la.solver import (
    analyse,
    build_equations,
    candidate_values,
    enumerate_assignments,
    leave_one_out,
    null_model,
)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"


def collect_sections(include_damaged: bool = False) -> tuple[list[tuple[str, Section]], dict[str, Fraction]]:
    docs = load_cached()
    known = values_mod.bind_to_sign_ids(fraction_readings(docs))
    sections: list[tuple[str, Section]] = []
    for doc in docs.values():
        tablet = parse_document(doc)
        for section in tablet.sections:
            if section.total.kind == "grand_total":
                continue  # a grand total sums sub-totals, not entries
            sections.append((tablet.id, section))
    return sections, known


def cmd_solve(args: argparse.Namespace) -> None:
    sections, known = collect_sections()
    if args.treat_all_unknown:
        known = {}
        print("Mode: every fraction sign treated as unknown (published values ignored)\n")
    all_equations = build_equations(sections, known, include_damaged=args.include_damaged)
    equations = [e for e in all_equations if e.satisfiable]
    rejected = [e for e in all_equations if not e.satisfiable]
    live = [e for e in equations if e.coefficients]
    trivial_ok = [e for e in equations if e.is_trivial]

    print(f"Sections with fraction arithmetic : {len(all_equations)}")
    print(f"  usable (integers already balance): {len(equations)}")
    print(f"    carrying unknown signs         : {len(live)}")
    print(f"    fully valued (test known values): {len(trivial_ok)}")
    print(f"  rejected (integer sums do not balance): {len(rejected)}")
    for e in rejected:
        kind = "fraction mismatch under known values" if e.is_trivial and abs(e.constant) < 1 else "integer mismatch"
        print(f"    {e.tablet:14s} line {e.total_line:2d}  residual {e.constant}  [{kind}]")
    print()

    if not live:
        print("No usable equation carries an unknown fraction sign. Nothing to solve.")
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "solve.json").write_text(json.dumps({
            "usable_equations": len(equations), "rejected": len(rejected), "unknowns": [],
        }, indent=2), encoding="utf-8")
        return

    ident = analyse(equations)
    print(f"Unknown signs in the system : {', '.join(ident.unknowns)}")
    print(f"Rank                        : {ident.rank} of {len(ident.unknowns)} unknowns")
    print(f"Consistent                  : {ident.consistent}")
    print(f"Free dimensions             : {ident.free_dimensions}")
    if ident.determined:
        print("Determined by the corpus alone:")
        for sign, value in sorted(ident.determined.items()):
            label = values_mod.LABELS.get(sign, sign)
            # A fraction sign must denote a proper fraction. A solution outside
            # (0, 1) means the arithmetic is consistent but the tablet is not:
            # a sign is lost, misread, or the scribe erred.
            flag = "" if 0 < value < 1 else "   <-- IMPOSSIBLE for a fraction sign"
            print(f"  {label} ({sign}) = {value}{flag}")
    else:
        print("Determined by the corpus alone: none")
    print()

    result: dict = {
        "rejected_equations": [
            {"tablet": e.tablet, "total_line": e.total_line, "constant": str(e.constant)} for e in rejected
        ],
        "equations": [
            {
                "tablet": e.tablet,
                "total_line": e.total_line,
                "coefficients": e.coefficients,
                "constant": str(e.constant),
                "damaged": e.damaged,
            }
            for e in equations
        ],
        "unknowns": ident.unknowns,
        "rank": ident.rank,
        "consistent": ident.consistent,
        "free_dimensions": ident.free_dimensions,
        "determined": {k: str(v) for k, v in ident.determined.items()},
    }

    if ident.unknowns and len(ident.unknowns) <= args.max_unknowns:
        grid = candidate_values(unit_only=(args.grid == "unit"))
        try:
            ranked = enumerate_assignments(equations, ident.unknowns, grid=grid)
        except ValueError as exc:
            print(f"Enumeration skipped: {exc}")
            ranked = []
        if ranked:
            best_score = ranked[0][1]
            print(f"Best assignments satisfy {best_score} of {len(live)} equations:")
            for assignment, hits in ranked[:5]:
                shown = ", ".join(f"{k}={v}" for k, v in sorted(assignment.items()))
                print(f"  {hits:3d}  {shown}")
            stats = null_model(equations, ident.unknowns, trials=args.null_trials, grid=grid)
            print()
            print(f"Null model over {stats['trials']} random assignments: "
                  f"mean {stats['mean']:.2f}, p95 {stats['p95']}, p99 {stats['p99']}, max {stats['max']}")
            verdict = "ABOVE" if best_score > stats["p99"] else "NOT above"
            print(f"Best score is {verdict} the 99th percentile of chance.")
            result["best_assignments"] = [
                {"assignment": {k: str(v) for k, v in a.items()}, "satisfied": n} for a, n in ranked[:20]
            ]
            result["null_model"] = stats

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "solve.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT_DIR / 'solve.json'}")


def cmd_validate(args: argparse.Namespace) -> None:
    sections, known = collect_sections()
    if not known:
        print("No published values are bound to sign ids; nothing to validate against.")
        return
    print("Leave-one-out recovery of published values")
    print("(hide one value, try to re-derive it from the corpus alone)\n")
    results = leave_one_out(sections, known)
    recovered = 0
    for sign, r in sorted(results.items()):
        status = "correct" if r["correct"] else ("wrong" if r["determined"] else "not determined")
        recovered += bool(r["correct"])
        print(f"  {sign:8s} true={r['true_value']:6s} equations={r['equations']:3d} "
              f"in-system={str(r['appears_in_system']):5s} -> {status}"
              + (f" ({r['recovered']})" if r["recovered"] else ""))
    print(f"\nRecovered {recovered} of {len(results)}.")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "validate.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_DIR / 'validate.json'}")


def cmd_order(args: argparse.Namespace) -> None:
    from fractions import Fraction as F

    docs = load_cached()
    raw_ev = ordering.collect(docs, decompose=False)
    ev = ordering.collect(docs)
    pairs, overruled = ev.dominant_pairs()
    contradictions = ev.contradictions()

    print("Compound signs are expanded into the marks they are written as "
          "(JE -> J E), matching SigLA's tracing.")
    print(f"  raw encoding      : {len(raw_ev.runs)} runs, {sum(raw_ev.heterogeneous_pairs.values())} transitions")
    print(f"  decomposed        : {len(ev.runs)} runs, {sum(ev.heterogeneous_pairs.values())} transitions")
    for o in overruled:
        if o["kept"]:
            ka, kb = o["kept"]; da, db = o["dropped"]
            print(f"  majority direction: {values_mod.LABELS.get(ka, ka)}->{values_mod.LABELS.get(kb, kb)} "
                  f"(n={o['kept_count']}) overrules {values_mod.LABELS.get(da, da)}->{values_mod.LABELS.get(db, db)} "
                  f"(n={o['dropped_count']})")
    print()

    print(f"Runs of two or more adjacent fractions : {len(ev.runs)}")
    print(f"  across sites                         : {', '.join(f'{k} {v}' for k, v in ev.sites.most_common())}")
    print(f"Transitions between different signs    : {sum(pairs.values())}")
    print(f"Distinct ordered pairs                 : {len(pairs)}")
    print(f"Pairs attested in BOTH directions      : {len(contradictions)}")
    print(f"Graph acyclic                          : {not ordering.has_cycle(pairs)}")

    stats = ordering.null_model(pairs, trials=args.null_trials)
    print(f"Chance of an acyclic graph under random directions: {stats['p_acyclic_by_chance']:.4f}")
    print()

    check = ordering.check_against_values(pairs, values_mod.KNOWN_VALUES)
    print(f"Published values respect the observed order: {check['respected']} of {check['checked']} pairs")
    for v in check["violations"]:
        a, b = v["pair"]
        la, lb = values_mod.LABELS.get(a, a), values_mod.LABELS.get(b, b)
        tentative = " [both/one value marked tentative in the paper]" if a in values_mod.tentative_signs() or b in values_mod.tentative_signs() else ""
        print(f"  violation: {la} -> {lb}  ({v['values'][0]} is not greater than {v['values'][1]}){tentative}")
    print()

    candidates = [F(n, 60) for n in range(1, 60)]
    bounds = ordering.bound_unknowns(pairs, values_mod.KNOWN_VALUES, candidates)
    if bounds:
        print("Signs without a published value, bounded by their neighbours:")
        for sign, b in bounds.items():
            print(f"  {sign:7s} {values_mod.describe(sign):44s} "
                  f"lower {b['lower_bound'] or '-':6s} upper {b['upper_bound'] or '-':6s} "
                  f"{b['candidates_remaining']}/{b['candidates_total']} candidates remain")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "ordering.json").write_text(json.dumps({
        "runs": len(ev.runs),
        "transitions": sum(pairs.values()),
        "distinct_pairs": {f"{a}>{b}": n for (a, b), n in pairs.items()},
        "contradictions": contradictions,
        "acyclic": not ordering.has_cycle(pairs),
        "null_model": stats,
        "value_check": check,
        "bounds": bounds,
    }, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT_DIR / 'ordering.json'}")



def cmd_compare(args: argparse.Namespace) -> None:
    from fractions import Fraction as F

    docs = load_cached()
    sections, _ = collect_sections()
    pairs = ordering.collect(docs).heterogeneous_pairs
    systems = compare.all_systems()

    print("Scoring published value systems against the corpus")
    print("(arithmetic = exact equations satisfied; ordering = attested pairs in decreasing order)")
    print("NOTE: arithmetic does not discriminate here — every system shares J = 1/2,")
    print("      so all of them satisfy HT 104 and all fail HT 9a. Ordering does the work.")
    print()

    result: dict = {"systems": {}, "sensitivity": {}, "windows": {}}
    for label, min_n, excl in [
        ("all attested pairs (n>=1)", 1, None),
        ("pairs with n>=2", 2, None),
        ("n>=1, KH 86 edge removed", 1, {("A701", "A702")}),
    ]:
        print(f"-- {label}")
        block = {}
        for name, vals in systems.items():
            sc = compare.score_system(name, vals, sections, pairs, min_attestations=min_n, exclude_pairs=excl)
            viol = ", ".join(f"{v['pair']} (n={v['attestations']})" for v in sc.violations) or "none"
            print(f"   {name:22s} arithmetic {sc.equations_satisfied}/{sc.equations_total}   "
                  f"ordering {sc.pairs_respected}/{sc.pairs_checked}   violations: {viol}")
            block[name] = {
                "arithmetic": [sc.equations_satisfied, sc.equations_total],
                "ordering": [sc.pairs_respected, sc.pairs_checked],
                "violations": sc.violations,
            }
        result["sensitivity"][label] = block
        print()

    print("Pairs on which the systems disagree (what to re-examine on the clay):")
    disc = compare.discriminating_pairs(systems, pairs)
    for d in disc:
        print(f"   {d['pair']:12s} n={d['attestations']}  respected by {', '.join(d['respected_by'])}"
              f" | violated by {', '.join(d['violated_by'])}")
    result["discriminating_pairs"] = disc
    print()

    candidates = sorted({F(n, d) for d in (2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24, 30, 40, 60) for n in range(1, d)})
    print("Windows the ordering evidence implies for the disputed signs:")
    for target in args.windows:
        label = values_mod.LABELS.get(target, target)
        others = {k: v for k, v in values_mod.KNOWN_VALUES.items() if k != target}
        b = ordering.bound_unknowns(pairs, others, candidates).get(target)
        if not b:
            continue
        print(f"   {label}: {b['lower_bound'] or '-'} < {label} < {b['upper_bound'] or '-'}"
              f"   ({b['candidates_remaining']} of {b['candidates_total']} candidates survive)")
        for name, vals in systems.items():
            v = vals.get(target)
            if v is None:
                continue
            lo = F(b["lower_bound"]) if b["lower_bound"] else None
            hi = F(b["upper_bound"]) if b["upper_bound"] else None
            fits = (hi is None or v < hi) and (lo is None or v > lo)
            print(f"      {name:22s} {str(v):6s} {'fits' if fits else 'outside'}")
        result["windows"][label] = b

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "compare.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {OUT_DIR / 'compare.json'}")



def cmd_ratios(args: argparse.Namespace) -> None:
    """Ration ratios: a headcount beside a commodity constrains values without a total."""
    docs = load_cached()
    pairs = [p for d in docs.values() for p in ratios.find_ration_pairs(d)]
    known = values_mod.KNOWN_VALUES

    plausible = [p for p in pairs if p.plausible(known)]
    print(f"Ration statements (headcount line followed by a commodity line): {len(pairs)}")
    print(f"  with a plausible ration (simple amount per person)           : {len(plausible)}")
    print(f"  pairing almost certainly spurious                            : {len(pairs) - len(plausible)}")
    print()
    for p in sorted(plausible, key=lambda q: q.tablet):
        fr = ",".join(values_mod.LABELS.get(f, f) for f in p.issued.fractions)
        broken = "[" if p.people.broken else ""
        print(f"   {p.tablet:10s} lines {p.headcount_line}->{p.commodity_line}: "
              f"{p.people.integer}{broken} people -> {p.issued.integer}{' ' + fr if fr else ''}"
              f"   ration {p.ration(known)} per person")
    print()

    result: dict = {"statements": len(pairs), "plausible": len(plausible), "solved": []}
    by_tablet: dict[str, list] = {}
    for p in pairs:
        by_tablet.setdefault(p.tablet, []).append(p)

    print("Tablets where a complete pair fixes the ration and a broken pair can then be solved:")
    for tablet, group in sorted(by_tablet.items()):
        complete = [p for p in group if p.complete and p.plausible(known)]
        broken = [p for p in group if p.issued.fractions and p.people.broken]
        if not complete or not broken:
            continue
        ration = complete[0].ration(known)
        for p in broken:
            for sign in dict.fromkeys(p.issued.fractions):
                label = values_mod.LABELS.get(sign, sign)
                sols = ratios.solve_broken_pair(p, ration, sign)
                print(f"   {tablet}: ration {ration} per person (from lines "
                      f"{complete[0].headcount_line}->{complete[0].commodity_line})")
                print(f"      broken pair needs: headcount x {ration} = {p.issued.integer} + {label}")
                for people, val in sols:
                    print(f"         headcount {people}  ->  {label} = {val}")
                verdict = ("UNIQUE" if len(sols) == 1 else f"{len(sols)} solutions")
                print(f"      -> {verdict} with a proper fraction"
                      + (f"; the published value of {label} is {known[sign]}" if sign in known else ""))
                result["solved"].append({
                    "tablet": tablet, "ration": str(ration), "sign": label,
                    "solutions": [[n, str(v)] for n, v in sols],
                })

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "ratios.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT_DIR / 'ratios.json'}")


def cmd_recover(args: argparse.Namespace) -> None:
    """Uniquely recoverable numerals in Linear A."""
    from la import recover, recover_la

    docs = load_cached()
    results = recover_la.recover_all(docs, strict=not args.relaxed, repeat_limit=args.repeat_limit)
    summary = recover.summarise(results)

    print(f"Linear A sections where the arithmetic says something is missing: {len(results)}")
    for verdict, count in summary["by_verdict"].items():
        print(f"  {verdict:18s} {count:3d}  {recover.VERDICT_MEANING[verdict]}")
    print()
    for r in results:
        print(f"{r.tablet:16s} {r.verdict:18s} residual {str(r.residual):>8s}  "
              f"gaps {r.open_quantities}  distributions {r.distinct_distributions}")
        for c in r.candidates[:args.show]:
            print(f"    {c.render(r.gaps)}")
        if r.note:
            print(f"    note: {r.note}")

    print("\nAgainst the published hypotheses:")
    published = recover_la.check_published(docs, strict=not args.relaxed)
    for row in published:
        mark = "reproduced" if row.get("residual_matches_published") else "not reproduced"
        print(f"  {row['tablet']:10s} {mark:15s} {row['published_claim']}")
        print(f"             our residual {row['residual']}, verdict {row['verdict']}")

    print("\nHeld-out corruption (the only honest accuracy figure):")
    holdout = recover_la.holdout_corruption(docs, strict=not args.relaxed,
                                            repeat_limit=args.repeat_limit)
    print(f"  {holdout['independence_warning']}")
    for row in holdout["by_verdict"]:
        print(f"    {row['verdict']:18s} n={row['n']:4d} amount found {row['accuracy']}")

    print("\nLinear A error rate, for comparison with Linear B:")
    rate = recover_la.error_rate(docs)
    print(f"  intact sections {rate['sections_scored']}, failures {rate['failures']}, "
          f"rate {rate['error_rate']}")
    print(f"  integers only  {rate['integers_only']}")
    print(f"  with fractions {rate['fraction_bearing']}")
    print(f"  {rate['caveat']}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "recover_la.json").write_text(json.dumps({
        "summary": summary,
        "sections": [r.to_dict() for r in results],
        "published_hypotheses": published,
        "holdout": holdout,
        "error_rate": rate,
        "system_comparison": recover_la.compare_systems(docs, strict=not args.relaxed),
    }, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {OUT_DIR / 'recover_la.json'}")


def cmd_lb_fetch(args: argparse.Namespace) -> None:
    from la.lb.fetch import main as lb_fetch_main

    lb_fetch_main()


def cmd_lb_audit(args: argparse.Namespace) -> None:
    """The Linear B arithmetic audit: the error-rate baseline."""
    from la import recover
    from la.lb import audit as lb_audit
    from la.lb import metrology

    tablets = lb_audit.load_tablets()
    print(f"DAMOS documents parsed: {len(tablets)}")
    series_map = lb_audit.infer_commodity_series(tablets)

    convention = lb_audit.compare_with_convention(tablets)
    print(f"Commodities seen: {convention['commodities']}; "
          f"series agrees with the hand-written convention for {convention['agree']}")
    if convention["disagree"]:
        print("  corpus usage disagrees with the convention for:")
        for row in convention["disagree"]:
            print(f"    {row['commodity']}: corpus says {row['corpus']}, convention says {row['convention']}")

    audits = lb_audit.audit_sections(tablets, series_map)
    rate = lb_audit.error_rate(audits, min_group=args.min_group)
    print("\nError rate")
    print(f"  sections found                {rate['sections_total']}")
    print(f"  excluded, content missing     {rate['excluded_content_missing']}")
    print(f"  excluded, open quantity       {rate['excluded_open_quantity']}")
    print(f"  excluded, units unresolved    {rate['excluded_unresolved']}")
    print(f"  excluded, editor restored     {rate['excluded_editorially_restored']}")
    print(f"  scored (clean tier)           {rate['scored']}")
    print(f"  failures                      {rate['failures']}")
    print(f"  ERROR RATE                    {rate['error_rate']}")
    print(f"  including edge-damaged        {rate['error_rate_including_edge']}")
    for row in rate["by_tier"]:
        print(f"    tier {row['tier']:6s} n={row['sections']:4d} failures={row['failures']:3d} "
              f"rate={row['error_rate']}")
    for label in ("counted_vs_measured", "by_unit_series", "by_site", "by_series", "by_hand"):
        rows = rate[label]
        if rows:
            print(f"  {label}:")
            for row in rows[:12]:
                print(f"    {row}")

    fits = {}
    for name, series in metrology.SERIES.items():
        sections = [s for t in tablets for s in t.sections]
        fit = lb_audit.fit_sizes(sections, series, series_map, trials=args.fit_trials)
        fits[name] = fit.to_dict()
        print(f"\nUnit ratios fitted from the corpus ({name}): {fit.equations} equations")
        print(f"  published sizes {fit.published} satisfy {fit.published_satisfied}")
        print(f"  best fitted     {fits[name]['fitted_sizes']} satisfy {fit.satisfied}")
        print(f"  agrees with published: {fit.agrees_with_published}")

    recoveries = lb_audit.recover_all(tablets, series_map, strict=not args.relaxed)
    rsummary = recover.summarise(recoveries)
    print(f"\nRecoverable numerals: {len(recoveries)} sections with a break beside a quantity")
    for verdict, count in rsummary["by_verdict"].items():
        print(f"  {verdict:18s} {count:4d}")
    print(f"  uniquely restored: {rsummary['uniquely_restored']} "
          f"({rsummary['unique_share_of_attempts']})")
    for r in recoveries:
        if r.verdict in (recover.UNIQUE, recover.IMPOSSIBLE):
            print(f"    {r.tablet:20s} {r.verdict:11s} residual {r.residual}"
                  + (f"  ->  {r.candidates[0].render(r.gaps)}" if r.candidates else ""))

    holdout = lb_audit.holdout_corruption(tablets, series_map, strict=not args.relaxed)
    print("\nHeld-out corruption")
    print(f"  {holdout['independence_warning']}")
    for row in holdout["by_verdict"]:
        print(f"    {row['verdict']:18s} n={row['n']:4d} amount found {row['accuracy']} "
              f"exact signs {row['reconstructs_exact_terms']}")
    for row in holdout["by_commodity_kind"]:
        print(f"    {row}")

    baseline = lb_audit.accounting_baseline(tablets, series_map)
    print("\n" + "=" * 72)
    print("MYCENAEAN ACCOUNTING ERROR RATE - ATTEMPTED, NOT OBTAINED")
    print("=" * 72)
    print(f"  {baseline['question']}")
    for ch in baseline["channels"]:
        print(f"\n  channel: {ch['channel']}")
        print(f"    unit of analysis: {ch['unit_of_analysis']}")
        for key in ("sections_found", "scored", "failures", "tablets", "values_checked",
                    "deviations", "error_rate", "deviation_rate",
                    "error_rate_including_edge_damage", "mean_absolute_deviation"):
            if key in ch and ch[key] is not None:
                print(f"    {key}: {ch[key]}")
        for key in ("limitation", "note"):
            if ch.get(key):
                print(f"    {key}: {ch[key]}")
    h = baseline["headline"]
    print(f"\n  OUTCOME: {baseline['outcome']}")
    print(f"  {h['deviations']}/{h['n']} = {h['rate']} ({h['source']})")
    print(f"    measures: {h['measures']}")
    print(f"    does NOT measure: {h['does_not_measure']}")
    print("  anomalies beyond rounding:")
    for row in h["anomalies_beyond_rounding"]:
        print(f"    {row['tablet']:18s} {row['commodity']:6s} "
              f"written {row['written']} expected {row['nearest_writeable']} ({row['deviation']:+d})")
    print("  caveats:")
    for c in baseline["caveats"]:
        print(f"    - {c}")
    print(f"  next: {baseline['if_a_base_rate_is_still_wanted']}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "lb_audit.json").write_text(json.dumps({
        "documents": len(tablets),
        "series_map": series_map,
        "convention_check": convention,
        "accounting_baseline": baseline,
        "error_rate": rate,
        "unit_ratio_fits": fits,
        "disputed_ratios": metrology.DISPUTED_RATIOS,
        "recovery": rsummary,
        "recovery_sections": [r.to_dict() for r in recoveries],
        "holdout": holdout,
    }, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {OUT_DIR / 'lb_audit.json'}")


def cmd_lb_ma(args: argparse.Namespace) -> None:
    """The Pylos Ma fixed-ratio pilot."""
    from la.lb import audit as lb_audit
    from la.lb import ma as lb_ma

    tablets = lb_audit.load_tablets()
    report = lb_ma.report(tablets)
    print(f"Pylos Ma assessments: {report['tablets']} "
          f"({report['complete_assessments']} complete)")

    fit = report["ratio_fit"]
    print("\nRatio, fitted from the tablets versus published")
    print(f"  published ({lb_ma.PUBLISHED_SOURCE}): {fit['published_ratio']}")
    print(f"  fitted from corpus                  : {fit['fitted_ratio']}")
    print(f"  agrees on all six: {fit['agrees_on_all_six']}")
    print(f"  exact matches per commodity: {fit['fitted_exact_matches']}")

    print("\nRounding granularity")
    for row in report["rounding"]["by_commodity"]:
        print(f"  {row['commodity']:6s} n={row['n']:3d} best={row['best_granularity']:4d} "
              f"rate={row['rate_at_best']:.2f} (at unit precision {row['rate_at_unit']:.2f})")
    print(f"  direction: {report['rounding_direction']}")

    for label in ("deviations_at_unit_precision", "deviations"):
        d = report[label]
        print(f"\n{label}")
        print(f"  values checked {d['values_checked']}, off {d['values_off']}, "
              f"rate {d['value_error_rate']}, mean |deviation| {d['mean_absolute_deviation']}")
        print(f"  tablets matching exactly {d['tablets_matching_exactly']}/{d['tablets_checked']}")

    print("\nAnomalies the ratio cannot explain as rounding")
    for row in report["deviations"]["outliers"]:
        if abs(row["deviation"]) >= args.min_deviation:
            print(f"  {row['tablet']:18s} {row['commodity']:6s} written {row['written']:5d} "
                  f"expected {row['nearest_writeable']:5d} ({row['deviation']:+d})")

    print("\nRestorations predicted from the ratio")
    for row in report["restorations"]:
        print(f"  {row['tablet']:18s} {row['commodity']:6s} survives {row['surviving']} "
              f"-> {row['predicted']}  admissible={row['consistent_with_break']}")
        if row["note"]:
            print(f"      {row['note']}")

    h = report["holdout"]
    print(f"\nHeld-out prediction of surviving values: {h['exact']}/{h['n']} exact "
          f"({h['exact_rate']}), within 1: {h['within_1_rate']}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "lb_ma.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {OUT_DIR / 'lb_ma.json'}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="la", description="Linear A fraction-value research tooling")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("fetch", help="crawl and cache the corpus (resumable)")
    sub.add_parser("census", help="phase 0: count the evidence available")

    p_solve = sub.add_parser("solve", help="phase 2: build and analyse the linear system")
    p_solve.add_argument("--include-damaged", action="store_true", help="include sections with damage near a quantity")
    p_solve.add_argument("--max-unknowns", type=int, default=6, help="enumerate only when unknowns <= this")
    p_solve.add_argument("--null-trials", type=int, default=5000)
    p_solve.add_argument("--treat-all-unknown", action="store_true",
                         help="ignore published values and solve for every fraction sign from the corpus alone")
    p_solve.add_argument("--grid", choices=["unit", "full"], default="unit",
                         help="hypothesis space: unit fractions (default) or all proper fractions")

    sub.add_parser("validate", help="phase 3: leave-one-out recovery of published values")

    sub.add_parser("ratios", help="ration ratios: headcount beside commodity")

    p_compare = sub.add_parser("compare", help="score competing published value systems against the corpus")
    p_compare.add_argument("--windows", nargs="*", default=["A701", "A706"],
                           help="sign ids to compute ordering windows for (default: A and H)")

    p_order = sub.add_parser("order", help="ordering evidence: fractions written in decreasing value")
    p_order.add_argument("--null-trials", type=int, default=5000)

    p_recover = sub.add_parser(
        "recover", help="which damaged Linear A numerals the arithmetic determines"
    )
    p_recover.add_argument("--relaxed", action="store_true",
                           help="permit sign repetition beyond the declared limit")
    p_recover.add_argument("--repeat-limit", type=int, default=2,
                           help="how many times one fraction sign may repeat (default 2)")
    p_recover.add_argument("--show", type=int, default=6,
                           help="how many candidate restorations to print per section")

    sub.add_parser("lb-fetch", help="crawl and cache the DAMOS Linear B corpus (resumable)")

    p_lb_audit = sub.add_parser(
        "lb-audit", help="Linear B arithmetic audit: the accounting error-rate baseline"
    )
    p_lb_audit.add_argument("--min-group", type=int, default=5,
                            help="smallest group reported in a per-hand or per-site breakdown")
    p_lb_audit.add_argument("--fit-trials", type=int, default=3000,
                            help="samples used when fitting unit ratios from the corpus")
    p_lb_audit.add_argument("--relaxed", action="store_true",
                            help="permit bundling violations in restoration candidates")

    p_lb_ma = sub.add_parser("lb-ma", help="Pylos Ma fixed-ratio pilot (7:7:2:3:1.5:150)")
    p_lb_ma.add_argument("--min-deviation", type=int, default=2,
                         help="smallest deviation to list as an anomaly")

    args = parser.parse_args()
    if args.command == "fetch":
        fetch_main()
    elif args.command == "census":
        census_main()
    elif args.command == "solve":
        cmd_solve(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "order":
        cmd_order(args)
    elif args.command == "compare":
        cmd_compare(args)
    elif args.command == "ratios":
        cmd_ratios(args)
    elif args.command == "recover":
        cmd_recover(args)
    elif args.command == "lb-fetch":
        cmd_lb_fetch(args)
    elif args.command == "lb-audit":
        cmd_lb_audit(args)
    elif args.command == "lb-ma":
        cmd_lb_ma(args)


if __name__ == "__main__":
    main()
