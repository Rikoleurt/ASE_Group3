"""Search the corpus by sign sequence (scholars' workbench, story G): which tablets have KU-RO,
AB81-AB02, ku-*-ro or ku|ka-ro, and where.

The scholars' transcriptions (lineara.eu) give each tablet's lines in order: signs, word
dividers, numbers and damage. Each sign item is the next of the tablet's signs, so its place in
the line gives the scholars' position, the id of its box on the Tablets page. A word ends at a
divider, a number, damage or the end of a line; a sequence matches inside one word unless
`across_words`.

Some transcriptions list signs the lines leave out (unidentified ones), so lines are matched
to positions by sign ID (see `lines_of`).

A query is signs separated by "-" or spaces. Each is a sign ID (AB81, ab1, A301), a reading (ku,
VIN), "*" for any one sign, or alternatives joined by "|" (ku|ka).
"""

import re
from dataclasses import dataclass
from threading import Lock

from backend.app import glyph_index
from backend.app.data_controller.correction_data_controller import catalogue_spelling

MAX_SIGNS = 12
TOKEN = re.compile(r"^(\*|[A-Za-z0-9*]{1,12}(\|[A-Za-z0-9*]{1,12}){0,5})$")


class BadQuery(ValueError):
    """The query is not a sign sequence."""


@dataclass(frozen=True)
class Sign:
    position: (
        int | None
    )  # the scholars' position (the box id on the Tablets page); None if unmatched
    sign: str
    reading: str
    word: int  # signs with the same number are one word


@dataclass(frozen=True)
class Line:
    slug: str
    tablet: str
    number: int  # 0-based
    signs: tuple[Sign, ...]


LOOKAHEAD = 6  # the positions list can hold a few signs the lines leave out (unidentified ones)


def lines_of(slug: str, tablet: str, doc: dict) -> list[Line]:
    """The tablet's lines, each sign with its scholars' position where it can be matched: the
    next position with the same sign ID, a few ahead at most. Unmatched signs (a ligature spelled
    differently, say) are still searched; they just have no position to highlight."""
    positions = [
        (int(s["position"]), str(s.get("sign") or ""))
        for s in sorted(doc.get("signs") or [], key=lambda s: s["position"])
        if s.get("position") is not None
    ]
    out, pointer, word = [], 0, 0
    for number, items in enumerate(doc.get("lines") or []):
        signs = []
        for item in items:
            if item.get("kind") == "sign":
                sign_id = str(item.get("id") or "")
                position = None
                for ahead in range(pointer, min(pointer + LOOKAHEAD, len(positions))):
                    if sign_id and positions[ahead][1] == sign_id:
                        position, pointer = positions[ahead][0], ahead + 1
                        break
                signs.append(Sign(position, sign_id, str(item.get("reading") or ""), word))
            else:
                word += 1  # a divider, a number or damage ends the word
        word += 1  # so does the end of the line
        if signs:
            out.append(Line(slug, tablet, number, tuple(signs)))
    return out


_lines: dict[int, list[Line]] = {}
_lock = Lock()


def corpus_lines() -> list[Line]:
    """Every tablet's lines, built once per glyph index (a new download builds a new one)."""
    from la import fetch, signboxes

    index = glyph_index.get_index()
    key = id(index)
    with _lock:
        if key not in _lines:
            _lines.clear()
            built = []
            for tablet, doc in sorted(fetch.load_cached().items()):
                slug = signboxes.slug(doc)
                if slug in index.slugs:
                    built.extend(lines_of(slug, tablet, doc))
            _lines[key] = built
        return _lines[key]


def parse(query: str) -> list[set[str] | None]:
    """One entry per sign: the sign IDs and readings it may be (lower case), None for any."""
    tokens = [token for token in re.split(r"[-\s]+", query.strip()) if token]
    if not tokens:
        raise BadQuery("Type a sign sequence, e.g. KU-RO or AB81-AB02.")
    if len(tokens) > MAX_SIGNS:
        raise BadQuery(f"Search for at most {MAX_SIGNS} signs.")
    out: list[set[str] | None] = []
    for token in tokens:
        if not TOKEN.fullmatch(token):
            raise BadQuery(
                f"“{token}” is not a sign: use a sign ID, a reading, * or alternatives with |."
            )
        if token == "*":
            out.append(None)
            continue
        options = set()
        for option in token.split("|"):
            options.add(option.lower())
            options.add(catalogue_spelling(option).lower())
        out.append(options)
    return out


def _fits(sign: Sign, wanted: set[str] | None) -> bool:
    return (
        wanted is None
        or sign.sign.lower() in wanted
        or (sign.reading and sign.reading.lower() in wanted)
    )


def search(
    lines: list[Line], query: list[set[str] | None], across_words: bool = False
) -> list[tuple[Line, list[Sign]]]:
    """(line, the signs matched) for each match, in tablet then line order."""
    hits = []
    size = len(query)
    for line in lines:
        for start in range(len(line.signs) - size + 1):
            run = line.signs[start : start + size]
            if not across_words and len({sign.word for sign in run}) > 1:
                continue
            if all(_fits(sign, wanted) for sign, wanted in zip(run, query)):
                hits.append((line, list(run)))
    return hits


def edition_lines(slug: str, tablet: str, reading_lines: list, signs_by_id: dict) -> list[Line]:
    """An accepted edition's lines from its reading: words as its transliteration splits them."""
    out = []
    word = 0
    for line in reading_lines:
        signs = []
        words = line.text.split()
        sizes = [len(w.split("-")) for w in words]
        index = 0
        for size in sizes:
            for sign_id in line.sign_ids[index : index + size]:
                sign = signs_by_id[sign_id]
                signs.append(Sign(sign_id, sign.sign or "", sign.reading or "", word))
            index += size
            word += 1
        for sign_id in line.sign_ids[index:]:  # anything the words did not cover
            sign = signs_by_id[sign_id]
            signs.append(Sign(sign_id, sign.sign or "", sign.reading or "", word))
            word += 1
        if signs:
            out.append(Line(slug, tablet, line.index, tuple(signs)))
    return out
