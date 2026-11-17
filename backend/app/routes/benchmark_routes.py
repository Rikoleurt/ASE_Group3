"""Read-only access to the published benchmark results (benchmark/history/*.json).

Public and database-free: the files hold only derived numbers (see benchmark/publish.py).
"""

import json
import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])

DEFAULT_HISTORY = Path(__file__).resolve().parents[3] / "benchmark" / "history"
VERSION_NAME = re.compile(r"^[A-Za-z0-9._@-]{1,100}$")
_cache: dict[Path, tuple[int, dict]] = {}


def history_dir() -> Path:
    return Path(os.getenv("BENCHMARK_HISTORY_DIR") or DEFAULT_HISTORY)


def _read(path: Path) -> dict:
    """Parse a JSON file, re-reading only when its modification time changed."""
    try:
        stamp = path.stat().st_mtime_ns
        cached = _cache.get(path)
        if cached and cached[0] == stamp:
            return cached[1]
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=503, detail="Benchmark results are unreadable.") from error
    _cache[path] = (stamp, data)
    return data


def _index() -> dict:
    folder = history_dir()
    if not folder.is_dir():
        raise HTTPException(status_code=503, detail="Benchmark results are not available on this server.")
    try:
        return _read(folder / "index.json")
    except FileNotFoundError as error:
        raise HTTPException(status_code=503, detail="Benchmark results are not available on this server.") from error


@router.get("")
def benchmark_index() -> dict:
    return _index()


@router.get("/{version}")
def benchmark_version(version: str) -> dict:
    if not VERSION_NAME.fullmatch(version) or version in {".", ".."}:
        raise HTTPException(status_code=404, detail="Unknown benchmark version.")
    listed = {entry.get("version") for entry in _index().get("versions", [])}
    if version not in listed:
        raise HTTPException(status_code=404, detail="Unknown benchmark version.")
    try:
        return _read(history_dir() / f"{version}.json")
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Unknown benchmark version.") from error
