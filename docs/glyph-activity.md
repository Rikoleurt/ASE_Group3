# Activity bubbles on glyphs

Part of the scholars' workbench (story I). Switch **Show activity on glyphs** on in the account
menu (it is remembered in this browser). A glyph of a corpus tablet then shows a bubble with how
much others have said or changed about it since you last opened it. Opening the glyph (selecting
it on a tablet, in the editor, or a place on the compare or merge page) clears its bubble.

The bubbles appear on the Tablets page (scholars' boxes), in the editor of a copy, and on the
compare and merge pages.

## What counts

A glyph is a sign of a corpus tablet, keyed by the tablet and its position in the scholars'
transcription. Its activity is read from what is already recorded, with its time:

- comments saved against it in the glyph pane;
- comments on, and saved changes to, a box that started as that scholars' sign, in any copy
  you can open (yours, shared with you, or open to everyone).

Your own comments and changes never count. A glyph you have never opened counts the last two
weeks.

When you open a glyph, the time is stored in `glyph_seen` (migration
`migration-workbench/204_glyph_seen.sql`).

## Not yet covered

These will come with notifications (Phase 2):

- boxes merged into an edition from another copy;
- signs of uploaded analyses;
- community discussions about a symbol.

## API

| Route | Does |
|---|---|
| `GET /tablets/{slug}/glyph-activity` | `{counts: {position: n}}` since you last opened each glyph (login needed) |
| `POST /glyphs/seen` `{tablet, position}` | you opened this glyph (204) |
