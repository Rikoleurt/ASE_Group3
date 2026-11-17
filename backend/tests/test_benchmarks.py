import json

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def write_history(folder, versions=("signs-v1", "model@test")):
    folder.mkdir(parents=True, exist_ok=True)
    for v in versions:
        (folder / f"{v}.json").write_text(json.dumps({"version": v, "signs": []}), encoding="utf-8")
    index = {"schema": 1, "versions": [{"version": v, "read_top1": 0.5} for v in versions]}
    (folder / "index.json").write_text(json.dumps(index), encoding="utf-8")


@pytest.fixture
def history(tmp_path, monkeypatch):
    folder = tmp_path / "history"
    write_history(folder)
    (tmp_path / "secret.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("BENCHMARK_HISTORY_DIR", str(folder))
    return folder


def test_index_lists_versions(history):
    body = client.get("/benchmarks").json()
    assert [v["version"] for v in body["versions"]] == ["signs-v1", "model@test"]


def test_one_version(history):
    response = client.get("/benchmarks/signs-v1")
    assert response.status_code == 200 and response.json()["version"] == "signs-v1"
    assert client.get("/benchmarks/model@test").json()["version"] == "model@test"


def test_unlisted_file_is_not_served(history):
    (history / "hidden.json").write_text("{}", encoding="utf-8")
    assert client.get("/benchmarks/hidden").status_code == 404
    assert client.get("/benchmarks/nope").status_code == 404


@pytest.mark.parametrize("name", ["..", "../secret", "..%2Fsecret", "%2e%2e%2fsecret", "a/b", "a%5Cb", "index%00", "x" * 200])
def test_traversal_is_rejected(history, name):
    assert client.get(f"/benchmarks/{name}").status_code in (404, 422)


def test_index_itself_is_not_a_version(history):
    assert client.get("/benchmarks/index").status_code == 404


def test_missing_folder_is_503(tmp_path, monkeypatch):
    monkeypatch.setenv("BENCHMARK_HISTORY_DIR", str(tmp_path / "nowhere"))
    for url in ("/benchmarks", "/benchmarks/signs-v1"):
        response = client.get(url)
        assert response.status_code == 503 and "not available" in response.json()["detail"]


def test_folder_without_index_is_503(tmp_path, monkeypatch):
    monkeypatch.setenv("BENCHMARK_HISTORY_DIR", str(tmp_path))
    assert client.get("/benchmarks").status_code == 503


def test_changed_file_is_re_read(history):
    assert client.get("/benchmarks/signs-v1").json()["signs"] == []
    path = history / "signs-v1.json"
    path.write_text(json.dumps({"version": "signs-v1", "signs": [1]}), encoding="utf-8")
    import os
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10_000_000))
    assert client.get("/benchmarks/signs-v1").json()["signs"] == [1]


def test_real_history_is_served(monkeypatch):
    monkeypatch.delenv("BENCHMARK_HISTORY_DIR", raising=False)
    body = client.get("/benchmarks").json()
    assert body["versions"]
    first = body["versions"][0]["version"]
    assert client.get(f"/benchmarks/{first}").json()["version"] == first
