# Sketch search and sign previews

## Sign previews

Every sign picker shows each sign as a small picture. The picture comes from
`GET /glyphs/{sign}/preview.png` (96 px, cached for a day), which serves the first of these
that exists:

1. **The sign's most typical drawing in the corpus.** The glyph index picks the occurrence
   nearest the sign's centre (`GlyphIndex.typical`). Its own crop is used if the sign crops
   are downloaded; otherwise its box is cut from the tablet's tracing.
2. **The sign's Unicode character**, drawn in Noto Sans Linear A.

If neither exists, the endpoint answers 404 and the picker shows the character, or `?`.

The catalogue (`GET /corrections/catalogue`) gives each sign's `reading` and `preview_url`.
The pickers rank matches in this order: exact readings and numbers (`ku`, `81`, `AB81`, `ab1`),
then readings starting with the query, then numbers starting with it, then names containing it.

Signs can be @-mentioned in discussions (`@[AB81 (ku)](sign:AB81)`). The mention shows the
sign's picture, and only signs in the catalogue are accepted.

## Sketch to search

`POST /glyphs/sketch` takes a PNG of a sketch and returns the most similar signs, best first.
The sketch can be strokes on a transparent background (what a canvas exports) or dark strokes
on a light background.

- **Public, with limits:** 60 sketches a minute per address and 256 KB per sketch. Sketches
  are not stored.
- **Busy reader:** if a tablet reading holds the reader for more than 5 s, the endpoint
  answers 503 rather than queueing.

How a sketch is scored (`backend/app/sketch_search.py`):

1. **Clean up.** The sketch is cropped to its ink and scaled to 256 px. It is thinned to a
   one-pixel skeleton and redrawn with an even pen 3.8% of its longest side wide: the median
   stroke width of the SigLA tracings (measured on 200 sign drawings). A thin mouse line and a
   wide finger stroke therefore both look like a tracing.
2. **Score.** It is scored the way the reader names a sign: the classifier's probabilities
   blended with the neighbour bank's (the best cosine to each sign's training crops), with the
   reader's own weights (`models/linear_a_reader.json`).

## Drawing pad and Find a sign

- **Draw it.** Every sign picker (the box editor, the correction form) has a ✎ **Draw it**
  button. It opens a drawing pad that takes a mouse, a finger or a pen, with undo, clear and a
  pen width. The suggestions update 400 ms after the last stroke, and only the latest answer is
  shown. Picking one fills the picker.
- **Find a sign** (`/signs`, **Signs** in the top bar). Every catalogue sign is listed with its
  typical drawing, with a search by number, reading or name, and the drawing pad beside it.
- **A sign's page** (`/signs/AB81`). It shows the sign's reading and its occurrences across
  the corpus, most typical first, each linking to its tablet. Unusual forms are marked. An
  occurrence whose crop is not downloaded shows its tablet's thumbnail instead, or a
  placeholder when that tablet's drawing is missing too.

## How well it works

Measured with `python scripts/eval_sketch.py` before building the drawing pad. There are no
team-drawn sketches yet, so two stand-ins are used:

- **Sketch-like tracings:** drawings from the dataset's *test* tablets (never trained on),
  thinned, redrawn with the even pen and jittered (±6° rotation, ±10% scale, a small shear).
- **Font characters:** each sign's Unicode character, the standard form a scholar draws from
  memory.

Top-k is the share of queries whose right sign is among the first k suggestions (blend
scoring):

| Stand-in | Signs | Queries | Top-1 | Top-5 | Top-12 |
|---|---|---|---|---|---|
| Sketch-like tracings | all | 622 | 44.2% | 69.5% | 78.8% |
| Sketch-like tracings | 20 most common | 299 | 60.2% | 85.3% | 91.0% |
| Font characters | all | 249 | 39.0% | 60.6% | 69.9% |
| Font characters | 20 most common | 20 | 90.0% | 100% | 100% |

The plan's go/no-go bar was a top-5 of at least 60% on the 20 most common signs. Both
stand-ins pass it. The 20 most common signs are A707, AB01, AB02, AB03, AB06, AB07, AB08, AB27,
AB28, AB30, AB31, AB41, AB51, AB57, AB59, AB60, AB67, AB77, AB80 and AB81.

Caveats:
- **Rare signs.** For rare signs, the font characters were also added to the classifier's
  training set (`la.cropsplus`), so the "all signs" font figures flatter it. The 20 most
  common signs never had font characters added.
- **Real sketches.** Real hand sketches should be measured once the team has drawn some.
  Add PNGs to `backend/tests/fixtures/sketches/<sign>-<n>.png` and extend the script.
- **Which scoring.** The classifier alone does better on font characters across all signs
  (64.7% top-5, against the blend's 60.6%). The blend is kept because it does best on the
  sketch-like tracings, which are closer to a real hand-drawn sketch.
