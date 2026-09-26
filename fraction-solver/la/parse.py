"""Parse lineara.eu document JSON into an arithmetic-ready tablet model.

The corpus gives us lines of tokens. What the solver needs is *entries* and
*totals*: which quantities are being summed, and what the scribe said they add
up to. That mapping is an interpretation, so every assumption here is explicit
and recorded on the parsed object rather than hidden in control flow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

# Total markers, by their syllabic spelling. ku-ro is the standard total;
# po-to-ku-ro a grand total over sub-totals; ki-ro a deficit/owed entry, which
# is NOT a total of the preceding entries and must never be treated as one.
TOTAL_MARKERS = {
    "ku-ro": "total",
    "po-to-ku-ro": "grand_total",
}
DEFICIT_MARKERS = {"ki-ro": "deficit"}


@dataclass
class Quantity:
    """A number and/or fraction signs attached to one line."""

    integer: int | None = None
    fractions: list[str] = field(default_factory=list)  # fraction sign ids, in order
    damaged: bool = False  # damage token adjacent to the quantity

    @property
    def has_value(self) -> bool:
        return self.integer is not None or bool(self.fractions)

    @property
    def open(self) -> bool:
        """True when the recorded value may be incomplete.

        A break beside a quantity means what survives is a lower bound, not the
        amount the scribe wrote. HT 13 line 2 reads `RE-ZA 5[ ]J[ ]` — broken on
        both sides — so reading it as exactly "5 + J" invents precision the clay
        does not have, and produces impossible equations downstream.
        """
        return self.damaged


@dataclass
class Entry:
    line_no: int
    quantity: Quantity
    commodity: str | None = None  # logogram sign id immediately before the quantity
    word: str | None = None  # syllabic word opening the line, if any


@dataclass
class Total:
    line_no: int
    kind: str  # "total" | "grand_total"
    marker: str  # e.g. "ku-ro"
    quantity: Quantity


@dataclass
class Section:
    """Entries closed by a total line.

    `opened_by` records a marker that started the section — notably a bare
    `ki-ro` line, which acts as a heading ("deficit:") rather than an entry, and
    whose following entries are what the next `ku-ro` totals. Mis-handling this
    silently inflates the sum with entries the scribe never counted.
    """

    entries: list[Entry]
    total: Total
    opened_by: str | None = None
    entries_incomplete: bool = False  # a break swallowed text before these entries

    @property
    def has_open_quantity(self) -> bool:
        """True when any amount in this section may be incomplete."""
        return any(e.quantity.open for e in self.entries) or self.total.quantity.open

    @property
    def yields_equation(self) -> bool:
        """Only a section with nothing missing can assert an exact equality."""
        return not self.has_open_quantity and not self.entries_incomplete


@dataclass
class Tablet:
    id: str
    site: str | None
    support: str | None
    period: str | None
    scribe: str | None
    sections: list[Section]
    trailing_entries: list[Entry]  # entries after the last total (no total to check)
    untotalled_groups: list[tuple[str | None, list[Entry]]]  # groups closed by a heading, never totalled
    deficits: list[Entry]  # ki-ro lines carrying their own quantity, excluded from sums
    layout: str
    damaged_lines: int
    unread: bool
    notes: list[str]
    upstream_arithmetic: dict | None

    @property
    def usable_sections(self) -> list[Section]:
        """Sections whose arithmetic we can attempt: a total and at least two entries."""
        return [s for s in self.sections if len(s.entries) >= 2]


def _sign_roles(doc: dict) -> list[str | None]:
    """Roles from signs[], positionally aligned with sign tokens in lines.

    Returns a list parallel to the flattened sequence of 'sign' tokens. When the
    counts disagree the alignment is untrustworthy, so we return an empty list
    and callers fall back to no commodity detection.
    """
    sign_tokens = [t for line in doc.get("lines", []) for t in line if t.get("kind") == "sign"]
    signs = doc.get("signs") or []
    if not signs or len(signs) != len(sign_tokens):
        return []
    # Confirm the alignment really matches before trusting it.
    for token, record in zip(sign_tokens, signs):
        if token.get("id") and record.get("sign") and token["id"] != record["sign"]:
            return []
    return [record.get("role") for record in signs]


def _line_words(line: list[dict], roles: list[str | None] | None = None) -> list[tuple[str, int, int]]:
    """Syllabic words on a line, with the token span each one covers.

    A word must end at a logogram. `ku-ro GRA 100` is the total marker followed by
    a commodity, not a word "ku-ro-GRA" — reading it as one hides the total.

    Spans matter because a marker divides its line: on `OLIV 31 *308 8 E ki-ro 1 X`
    the quantities before `ki-ro` are entries and those after it are a balance owed.
    """
    words: list[tuple[str, int, int]] = []
    current: list[str] = []
    start: int | None = None
    sign_index = 0

    def flush(end: int) -> None:
        nonlocal current, start
        if current and start is not None:
            words.append(("-".join(current), start, end))
        current = []
        start = None

    for i, token in enumerate(line):
        if token.get("kind") == "sign":
            role = roles[sign_index] if roles and sign_index < len(roles) else None
            sign_index += 1
            reading = token.get("reading")
            # Only syllabograms build words. When roles are unavailable, fall back
            # to the reading's shape: logogram readings are conventionally
            # uppercase (GRA, VIN, OLE) while syllabograms are lowercase.
            is_syllabic = (role == "syllabogram") if role else bool(reading and reading.islower())
            if reading and is_syllabic:
                if start is None:
                    start = i
                current.append(reading)
            else:
                flush(i)
        else:
            flush(i)
    flush(len(line))
    return words


def _quantity(line: list[dict]) -> Quantity:
    """The quantity expressed on a line: its integer and any fraction signs."""
    q = Quantity()
    for i, token in enumerate(line):
        kind = token.get("kind")
        if kind == "number":
            value = token.get("value")
            if isinstance(value, int):
                q.integer = value if q.integer is None else q.integer + value
        elif kind == "fraction":
            fid = token.get("id")
            if fid:
                q.fractions.append(fid)
        elif kind == "damage":
            neighbours = line[max(0, i - 1): i + 2]
            if any(n.get("kind") in {"number", "fraction"} for n in neighbours):
                q.damaged = True
    return q


def parse_document(doc: dict) -> Tablet:
    lines = doc.get("lines") or []
    roles = _sign_roles(doc)

    role_iter = iter(roles) if roles else None
    entries: list[Entry] = []
    sections: list[Section] = []
    deficits: list[Entry] = []
    untotalled: list[tuple[str | None, list[Entry]]] = []
    opened_by: str | None = None
    span_incomplete = False
    notes: list[str] = []
    damaged_lines = 0

    for line_no, line in enumerate(lines, 1):
        # Walk sign tokens in order so roles stay aligned across the whole document.
        line_roles: list[str | None] = []
        for token in line:
            if token.get("kind") == "sign":
                line_roles.append(next(role_iter) if role_iter is not None else None)

        words = _line_words(line, line_roles)
        if any(t.get("kind") == "damage" for t in line):
            damaged_lines += 1
        # A line that opens with a break has lost text before what survives, so
        # any entries in this section are incomplete (e.g. HT 46a, supra mutila).
        if line and line[0].get("kind") == "damage":
            span_incomplete = True

        marker_hit = next(((w, s, e) for (w, s, e) in words if w in TOTAL_MARKERS), None)
        deficit_hit = next(((w, s, e) for (w, s, e) in words if w in DEFICIT_MARKERS), None)

        if marker_hit:
            marker, start, end = marker_hit
            # Quantities before the marker are entries on the same line; the
            # total is only what follows it.
            before = _quantity(line[:start])
            if before.has_value:
                entries.append(Entry(line_no=line_no, quantity=before, word=words[0][0] if words else None))
            total = Total(
                line_no=line_no,
                kind=TOTAL_MARKERS[marker],
                marker=marker,
                quantity=_quantity(line[end:]),
            )
            sections.append(
                Section(
                    entries=entries,
                    total=total,
                    opened_by=opened_by,
                    entries_incomplete=span_incomplete,
                )
            )
            entries = []
            opened_by = None
            span_incomplete = False
            continue

        if deficit_hit:
            marker, start, end = deficit_hit
            # KI-RO marks a balance owed, not an addend. Anything before it on the
            # line is a real entry; anything after it is the deficit.
            before = _quantity(line[:start])
            after = _quantity(line[end:])
            if before.has_value:
                entries.append(Entry(line_no=line_no, quantity=before, word=words[0][0] if words else None))
            if after.has_value:
                deficits.append(Entry(line_no=line_no, quantity=after, word=marker))
            elif not before.has_value:
                # A bare heading: whatever preceded it is a separate, untotalled
                # group; the entries that follow are what the next total covers.
                if entries:
                    untotalled.append((opened_by, entries))
                entries = []
                opened_by = marker
            continue

        quantity = _quantity(line)

        if quantity.has_value:
            commodity = None
            if line_roles:
                sign_idx = 0
                for token in line:
                    if token.get("kind") == "sign":
                        if line_roles[sign_idx] == "logogram":
                            commodity = token.get("id")
                        sign_idx += 1
                    elif token.get("kind") in {"number", "fraction"}:
                        break
            entries.append(
                Entry(
                    line_no=line_no,
                    quantity=quantity,
                    commodity=commodity,
                    word=words[0][0] if words else None,
                )
            )

    if not roles:
        notes.append("sign roles unavailable (signs[] did not align with line tokens)")
    if any(s.total.kind == "grand_total" for s in sections):
        notes.append("grand total present: it should be checked against sub-totals, not entries")

    layout = _classify_layout(sections, entries, deficits, lines)

    return Tablet(
        id=doc.get("id", "?"),
        site=doc.get("site"),
        support=doc.get("support"),
        period=doc.get("period"),
        scribe=doc.get("scribe"),
        sections=sections,
        trailing_entries=entries,
        untotalled_groups=untotalled,
        deficits=deficits,
        layout=layout,
        damaged_lines=damaged_lines,
        unread=bool(doc.get("unread")),
        notes=notes,
        upstream_arithmetic=doc.get("arithmetic"),
    )


def _classify_layout(
    sections: list[Section],
    trailing: list[Entry],
    deficits: list[Entry],
    lines: list,
) -> str:
    if not lines:
        return "empty"
    if not sections:
        return "no_total"
    kinds = [s.total.kind for s in sections]
    if len(sections) == 1:
        base = "single_total"
    elif "grand_total" in kinds:
        base = "sections_with_grand_total"
    else:
        base = "multi_total"
    if deficits:
        base += "+deficit"
    if trailing:
        base += "+trailing_entries"
    return base


def integer_sum(section: Section) -> int:
    return sum(e.quantity.integer or 0 for e in section.entries)


def fraction_counts(quantities: list[Quantity]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for q in quantities:
        for fid in q.fractions:
            counts[fid] = counts.get(fid, 0) + 1
    return counts


def evaluate_section(section: Section, values: dict[str, Fraction]) -> dict:
    """Check a section against known fraction values, exactly.

    Returns the integer and fraction balance separately: the integer part is
    independent of any hypothesis, the fraction part is only as good as `values`.
    """
    entry_int = integer_sum(section)
    total_int = section.total.quantity.integer or 0

    entry_fracs = fraction_counts([e.quantity for e in section.entries])
    total_fracs = fraction_counts([section.total.quantity])

    unknown = sorted(
        {f for f in entry_fracs if f not in values} | {f for f in total_fracs if f not in values}
    )

    entry_frac_value = sum((values[f] * n for f, n in entry_fracs.items() if f in values), Fraction(0))
    total_frac_value = sum((values[f] * n for f, n in total_fracs.items() if f in values), Fraction(0))

    return {
        "integer_balances": entry_int == total_int,
        "integer_delta": entry_int - total_int,
        "entry_fractions": entry_fracs,
        "total_fractions": total_fracs,
        "unknown_fraction_signs": unknown,
        "fully_valued": not unknown,
        "fraction_delta": entry_frac_value - total_frac_value if not unknown else None,
        "balances": (entry_int + entry_frac_value) == (total_int + total_frac_value) if not unknown else None,
        "damaged": any(e.quantity.damaged for e in section.entries) or section.total.quantity.damaged,
    }
