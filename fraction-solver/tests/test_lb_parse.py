"""Linear B transliteration parsing, on hand-built lines with known readings.

Every test here encodes a convention that was misread at some point while building the
audit, and each misreading changed a result rather than crashing. They are the regression
guard for the editorial conventions, which is where all the risk in this parser lives.
"""

from __future__ import annotations

from la.lb import metrology, parse
from la.lb.parse import (
    BLANK_NOTE,
    BREAK_AFTER,
    GAP,
    LOST_BEFORE,
    LOST_NOTE,
    NUMBER,
    RESTORE_END,
    RESTORE_START,
    SIGN,
    WORD,
)


def doc(content: str, **meta):
    """A DAMOS-shaped record around some transliterated content."""
    return {
        "item": {"heading_short": meta.pop("id", "KN Xx 1"), "content": content,
                 "series": meta.pop("series", "X"), "subseries": meta.pop("subseries", "-"),
                 "set": None},
        "meta": {"Site": meta.pop("site", "Knossos"), "Hand": meta.pop("hand", "138"),
                 "Stylus": None, "Chronology": None, "Preserved": "Yes", **meta},
        "_damos_id": 1,
    }


def kinds(tokens):
    return [t.kind for t in tokens]


class TestUnderdots:
    def test_combining_marks_are_stripped_for_matching(self):
        # OLIV with four underdots is still OLIV.
        tokens, _ = parse.tokenise(".1  ỌḶỊṾ 82  T 4")
        assert [t.text for t in tokens if t.kind == SIGN] == ["OLIV", "T"]

    def test_underdotted_numerals_still_parse(self):
        tokens, _ = parse.tokenise(".1  GRA 1̣5̣0")
        assert [t.value for t in tokens if t.kind == NUMBER] == [150]


class TestBrackets:
    """`1[`, `]1` and `[1]` mean three different things, and conflating them changes results."""

    def test_trailing_unclosed_bracket_is_a_break(self):
        tokens, _ = parse.tokenise(".1  OLE S 1[")
        assert BREAK_AFTER in kinds(tokens)
        assert RESTORE_START not in kinds(tokens)

    def test_leading_unopened_bracket_is_lost_text(self):
        tokens, _ = parse.tokenise(".1  ]to-so  VIR 10")
        assert kinds(tokens)[0] == LOST_BEFORE

    def test_bracket_pair_with_content_is_an_editorial_restoration(self):
        tokens, _ = parse.tokenise(".1  ka-ri-se-u [VIR 1] wi-je-mo VIR 1")
        assert RESTORE_START in kinds(tokens) and RESTORE_END in kinds(tokens)
        assert GAP not in kinds(tokens)

    def test_empty_bracket_pair_is_a_gap(self):
        tokens, _ = parse.tokenise(".1  o-[   ]  ,  ko-no-so  VIR 5")
        assert GAP in kinds(tokens)

    def test_restored_quantities_are_flagged(self):
        tablet = parse.parse_document(doc(".1 a VIR 1\n.2 b [VIR 1]\n.3 to-so VIR 2"))
        assert [m.restored for m in tablet.entries] == [False, True]
        assert tablet.sections[0].has_restored


class TestBreakAdjacency:
    """A bracket touching the numeral shortens it; a spaced one ends the line."""

    def test_attached_bracket_opens_the_quantity(self):
        tablet = parse.parse_document(doc(".1 a OLE S 1[\n.2 b OLE S 2\n.3 to-so OLE S 4"))
        assert tablet.entries[0].damaged is True
        assert tablet.entries[1].damaged is False

    def test_detached_bracket_is_edge_damage_not_a_short_numeral(self):
        tablet = parse.parse_document(doc(".1 a TELA 1        [\n.2 b TELA 2\n.3 to-so TELA 3"))
        assert tablet.entries[0].damaged is False
        assert 1 in tablet.soft_loss_lines
        assert tablet.sections[0].tier == "edge"


class TestSplitNumerals:
    def test_a_numeral_cut_by_a_bracket_is_rejoined(self):
        # PY Ma 120: `[O M  1]4` is fourteen, not one-then-four.
        tokens, _ = parse.tokenise(".1  pe-to-no *146 63  [O M  1]4")
        assert [t.value for t in tokens if t.kind == NUMBER] == [63, 14]

    def test_the_closing_bracket_survives_the_merge(self):
        # Otherwise the restoration never closes and later measures are wrongly flagged.
        tokens, _ = parse.tokenise(".1  [O M 1]4  ME 500")
        assert kinds(tokens).count(RESTORE_END) == 1
        tablet = parse.parse_document(doc(".1  a [O M 1]4  ME 500"))
        me = [m for m in tablet.measures if m.commodity == "ME"]
        assert me and me[0].restored is False


