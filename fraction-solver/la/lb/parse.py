"""Tokenise DAMOS Linear B transliterations into measures, entries and totals.

DAMOS stores each document as the editors' transliteration with no structural markup
for quantities — `to-so OLE 3 S 2 V 2` is a plain string — so everything the audit
needs has to be recovered from the typographic conventions. Six of them are easy to
get wrong, and each one cost a wrong answer before it was handled:

* **Square brackets mean three different things.** `1[` is a break the numeral may
  continue into, so the amount is a lower bound. `]VIR 1` means text was lost *before*
  what survives, so whole entries may be missing. But `[VIR 1]` is neither: it is text
  the editor has **restored**. Auditing whether a scribe's total matches entries an
  editor supplied *in order to* make it match is circular, so restored quantities are
  flagged and excluded from the headline error rate.
* **Uncertain readings are combining underdots** (U+0323). `ỌḶỊṾ` is OLIV with four
  underdots; comparing it to "OLIV" fails and the commodity silently vanishes.
* **A line carries many measures, not one.** Pylos Ma assessments list six commodities
  on one line, so the unit of analysis is the (commodity, quantity) group.
* **The commodity is often written once and then implied.** On KN Fp 1 half the entries
  read only `S 1`; the oil is understood. That inference is flagged per measure.
* **A bare number after a word counts that word, not the last logogram.** On KN Ap 639,
  `MUL 1 ko-wa 2` is one woman and two girls — not two more women. Inheriting the
  logogram across a word turns every `ko-wa` into a miscount.
* **`to-so` is not always a total.** It means "so much", and on KN F(1) 157 it opens the
  tablet with the entries *after* it. Only a marker with entries already accumulated
  closes a section, exactly as with Linear A's `ku-ro`.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from la.lb import metrology
from la.lb.metrology import Series

# "So much" — the total. `-de` is the enclitic "and". `ku-su-to-ro-qa` (xustropha,
# "sum") and `to-so-ku-su-pa` / `ku-su-pa` ("so much all together") are grand totals:
# rare, but they are the only Linear B total words besides to-so/to-sa, and omitting
# them would drop real arithmetic. A grand total may cover sub-totals rather than
# entries, which is flagged the same way the Linear A parser flags po-to-ku-ro.
TOTAL_MARKERS = {"to-so", "to-sa", "to-so-de", "to-sa-de"}
GRAND_TOTAL_MARKERS = {"ku-su-to-ro-qa", "to-so-ku-su-pa", "ku-su-pa", "to-sa-ku-su-pa"}

# Amounts that are not addends. `o-pe-ro` is a deficit owed (Linear A's ki-ro),
# `a-pu-do-si` a delivery against an assessment, `o-u-di-do-si` ("they do not give")
# an exemption. Summing any of these is the Linear B form of the inline-KI-RO mistake
# that corrupted the first Linear A pass.
DEFICIT_MARKERS = {"o-pe-ro", "o-pe-ro-si", "o-pe-ro-te", "o", "o-pe"}
DELIVERY_MARKERS = {"a-pu-do-si", "a-pu-do-si-si", "a-pu-do-ke"}
EXEMPTION_MARKERS = {"o-u-di-do-si", "o-u-di-do-to", "o-u-qe-di-do-si", "o-u-di-do-ta"}

#: Words that never become a commodity in their own right: they mark the role of what
#: follows and leave the commodity in force unchanged.
ROLE_MARKERS = (
    TOTAL_MARKERS | GRAND_TOTAL_MARKERS | DEFICIT_MARKERS | DELIVERY_MARKERS | EXEMPTION_MARKERS
)

# Editorial notes. The distinction between the two groups is load-bearing: `vacat` is
# clay the scribe deliberately left blank, so nothing is missing, whereas `sup. mut.`
# means the top of the tablet has broken away and entries may be gone. Treating the
# second as merely "empty" is what made a fragmentary Knossos tablet look like a
# scribal error in the first pass of this audit.
LOST_EDITORIAL_RE = re.compile(
    r"(inf\.\s*mut\.|sup\.\s*mut\.|dex\.\s*mut\.|sin\.\s*mut\.|im\.\s*mut\.|"
    r"infra\s+mut\.|supra\s+mut\.|mut\.|deest|desunt|lacuna|vest\.|vestigia|"
    r"fragmentum\s+\w+)",
    re.IGNORECASE,
)
BLANK_EDITORIAL_RE = re.compile(
    r"(reliqua\s+pars\s+sine\s+regulis|vacat|vac\.|graffito)",
    re.IGNORECASE,
)

LINE_LABEL_RE = re.compile(
    r"^\s*(?:(?:v|r|lat\.\s*inf|lat\.\s*sup|lat\.\s*dex|lat\.\s*sin|sup|inf)\s*\.\s*"
    r"[→↓←↑]?)?\s*(?:\.\s*[0-9A-Za-z]+)?"
)

# One scanner over the whole line, so every token keeps its character offsets.
# Offsets matter for one reason: whether a bracket is *attached* to the numeral before
# it. `S 1[` says the numeral may run on into the break, so the amount is a lower
# bound; `TELA 1        [` says the line breaks off after a complete amount, so what
# is lost is whole entries. Standard Mycenaean editorial practice distinguishes the two
# by exactly this spacing, and DAMOS preserves it.
TOKEN_SCANNER = re.compile(
    r"(?P<lost>\x00L\x00)"
    r"|(?P<blank>\x00B\x00)"
    r"|(?P<illegible>\x00I\x00)"
    r"|(?P<bracket>[\[\]])"
    r"|(?P<number>\d+)"
    r"|(?P<starword>\*\d+[a-z]?(?:-[a-z0-9*]+)+)"
    r"|(?P<starsign>\*\d+[a-z]?)"
    r"|(?P<sign>[A-Z][A-Za-z0-9]*(?:[+:;][A-Za-z0-9]+)*)"
    r"|(?P<word>[a-z][a-z0-9]*(?:-[a-z0-9*]+)*)"
    r"|(?P<divider>[,/])"
    r"|(?P<other>\S)"
)

#: Typographic variant suffixes. `TELA;1` and `TELA;2` are cloth types and `OVIS:m` is
#: the male form; a total written `to-sa TELA 40` covers all TELA variants at once, so
#: entries and totals are matched on the base sign. Ligatures (`GRA+PE`) are *not*
#: stripped: those are distinct commodities, not notational variants of one.
VARIANT_SPLIT_RE = re.compile(r"[;:]")


def base_commodity(name: str | None) -> str | None:
    """The sign a commodity is a typographic variant of, for matching totals to entries."""
    if not name:
        return name
    return VARIANT_SPLIT_RE.split(name)[0]


def strip_marks(text: str) -> tuple[str, bool]:
    """Remove combining marks, reporting whether any were present.

    Underdots mark an uncertain reading. They must go before any sign is matched, but
    that they were there is evidence about the tablet's condition, so it is kept.
    """
    decomposed = unicodedata.normalize("NFD", text)
    kept = [c for c in decomposed if unicodedata.category(c) != "Mn"]
    return unicodedata.normalize("NFC", "".join(kept)), len(kept) != len(decomposed)


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

#: Token kinds. The three bracket kinds are the whole reason this stage exists.
WORD = "word"
SIGN = "sign"
NUMBER = "number"
BREAK_AFTER = "break_after"        # trailing `[` : the amount may continue
LOST_BEFORE = "lost_before"        # leading `]` : entries may be missing
GAP = "gap"                        # `[ ]` with nothing inside : content lost
RESTORE_START = "restore_start"    # `[` of an editorial restoration
RESTORE_END = "restore_end"        # `]` of an editorial restoration
LOST_NOTE = "lost_note"            # sup. mut., deest, vest. : clay broken away
BLANK_NOTE = "blank_note"          # vacat : left blank on purpose, nothing missing
ILLEGIBLE = "illegible"
DIVIDER = "divider"


@dataclass
class Token:
    kind: str
    text: str
    value: int | None = None
    uncertain: bool = False
    start: int = 0
    end: int = 0
    attached: bool = False       # nothing but text immediately before this token
    attached_next: bool = False  # nothing but text immediately after it


def _classify_brackets(tokens: list[Token]) -> list[Token]:
    """Resolve raw `[` and `]` into break, lost-text, gap or editorial restoration.

    **Adjacency decides, not matching.** An earlier version paired any `[` with a later
    `]` and called the contents "restored", which misread PY Ma 397:

        KE  M  2[     *152  10   O  M  5          ]  ME  500

    Those two brackets are the *two edges of one lacuna*, not a pair enclosing supplied
    text — the reading is "2, then the tablet breaks" and later "the tablet resumes,
    then ME 500". Treating it as a restoration hid the break, so `KE M 2` was scored as a
    sound value that disagreed with the series rather than as a damaged one the series
    could restore.

    A restoration hugs its content: `[VIR 1]`, `[ki-]ta-no`, `[a-pu-]do-si`, `[O M 1]4`.
    So a bracket pair is a restoration only when the opener has text immediately after it
    *and* the closer has text immediately before it. Every other bracket marks a lacuna
    edge: `[` that the text runs into, `]` that it emerges from.
    """
    kinds: dict[int, str] = {}
    opens: list[int] = []
    for i, tok in enumerate(tokens):
        if tok.kind != "raw_bracket":
            continue
        if tok.text == "[":
            if tok.attached_next:
                opens.append(i)      # could be hugging content it restores
            else:
                kinds[i] = BREAK_AFTER
        else:  # "]"
            if tok.attached and opens:
                start = opens.pop()
                inner = [t for t in tokens[start + 1:i] if t.kind in {WORD, SIGN, NUMBER}]
                kinds[start], kinds[i] = (
                    (RESTORE_START, RESTORE_END) if inner else (GAP, GAP)
                )
            else:
                kinds[i] = LOST_BEFORE
    for i in opens:
        kinds[i] = BREAK_AFTER   # hugged content but nothing closed it: a lacuna edge

    out: list[Token] = []
    for i, tok in enumerate(tokens):
        if tok.kind == "raw_bracket":
            out.append(Token(
                kinds.get(i, GAP), tok.text,
                start=tok.start, end=tok.end,
                attached=tok.attached, attached_next=tok.attached_next,
            ))
        else:
            out.append(tok)
    return _merge_split_numerals(_collapse_lacunae(out))


def _collapse_lacunae(tokens: list[Token]) -> list[Token]:
    """A break immediately followed by a resumption is one bounded gap.

    `o-[   ]  ,  ko-no-so` records a lacuna with nothing legible in it, so content is
    certainly missing — a hard loss, not the softer "the line breaks off at the edge".
    """
    out: list[Token] = []
    i = 0
    while i < len(tokens):
        if (
            tokens[i].kind == BREAK_AFTER
            and i + 1 < len(tokens)
            and tokens[i + 1].kind == LOST_BEFORE
        ):
            out.append(Token(GAP, "[]", start=tokens[i].start, end=tokens[i + 1].end,
                             attached=tokens[i].attached))
            i += 2
            continue
        if tokens[i].kind == GAP and out and out[-1].kind == GAP:
            i += 1
            continue
        out.append(tokens[i])
        i += 1
    return out


BRACKET_KINDS = {BREAK_AFTER, LOST_BEFORE, GAP, RESTORE_START, RESTORE_END}


def _merge_split_numerals(tokens: list[Token]) -> list[Token]:
    """Rejoin a numeral a bracket cuts in half.

    PY Ma 120 reads `[O M  1]4̣` — the editor restored the `1`, the `4` survives, and
    the amount is **14**. Because the bracket falls inside the numeral, a naive scan
    yields two numbers, and `O M 1` plus a stray `4` is both wrong and silently
    plausible. The giveaway is that nothing separates them: digit, bracket and digit are
    all mutually attached, so the numeral is one token interrupted by an editorial mark.
    The result is flagged as partly restored, because part of it is the editor's.
    """
    out: list[Token] = []
    i = 0
    while i < len(tokens):
        if (
            i + 2 < len(tokens)
            and tokens[i].kind == NUMBER
            and tokens[i + 1].kind in BRACKET_KINDS
            and tokens[i + 1].attached
            and tokens[i + 2].kind == NUMBER
            and tokens[i + 2].attached
        ):
            text = tokens[i].text + tokens[i + 2].text
            merged = Token(
                NUMBER,
                text,
                value=int(text),
                start=tokens[i].start,
                end=tokens[i + 2].end,
                uncertain=True,
            )
            out.append(merged)
            # The bracket still has to be emitted, or a restoration that opened before
            # the numeral never closes and every later measure on the line is wrongly
            # marked as the editor's work.
            out.append(tokens[i + 1])
            i += 3
            continue
        out.append(tokens[i])
        i += 1
    return out


def tokenise(raw_line: str) -> tuple[list[Token], str | None]:
    """Split one transliterated line into tokens, returning also its line label."""
    label_match = LINE_LABEL_RE.match(raw_line)
    label = (label_match.group(0).strip() or None) if label_match else None
    body = raw_line[label_match.end():] if label_match else raw_line

    body, _ = strip_marks(body)
    body = LOST_EDITORIAL_RE.sub(lambda m: "\x00L\x00".ljust(len(m.group(0))), body)
    body = BLANK_EDITORIAL_RE.sub(lambda m: "\x00B\x00".ljust(len(m.group(0))), body)
    body = re.sub(r"[•]", "\x00I\x00", body)
    body = re.sub(r"['‘’]", " ", body)

    tokens: list[Token] = []
    for m in TOKEN_SCANNER.finditer(body):
        kind = m.lastgroup or "other"
        text = m.group()
        start, end = m.start(), m.end()
        attached = start > 0 and not body[start - 1].isspace()
        attached_next = end < len(body) and not body[end].isspace()
        # Both sides are carried on every token, not just brackets: merging a numeral a
        # bracket splits (`1]4` = 14) needs to know the *digits* are attached too, and
        # telling a restoration from a lacuna edge needs the bracket's right-hand side.
        common = {"start": start, "end": end, "attached": attached, "attached_next": attached_next}
        if kind == "lost":
            tokens.append(Token(LOST_NOTE, "lost", **common))
        elif kind == "blank":
            tokens.append(Token(BLANK_NOTE, "blank", **common))
        elif kind == "illegible":
            tokens.append(Token(ILLEGIBLE, "*", **common))
        elif kind == "bracket":
            tokens.append(Token("raw_bracket", text, **common))
        elif kind == "number":
            tokens.append(Token(NUMBER, text, value=int(text), **common))
        elif kind in {"sign", "starsign"}:
            tokens.append(Token(SIGN, text, **common))
        elif kind in {"word", "starword"}:
            tokens.append(Token(WORD, text.lower(), **common))
        else:
            tokens.append(Token(DIVIDER, text, **common))
    return _classify_brackets(tokens), label


# ---------------------------------------------------------------------------
# Measures
# ---------------------------------------------------------------------------


@dataclass
class Measure:
    """One (commodity, quantity) group: the unit of Linear B arithmetic."""

    commodity: str | None
    terms: list[tuple[str, int]] = field(default_factory=list)  # (unit, count), largest first
    line_label: str | None = None
    line_no: int = 0
    damaged: bool = False            # a break may have swallowed part of the amount
    uncertain: bool = False          # underdotted sign or numeral
    inherited_commodity: bool = False
    restored: bool = False           # the editor supplied this, not the clay
    counted_noun: bool = False       # the "commodity" is a word (ko-wa, ko-wo)
    role: str = "entry"              # entry | total | deficit | delivery | exemption

    @property
    def has_value(self) -> bool:
        return bool(self.terms)

    @property
    def open(self) -> bool:
        """The written amount may be incomplete, so it is a lower bound."""
        return self.damaged

    def series(self, series_map: dict[str, str] | None = None) -> Series | None:
        """The unit series this measure is in, or None when it cannot be resolved.

        A metrogram settles it directly (`T` dry, `S` liquid, `M` weight); otherwise
        the commodity decides. `series_map`, derived from corpus usage by
        `audit.infer_commodity_series`, takes precedence over the hand-written
        convention because the corpus is the better witness.
        """
        if self.counted_noun:
            return None
        base = metrology.series_for(self.commodity)
        if series_map is not None and self.commodity in series_map:
            name = series_map[self.commodity]
            base = metrology.SERIES.get(name) if name else None
        for unit, _ in self.terms:
            if unit == "UNIT":
                continue
            return metrology.metrogram_series(unit, base)  # None means truly ambiguous
        return base

    def value(self, series_map: dict[str, str] | None = None) -> int | None:
        """Value in the series' smallest unit, or None when unresolvable.

        A counted commodity has no series, so its value is the bare number. That lets
        counted and measured tablets share one audit path, which makes the series map
        load-bearing: reading a measured commodity as counted would compare whole
        units against subunits and invent a mismatch.
        """
        if not self.terms:
            return None
        series = self.series(series_map)
        if series is None:
            if any(u != "UNIT" for u, _ in self.terms):
                return None  # a subunit we cannot place: refuse rather than guess
            return sum(c for u, c in self.terms if u == "UNIT")
        if any(u != "UNIT" and u not in series.units for u, _ in self.terms):
            return None
        if "UNIT" in {u for u, _ in self.terms} and "UNIT" not in series.units:
            return None  # e.g. a bare number under the weight series: no top unit
        try:
            return metrology.value_in_smallest(self.terms, series)
        except ValueError:
            return None

    def render(self) -> str:
        body = " ".join(f"{u} {c}" if u != "UNIT" else str(c) for u, c in self.terms)
        return f"{self.commodity or '?'} {body}".strip()


def counted_noun_candidates(content: str) -> set[str]:
    """Words written immediately before a bare number, on this document.

    The input to `audit.infer_counted_nouns`, which decides whether such a word counts
    itself or merely labels a quantity of the commodity in force.
    """
    out: set[str] = set()
    for raw in content.splitlines():
        if not raw.strip():
            continue
        tokens, _ = tokenise(raw)
        for a, b in zip(tokens, tokens[1:]):
            if a.kind == WORD and b.kind == NUMBER and a.text not in ROLE_MARKERS:
                out.add(a.text)
    return out


def measures_from_tokens(
    tokens: list[Token],
    line_no: int,
    label: str | None,
    carried_commodity: str | None = None,
    counted_nouns: frozenset[str] = frozenset(),
) -> tuple[list[Measure], str | None, str | None]:
    """Group a line's tokens into measures.

    Returns the measures, the commodity left in force for the next line, and how badly
    this line has lost text: `"hard"`, `"soft"` or None.

    The distinction decides how much of the corpus is usable, so it is worth stating.
    A **hard** loss is an empty bracket pair or an editorial note like `sup. mut.`:
    content is unambiguously missing, and any total above it is unauditable. A **soft**
    loss is edge damage — a detached `[` where the line breaks off, or a `]` where it
    resumes. Entries may or may not have been lost there.

    Treating every soft loss as hard leaves almost nothing: only 3 of the 56 Knossos
    tablets carrying a total are free of brackets altogether. Treating every soft loss
    as harmless would quietly count missing entries as scribal error. So both are
    recorded and the audit reports the error rate at each tier.
    """
    measures: list[Measure] = []
    current: Measure | None = None
    commodity = carried_commodity
    commodity_on_this_line = False
    last_word: str | None = None
    role = "entry"
    expect_unit: str | None = None
    in_restoration = False
    loss: str | None = None

    def mark(level: str) -> None:
        nonlocal loss
        if level == "hard" or loss is None:
            loss = level

    def close() -> None:
        nonlocal current, expect_unit
        if current is not None and current.has_value:
            measures.append(current)
        current = None
        expect_unit = None

    def begin(as_noun: str | None = None) -> Measure:
        return Measure(
            commodity=as_noun or commodity,
            line_label=label,
            line_no=line_no,
            inherited_commodity=(
                as_noun is None and commodity is not None and not commodity_on_this_line
            ),
            restored=in_restoration,
            counted_noun=as_noun is not None,
            role=role,
        )

    for i, tok in enumerate(tokens):
        if tok.kind == RESTORE_START:
            in_restoration = True
            continue
        if tok.kind == RESTORE_END:
            in_restoration = False
            continue

        if tok.kind == GAP:
            # A bounded lacuna with nothing legible in it. Two things can be true at once:
            # content is missing from the section, *and* if the lacuna opened right against
            # a numeral (`RI M 14[   ]`) that numeral may have run on into it. Recording
            # only the first loses every restorable value on a fragmentary Pylos tablet.
            if tok.attached:
                if current is not None:
                    current.damaged = True
                elif measures and measures[-1].line_no == line_no:
                    measures[-1].damaged = True
            close()
            mark("hard")
            continue

        if tok.kind == LOST_BEFORE:
            close()
            mark("soft")   # the line resumes after edge damage
            continue

        if tok.kind == BREAK_AFTER:
            # Attached to the numeral (`S 1[`): the amount may run on into the break, so
            # what survives is a lower bound. Detached (`TELA 1      [`): the amount is
            # complete and the *line* breaks off, so whole entries may be lost. Reading
            # every trailing bracket the first way marks sound quantities as damaged and
            # throws away most of the auditable corpus; reading every one the second way
            # loses the recoverable cases. The spacing is the evidence.
            if tok.attached:
                if current is not None:
                    current.damaged = True
                elif measures and measures[-1].line_no == line_no:
                    measures[-1].damaged = True
                else:
                    mark("soft")
            else:
                mark("soft")
            continue

        if tok.kind == DIVIDER:
            close()
            continue

        if tok.kind == WORD:
            close()
            if tok.text in TOTAL_MARKERS:
                role = "total"
            elif tok.text in GRAND_TOTAL_MARKERS:
                role = "grand_total"
            elif tok.text in DEFICIT_MARKERS:
                role = "deficit"
            elif tok.text in DELIVERY_MARKERS:
                role = "delivery"
            elif tok.text in EXEMPTION_MARKERS:
                role = "exemption"
            # Only a word the corpus shows to be a counted category (`ko-wa`, `ko-wo`)
            # may claim a bare number for itself. A personal name may not: on the Knossos
            # As tablets, `a-ma-no 1` is one *man*, the VIR being understood from the lines
            # around it, and treating the name as the commodity detaches every such entry
            # from its total and empties the auditable corpus.
            last_word = tok.text if tok.text in counted_nouns else None
            continue

        if tok.kind == LOST_NOTE:
            close()
            mark("hard")
            last_word = None
            continue

        if tok.kind in {BLANK_NOTE, ILLEGIBLE}:
            close()
            last_word = None
            continue

        if tok.kind == SIGN:
            name = tok.text
            # A metrogram subdivides the quantity in progress, and counts as one
            # whenever any commodity is in force — including one named a token earlier
            # on the same line, which is the `OLE S 1` case.
            if name in metrology.METROGRAMS and (current is not None or commodity is not None):
                if current is None:
                    current = begin()
                expect_unit = name
                last_word = None
                continue
            close()
            commodity = name
            commodity_on_this_line = True
            last_word = None
            current = begin()
            current.uncertain = tok.uncertain
            continue

        if tok.kind == NUMBER:
            if current is None:
                # A bare number straight after a content word counts that word.
                # `MUL 1 ko-wa 2` is one woman and two girls.
                current = begin(as_noun=last_word if expect_unit is None else None)
            current.terms.append((expect_unit or "UNIT", tok.value or 0))
            expect_unit = None
            nxt = tokens[i + 1] if i + 1 < len(tokens) else None
            if nxt is not None and nxt.kind == BREAK_AFTER and nxt.attached:
                current.damaged = True
            continue

    close()
    return measures, commodity, loss


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


@dataclass
class LBSection:
    """Entries closed by a total, for one commodity."""

    commodity: str | None
    entries: list[Measure]
    total: Measure
    series: Series | None
    tablet: str = "?"
    entries_incomplete: bool = False  # content certainly missing above the total
    edge_damage: bool = False         # the tablet breaks off in the span; entries may be lost
    grand: bool = False               # a grand total, which may cover sub-totals not entries

    @property
    def has_open_quantity(self) -> bool:
        return any(m.open for m in self.entries) or self.total.open

    @property
    def tier(self) -> str:
        """How far the arithmetic can be trusted.

        * `clean`  — nothing missing anywhere in the span; the sum is the scribe's own.
        * `edge`   — the tablet breaks off in the span, so an entry may be lost.
        * `broken` — content is certainly missing; the sum is not the scribe's.
        """
        if self.entries_incomplete:
            return "broken"
        if self.edge_damage:
            return "edge"
        return "clean"

    @property
    def has_restored(self) -> bool:
        """True when an editor supplied part of the arithmetic.

        Checking a total against entries the editor restored *so that* it would match
        is circular, so these are reported apart from the headline error rate.
        """
        return any(m.restored for m in self.entries) or self.total.restored

    @property
    def yields_equation(self) -> bool:
        """Only a section with nothing missing can assert an exact equality."""
        return not self.has_open_quantity and not self.entries_incomplete

    def entry_sum(self, series_map: dict[str, str] | None = None) -> int | None:
        values = [m.value(series_map) for m in self.entries]
        if any(v is None for v in values):
            return None
        return sum(values)  # type: ignore[arg-type]

    def residual(self, series_map: dict[str, str] | None = None) -> int | None:
        """Recorded total minus summed entries, in the smallest unit.

        Zero means the scribe's arithmetic is right; positive means the entries fall
        short, which is what a break can legitimately explain.
        """
        total = self.total.value(series_map)
        entries = self.entry_sum(series_map)
        if total is None or entries is None:
            return None
        return total - entries


@dataclass
class LBTablet:
    id: str
    damos_id: int
    site: str | None
    series_code: str | None
    subseries: str | None
    set_code: str | None
    hand: str | None
    stylus: str | None
    chronology: str | None
    preserved: bool
    measures: list[Measure]
    sections: list[LBSection]
    hard_loss_lines: set[int] = field(default_factory=set)
    soft_loss_lines: set[int] = field(default_factory=set)
    notes: list[str] = field(default_factory=list)

    @property
    def entries(self) -> list[Measure]:
        return [m for m in self.measures if m.role == "entry"]

    @property
    def totals(self) -> list[Measure]:
        return [m for m in self.measures if m.role == "total"]


def _clean_hand(value: str | None) -> str | None:
    """DAMOS writes an unattributed hand as '-'; make that absent, not a label."""
    if not value or value.strip() in {"-", "?", ""}:
        return None
    return value.strip()


def parse_document(doc: dict, counted_nouns: frozenset[str] = frozenset()) -> LBTablet:
    """Parse one DAMOS record.

    `counted_nouns` names the words that count themselves rather than labelling a quantity
    of the commodity in force. It is corpus-derived — see `audit.infer_counted_nouns` —
    because nothing in a word's spelling distinguishes `ko-wa` ("girl", a counted category)
    from `a-ma-no` (a man's name, where the bare number counts men).
    """
    item = doc.get("item") or {}
    meta = doc.get("meta") or {}
    content = item.get("content") or ""

    measures: list[Measure] = []
    hard: set[int] = set()
    soft: set[int] = set()
    commodity: str | None = None

    for line_no, raw in enumerate(content.splitlines(), 1):
        if not raw.strip():
            continue
        tokens, label = tokenise(raw)
        line_measures, commodity, loss = measures_from_tokens(
            tokens, line_no=line_no, label=label, carried_commodity=commodity,
            counted_nouns=counted_nouns,
        )
        if loss == "hard":
            hard.add(line_no)
        elif loss == "soft":
            soft.add(line_no)
        measures.extend(line_measures)

    tablet_id = item.get("heading_short") or item.get("heading") or str(doc.get("_damos_id", "?"))
    sections = _build_sections(measures, tablet_id, hard, soft)

    return LBTablet(
        id=tablet_id,
        damos_id=int(doc.get("_damos_id") or 0),
        site=meta.get("Site"),
        series_code=item.get("series"),
        subseries=item.get("subseries"),
        set_code=item.get("set"),
        hand=_clean_hand(meta.get("Hand")),
        stylus=_clean_hand(meta.get("Stylus")),
        chronology=meta.get("Chronology"),
        preserved=str(meta.get("Preserved", "")).strip().lower() == "yes",
        measures=measures,
        sections=sections,
        hard_loss_lines=hard,
        soft_loss_lines=soft,
    )


def _build_sections(
    measures: list[Measure],
    tablet_id: str,
    hard_loss_lines: set[int],
    soft_loss_lines: set[int],
) -> list[LBSection]:
    """Pair each total with the entries it closes, matched on commodity.

    A Linear B total line often restates several commodities at once
    (`to-sa MUL 45 ko-wa 5 ko-wo 4`), each totalling its own entries, so sections are
    cut per commodity rather than per line. Entries are consumed once a total claims
    them, so a later total covers only what follows the first.

    A section is `entries_incomplete` when a gap falls anywhere in the span it covers:
    what survives then understates the sum for a reason no single quantity records.
    This is the Linear B form of the *supra mutila* rule that had to be added on the
    Linear A side after HT 46a produced a 42.5 "shortfall" that was simply a missing
    entry list.
    """
    sections: list[LBSection] = []
    pending: dict[str | None, list[Measure]] = {}
    span_start = 1
    last_total_line = 0

    for measure in measures:
        if measure.role == "entry":
            pending.setdefault(base_commodity(measure.commodity), []).append(measure)
            continue
        if measure.role not in {"total", "grand_total"}:
            continue  # deficits, deliveries and exemptions are never addends
        # Matched on the base sign, so `to-sa TELA 40` collects TELA, TELA;1 and TELA;2.
        entries = pending.pop(base_commodity(measure.commodity), [])
        # The span runs from the last total (or the top of the tablet) to this one —
        # *not* from the first surviving entry. Entries lost above the first survivor
        # are exactly the case that must invalidate the section, and measuring the span
        # from the survivors makes that loss invisible.
        #
        # One line can carry several totals (`to-sa MUL 45 ko-wa 5 ko-wo 4`), each for a
        # different commodity. They are siblings covering the same span, so the span
        # only advances when a *later* line is reached; advancing per total gave the
        # second and third an empty span and silently marked them complete.
        if measure.line_no != last_total_line:
            span_start = last_total_line + 1
            last_total_line = measure.line_no
        span = range(span_start, measure.line_no + 1)
        incomplete = any(line in hard_loss_lines for line in span)
        edge = any(line in soft_loss_lines for line in span)
        if len(entries) < 2:
            continue  # one entry equalling its own total says nothing about arithmetic
        sections.append(
            LBSection(
                commodity=measure.commodity,
                entries=entries,
                total=measure,
                series=measure.series() or entries[0].series(),
                tablet=tablet_id,
                entries_incomplete=incomplete,
                edge_damage=edge,
                grand=measure.role == "grand_total",
            )
        )
    return sections
