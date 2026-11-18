# Corrected copies of a tablet's boxes (#83)

A user corrects the reader's boxes on a **copy**: move, resize, draw and delete boxes, and
name each box's sign. The analysis itself never changes. Each user has one copy per upload
(and, from #82, per corpus tablet). Until sharing lands (#84) a copy is its owner's only;
everyone else gets 404, as with history.

## Setup

For a database created before this feature, apply the migrations in order (both can be
run again safely):

```bash
mysql -h 127.0.0.1 -P 3306 -u YOUR_MYSQL_USER -p ase3 < backend/app/database/migration-81/081_uploaded_image.sql
mysql -h 127.0.0.1 -P 3306 -u YOUR_MYSQL_USER -p ase3 < backend/app/database/migration-83/083_box_sets.sql
```

## Tables

| Table | Holds |
|---|---|
| `box_set` | the copy: owner, the analysis (or corpus tablet) it copies, where it started (model or scholars), its `version`, image size |
| `box` | each box as a fraction of the image, its sign, where it came from (model, scholar, user), and the model's original box, sign, confidence and top guesses. A deleted box stays, marked `deleted`, so it can be brought back |
| `box_change` | every change: who, when, the version it made, the box before and after (`{box, sign, deleted}`), and which change it undid or was undone by |

## API

| Route | Does |
|---|---|
| `POST /box-sets` `{analysis_id}` | opens your copy of your analysis, making it from the model's boxes the first time (201; 200 if it existed) |
| `GET /analysis/{id}/box-set` | your copy of that analysis, or 404 |
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

## The reading

Every response carries `reading`: the lines, transliteration and fraction formulas worked
out from the copy's boxes by the same code as an analysis (`read_signs`). A sign's `id` is
its box's id. A box the model read and the user left alone keeps the model's confidence; a
box the user drew or named counts as 100%.