class TestMetrograms:
    def test_a_metrogram_after_its_commodity_stays_with_it(self):
        # `OLE S 1` is one S of oil, not a commodity called S.
        tablet = parse.parse_document(doc(".1 a OLE S 1\n.2 b OLE S 2\n.3 to-so OLE S 3"))
        assert [m.commodity for m in tablet.entries] == ["OLE", "OLE"]
        assert tablet.entries[0].terms == [("S", 1)]

    def test_full_quantity_chain_parses_in_order(self):
        tablet = parse.parse_document(doc(".1 to-so OLE 3 S 2 V 2"))
        total = tablet.totals[0]
        assert total.terms == [("UNIT", 3), ("S", 2), ("V", 2)]
        # 1 unit = 3 S = 18 V = 72 Z; 1 S = 24 Z; 1 V = 4 Z.
        assert total.value() == 3 * 72 + 2 * 24 + 2 * 4 == 272

    def test_commodity_is_inherited_across_lines(self):
        tablet = parse.parse_document(doc(".1 a OLE S 1\n.2 b V 4\n.3 to-so OLE S 1 V 4"))
        assert tablet.entries[1].commodity == "OLE"
        assert tablet.entries[1].inherited_commodity is True

    def test_a_new_commodity_ends_the_previous_measure(self):
        tablet = parse.parse_document(doc(".1 a *146 28 RI M 28 KE M 8"))
        assert [(m.commodity, m.terms) for m in tablet.entries] == [
            ("*146", [("UNIT", 28)]), ("RI", [("M", 28)]), ("KE", [("M", 8)]),
        ]


class TestCountedNouns:
    """Which words count themselves, and which merely label a quantity of the logogram."""

    def test_a_known_counted_noun_takes_its_own_number(self):
        # KN Ap 639: `MUL 1 ko-wa 2` is one woman and two girls, not three women.
        tablet = parse.parse_document(doc(".1 a MUL 1 ko-wa 2"), counted_nouns=frozenset({"ko-wa"}))
        assert [(m.commodity, m.counted_noun) for m in tablet.entries] == [
            ("MUL", False), ("ko-wa", True),
        ]

    def test_a_personal_name_does_not(self):
        # KN As 1520: `a-ma-no 1` is one *man*; the VIR is understood from nearby lines.
        # Treating the name as the commodity detaches the entry from its total.
        tablet = parse.parse_document(doc(".1 a-ma-no VIR 1\n.2 da-ko-so 1\n.3 to-so VIR 2"))
        assert [m.commodity for m in tablet.entries] == ["VIR", "VIR"]
        assert tablet.sections and tablet.sections[0].residual() == 0

    def test_candidates_are_words_before_a_bare_number(self):
        found = parse.counted_noun_candidates(".1 a MUL 1 ko-wa 2 ko-wo 1")
        assert "ko-wa" in found and "ko-wo" in found
        assert "mul" not in found  # a logogram is not a word

    def test_role_markers_are_never_candidates(self):
        assert "to-so" not in parse.counted_noun_candidates(".1 to-so VIR 10")
        assert "o" not in parse.counted_noun_candidates(".1 *146 21 o 2")

    def test_role_markers_do_not_become_commodities(self):
        tablet = parse.parse_document(doc(".1 a *146 21 o 2"))
        deficit = [m for m in tablet.measures if m.role == "deficit"]
        assert deficit and deficit[0].commodity == "*146"
        assert deficit[0].counted_noun is False


class TestRoles:
    def test_to_so_marks_a_total(self):
        tablet = parse.parse_document(doc(".1 a VIR 1\n.2 b VIR 1\n.3 to-so VIR 2"))
        assert [m.role for m in tablet.measures] == ["entry", "entry", "total"]

    def test_o_pe_ro_is_a_deficit_not_an_addend(self):
        tablet = parse.parse_document(
            doc(".1 a AROM 11\n.2 b AROM 11\n.3 to-sa AROM 22\n.4 to-sa-de o-pe-ro AROM 31")
        )
        section = tablet.sections[0]
        assert section.residual() == 0, "the 31 owed must not enter the sum"

    def test_exemptions_and_deliveries_are_excluded(self):
        tablet = parse.parse_document(
            doc(".1 a RI M 5\n.2 b RI M 5\n.3 a-pu-do-si RI M 3\n"
                ".4 o-u-di-do-si RI M 2\n.5 to-so RI M 10")
        )
        assert tablet.sections[0].residual() == 0

    def test_grand_totals_are_marked(self):
        tablet = parse.parse_document(doc(".1 a VIR 1\n.2 b VIR 1\n.3 ku-su-to-ro-qa VIR 2"))
        assert tablet.sections[0].grand is True

    def test_to_so_as_a_heading_makes_no_section(self):
        # KN F(1) 157 opens with `to-so`; the entries follow it, so nothing is totalled.
        tablet = parse.parse_document(doc(".1 e-ko-so , / to-so GRA 400\n.2 CYP 5 T 3"))
        assert tablet.sections == []


