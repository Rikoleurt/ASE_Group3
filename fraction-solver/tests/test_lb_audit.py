"""The Linear B audit: what counts as an error, and what is excluded from the count.

The exclusions are the whole methodology. An error rate that counts damaged tablets, or
totals an editor restored, measures the archive's condition and the editors' judgement
rather than the scribes' arithmetic — so each exclusion gets a test.
"""

from __future__ import annotations

from fractions import Fraction

from la.lb import audit, ma, metrology, parse
from la.lb.metrology import DRY, LIQUID


def doc(content: str, **meta):
    return {
        "item": {"heading_short": meta.pop("id", "KN Xx 1"), "content": content,
                 "series": meta.pop("series", "X"), "subseries": meta.pop("subseries", "-"),
                 "set": None},
        "meta": {"Site": meta.pop("site", "Knossos"), "Hand": meta.pop("hand", "138"),
                 "Stylus": None, "Chronology": None, "Preserved": "Yes", **meta},
        "_damos_id": 1,
    }


def tablets(*contents, **meta):
    return [parse.parse_document(doc(c, **meta)) for c in contents]


class TestMetrology:
    def test_ratio_chains_match_the_published_system(self):
        assert DRY.in_smallest("UNIT") == 240   # 10 T x 6 V x 4 Z
        assert DRY.in_smallest("T") == 24
        assert LIQUID.in_smallest("UNIT") == 72  # 3 S x 6 V x 4 Z
        assert LIQUID.in_smallest("S") == 24

    def test_render_writes_a_value_back_canonically(self):
        assert metrology.render(272, LIQUID) == "UNIT 3 S 2 V 2"
        assert metrology.render(0, LIQUID) == "0"

    def test_render_is_the_inverse_of_valuing(self):
        for value in (1, 5, 23, 24, 72, 100, 272):
            rendered = metrology.render(value, LIQUID)
            terms = []
            parts = rendered.split()
            for i in range(0, len(parts), 2):
                terms.append((parts[i], int(parts[i + 1])))
            assert metrology.value_in_smallest(terms, LIQUID) == value

    def test_fraction_of_unit_bridges_to_linear_a(self):
        assert metrology.as_fraction_of_unit(24, LIQUID) == Fraction(1, 3)  # 1 S = 1/3 unit

    def test_disputed_ratios_are_named(self):
        assert "weight:N:P" in metrology.DISPUTED_RATIOS
        assert "P 20" in metrology.DISPUTED_RATIOS["weight:N:P"]


class TestSeriesInference:
    def test_a_commodity_is_assigned_by_the_subunits_it_takes(self):
        ts = tablets(".1 to-so GRA 2 T 3", ".1 to-so OLE 2 S 1", ".1 to-so RI M 5")
        smap = audit.infer_commodity_series(ts)
        assert smap["GRA"] == "dry"
        assert smap["OLE"] == "liquid"
        assert smap["RI"] == "weight"

    def test_a_never_subdivided_commodity_is_counted(self):
        smap = audit.infer_commodity_series(tablets(".1 to-so OVIS 100", ".1 *146 28"))
        assert smap["OVIS"] == ""
        assert smap["*146"] == ""

    def test_v_and_z_alone_leave_the_series_undetermined(self):
        # Both capacity series share V and Z, so they cannot settle which one applies.
        profiles = audit.profile_commodities(tablets(".1 to-so ZZZ V 3 Z 1"))
        assert profiles["ZZZ"].inferred is None
        assert profiles["ZZZ"].only_capacity_subunits is True

    def test_inference_overrides_the_hand_written_convention(self):
        # *146 is conventionally listed under weight but the corpus only ever counts it.
        smap = audit.infer_commodity_series(tablets(".1 a *146 28\n.2 b *146 4"))
        section_map = smap
        assert section_map["*146"] == ""


