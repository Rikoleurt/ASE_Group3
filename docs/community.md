# Community discussions

New analyses retain their uploaded PNG/JPEG privately on disk. Their immutable
model result and image reference are stored in MySQL. Sharing publishes either
the whole tablet or a selected symbol in a discussion; it does not rerun inference. Existing
history comments remain private and are never copied into the public thread.

## Database setup

A fresh database uses `backend/app/database/init.sql`, including the private
comments and community tables. For an existing database, apply these scripts in
order (migration 17 must already be installed):

```bash
docker compose exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot "$MYSQL_DATABASE"' < backend/app/database/migration-60/060-migration.sql
docker compose exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot "$MYSQL_DATABASE"' < backend/app/database/migration-60/061-community.sql
docker compose exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot "$MYSQL_DATABASE"' < backend/app/database/migration-60/074-symbol-discussions.sql
```

Scripts 060 and 061 can be run again without deleting existing records. Run 074
**once**, only on a database using the old community schema (not after a fresh
`init.sql`). It reports duplicate titles and atomically replaces the old unique
analysis index with unique discussion targets and titles. If existing titles
collide, the ALTER fails without changing the table: rename the conflicting
titles intentionally before retrying. It never deletes discussions or comments.
Do not delete the MySQL volume to apply a migration. Old analyses have no `analysis_image`
record: their pixels were never retained, so users must upload and analyze them
again before sharing. Existing private notes stay in `analysis_comment`.

## Image storage

`TABLET_STORAGE_DIR` defaults to `storage/tablets/` at the repository root.
Use an absolute path on a persistent, writable volume for deployment. The backend
currently runs on the host, so the MySQL Docker volume does **not** store images.
If the API is containerized, mount the image directory into that container and
set `TABLET_STORAGE_DIR` to the mount path. Back up and restore this directory
along with MySQL. Never expose it as a public static directory.

Files use generated UUID names and are only served after an API lookup. Upload
size/type/dimension validation remains in place. The analysis and its image
reference commit together; a failed database save removes the newly written file.
Disk-write failures return 503 instead of reporting a saved analysis. A process
crash or a manual database deletion can leave an unreferenced file; automatic
retention/garbage collection is not part of this first version.

## API

Paths below are backend paths; the frontend uses the `/api` proxy prefix.

| Method | Route | Access and result |
| --- | --- | --- |
| GET | `/analysis/{analysis_id}/image` | Owner only; private image |
| POST | `/community/discussions` | Session + CSRF; `{analysis_id, title, sign_id?}`; owner only |
| GET | `/community/discussions?limit=20&before=ID` | Public; `{items, next_before}`, newest first |
| GET | `/community/discussions/{id}` | Public; author, title, date, image URL, tablet ancestry, saved result or selected symbol |
| GET | `/community/discussions/{id}/image` | Public tablet image or PNG crop of the shared symbol |
| GET | `/community/discussions/{id}/comments` | Public; complete thread in chronological order |
| POST | `/community/discussions/{id}/comments` | Session + CSRF; `{body}`; any logged-in user |

Titles are 1–160 characters after trimming and unique across **all** discussions.
The database compares trimmed titles case-insensitively but accent-sensitively
(`utf8mb4_0900_as_ci`). A collision returns 409 with a message asking for another
title, including when two different analyses are shared concurrently. Reopening
an already shared target returns its existing thread rather than creating or
renaming a discussion.

Comments are 1–2000 characters. Analysis/discussion IDs are positive
integers; detection IDs may also be zero. Timestamps are UTC, and authors come
from the server session. Only
usernames and IDs are public, never account email addresses. Comments render as
plain text. POSTs require `X-CSRF-Token` from the current session.

Sharing returns 201 with the discussion ID, or 200 with the existing discussion
when already shared. A generated target key and an ownership lock allow one
general discussion per analysis and one discussion per detected occurrence,
including concurrent requests.
`sign_id` is the occurrence ID within the saved analysis, not the glyph catalogue
ID. A null/omitted `sign_id` targets the entire tablet. Missing/foreign analyses
and missing occurrences return 404; analyses without an available saved image
return 409. Failed storage
requests return 503. Invalid input returns 422.

## Symbol discussions and tablet tree

The UI offers sharing after analysis, from history for records with an image,
and from the general discussion of a tablet shared by the signed-in user.
Hover or focus a detection box and choose **Open discussion**. The card stays
reachable across the gap; Tab reaches its button, Shift+Tab returns to the box,
and Tab from the button proceeds to the next box. Touch users can tap a box.
The dialog pre-fills an editable title using the model reading (then label or
catalogue ID). An unidentified symbol defaults to `symbol-{id}`. Publication is
explicit; a title conflict keeps the draft editable. Success navigates to the
new or existing thread.

The server resolves the occurrence from the immutable saved result and crops the
retained image using its normalized box, clipping to image boundaries. The client
cannot submit replacement coordinates. Crops are generated as PNG on demand and
are not stored in files or a new table. Sharing just a symbol exposes only that
symbol's pixels and reading, the author's username and the tablet filename; it
does not expose the full tablet image or unrelated predictions.

Each detail response includes `tablet_filename`, optional `symbol_name` and
`symbol`, optional `parent_discussion`, and `symbol_discussions`. A symbol thread
omits `result`; a general tablet thread retains the existing full analysis. The
page shows who created a discussion about which symbol from which tablet,
independently of the custom discussion title. The tree links to the tablet's
general discussion and all its shared symbol threads. The parent is resolved
through the analysis ID, so it also appears if shared later. Sharing a symbol
never creates a general discussion automatically. The history's `discussion_id`
continues to refer only to the general discussion.

Community is readable without login; posting requires login. Comments append on
successful submission. Reload the discussion to see comments posted by others;
this version has no live updates, nested replies, or public comment editing.

## Validation

```bash
backend/.venv/bin/python -m pytest backend/tests/test_community.py backend/tests/test_symbol_discussions.py backend/tests/test_history.py backend/tests/test_api_contract.py -q
RUN_MYSQL_TESTS=1 backend/.venv/bin/python -m pytest backend/tests/test_community_mysql.py -q
npm --prefix frontend run test:unit -- --run Community TabletOverlay SignCard AnalysisView History ApiContract
```

Use a dedicated initialized MySQL database for integration tests. The community
test checks public reads, private images, two authors, CSRF, thread separation,
concurrent sharing, old analyses, and repeatable migration without data loss.

The symbol extension adds coverage for crop pixels and boundaries, title
collisions and concurrent publication, unknown/foreign occurrences, ancestry
with a parent created later, keyboard access, and editable default titles.
On 24 November 2026, the targeted backend tests above passed (50 tests), and
the targeted frontend tests passed (71 tests), including publication from the
owner's general tablet discussion. The frontend test simulates the native
`dialog.showModal()` operation because jsdom does not implement it.
MySQL integration tests, lint and builds were not run. No migration was applied
by the agent.
