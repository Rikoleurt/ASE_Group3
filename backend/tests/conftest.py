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


class RecordedNotifications:
    """Notifications in memory: rows as NotificationDataController.add takes them."""

    def __init__(self):
        self.rows = []

    def add(self, rows):
        self.rows.extend(rows)

    def to(self, user_id):
        return [row for row in self.rows if row[0] == user_id]


@pytest.fixture(autouse=True)
def notifications(monkeypatch):
    """No test writes notifications to a database; each sees the ones its actions made."""
    from backend.app import notifications as module
    recorder = RecordedNotifications()
    monkeypatch.setattr(module, "SINK", recorder)
    return recorder