class TestErrorRateExclusions:
    def balanced(self):
        return ".1 a VIR 1\n.2 b VIR 1\n.3 to-so VIR 2"

    def unbalanced(self):
        return ".1 a VIR 1\n.2 b VIR 1\n.3 to-so VIR 5"

    def rate(self, *contents):
        ts = tablets(*contents)
        smap = audit.infer_commodity_series(ts)
        return audit.error_rate(audit.audit_sections(ts, smap), min_group=1)

    def test_a_clean_mismatch_counts_as_an_error(self):
        r = self.rate(self.unbalanced())
        assert r["scored"] == 1 and r["failures"] == 1 and r["error_rate"] == 1.0

    def test_a_clean_match_counts_as_correct(self):
        r = self.rate(self.balanced())
        assert r["scored"] == 1 and r["failures"] == 0 and r["error_rate"] == 0.0

    def test_damage_is_not_error(self):
        r = self.rate("sup. mut.\n.1 a VIR 1\n.2 b VIR 1\n.3 to-so VIR 5")
        assert r["scored"] == 0
        assert r["excluded_content_missing"] == 1

    def test_an_open_quantity_is_not_error(self):
        r = self.rate(".1 a OLE S 1[\n.2 b OLE S 1\n.3 to-so OLE S 4")
        assert r["scored"] == 0
        assert r["excluded_open_quantity"] == 1

    def test_an_editorially_restored_total_is_excluded_as_circular(self):
        r = self.rate(".1 a VIR 1\n.2 b [VIR 1]\n.3 to-so VIR 2")
        assert r["scored"] == 0
        assert r["excluded_editorially_restored"] == 1

    def test_unresolvable_units_are_excluded_not_scored_as_correct(self):
        r = self.rate(".1 a ZZZ V 1\n.2 b ZZZ V 1\n.3 to-so ZZZ V 2")
        assert r["scored"] == 0
        assert r["excluded_unresolved"] == 1

    def test_edge_damage_is_reported_as_its_own_tier(self):
        r = self.rate(".1 a VIR 1      [\n.2 b VIR 1\n.3 to-so VIR 5")
        assert r["scored"] == 0, "edge-damaged sections stay out of the headline"
        tiers = {row["tier"]: row for row in r["by_tier"]}
        assert "edge" in tiers and tiers["edge"]["failures"] == 1
        assert r["error_rate_including_edge"] == 1.0

    def test_breakdowns_group_by_hand_and_site(self):
        ts = tablets(self.unbalanced(), self.balanced())
        smap = audit.infer_commodity_series(ts)
        r = audit.error_rate(audit.audit_sections(ts, smap), min_group=1)
        assert r["by_hand"][0]["group"] == "138"
        assert r["by_hand"][0]["sections"] == 2
        assert r["by_site"][0]["group"] == "Knossos"


class TestSizeFitting:
    def test_ratios_are_recovered_from_balanced_sections(self):
        # Two sections that pin S and V against Z: 1 S = 24 Z and 1 V = 4 Z.
        ts = tablets(
            ".1 a OLE S 1\n.2 b OLE Z 12\n.3 to-so OLE Z 36",
            ".1 a OLE V 1\n.2 b OLE Z 2\n.3 to-so OLE Z 6",
            ".1 a OLE 1\n.2 b OLE Z 8\n.3 to-so OLE Z 80",
        )
        smap = audit.infer_commodity_series(ts)
        sections = [s for t in ts for s in t.sections]
        fit = audit.fit_sizes(sections, LIQUID, smap, trials=400)
        assert fit.equations >= 2
        assert fit.published_satisfied == fit.equations, (
            "the published ratios must satisfy sections built from them"
        )

    def test_the_fit_reports_inconsistency_rather_than_averaging(self):
        ts = tablets(
            ".1 a OLE V 1\n.2 b OLE Z 2\n.3 to-so OLE Z 6",    # V = 4 Z
            ".1 a OLE V 1\n.2 b OLE Z 2\n.3 to-so OLE Z 9",    # V = 7 Z: contradictory
        )
        smap = audit.infer_commodity_series(ts)
        sections = [s for t in ts for s in t.sections]
        fit = audit.fit_sizes(sections, LIQUID, smap, trials=200)
        assert fit.published_satisfied < fit.equations


class TestHoldoutCorruption:
    def test_truncation_prefixes_include_losing_the_amount_entirely(self):
        prefixes = audit._truncations([("S", 2), ("V", 3)])
        assert [] in prefixes
        assert [("S", 2)] in prefixes
        assert [("S", 1)] in prefixes
        assert [("S", 2), ("V", 1)] in prefixes

    def test_holdout_only_uses_sections_that_already_balance(self):
        ts = tablets(".1 a VIR 1\n.2 b VIR 1\n.3 to-so VIR 5")  # does not balance
        smap = audit.infer_commodity_series(ts)
        assert audit.holdout_corruption(ts, smap)["usable_sections"] == 0

    def test_holdout_recovers_a_truncated_headcount(self):
        ts = tablets(".1 a VIR 3\n.2 b VIR 4\n.3 to-so VIR 7")
        smap = audit.infer_commodity_series(ts)
        result = audit.holdout_corruption(ts, smap, trials_per_section=10)
        assert result["attempts"] > 0
        assert result["determination_accuracy"] == 1.0


