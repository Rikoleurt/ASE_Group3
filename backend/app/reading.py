"""Tablet reading: the lineara.eu transcription of a tablet, its arithmetic
audited by fraction-solver, and its fraction signs identified from their shape.

This is where the week-1 research code (`fraction-solver/la`) meets the web app.
Nothing here is trained: the transcription is the published one, the audit is
exact arithmetic, and sign identification is nearest-neighbour shape matching.

Data licence: transcriptions and sign drawings are SigLA-derived, CC BY-NC-SA 4.0.
They are cached locally (never committed) and served with their credit line.
"""

import json
import re
import sys
from fractions import Fraction
from functools import lru_cache
from pathlib import Path

import numpy as np

FRACTION_SOLVER = Path(__file__).resolve().parents[2] / "fraction-solver"
if str(FRACTION_SOLVER) not in sys.path:
    # fraction-solver is a separate tool, not an installed package; pytest.ini adds
    # it to the path for tests, this does the same for the running server.
    sys.path.insert(0, str(FRACTION_SOLVER))

from la import fetch, recover_la, shapes, signboxes, values  # noqa: E402
from la.parse import Quantity, parse_document  # noqa: E402

SLUG = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")

# Shape matching is only offered where it was measured to work: leave-one-out
# over the fraction signs scored 88% top-1 by contour distance (FINDINGS.md §4).
# Across the full sign inventory it reaches 35%, which is not worth showing.
TOP_GUESSES = 5

CREDIT = {
    "licence": "CC BY-NC-SA 4.0",
    "url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
    "text": (
        "Transcription and sign drawings from SigLA (Salgarella & Castellan) via "
        "lineara.eu (M. Navarre). Fraction values: Corazza et al. 2021, Table 8."
    ),
}


class DocumentUnavailable(Exception):
    """The tablet is not cached and could not be fetched from lineara.eu."""


def load_document(slug: str) -> dict:
    """A tablet's lineara.eu record, from the cache or fetched once into it."""
    if not SLUG.fullmatch(slug):
        raise ValueError(f"Not a tablet id: {slug!r}")
    path = fetch.cache_path(slug)
    if not path.exists():
        try:
            raw = fetch._get(fetch.DOC_URL.format(slug=slug), retries=1)
            json.loads(raw)  # validate before writing, as la.fetch does
        except Exception as error:  # noqa: BLE001 - network or not a document
            raise DocumentUnavailable(slug) from error
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return json.loads(path.read_text(encoding="utf-8"))


def _fraction(value: Fraction | None) -> str | None:
    return None if value is None else str(value)


def _token(token: dict) -> dict:
    kind = token.get("kind")
    out = {"kind": kind}
    if kind == "sign":
        out |= {"id": token.get("id"), "text": token.get("reading") or token.get("id")}
    elif kind == "number":
        out |= {"text": str(token.get("value")), "value": token.get("value")}
    elif kind == "fraction":
        claim = values.BY_SIGN_ID.get(token.get("id"))
        out |= {
            "id": token.get("id"),
            "text": token.get("reading") or token.get("id"),
            "value": _fraction(claim.value) if claim else None,
            "tentative": bool(claim and claim.tentative),
        }
    elif kind == "damage":
        out["text"] = "[ ]"
    return out


def _quantity(quantity: Quantity) -> dict:
    return {
        "integer": quantity.integer,
        "fractions": [values.LABELS.get(f, f) for f in quantity.fractions],
        "value": _fraction(recover_la.quantity_value(quantity, values.KNOWN_VALUES)),
        "damaged": quantity.damaged,
    }


