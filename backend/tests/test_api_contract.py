"""The committed OpenAPI snapshot is the contract the frontend tests check against.

After an intentional API change, regenerate it and commit the result:

    UPDATE_API_CONTRACT=1 uv run --project backend python -m pytest backend/tests/test_api_contract.py
"""

import json
import os
from pathlib import Path

from backend.app.main import app

CONTRACT = Path(__file__).resolve().parents[2] / "contract" / "openapi.json"


def render(schema: dict) -> str:
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def test_openapi_matches_committed_contract():
    current = render(app.openapi())
    if os.getenv("UPDATE_API_CONTRACT") == "1":
        CONTRACT.parent.mkdir(exist_ok=True)
        CONTRACT.write_text(current, encoding="utf-8")
    assert CONTRACT.is_file(), "contract/openapi.json is missing; see this file's docstring"
    assert CONTRACT.read_text(encoding="utf-8") == current, (
        "The API no longer matches contract/openapi.json. If the change is intended, "
        "regenerate the contract (see this file's docstring) and check the frontend tests."
    )
