"""Golden tests on hand-verified tablets, plus the arithmetic invariants.

The two tablets below were read line by line against lineara.eu and checked by
hand. They encode the two structural cases that matter: a plain single total
(HT 13) and a total that covers only the entries after a bare `ki-ro` heading
(HT 88). If either breaks, the census counts are wrong.
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import pytest

from la.parse import evaluate_section, fraction_counts, parse_document

CACHE = Path(__file__).resolve().parent.parent / "data" / "cache"


def load(slug: str) -> dict:
    path = CACHE / f"{slug}.json"
    if not path.exists():
        pytest.skip(f"{slug} not cached; run `python -m la.fetch` first")
    return json.loads(path.read_text(encoding="utf-8"))


class TestHT13:
    """Plain tablet: six entries, one ku-ro total, fractions on entries and total."""

    def test_structure(self):
        t = parse_document(load("HT-13"))
        assert t.layout == "single_total"
        assert len(t.sections) == 1
        section = t.sections[0]
        assert len(section.entries) == 6
        assert section.total.marker == "ku-ro"
        assert section.total.line_no == 8

    def test_integers_balance(self):
        t = parse_document(load("HT-13"))
        ev = evaluate_section(t.sections[0], {})
        assert ev["integer_balances"] is True
        assert ev["integer_delta"] == 0

    def test_fractions_do_not_balance(self):
        """Two J on entries, one J on the total: the corpus as transcribed is off by J.

        lineara.eu reports this tablet as balancing because it only sums integers.
        Catching that difference is the point of the project.
        """
        t = parse_document(load("HT-13"))
        section = t.sections[0]
        entry_fracs = fraction_counts([e.quantity for e in section.entries])
        total_fracs = fraction_counts([section.total.quantity])
        assert entry_fracs == {"A707": 2}
        assert total_fracs == {"A707": 1}

        ev = evaluate_section(section, {"A707": Fraction(1, 2)})
        assert ev["fraction_delta"] == Fraction(1, 2)
        assert ev["balances"] is False

    def test_upstream_says_balances(self):
        doc = load("HT-13")
        assert doc["arithmetic"]["status"] == "balances"
        assert "integers" in doc["arithmetic"]["detail"]


class TestHT88:
    """A bare `ki-ro` heading opens the section that the ku-ro total covers."""

    def test_total_covers_only_the_deficit_section(self):
        t = parse_document(load("HT-88"))
        assert len(t.sections) == 1
        section = t.sections[0]
        assert section.opened_by == "ki-ro"
        assert len(section.entries) == 6
        ev = evaluate_section(section, {})
        assert ev["integer_balances"] is True

    def test_earlier_entries_are_kept_but_untotalled(self):
        t = parse_document(load("HT-88"))
        assert len(t.untotalled_groups) == 1
        _marker, entries = t.untotalled_groups[0]
        assert len(entries) == 3
        assert sum(e.quantity.integer or 0 for e in entries) == 33

    def test_matches_upstream_verdict(self):
        doc = load("HT-88")
        t = parse_document(doc)
        ours = evaluate_section(t.sections[0], {})["integer_balances"]
        assert (doc["arithmetic"]["status"] == "balances") == ours


class TestArithmetic:
    def test_values_stay_exact(self):
        """A third must never become 0.333...; exactness is the whole point."""
        t = parse_document(load("HT-13"))
        ev = evaluate_section(t.sections[0], {"A707": Fraction(1, 3)})
        assert isinstance(ev["fraction_delta"], Fraction)
        assert ev["fraction_delta"] == Fraction(1, 3)

    def test_unknown_signs_block_a_verdict(self):
        t = parse_document(load("HT-13"))
        ev = evaluate_section(t.sections[0], {})
        assert ev["unknown_fraction_signs"] == ["A707"]
        assert ev["fully_valued"] is False
        assert ev["balances"] is None
        assert ev["fraction_delta"] is None


class TestQuantities:
    def test_damage_next_to_a_quantity_is_flagged(self):
        t = parse_document(load("HT-13"))
        line2 = next(e for e in t.sections[0].entries if e.line_no == 2)
        assert line2.quantity.damaged is True
        line3 = next(e for e in t.sections[0].entries if e.line_no == 3)
        assert line3.quantity.damaged is False
