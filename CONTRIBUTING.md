# Contributing: tests and CI

Every pull request to `main`, and every push to `main`, runs
[.github/workflows/ci.yml](.github/workflows/ci.yml). This page explains what it
runs, how to run the same checks locally, and what to do when one fails.

CI uses **Node 22** and **Python 3.12**. Run every command below from the
repository root.

## Test tiers

| Tier | What it covers | Needs | Command |
| --- | --- | --- | --- |
| Backend unit and API | Routes, controllers, password hashing, upload handling, with the MySQL driver mocked | Nothing running | `uv run --project backend --no-sync python -m pytest backend/tests -m "not mysql"` |
| YOLO inference | Real CPU inference on HT13 and uploads with the generic `yolo26n.pt`, in the same run as the tier above | `yolo26n.pt` at the repo root | (included above) |
| Trained sign reader | The trained detector and classifier on HT13 and an uploaded tablet | `models/` from `python scripts/fetch_models.py` | (included above; skipped without the models) |
| API contract | `contract/openapi.json` matches the backend, and the frontend only calls endpoints and reads fields that exist in it | Nothing running | Backend: `backend/tests/test_api_contract.py`; frontend: `ApiContract.spec.js` |
| MySQL integration | Registration, login, uniqueness, profile fields and the seed account against a real database | MySQL initialized by `init.sql` | `RUN_MYSQL_TESTS=1 uv run --project backend --no-sync python -m pytest backend/tests -m mysql` |
| Frontend unit | Vue components and views, with `fetch` stubbed | Nothing running | `npm --prefix frontend run test:unit -- --run` |
| Research | `fraction-solver` on synthetic data | Nothing running | `uv run --project fraction-solver --no-sync python -m pytest fraction-solver/tests -ra` |
| Research, corpus | `test_parse.py` on real lineara.eu tablets | The cached corpus (`python -m la.cli fetch`) | (included above; skipped without the corpus) |

The corpus is CC BY-NC-SA and may not be redistributed, so CI never has it: the
corpus tests always show as skipped there. CI does not download the trained
models either, so their tests are skipped too. A green run does not mean these
tests ran; run them locally when you change the reader or the corpus code.

## Setup

```bash
npm ci
npm --prefix frontend ci
uv sync --project backend --locked --dev --extra cpu --python 3.12
uv sync --project fraction-solver --locked --dev --python 3.12
```

`--extra cpu` installs CPU-only PyTorch, as CI does (1.4 GB instead of 5.8 GB).
Leave it out if you train models on a GPU with this environment.

## Reproducing each CI job

**`frontend`**

```bash
npm --prefix frontend run lint:check
npm --prefix frontend run test:unit -- --run
npm --prefix frontend run build
```

`lint:check` reports problems without changing files; `npm run lint` fixes them.

**`backend`**

```bash
uv run --project backend --no-sync python -m pytest backend/tests -m "not mysql" -ra
docker compose up -d --wait mysql
RUN_MYSQL_TESTS=1 uv run --project backend --no-sync python -m pytest backend/tests -m mysql -ra
```

The MySQL tests create test accounts and delete them afterwards. They use the
`.env.example` defaults; if you changed `MYSQL_PORT` or the credentials in `.env`,
add `--env-file .env` after `uv run`.

**`research`**

```bash
uv run --project fraction-solver --no-sync python -m pytest fraction-solver/tests -ra
```

## Known bugs are tests that fail on purpose

A bug that is reported but not fixed yet gets a test that describes the correct
behaviour, marked as an expected failure with its issue number:

```python
@pytest.mark.xfail(reason="Known bug #27: DecompressionBombError is not caught and becomes a 500")
```

In Vitest, use `it.fails(...)` with a comment naming the issue.

These markers are strict. While the bug exists, the test fails and CI stays
green. When a change fixes the bug, the test passes, and CI **fails** with
`XPASS(strict)` (pytest) or a failing `it.fails` test (Vitest). That is the
signal to remove the marker in the same pull request as the fix, so the test
then guards against the bug coming back.

Current known bug: #27 (decompression-bomb uploads).

## When the API changes

`contract/openapi.json` is a snapshot of the backend's OpenAPI schema. If you
change a route or a response model on purpose, regenerate it and commit it with
your change:

```bash
UPDATE_API_CONTRACT=1 uv run --project backend --no-sync python -m pytest backend/tests/test_api_contract.py
```

The diff of that file shows reviewers exactly what changed in the API, and the
frontend contract tests then check that the frontend still matches it.

## Which jobs run

On a pull request, each job runs only when its area changed:

| Job | Runs when these change |
| --- | --- |
| `frontend` | `frontend/`, `package.json`, `package-lock.json`, `contract/` |
| `backend` | `backend/`, `contract/`, `fraction-solver/la/` (the backend imports it), `scripts/fetch_models.py`, `yolo26n.pt`, `docker-compose.yml`, `.env.example` |
| `research` | `fraction-solver/` |

Changes to `.github/workflows/`, `pytest.ini` or `scripts/ci_summary.py` run
every job, and so do pushes to `main` and manual runs (Actions → CI → Run
workflow). A skipped job counts as passed for merging.

Each run's page shows a table of passed, failed, skipped and known-bug tests,
and the JUnit reports are attached to the run.

## Running the whole workflow locally

[act](https://github.com/nektos/act) runs the workflow in Docker. Two
differences from GitHub: the upload steps are skipped (reports stay in
`reports/`), and it does not remove the MySQL container between runs
(`docker rm -f ase-mysql`).

```bash
act pull_request -P ubuntu-24.04=catthehacker/ubuntu:act-24.04 --bind
```