class TestMaSeries:
    """The Pylos Ma fixed-ratio pilot, on synthetic assessments built from the ratio."""

    def ma_doc(self, values, tablet_id="PY Ma 1"):
        cells = []
        for commodity, value in zip(ma.COMMODITIES, values):
            if value is None:
                continue
            unit = " M" if commodity in {"RI", "KE", "O"} else ""
            cells.append(f"{commodity}{unit} {value}")
        return doc(".1 pa-ki-ja  " + "  ".join(cells), id=tablet_id, series="M", subseries="a")

    def test_the_ratio_is_recovered_from_exact_assessments(self):
        ts = [
            parse.parse_document(self.ma_doc([28, 28, 8, 12, 6, 600], "PY Ma 1")),
            parse.parse_document(self.ma_doc([70, 70, 20, 30, 15, 1500], "PY Ma 2")),
            parse.parse_document(self.ma_doc([42, 42, 12, 18, 9, 900], "PY Ma 3")),
        ]
        assessments = ma.extract(ts)
        assert len(assessments) == 3
        fit = ma.fit_ratio(assessments)
        assert fit["agrees_on_all_six"] is True

    def test_exact_assessments_show_no_deviation(self):
        ts = [parse.parse_document(self.ma_doc([28, 28, 8, 12, 6, 600]))]
        d = ma.deviations(ma.extract(ts))
        assert d["values_off"] == 0
        assert d["tablets_matching_exactly"] == 1

    def test_a_planted_error_is_flagged(self):
        ts = [parse.parse_document(self.ma_doc([28, 28, 8, 22, 6, 600]))]  # *152 should be 12
        d = ma.deviations(ma.extract(ts))
        assert d["values_off"] == 1
        assert d["outliers"][0]["commodity"] == "*152"
        assert d["outliers"][0]["deviation"] == 10

    def test_coarse_rounding_is_detected_rather_than_scored_as_error(self):
        # ME assessed to the nearest 50 rather than the nearest unit.
        ts = [
            parse.parse_document(self.ma_doc([24, 24, 7, 10, 5, 500], "PY Ma 1")),
            parse.parse_document(self.ma_doc([23, 23, 7, 10, 5, 500], "PY Ma 2")),
        ]
        a = ma.extract(ts)
        grain = ma.rounding_granularity(a)
        me = next(r for r in grain["by_commodity"] if r["commodity"] == "ME")
        assert me["best_granularity"] > 1
        assert me["rate_at_best"] > me["rate_at_unit"]

    def test_a_damaged_value_is_predicted_from_the_ratio(self):
        # KE broken; *146 = 24 implies KE = 7.
        d = doc(".1 pa-ki-ja *146 24  RI M 24  KE M 2[  *152 10  O M 5  ME 500",
                id="PY Ma 397", series="M", subseries="a")
        a = ma.extract([parse.parse_document(d)])
        assert "KE" in a[0].damaged
        restorations = ma.restore_damaged(a)
        ke = next(r for r in restorations if r.commodity == "KE")
        assert ke.predicted == 7
        assert ke.consistent_with_break is True

    def test_a_prediction_below_what_survives_is_refused(self):
        # A break cannot shrink a numeral, so such a prediction refutes itself.
        d = doc(".1 pa-ki-ja *146 24  RI M 24  KE M 20[  *152 10  O M 5  ME 500",
                id="PY Ma X", series="M", subseries="a")
        a = ma.extract([parse.parse_document(d)])
        ke = next(r for r in ma.restore_damaged(a) if r.commodity == "KE")
        assert ke.consistent_with_break is False
        assert "cannot reduce" in ke.note

    def test_only_the_assessment_line_is_used(self):
        # Deliveries and exemptions on later lines must not enter the assessment.
        d = doc(".1 pa-ki-ja *146 28 RI M 28 KE M 8 *152 12 O M 6 ME 600\n"
                ".2 o-da-a2 , ka-ke-we , o-u-di-do-si *146 1 RI M 1",
                id="PY Ma 90", series="M", subseries="a")
        a = ma.extract([parse.parse_document(d)])
        assert a[0].values["*146"] == 28

    def test_holdout_predicts_surviving_values(self):
        ts = [parse.parse_document(self.ma_doc([28, 28, 8, 12, 6, 600]))]
        h = ma.holdout(ma.extract(ts))
        assert h["n"] == 5
        assert h["exact_rate"] == 1.0

    def test_the_candidate_space_stays_simple(self):
        # Without a denominator bound the fit chases the sample and returns absurdities.
        cands = ma._simple_candidates(Fraction(3))
        assert Fraction(3) in cands
        assert all(c.denominator <= ma.MAX_RATIO_DENOMINATOR for c in cands)
        assert Fraction(70, 23) not in cands
