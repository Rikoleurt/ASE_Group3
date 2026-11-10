# Community discussions

New analyses retain their uploaded PNG/JPEG privately on disk. Their immutable
model result and image reference are stored in MySQL. Sharing publishes that
image and result in a single discussion; it does not rerun inference. Existing
history comments remain private and are never copied into the public thread.

## Database setup

A fresh database uses `backend/app/database/init.sql`, including the private
comments and community tables. For an existing database, apply these scripts in
order (migration 17 must already be installed):

```bash
docker compose exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot "$MYSQL_DATABASE"' < backend/app/database/migration-60/060-migration.sql
docker compose exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot "$MYSQL_DATABASE"' < backend/app/database/migration-60/061-community.sql
```

Both scripts can be run again without deleting existing records. Do not delete
the MySQL volume to apply a migration. Old analyses have no `analysis_image`
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
| POST | `/community/discussions` | Session + CSRF; `{analysis_id, title}`; owner only |
| GET | `/community/discussions?limit=20&before=ID` | Public; `{items, next_before}`, newest first |
| GET | `/community/discussions/{id}` | Public; author, title, date, image URL, saved result |
| GET | `/community/discussions/{id}/image` | Public image of an explicitly shared analysis |
| GET | `/community/discussions/{id}/comments` | Public; complete thread in chronological order |
| POST | `/community/discussions/{id}/comments` | Session + CSRF; `{body}`; any logged-in user |

Titles are 1–160 characters after trimming; comments are 1–2000. IDs are positive
integers, timestamps are UTC, and authors come from the server session. Only
usernames and IDs are public, never account email addresses. Comments render as
plain text. POSTs require `X-CSRF-Token` from the current session.

Sharing returns 201 with the discussion ID, or 200 with the existing discussion
when already shared. A unique analysis constraint and an ownership lock prevent
duplicate discussions, including concurrent requests. Missing/foreign analyses
return 404; analyses without an available saved image return 409. Failed storage
requests return 503. Invalid input returns 422.

The UI offers sharing after analysis and from history for records with an image.
Community is readable without login; posting requires login. Comments append on
successful submission. Reload the discussion to see comments posted by others;
this version has no live updates, nested replies, or public comment editing.

## Validation

```bash
backend/.venv/bin/python -m pytest backend/tests -m 'not mysql' -q
RUN_MYSQL_TESTS=1 backend/.venv/bin/python -m pytest backend/tests -m mysql -q
npm --prefix frontend run test:unit -- --run
npm --prefix frontend run lint:check
npm --prefix frontend run build
```

Use a dedicated initialized MySQL database for integration tests. The community
test checks public reads, private images, two authors, CSRF, thread separation,
concurrent sharing, old analyses, and repeatable migration without data loss.
