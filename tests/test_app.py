import csv
import io
import time

import pytest
from fastapi.testclient import TestClient

from sherlock_local.app import create_app
from sherlock_local.jobs import JobManager


@pytest.fixture
def client():
    with TestClient(create_app(), base_url="http://127.0.0.1:8765") as client:
        yield client


@pytest.mark.parametrize("username", ["", " ", "--help", "a/b", "x\ny", "x" * 65, "https://example.com"])
def test_rejects_invalid_username(client, username):
    assert client.post("/api/searches", json={"username": username, "sites": ["GitHub"]}).status_code == 422


def test_rejects_unknown_platform(client):
    assert client.post("/api/searches", json={"username": "alice", "sites": ["NOT-A-SITE"]}).status_code == 422


def test_rejects_cross_origin(client):
    assert client.post("/api/searches", headers={"Origin": "https://evil.example"}, json={"username": "alice"}).status_code == 403


def test_rejects_untrusted_host(client):
    assert client.get("/api/sites", headers={"Host": "evil.example"}).status_code == 400


def test_catalog_and_missing_search(client):
    data = client.get("/api/sites").json()
    assert "GitHub" in data["sites"]
    assert client.get("/api/searches/missing").status_code == 404
    assert client.delete("/api/searches/missing").status_code == 404


def test_loopback_origin_allowed(client):
    response = client.post("/api/searches", headers={"Origin": "http://127.0.0.1:8765"}, json={"username": ""})
    assert response.status_code == 422


def test_job_lifecycle_csv_and_single_active_scan(tmp_path):
    # A real subprocess implements the worker protocol; no live networking needed.
    script = tmp_path / "fixture.py"
    script.write_text('import json,time\nprint(json.dumps({"type":"started","total":2}),flush=True)\nprint(json.dumps({"type":"result","site":"=formula","url":"https://example.com/alice","status":"found","detail":"","elapsed":0.1}),flush=True)\ntime.sleep(0.5)\nprint(json.dumps({"type":"result","site":"Other","url":"https://example.com/alice","status":"unknown","detail":"Timeout","elapsed":None}),flush=True)\nprint(json.dumps({"type":"done"}),flush=True)\n')
    manager = JobManager(command_factory=lambda payload: [__import__("sys").executable, "-u", str(script)])
    with TestClient(create_app(manager), base_url="http://127.0.0.1:8765") as client:
        response = client.post("/api/searches", json={"username":"alice", "sites":["GitHub"]})
        assert response.status_code == 202
        job_id = response.json()["id"]
        assert client.post("/api/searches", json={"username":"bob"}).status_code == 409
        for _ in range(100):
            snapshot = client.get(f"/api/searches/{job_id}").json()
            if snapshot["state"] != "running":
                break
            time.sleep(0.03)
        assert snapshot["state"] == "completed"
        assert snapshot["total"] == 2
        assert [r["status"] for r in snapshot["results"]] == ["found", "unknown"]
        export = client.get(f"/api/searches/{job_id}/csv")
        rows = list(csv.reader(io.StringIO(export.content.decode("utf-8-sig"))))
        assert rows[1][1] == "'=formula"
        assert len(rows) == 3


def test_cancel_terminates_process(tmp_path):
    script = tmp_path / "wait.py"
    script.write_text('import time\ntime.sleep(60)\n')
    manager = JobManager(command_factory=lambda payload: [__import__("sys").executable, str(script)])
    with TestClient(create_app(manager), base_url="http://127.0.0.1:8765") as client:
        job_id = client.post("/api/searches", json={"username":"alice", "sites":["GitHub"]}).json()["id"]
        assert client.delete(f"/api/searches/{job_id}").json()["state"] == "cancelled"


def test_worker_failure_is_reported(tmp_path):
    script = tmp_path / "fail.py"
    script.write_text('raise RuntimeError("failed")\n')
    manager = JobManager(command_factory=lambda payload: [__import__("sys").executable, str(script)])
    with TestClient(create_app(manager), base_url="http://127.0.0.1:8765") as client:
        job_id = client.post("/api/searches", json={"username":"alice", "sites":["GitHub"]}).json()["id"]
        for _ in range(100):
            snapshot = client.get(f"/api/searches/{job_id}").json()
            if snapshot["state"] != "running":
                break
            time.sleep(0.03)
        assert snapshot["state"] == "failed"
        assert snapshot["error"]


def test_nonreading_worker_does_not_block_start_and_expires(tmp_path):
    script = tmp_path / "stuck.py"
    script.write_text('import time\ntime.sleep(60)\n')
    manager = JobManager(command_factory=lambda payload: [__import__("sys").executable, str(script)], max_seconds=0.2)
    started = time.monotonic()
    job = manager.start("alice", ["x" * 10000], 3)
    assert time.monotonic() - started < 1
    try:
        for _ in range(100):
            snapshot = manager.get(job["id"])
            if snapshot["state"] != "running":
                break
            time.sleep(0.02)
        assert snapshot["state"] == "failed"
        assert "süre" in snapshot["error"]
    finally:
        manager.close()


def test_job_retention_is_bounded(tmp_path):
    script = tmp_path / "done.py"
    script.write_text('import sys\nsys.stdin.readline()\nprint(\'{"type":"done"}\')\n')
    manager = JobManager(command_factory=lambda payload: [__import__("sys").executable, str(script)], max_jobs=2)
    ids = []
    try:
        for _ in range(3):
            job = manager.start("alice", ["GitHub"], 3)
            ids.append(job["id"])
            for _ in range(100):
                if manager.get(job["id"])["state"] != "running":
                    break
                time.sleep(0.02)
        with pytest.raises(KeyError):
            manager.get(ids[0])
        assert manager.get(ids[-1])["state"] == "completed"
    finally:
        manager.close()
