"""scripts/fetch_corpus.py: the corpus data from the corpus-v1 release, unpacked safely."""
import io
import json
import zipfile

import pytest

from scripts import fetch_corpus


def zipped(files: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


ARCHIVES = {
    "linear_a_corpus.zip": zipped({"data/LICENCE-corpus.txt": "CC BY-NC-SA", "data/cache/HT-13.json": "{}",
                                   "out/yolo_signs/annotations.json": "[]"}),
    "linear_a_tracings.zip": zipped({"data/images/HT-13/HT-13-1367w-a.png": "tracing"}),
    "linear_a_sign_crops.zip": zipped({"data/images/HT-13/HT-13_1-10w-b.png": "crop"}),
}


@pytest.fixture
def github(monkeypatch, tmp_path):
    """A fake GitHub: the release JSON, then each archive's bytes."""
    release = {"assets": [{"name": name, "url": f"https://api.github.test/assets/{name}", "size": len(data)}
                          for name, data in ARCHIVES.items()]}
    monkeypatch.setattr(fetch_corpus, "TARGET", tmp_path / "fraction-solver")
    monkeypatch.setattr(fetch_corpus, "token", lambda: "secret")
    monkeypatch.setattr("sys.argv", ["fetch_corpus.py"])
    requests = []

    def urlopen(req):
        requests.append(req)
        if "/releases/tags/corpus-v1" in req.full_url:
            return io.BytesIO(json.dumps(release).encode())
        return io.BytesIO(ARCHIVES[req.full_url.rsplit("/", 1)[-1]])

    monkeypatch.setattr(fetch_corpus.urllib.request, "urlopen", urlopen)
    return release, requests


def test_downloads_the_corpus_and_drawings_with_the_token(github):
    _, requests = github
    assert fetch_corpus.main() == 0
    root = fetch_corpus.TARGET
    assert (root / "data/cache/HT-13.json").read_text() == "{}"
    assert (root / "out/yolo_signs/annotations.json").read_text() == "[]"
    assert (root / "data/images/HT-13/HT-13-1367w-a.png").read_text() == "tracing"
    assert (root / "data/LICENCE-corpus.txt").exists()
    assert not (root / "data/images/HT-13/HT-13_1-10w-b.png").exists()  # crops only when asked
    assert all(req.get_header("Authorization") == "token secret" for req in requests)


def test_crops_on_request_and_files_present_are_kept(github, monkeypatch):
    root = fetch_corpus.TARGET
    (root / "data/cache").mkdir(parents=True)
    (root / "data/cache/HT-13.json").write_text("mine")
    monkeypatch.setattr("sys.argv", ["fetch_corpus.py", "--with-crops"])
    assert fetch_corpus.main() == 0
    assert (root / "data/cache/HT-13.json").read_text() == "mine"
    assert (root / "data/images/HT-13/HT-13_1-10w-b.png").read_text() == "crop"


def test_an_incomplete_download_stops(github):
    release, _ = github
    release["assets"][0]["size"] += 1
    assert fetch_corpus.main() == 1
    assert not (fetch_corpus.TARGET / "data").exists()


@pytest.mark.parametrize("name", ["../evil.txt", "/etc/passwd", "backend/app/main.py", "data/../../x"])
def test_archives_cannot_write_outside_the_corpus_folders(name, tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_corpus, "TARGET", tmp_path)
    archive = tmp_path / "bad.zip"
    archive.write_bytes(zipped({name: "x"}))
    with pytest.raises(ValueError, match="Unexpected path"):
        fetch_corpus.unpack(archive, force=False)
