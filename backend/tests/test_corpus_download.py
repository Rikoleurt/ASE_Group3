"""The Tablets page's download button: admins fetch the corpus-v1 release onto the server."""
from threading import Event

import pytest
from fastapi.testclient import TestClient

from backend.app import corpus, corpus_download, glyph_index
from backend.app.main import app
from backend.tests.test_admin import logged_in
from scripts import fetch_corpus


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    monkeypatch.setattr(corpus_download, "_state", {"state": "idle", "log": [], "error": None})


def wait_until_finished(client):
    for _ in range(200):
        status = client.get("/tablets/download").json()
        if status["state"] != "running":
            return status
        Event().wait(0.02)
    raise AssertionError("the download did not finish")


def test_an_admin_downloads_and_the_list_and_index_are_refreshed(monkeypatch):
    calls = []

    def fetch(log):
        calls.append(True)
        log("downloading linear_a_corpus.zip (1.9 MB)…")
        log("  unpacked 1885 file(s) into fraction-solver/")

    monkeypatch.setattr(fetch_corpus, "fetch", fetch)
    corpus._drawn[1] = (0.0, [], 706)
    monkeypatch.setattr(glyph_index, "_index", object())
    with logged_in(monkeypatch, admin=True) as client:
        assert client.get("/tablets/download").json() == {"state": "idle", "log": [], "error": None}
        started = client.post("/tablets/download")
        assert started.status_code == 202 and started.json()["state"] in ("running", "done")
        assert wait_until_finished(client) == {"state": "done", "error": None, "log": [
            "downloading linear_a_corpus.zip (1.9 MB)…", "  unpacked 1885 file(s) into fraction-solver/"]}
    assert calls == [True]
    assert corpus._drawn == {} and glyph_index._index is None  # listed and indexed again


def test_a_second_download_waits_for_the_first(monkeypatch):
    release = Event()
    monkeypatch.setattr(fetch_corpus, "fetch", lambda log: release.wait(5))
    with logged_in(monkeypatch, admin=True) as client:
        assert client.post("/tablets/download").status_code == 202
        busy = client.post("/tablets/download")
        assert (busy.status_code, busy.json()["detail"]) == (409, "A download is already running.")
        release.set()
        assert wait_until_finished(client)["state"] == "done"


def test_a_failure_is_reported(monkeypatch):
    def fetch(log):
        raise fetch_corpus.FetchError("Cannot read release corpus-v1: HTTP 404 (set GITHUB_TOKEN: the repository is private)")

    monkeypatch.setattr(fetch_corpus, "fetch", fetch)
    with logged_in(monkeypatch, admin=True) as client:
        client.post("/tablets/download")
        status = wait_until_finished(client)
    assert status["state"] == "failed" and "GITHUB_TOKEN" in status["error"]


def test_an_unexpected_error_is_reported_without_details(monkeypatch):
    def fetch(log):
        raise OSError("disk full at C:/secret/path")

    monkeypatch.setattr(fetch_corpus, "fetch", fetch)
    with logged_in(monkeypatch, admin=True) as client:
        client.post("/tablets/download")
        status = wait_until_finished(client)
    assert status == {"state": "failed", "log": [], "error": "The download failed (OSError). See the server log."}


def test_only_admins_with_the_csrf_token_can_download(monkeypatch):
    monkeypatch.setattr(fetch_corpus, "fetch", lambda log: pytest.fail("must not download"))
    with logged_in(monkeypatch, admin=False) as client:
        assert client.post("/tablets/download").status_code == 403
        assert client.get("/tablets/download").status_code == 403
    with logged_in(monkeypatch, admin=True, csrf=False) as client:
        assert client.post("/tablets/download").status_code == 403
    with TestClient(app) as client:
        assert client.post("/tablets/download").status_code == 401
