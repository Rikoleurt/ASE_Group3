# Corrected copies of a tablet's boxes (#83)

A user corrects the reader's boxes on a **copy**: move, resize, draw and delete boxes, and
name each box's sign. The analysis itself never changes. Each user has one copy per upload,
and any number of copies of a corpus tablet (#82; several since the scholars' workbench), each
with an optional title. A copy is private until its owner shares it (see Sharing).

## Setup

For a database created before this feature, apply the migrations in order (#93's 060/061 keep
the uploaded images; all can be run again safely):

```bash
mysql -h 127.0.0.1 -P 3306 -u YOUR_MYSQL_USER -p ase3 < backend/app/database/migration-60/060-migration.sql
mysql -h 127.0.0.1 -P 3306 -u YOUR_MYSQL_USER -p ase3 < backend/app/database/migration-60/061-community.sql
mysql -h 127.0.0.1 -P 3306 -u YOUR_MYSQL_USER -p ase3 < backend/app/database/migration-83/083_box_sets.sql
mysql -h 127.0.0.1 -P 3306 -u YOUR_MYSQL_USER -p ase3 < backend/app/database/migration-84/084_box_set_sharing.sql
mysql -h 127.0.0.1 -P 3306 -u YOUR_MYSQL_USER -p ase3 < backend/app/database/migration-86/086_box_comments.sql
mysql -h 127.0.0.1 -P 3306 -u YOUR_MYSQL_USER -p ase3 < backend/app/database/migration-workbench/201_box_set_versions.sql
mysql -h 127.0.0.1 -P 3306 -u YOUR_MYSQL_USER -p ase3 < backend/app/database/migration-workbench/202_box_set_editions.sql
mysql -h 127.0.0.1 -P 3306 -u YOUR_MYSQL_USER -p ase3 < backend/app/database/migration-workbench/203_edition_releases_votes.sql
mysql -h 127.0.0.1 -P 3306 -u YOUR_MYSQL_USER -p ase3 < backend/app/database/migration-workbench/204_glyph_seen.sql
mysql -h 127.0.0.1 -P 3306 -u YOUR_MYSQL_USER -p ase3 < backend/app/database/migration-workbench/205_box_marks.sql
mysql -h 127.0.0.1 -P 3306 -u YOUR_MYSQL_USER -p ase3 < backend/app/database/migration-workbench/206_tablet_bookmarks.sql
```

## Tables

| Table | Holds |
|---|---|
| `box_set` | the copy: owner, the analysis (or corpus tablet) it copies, where it started (model or scholars), its `version`, image size |
| `box` | each box as a fraction of the image, its sign, where it came from (model, scholar, user), and the model's original box, sign, confidence and top guesses. A deleted box stays, marked `deleted`, so it can be brought back |
| `box_change` | every change: who, when, the version it made, the box before and after (`{box, sign, deleted}`), and which change it undid or was undone by |

## Versions of a tablet, and comparing them (workbench)

A corpus tablet's **versions** are the scholars' published boxes, the model's, and every copy
of it you can open: yours, and others' shared with you or with everyone.

- **The Tablets page lists them.** Tick two to six of them and **Compare**.
- **The compare page** (`/tablets/HT-13/compare?v=scholar&v=copy:4`) matches their boxes into
  *places* (`backend/app/box_matching.py`):
  - boxes overlapping at least 40% (intersection over union) are one place, with one box per
    version at most;
  - each place *agrees*, has *different signs*, or is *missing* from some versions;
  - it is flagged when its boxes overlap less than 80%, i.e. they sit in different places;
  - places are listed in reading order, with how often each pair of versions agrees.
- **Colours.** Each version has its own colour (Okabe-Ito, distinguishable with colour-vision
  deficiencies). Boxes in the same place are drawn nested, so every colour stays visible.

Each box also records where it came from (`source_kind`, `source_box_id`): the scholars' or the
model's sign it started as. Merged editions (story D) add another copy's box at a version
(`source_set_id`, `source_version`) and its author (`source_author_id`), who is credited.

## Epigraphic marks and reading order (workbench)

Each box can carry marks in GORILA/SigLA conventions, set in the editor's box panel. They are
saved, shown in the history and undone like any other change, and kept in merges and releases.

| Mark | Choices | In the transliteration |
|---|---|---|
| Reading | certain, uncertain (shortcut **U**), illegible | uncertain signs dotted under (ḳụ); illegible as • |
| Preservation | whole, partly preserved, lost and restored | ⸢ku⸣ for partly preserved; [ku] for restored |
| Word end | after this sign (shortcut **W**) | the word ends here, wherever the gap |
| Other possible readings | up to five catalogue signs | listed on the box |

**Reading order.** It is worked out from the layout unless a scholar sets it by hand:

1. Click **Reading order**, then the boxes in order; **New line** starts the next line.
2. **Done** keeps the order; **Use the automatic order** removes it.

Boxes left out of a hand-set order follow it, in the automatic order.

The marks are stored as JSON in `box.marks` (migration
`migration-workbench/205_box_marks.sql`). Changes saved before them read as no marks.

## Working comfortably in the editor (workbench)

- **Zoom and pan.**
  - Zoom with the − / + / Fit buttons, Ctrl + wheel (a trackpad pinch arrives as this), or the
    keys + − 0. Zoom goes up to 800% and keeps the point under the cursor in place.
  - Pan by scrolling, or by dragging with the space bar held or the middle button.
  - The editor is widened inside a scrolling frame rather than transformed, so boxes, handles
    and badges stay exactly where they belong.
- **Invert and More contrast** change how the drawing is shown, never the image.
- **Shortcuts**, listed with **?**:
  - N / P: next / previous box in reading order;
  - V / D: select and move / draw a box;
  - 1–5: name the selected box with the model's guess;
  - U / W: uncertain / word end;
  - arrows (with Shift to resize), Delete, Ctrl+Z, Ctrl+S.

  Shortcuts do nothing while you type in a field.
- **Bookmarks.** ☆ beside a tablet's name bookmarks it (`tablet_bookmark`, migration
  `migration-workbench/206_tablet_bookmarks.sql`; `GET /bookmarks`,
  `PUT` / `DELETE /bookmarks/{slug}`, at most 200).