def reading(slug: str) -> dict:
    """Transcription and arithmetic audit for one tablet."""
    doc = load_document(slug)
    tablet = parse_document(doc)
    sections = []
    for section in tablet.sections:
        recovery = recover_la.recover_section(tablet.id, section, values.KNOWN_VALUES)
        entries_value = sum(
            (recover_la.quantity_value(e.quantity, values.KNOWN_VALUES) or Fraction(0) for e in section.entries),
            Fraction(0),
        )
        sections.append({
            "entries": [
                {"line": e.line_no, "word": e.word, "quantity": _quantity(e.quantity)} for e in section.entries
            ],
            "total": {"line": section.total.line_no, "marker": section.total.marker,
                      "quantity": _quantity(section.total.quantity)},
            "integer_sum": sum(e.quantity.integer or 0 for e in section.entries),
            "entries_value": _fraction(entries_value),
            "residual": _fraction(recovery.residual),
            "verdict": recovery.verdict,
            "means": recover_la.recover.VERDICT_MEANING[recovery.verdict],
        })
    return {
        "id": tablet.id,
        "slug": slug,
        "site": tablet.site,
        "period": tablet.period,
        "scribe": tablet.scribe,
        "url": doc.get("url"),
        "lines": [{"number": n, "tokens": [_token(t) for t in line]} for n, line in enumerate(doc.get("lines") or [], 1)],
        "sections": sections,
        "upstream_arithmetic": tablet.upstream_arithmetic,
        "credit": CREDIT,
    }


@lru_cache(maxsize=1)
def _fraction_references() -> tuple[shapes.Glyph, ...]:
    """Every cached fraction-sign drawing, as normalised glyphs (built once)."""
    glyphs = []
    for doc in fetch.load_cached().values():
        for s in doc.get("signs") or []:
            if s.get("role") != "fraction" or not s.get("image") or not s.get("sign"):
                continue
            path = signboxes.image_path(doc, s["image"])
            if path.exists():
                glyphs.append(shapes.build(path, sign=s["sign"], tablet=doc["id"]))
    return tuple(glyphs)


def _guesses(glyph: shapes.Glyph, references: tuple[shapes.Glyph, ...]) -> list[dict]:
    """Nearest signs by contour distance, one entry per sign, closest first.

    References from the same tablet are excluded: one scribe's marks on one tablet
    are unusually alike, and matching them would overstate how well this works.
    """
    best: dict[str, float] = {}
    for ref in references:
        if ref.tablet == glyph.tablet:
            continue
        d = shapes.hausdorff(glyph, ref)
        if d < best.get(ref.sign, float("inf")):
            best[ref.sign] = d
    ranked = sorted(best.items(), key=lambda kv: kv[1])[:TOP_GUESSES]
    return [{"sign": sign, "label": values.LABELS.get(sign, values.OPEN_SIGNS.get(sign, sign)),
             "distance": round(d, 2)} for sign, d in ranked]


def identify_mask(ink: np.ndarray, tablet: str) -> list[dict]:
    """Shape guesses for one fraction sign given as an ink mask (e.g. a detected box)."""
    mask = shapes.normalise(ink)
    glyph = shapes.Glyph(sign="", tablet=tablet, path=Path(), mask=mask,
                         hu=shapes.hu_moments(mask), contour=shapes.boundary(mask))
    return _guesses(glyph, _fraction_references())


def fraction_signs(slug: str) -> dict:
    """Identify each fraction sign on a tablet from its drawing alone, then compare
    with the transcription. Needs the sign images (`python -m la.cli images`)."""
    doc = load_document(slug)
    references = _fraction_references()
    signs = [s for s in doc.get("signs") or [] if s.get("role") == "fraction" and s.get("image")]
    results = []
    for s in signs:
        path = signboxes.image_path(doc, s["image"])
        if not path.exists() or not references:
            continue
        guesses = _guesses(shapes.build(path, sign=s["sign"], tablet=doc["id"]), references)
        results.append({
            "position": s["position"],
            "transcribed": {"sign": s["sign"], "label": values.LABELS.get(s["sign"], s["sign"])},
            "guesses": guesses,
            "correct": bool(guesses) and guesses[0]["sign"] == s["sign"],
            "image": f"/tablets/{slug}/signs/{s['position']}.png",
        })
    return {
        "id": doc["id"],
        "available": bool(results),
        "references": len(references),
        "method": "Nearest neighbour by contour (Hausdorff) distance; no training. "
                  "Measured at 88% top-1 on fraction signs, so only fraction signs are attempted.",
        "signs": results,
        "credit": CREDIT,
    }


def sign_image(slug: str, position: int) -> Path | None:
    """The cached drawing of one sign on a tablet."""
    doc = load_document(slug)
    for s in doc.get("signs") or []:
        if s.get("position") == position and s.get("image"):
            path = signboxes.image_path(doc, s["image"])
            return path if path.exists() else None
    return None
