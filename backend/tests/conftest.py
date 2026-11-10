import os
import pytest

# The app warms its models in a background thread at startup; tests start the
# app many times and mock the models, so they skip it.
os.environ.setdefault("PRELOAD_MODELS", "0")


@pytest.fixture(autouse=True)
def private_tablet_storage(monkeypatch, tmp_path):
    monkeypatch.setenv("TABLET_STORAGE_DIR", str(tmp_path / "tablets"))
