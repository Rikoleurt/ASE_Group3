import os
import pytest

# The app warms its models in a background thread at startup; tests start the
# app many times and mock the models, so they skip it.
os.environ.setdefault("PRELOAD_MODELS", "0")


@pytest.fixture(autouse=True)
def private_tablet_storage(monkeypatch, tmp_path):
    monkeypatch.setenv("TABLET_STORAGE_DIR", str(tmp_path / "tablets"))


@pytest.fixture(autouse=True)
def fresh_rate_limits():
    """Rate limits (#98) are per process: start every test from zero."""
    from backend.app.rate_limit import COMMENTS, FAILED_LOGINS, UPLOADS
    for limit in (COMMENTS, FAILED_LOGINS, UPLOADS):
        limit.reset()
