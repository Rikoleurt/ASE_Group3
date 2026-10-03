# ASE Group 3 — FastAPI and MySQL

The Python import root is this repository (`ASE_Group3`), not `backend`.
Run all commands below from the repository root. Python 3.12+ and Docker Compose
are required; Docker Desktop must be running when using Docker.

## Architecture

```text
backend/
├── __init__.py
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── model/user.py
│   ├── data_controller/
│   │   ├── data_controller.py
│   │   └── user_data_controller.py
│   ├── routes/user_routes.py
│   └── database/init.sql
├── tests/
└── pyproject.toml
```

Imports use `backend.app...`. Routes handle HTTP requests and responses; data
controllers handle authentication, parameterized SQL, connections and transactions.
MySQL enforces uniqueness on `user.email`. Emails are normalized to lowercase.
Passwords are stored as salted PBKDF2-HMAC-SHA256 hashes (600,000 iterations).
API responses never include the password or its hash.

## Install and configure

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

Edit `.env` if needed, then export it in the terminal used to run FastAPI:

```bash
set -a
source .env
set +a
```

The application reads `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`
and `MYSQL_DATABASE`. Defaults are `127.0.0.1`, `3306`, `ase`, `ase`, and `ase`.
Compose also reads `.env` and uses `MYSQL_ROOT_PASSWORD` (default `root`).
These default credentials and the seeded account are for local development.
FastAPI does not load `.env` automatically; export it as above.

## Start MySQL and FastAPI

```bash
docker compose up -d --wait mysql
uvicorn backend.app.main:app --reload
```

If ports 3306 or 8000 are occupied, use another port without stopping existing
services (set `MYSQL_PORT=3307` in `.env` to keep this choice):

```bash
export MYSQL_PORT=3307
docker compose up -d --wait mysql
uvicorn backend.app.main:app --reload --port 8001
```

OpenAPI documentation: http://127.0.0.1:8000/docs. Health check: `/health`.
Importing the application or calling `/health` does not require a database connection.

Alternatively, with uv, keep the same working directory:

```bash
uv sync --project backend
uv run --project backend uvicorn backend.app.main:app --reload
```

`npm run dev:backend` uses this uv command; `npm run dev` also starts the frontend.
The frontend requires Node `^22.18.0 || >=24.12.0`.

## Database initialization

Compose mounts `backend/app/database/init.sql`. It creates the `user` table
(`id`, `email`, `password`) and the initial account `dev@ase3.com` / `dev`.
The SQL seed contains only a password hash. The SQL runs in the database selected
by `MYSQL_DATABASE`, so changing its name works on a fresh volume.

Initialization scripts and creation variables apply only to an empty MySQL data
directory; an existing volume is preserved (see the
[official MySQL image documentation](https://hub.docker.com/_/mysql)).
To apply the schema and seed to an existing Compose database without deleting data:

```bash
docker compose exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_PASSWORD" mysql -u "$MYSQL_USER" "$MYSQL_DATABASE"' < backend/app/database/init.sql
```

The script is idempotent and does not overwrite an existing user's password.
For a local MySQL server, create the database and database user first, then run
`mysql -h 127.0.0.1 -u ase -p ase < backend/app/database/init.sql` (adapt the names).

## API

Both routes accept JSON with `email` and `password`:

```bash
curl -X POST http://127.0.0.1:8000/users/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"student@ase3.com","password":"my-password"}'

curl -X POST http://127.0.0.1:8000/users/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"dev@ase3.com","password":"dev"}'
```

Registration returns `201` with `{ "id": 2, "email": "student@ase3.com" }`
(the ID is generated), or `409` for a duplicate email. Login returns `200` with
`{ "authenticated": true, "user": { "id": 1, "email": "dev@ase3.com" } }`,
or `401` for incorrect credentials. Invalid input returns `422`.
Login validates credentials; it does not issue a session or JWT.

## Tests

```bash
python -m pytest backend/tests -q
RUN_MYSQL_TESTS=1 python -m pytest backend/tests -q
```

The first command tests routes, real controllers, hashing and SQL using a mocked
MySQL connection. The second also exercises a running, initialized MySQL database;
it creates a uniquely named test account and deletes only that account afterward.
With uv, replace `python` by `uv run --project backend python`.

The independent fraction solver needs its own scientific dependencies:

```bash
uv run --project backend --with numpy --with scipy --with pillow --with sympy python -m pytest fraction-solver/tests -q
npm --prefix frontend run test:unit -- --run
```
