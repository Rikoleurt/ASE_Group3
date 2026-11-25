# Admin and reviewer roles (#80)

Two roles sit on each account, both off by default:

| Role | Lets the user | Set by |
|---|---|---|
| Admin | open the **Admin** page, grant and remove roles, export corrections for training (#87) | another admin, or SQL for the first one |
| Reviewer | approve or reject sign corrections on the **Review** page | an admin, or `SIGN_REVIEWERS` in `.env` |

The seeded `dev` account is both. The API checks the role on every request; the
frontend only hides links the API would refuse.

## Setup

For a database created before this feature, apply the migration once. It is safe to
run again, and it makes `dev` an admin and a reviewer:

```bash
mysql -h 127.0.0.1 -P 3306 -u YOUR_MYSQL_USER -p ase3 < backend/app/database/migration-80/080_user_roles.sql
```

To make the first admin on a deployment without `dev`:

```sql
UPDATE `user` SET is_admin = TRUE WHERE username = 'their-username';
```

From then on, admins manage roles on the **Admin** page.

## Rules

- An admin cannot remove their own admin role, and nobody can remove the last admin's
  (409): the site always keeps one.
- Users named in `SIGN_REVIEWERS` are reviewers whatever their role says. The admin
  page shows them as reviewers and explains why the box is locked.
- Role changes apply on the user's next request; no new login is needed.

## API

| Route | Who | Does |
|---|---|---|
| `GET /admin/users?q=&limit=&offset=` | admins | users whose username or email contains `q` (literally, `%` and `_` included), by username, 50 per page, with the total |
| `PATCH /admin/users/{id}` | admins, with the CSRF token | sets `admin`, `reviewer` or both; a missing role is left as it is |

`/users/me` and the login response carry `admin` and `reviewer` flags beside the
user; the user object itself is unchanged.

Errors: 401 when logged out, 403 for non-admins or a missing CSRF token, 404 for an
unknown user, 409 when removing your own admin role, 422 for a body with no role,
503 when the database is unavailable.

## Training export (#87)

The **Admin** page's *Training data* section downloads every user's corrected boxes (#83), with
the sign corrections reviewers approved (#52), to train the reader on:

| Route | Gives |
|---|---|
| `GET /admin/export/corrections` | JSON in the training annotations' shape: per copy its image size and each box's sign, pixel `xyxy`, where it came from (`model`, `scholar`, `user`), whether the user changed it, and the original sign; then `label_corrections`, #52's approved export |
| `GET /admin/export/corrections.zip` | a YOLO dataset: `images/copy-<id>.png\|jpg`, `labels/copy-<id>.txt` (`class cx cy w h`), `classes.txt` and the JSON as `corrections.json` |

By default only copies whose owner is an admin or a reviewer are exported: anyone can register
and correct boxes, so other users' copies are not vetted. `?everyone=true` (the *Include copies by
all users* box) adds them; every copy carries `owner_trusted`. Both are admins only (403 for everyone else).
The zip is written to a temporary file and streamed, then deleted. Deleted boxes are left out. Boxes with no sign stay
in the JSON (sign null) but cannot be YOLO labels; the zip counts them in
`corrections.json` (`unnamed_boxes_left_out`). A copy whose image is missing on the server is
listed under `missing_images` and left out of the zip's images and labels. Owners appear only as
account numbers. The editor tells users that corrections may be used for training.
