import os

# The app warms its models in a background thread at startup; tests start the
# app many times and mock the models, so they skip it.
os.environ.setdefault("PRELOAD_MODELS", "0")

import pytest


@pytest.fixture(autouse=True)
def upload_dir(tmp_path, monkeypatch):
    """Uploads go to a fresh folder per test, never into the repository's var/uploads (#81)."""
    folder = tmp_path / "uploads"
    monkeypatch.setenv("UPLOAD_DIR", str(folder))
    return folder