- **Recent tablets.** Bookmarked and recently opened tablets (the last 8, remembered in this
  browser) are listed first on the Tablets page.

## Merging versions into an edition (workbench)

From the versions list (or the compare page), **Merge into an edition** opens
`/tablets/HT-13/merge?v=…`. The page lists the same places as compare and asks, place by place,
whose box to keep, or to leave the place out.

- **Defaults:** the sign most versions agree on. Between equally common signs, the scholars'
  sign wins if they have one there, otherwise the earliest version's.
- **What is shown:** only the places where the versions differ are listed at first, as
  agreeing places need no choice.
- **Bulk choices:** "Majority everywhere", and "Take every box from" one version.

`POST /box-sets/merge` creates the edition (`kind: "edition"`), a new copy of your own:

- **No trusted geometry:** the server rebuilds the places from the versions as they are now,
  and never takes a box's position from the page.
- **Stale versions:** a copy whose version changed since the page loaded is refused with 409,
  as is a different number of places. The page then offers a reload.
- **Credit:** each box keeps its source, the copy and version it came from and that copy's
  owner. The edition lists what it was merged from (`merged_from`) and its `contributors`:
  authors of merged boxes and everyone who saved a change.
- **Afterwards:** the edition opens in the normal editor (history, comments, sharing).

Migration: `migration-workbench/202_box_set_editions.sql`.

Releasing editions, voting on them and the community edition are described in [editions.md](editions.md).

## API

