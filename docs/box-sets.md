# Corrected copies of a tablet's boxes (#83)

A user corrects the reader's boxes on a **copy**: move, resize, draw and delete boxes, and
name each box's sign. The analysis itself never changes. Each user has one copy per upload
and one per corpus tablet (#82). A copy is private until its owner shares it (see Sharing).

## Setup

For a database created before this feature, apply the migrations in order (#93's 060/061 keep
the uploaded images; all can be run again safely):

```bash
mysql -h 127.0.0.1 -P 3306 -u YOUR_MYSQL_USER -p ase3 < backend/app/database/migration-60/060-migration.sql
mysql -h 127.0.0.1 -P 3306 -u YOUR_MYSQL_USER -p ase3 < backend/app/database/migration-60/061-community.sql
mysql -h 127.0.0.1 -P 3306 -u YOUR_MYSQL_USER -p ase3 < backend/app/database/migration-83/083_box_sets.sql
mysql -h 127.0.0.1 -P 3306 -u YOUR_MYSQL_USER -p ase3 < backend/app/database/migration-84/084_box_set_sharing.sql
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
| `POST /box-sets` `{tablet, start}` | the same for a corpus tablet, starting from the model's boxes (`start: "model"`, the default) or the scholars' (`"scholar"`). A later request returns the existing copy, whatever its start |
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
| `GET /tablets/{slug}/boxes?source=scholar\|model` | the boxes and their reading, in an analysis's shape |

The scholars' boxes come from the training annotations (`fraction-solver/out/yolo_signs/annotations.json`,
loaded by the glyph index). The model's are read from the tracing the first time they are asked
for (about 20 s on a laptop CPU) and kept in memory per tablet and model version. A scholar's box
counts as 100% confident and has no model guesses. A tablet copy's image is the tracing.

## Sharing (#84)

The owner shares a copy with named people, or with everyone logged in, at a level. Each level
includes the ones above it:

| Level | May |
|---|---|
| View | see the copy, its change log and its image |
| Comment | also comment on boxes (#86) |
| Edit | also save changes and undo them |
| Manage | also share the copy, and change or revoke others' access |
| Owner | also delete the copy. Nobody can change the owner's access |

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

## The reading

Every response carries `reading`: the lines, transliteration and fraction formulas worked
out from the copy's boxes by the same code as an analysis (`read_signs`). A sign's `id` is
its box's id. A box the model read and the user left alone keeps the model's confidence; a
box the user drew or named counts as 100%.
