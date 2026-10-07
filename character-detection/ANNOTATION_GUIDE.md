# Annotation guide

Rules for photographing and annotating the character detection dataset. Every image must follow the same rules: inconsistent boxes hurt the model more than missing data.

## Scope

- **Printed** characters only: digits `0–9` and Latin letters `a–z`, `A–Z`.
- One class: **`character`**. We only mark *where* a character is, not *which* one.
- Not annotated: punctuation, symbols (`@ € % & …`), handwriting, drawings, stylised lettering.

## Boxes

1. **One box per character.** `10` is two boxes, `Hello` is five.
2. **Tight fit.** Each edge of the box touches the outermost ink of the glyph, with no margin. Zoom in for small characters.
3. **The whole glyph, nothing else.**
   - Include the dot of `i` and `j`, and the descender of `g p q y`.
   - Include accents (`é`, `ç`): the accent is part of the character.
   - Exclude underlines, table borders and the lines of the paper.
4. **Overlapping boxes are fine** when characters overlap in italic or tight fonts. Never merge two characters into one box.
5. **Ligatures** (`fi`, `fl` in some fonts): one box per letter if the letters can be told apart, otherwise one box for the ligature. Prefer fonts and texts without ligatures.

## Hard cases

| Case | Rule |
|---|---|
| Character cut by the image edge | Annotate if more than half of it is visible, box only the visible part |
| Character partly hidden (finger, object) | Same rule: more than half visible → annotate the visible part |
| Vertical or rotated text (e.g. a side banner) | Annotate normally: one upright box per character, enclosing the whole rotated glyph |
| Too small or too blurry to read | Do not annotate. If you cannot read it, the model should not be asked to |
| Plain readable text in a logo (e.g. a ministry name) | Annotate |
| Stylised or unreadable lettering in a logo or picture | Do not annotate |
| Text showing through from another page, mirrored or not | Do not annotate: it is not printed on this page |
| Unsure | Annotate it the way you would want the model to answer, and note the file name in `data/notes.md` |

## Photos

**Target:** about 60 photos taken from about 20 different sheets, with roughly 20–60 characters per photo. More photos can be added later where the model fails.

**Frame a zone, not the whole page.** A full page holds hundreds of characters: too long to annotate, and body text becomes a few pixels tall once the photo is resized. Photograph a title block, a table or a few lines instead, close enough that the smallest characters are easy to read. One document can give 4–5 photos this way.

Sheets do not need to contain only text. Icons, drawings and decorations are useful: they show the model what is *not* a character.

**Vary** each of these across the set:
- source: printed pages, books, magazines, packaging, labels, signs;
- font: serif, sans serif, bold, italic, monospace;
- character size and density: from a single large character to dense text;
- lighting: daylight, lamp, shadow on part of the page;
- angle and distance: straight on, tilted, close, far;
- background: white paper, coloured paper, cardboard.

**Avoid:**
- several photos of a sheet that are nearly identical: change the angle, light or framing between shots;
- personal information (addresses, names, documents).

## File naming

```
sheet<NN>_<MM>.jpg      e.g. sheet07_03.jpg = third photo of sheet 7
```

All zones photographed from the same document share its sheet number. The sheet number lets us keep every photo of a sheet in the same split (train, val or test). Two photos of the same sheet in train and test would inflate the scores.

Put photos in `data/originals/`: a framed zone as `sheetNN_MM`, a whole page as `sheetNN` (the script cuts it into tiles numbered `_01` to `_12`). They are converted and resized by `scripts/prepare_images.py`.

## Label Studio configuration

Project type: *Object Detection with Bounding Boxes*, with this labeling interface:

```xml
<View>
  <Image name="image" value="$image" zoom="true"/>
  <RectangleLabels name="label" toName="image">
    <Label value="character"/>
  </RectangleLabels>
</View>
```

Export in **YOLO** format.