| Route | Does |
|---|---|
| `POST /box-sets` `{analysis_id}` | opens your copy of your analysis, making it from the model's boxes the first time (201; 200 if it existed) |
| `POST /box-sets` `{tablet, start}` | the same for a corpus tablet, starting from the model's boxes (`start: "model"`, the default) or the scholars' (`"scholar"`). A later request returns your most recently changed copy, whatever its start |
| `POST /box-sets` `{tablet, start, new: true, title?}` | another copy of the tablet, with an optional title (up to 120 characters) |
| `GET /tablets/{slug}/versions` | the scholars', the model's and the copies you can open (logged out: the first two) |
| `GET /tablets/{slug}/compare?v=…&v=…` | two to six versions (`scholar`, `model`, `copy:<id>`) matched into places, with agreement per pair (login needed) |
| `POST /box-sets/merge` `{tablet, title?, sources: [{key, version?}], picks: [key or null per place]}` | a new edition merged from 2 to 6 versions (201); 409 if a version changed since the merge page loaded |
| `GET /analysis/{id}/box-set`, `GET /tablets/{slug}/box-set` | your copy of that analysis or tablet, or 404 |
| `GET /box-sets/{id}` | the copy, with its boxes and the reading worked out from them |
| `PATCH /box-sets/{id}` `{version, changes}` | one save, all or nothing (see below) |
| `GET /box-sets/{id}/changes?limit=&before=` | the change log, newest first, paged backwards |
| `POST /box-sets/{id}/changes/{change}/revert` `{version}` | undoes one change |
| `GET /box-sets/{id}/image` | the image the boxes are drawn on, never cached |
| `DELETE /box-sets/{id}` | throws the copy and its log away; the analysis stays |

Writes need the CSRF token, like every other write.

### Saving

A save lists changes in order:

```json
{"version": 3, "changes": [
  {"op": "add", "box": {"x": 0.5, "y": 0.2, "w": 0.04, "h": 0.05}, "sign": "AB81"},
  {"op": "update", "box_id": 12, "box": {"x": 0.11, "y": 0.2, "w": 0.04, "h": 0.05}},
  {"op": "update", "box_id": 13, "sign": "A707"},
  {"op": "update", "box_id": 14, "sign": null},
  {"op": "delete", "box_id": 15}
]}
```

- `update` changes only the fields it gives; `sign: null` clears the sign.
- Boxes must lie inside the image and be at least 0.002 of its size on each side.
- Signs must be in the catalogue (`GET /corrections/catalogue`) and are stored as it spells
  them (`ab2` becomes `AB02`).
- At most 500 changes per save and 2000 boxes per copy.
- Changes that alter nothing are skipped; a save that alters nothing keeps the version.
- `version` must be the copy's current version. If someone else saved in between, the save
  is refused with **409** and the current copy, so the editor can reload. Nothing is written.
- An unknown box or sign is **422**, and nothing is written.

### Undo

Undoing a change puts its box back as the change found it: an added box is deleted again,
a deleted one comes back. It is itself recorded as a change (`revert`). It is refused with
422 when the change was already undone, or when the box was changed again since (undo the
later change first), since undoing it would silently throw the later change away.

## Corpus tablets (#82)

The **Tablets** page lists every corpus tablet with published boxes and shows its tracing with
either set of boxes. These routes are public; the data is CC BY-NC-SA and every response
carries the credit line.

| Route | Does |
|---|---|
| `GET /tablets?q=&limit=&offset=` | tablets with published boxes; `q` matches the id loosely (`ht13`, `HT 13`, `HT-13`) |
| `GET /tablets/{slug}/image` | the full tracing |
| `GET /tablets/{slug}/boxes?source=scholar\|model` | the boxes and their reading, in an analysis's shape; the model's need a login |

