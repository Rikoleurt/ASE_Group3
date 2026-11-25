# Searching the corpus by sign sequence

Part of the scholars' workbench (story G). On the Tablets page, switch the search to **Sign
sequence** and type a sequence. The results list each tablet that has it, with what matched;
opening one highlights the matched signs on the tablet.

## Queries

Signs are separated by `-` or spaces. Each sign is one of:

| Write | Matches | Example |
|---|---|---|
| a reading | the sign read that way | `ku-ro`, `VIN` |
| a sign number | that sign, however it is spelled | `AB81-AB02`, `ab1` (AB01) |
| `*` | any one sign | `ku-*-ro` |
| alternatives with `\|` | any of them | `ku\|ka-ro` |

At most 12 signs.

**Words.** A match stays inside one word unless **Across word breaks** is ticked. A word
ends at a word divider, a number, damage, or the end of a line.

**Drawing.** **Draw a sign to add** opens the sketch pad; picking a suggestion adds that
sign to the query.

## What is searched

- **The scholars' transcriptions** (lineara.eu), line by line. Each line's signs are matched
  to the scholars' positions (the boxes on the Tablets page) by sign ID. Some transcriptions
  list signs the lines leave out, unidentified ones for instance.
  - On tablets with positions, 94% of signs are matched (measured on the corpus).
  - A sign that cannot be matched is still searched, but has no box to highlight.
  - Tablets with no positions at all are searched too.
- **The community editions:** each tablet's accepted release (see [editions.md](editions.md)),
  in its reading order, with words as its transliteration splits them. A match opens the
  release.

## API

`GET /corpus/search?q=ku-ro&source=scholar|edition&across_words=false&limit=30&offset=0` returns
the tablets with matches (paged by tablet), each match's line, positions and text, and the
totals. A query that is not a sign sequence gets 422 with the reason.
