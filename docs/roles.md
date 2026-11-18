# Admin and reviewer roles (#80)

Two roles sit on each account, both off by default:

| Role | Lets the user | Set by |
|---|---|---|
| Admin | open the **Admin** page, grant and remove roles | another admin, or SQL for the first one |
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

- An admin cannot remove their own admin role, so a site never loses its last admin
  by accident. Another admin can.
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