The scholars' boxes come from the training annotations (`fraction-solver/out/yolo_signs/annotations.json`,
loaded by the glyph index). The model's are read from the tracing the first time they are asked
for (about 20 s on a laptop CPU) and kept in memory per tablet and model version, for the whole
corpus. Reading runs one tablet at a time: a request that finds the reader busy gets 503 ("try
again in a moment") instead of waiting, so a burst of requests cannot tie up the server. A scholar's box
counts as 100% confident and has no model guesses. A tablet copy's image is the tracing.

## Sharing (#84)

The owner shares a copy with named people, or with everyone logged in, at a level. Each level
includes the ones above it:

| Level | May |
|---|---|
| View | see the copy, its change log and its image |
| Comment | also comment on boxes (#86) |
| Edit | also save changes and undo them |
| Manage | also share the copy, and change or revoke others' access, except Manage itself |
| Owner | also give, change or take away Manage, and delete the copy. Nobody can change the owner's access |

A user's level is the higher of their own share and the copy's level for everyone logged in
(`box_set.everyone`: none, view, comment or edit; never manage). The rules are in
`backend/app/sharing.py`. Someone who may not see a copy gets **404**, so its existence does not
leak; someone who may see it but not do this gets **403** with the reason. Every copy response
carries `permission` (your level) and `everyone`.

| Route | Who | Does |
|---|---|---|
| `GET /users/search?q=` | logged in | usernames starting with `q` (2+ characters, at most 10, never emails) |
| `GET /box-sets/{id}/shares` | manage | the people with access, and the everyone-level |
| `PUT /box-sets/{id}/shares/{user}` `{permission}` | manage | share with someone, or change their level (409 for the owner or yourself) |
| `DELETE /box-sets/{id}/shares/{user}` | manage, or that user | revoke access; anyone may leave a copy shared with them |
| `PUT /box-sets/{id}/everyone` `{permission}` | manage | the level for everyone logged in |
| `GET /users/me/shared-copies` | logged in | other people's copies you can open, newest change first |

A shared upload's image is reached through the copy (`/box-sets/{id}/image`), so revoking access
to the copy also revokes it to the image. The **Shared with me** page lists your shared copies;
the editor is read only below Edit, and owners and managers get a **Share** button.

## History and comments (#86)

The editor's **History** panel lists every saved change, newest first, one group per save, with
who made it and when ("Renamed AB81 (ku) to AB02 (ro)", "Moved and resized …", "Drew a box",
"Undid change 12"). Selecting a change selects its box and outlines, dashed, where the box was
before. People with Edit access can **Undo** a change (`POST …/changes/{id}/revert`); undone
changes are struck through. Undo saves at once, so it waits until unsaved edits are saved or
discarded. The panel filters by person and by the selected box.

**Comments** sit beside it: the selected box's thread, or the whole copy's thread when no box is
selected. Anyone who can see the copy reads them; Comment access writes them. Plain text, 1 to
2000 characters after trimming; at most 10 a minute per person (429). Authors delete their own; the owner and managers can delete any.

| Route | Who | Does |
|---|---|---|
| `GET /box-sets/{id}/comments?box_id=&limit=` | view | the newest 500 (or `limit`), oldest first; `box_id` for one box's thread |
| `POST /box-sets/{id}/comments` `{box_id?, body}` | comment | `box_id` must be a box on the copy, or null for the copy |
| `DELETE /box-sets/{id}/comments/{comment}` | author, or manage | 403 for someone else's comment |

Comments live in `box_comment` (migration-86). Deleting a copy deletes its comments; deleting an
account keeps that person's comments, shown as by "Deleted account". #74's tablet and symbol discussions had
not landed, so these are separate; they can move onto #74's threads later.

## Training export (#87)

Admins export every copy's boxes for training: see [roles](roles.md#training-export-87).

## The reading

Every response carries `reading`: the lines, transliteration and fraction formulas worked
out from the copy's boxes by the same code as an analysis (`read_signs`). A sign's `id` is
its box's id. A box the model read and the user left alone keeps the model's confidence; a
box the user drew or named counts as 100%.
