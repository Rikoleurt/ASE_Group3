See the [repository README](../README.md) for installation, MySQL configuration,
API examples and tests. The Python import root is the repository, not this folder.

From `ASE_Group3`:

```bash
uv sync --project backend
docker compose up -d --wait mysql
uv run --project backend uvicorn backend.app.main:app --reload
```