class TestVariants:
    def test_a_total_covers_typographic_variants_of_its_sign(self):
        # KN Ld 598: TELA 1 + TELA;1 37 + TELA 2 = to-sa TELA 40.
        tablet = parse.parse_document(
            doc(".1 a TELA 1\n.2 b TELA;1 37 c TELA 2\n.3 to-sa TELA 40")
        )
        assert len(tablet.sections) == 1
        assert tablet.sections[0].residual() == 0

    def test_ligatures_are_not_merged_with_their_base(self):
        assert parse.base_commodity("GRA+PE") == "GRA+PE"
        assert parse.base_commodity("TELA;1") == "TELA"
        assert parse.base_commodity("OVIS:m") == "OVIS"


class TestLossTiers:
    def test_vacat_is_blank_not_lost(self):
        tokens, _ = parse.tokenise(".7    vac.")
        assert kinds(tokens) == [BLANK_NOTE]
        tablet = parse.parse_document(doc(".1 a VIR 1\n.2 vac.\n.3 b VIR 1\n.4 to-so VIR 2"))
        assert tablet.sections[0].tier == "clean"

    def test_sup_mut_is_lost_content(self):
        tokens, _ = parse.tokenise("      sup. mut.")
        assert kinds(tokens) == [LOST_NOTE]

    def test_a_mutila_tablet_cannot_be_audited(self):
        tablet = parse.parse_document(
            doc("sup. mut.\n.1 a VIR 1\n.2 b VIR 1\n.3 to-so VIR 10")
        )
        assert tablet.sections[0].tier == "broken"
        assert tablet.sections[0].entries_incomplete is True

    def test_a_break_below_the_total_does_not_invalidate_it(self):
        tablet = parse.parse_document(
            doc(".1 a VIR 1\n.2 b VIR 1\n.3 to-so VIR 2\n.4 inf. mut.")
        )
        assert tablet.sections[0].tier == "clean"

    def test_span_starts_at_the_top_not_at_the_first_survivor(self):
        # Entries lost above the first one that survives must still invalidate the total.
        tablet = parse.parse_document(
            doc(".1 ]  [\n.2 a VIR 1\n.3 b VIR 1\n.4 to-so VIR 7")
        )
        assert tablet.sections[0].tier != "clean"

    def test_sibling_totals_on_one_line_share_the_span(self):
        # `to-sa MUL 45 ko-wa 5` : both totals cover the same span, so both are broken.
        tablet = parse.parse_document(
            doc("sup. mut.\n.1 a MUL 1 ko-wa 1\n.2 b MUL 1 ko-wa 1\n.3 to-sa MUL 2 ko-wa 2"),
            counted_nouns=frozenset({"ko-wa"}),
        )
        assert len(tablet.sections) == 2
        assert all(s.tier == "broken" for s in tablet.sections), (
            "the second total on the line must not get an empty span"
        )


class TestMetrologyIntegration:
    def test_t_disambiguates_to_dry_and_s_to_liquid(self):
        dry = parse.parse_document(doc(".1 to-so GRA 2 T 3"))
        liq = parse.parse_document(doc(".1 to-so OLE 2 S 1"))
        assert dry.totals[0].series() is metrology.DRY
        assert liq.totals[0].series() is metrology.LIQUID

    def test_an_unplaceable_subunit_refuses_to_guess(self):
        # V alone under an unknown commodity cannot be assigned to dry or liquid.
        tablet = parse.parse_document(doc(".1 to-so ZZZ V 3"))
        assert tablet.totals[0].value() is None

    def test_a_counted_commodity_values_as_its_bare_number(self):
        tablet = parse.parse_document(doc(".1 to-so OVIS 100"))
        assert tablet.totals[0].value() == 100


class TestMetadata:
    def test_hand_is_read_and_a_dash_means_absent(self):
        assert parse.parse_document(doc(".1 a", hand="138")).hand == "138"
        assert parse.parse_document(doc(".1 a", hand="-")).hand is None

    def test_sections_need_at_least_two_entries(self):
        tablet = parse.parse_document(doc(".1 a VIR 1\n.2 to-so VIR 1"))
        assert tablet.sections == []
