import io
import json
import urllib.error

import pytest

from scripts import fetch_models

RELEASE = {"assets": [
    {"name": name, "url": f"https://api.github.test/assets/{index}", "size": len(name)}
    for index, name in enumerate(fetch_models.ASSETS)
]}


@pytest.fixture
def github(monkeypatch, tmp_path):
    """A fake GitHub: the release JSON, then each asset's bytes (its own name)."""
    monkeypatch.setattr(fetch_models, "MODELS", tmp_path / "models")
    monkeypatch.setattr(fetch_models, "token", lambda: "secret")
    monkeypatch.setattr("sys.argv", ["fetch_models.py"])
    requests = []

    def urlopen(req):
        requests.append(req)
        if "/releases/tags/" in req.full_url:
            return io.BytesIO(json.dumps(RELEASE).encode())
        asset = next(a for a in RELEASE["assets"] if a["url"] == req.full_url)
        return io.BytesIO(asset["name"].encode())

    monkeypatch.setattr(fetch_models.urllib.request, "urlopen", urlopen)
    return requests


def test_downloads_every_asset_with_the_token(github):
    assert fetch_models.main() == 0
    for name in fetch_models.ASSETS:
        assert (fetch_models.MODELS / name).read_bytes() == name.encode()
    assert all(req.get_header("Authorization") == "token secret" for req in github)
    assert not list(fetch_models.MODELS.glob("*.part"))


def test_keeps_files_already_present(github):
    fetch_models.MODELS.mkdir()
    (fetch_models.MODELS / "linear_a_signs.pt").write_bytes(b"mine")
    assert fetch_models.main() == 0
    assert (fetch_models.MODELS / "linear_a_signs.pt").read_bytes() == b"mine"
    assert len(github) == 1 + len(fetch_models.ASSETS) - 1


def test_incomplete_download_is_discarded(github, monkeypatch):
    monkeypatch.setitem(RELEASE["assets"][0], "size", 10**6)
    assert fetch_models.main() == 1
    assert not (fetch_models.MODELS / fetch_models.ASSETS[0]).exists()
    assert not list(fetch_models.MODELS.glob("*.part"))


def test_missing_release_without_token_explains_why(monkeypatch, capsys):
    monkeypatch.setattr(fetch_models, "token", lambda: None)
    monkeypatch.setattr("sys.argv", ["fetch_models.py"])

    def not_found(req):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr(fetch_models.urllib.request, "urlopen", not_found)
    assert fetch_models.main() == 1
    assert "GITHUB_TOKEN" in capsys.readouterr().err


def test_environment_token_wins_over_git(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "from-env")
    monkeypatch.setattr(fetch_models.subprocess, "run", lambda *a, **k: pytest.fail("git was asked"))
    assert fetch_models.token() == "from-env"


def test_optional_reader_files_are_downloaded_when_the_release_has_them(github, monkeypatch):
    extra = [{"name": name, "url": f"https://api.github.test/assets/x{index}", "size": len(name)}
             for index, name in enumerate(fetch_models.OPTIONAL[:2])]
    monkeypatch.setitem(RELEASE, "assets", RELEASE["assets"] + extra)
    assert fetch_models.main() == 0
    for name in fetch_models.OPTIONAL[:2]:
        assert (fetch_models.MODELS / name).read_bytes() == name.encode()
    for name in fetch_models.OPTIONAL[2:]:  # not in this release: skipped, not an error
        assert not (fetch_models.MODELS / name).exists()


def test_the_default_release_is_reader_v2(github):
    fetch_models.main()
    assert github[0].full_url.endswith("/releases/tags/reader-v2")
