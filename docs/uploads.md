# Kept uploads (#81)

Each analysis keeps the image it was run on, so it can be reopened from history with
its boxes, and later corrected and shared (#83, #84).

## Where files go

Files are written under `UPLOAD_DIR` (default `var/uploads` in the repository, which
git ignores) as `<key[:2]>/<key>.png` or `.jpg`. The key is 32 random hex characters;
the user's filename is never part of the path. A deployment should point `UPLOAD_DIR`
at a mounted volume, so uploads survive a redeploy, and back that folder up together
with the database.

The `uploaded_image` table keeps each file's owner, key, SHA-256, format, size and
dimensions; `analysis.image_id` links an analysis to it. Analyses saved before this
feature have no image (`image_id` is NULL, `has_image` is false) and still open.

For an existing database, apply the migration once (safe to run again):

```bash
mysql -h 127.0.0.1 -P 3306 -u YOUR_MYSQL_USER -p ase3 < backend/app/database/migration-81/081_uploaded_image.sql
```

## Saving

`POST /analysis` writes the file first, then the image record and the analysis in one
database transaction. If the database refuses, or anything else fails, the file is
deleted again, so there are no records without files and no files without records.
A disk that refuses the file returns 503 and saves nothing.

## Reading

`GET /analysis/{id}/image` returns the image to the analysis's owner (sharing comes in
#84). Everyone else, analyses without an image, and files removed by hand get 404.
Responses are never cached (`Cache-Control: no-store`), since access can be revoked.
History rows and details carry `has_image`.

## Not handled yet

- Deleting an account deletes its records (`ON DELETE CASCADE`) but not its files.
  A cleanup that removes files no record points to is left for later.
