import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from sherlock_local import worker


def test_actual_sherlock_engine_reports_found_missing_blocked(monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(404 if self.path.startswith("/missing/") else 200)
            self.end_headers()
            self.wfile.write(b'<span id="challenge-error-text">' if self.path.startswith("/blocked/") else b"Profile")

        do_HEAD = do_GET

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    definitions = {name: {"urlMain": base, "url": base + path + "/{}", "errorType": "status_code", "username_claimed": "alice"}
                   for name, path in [("Found", "/found"), ("Missing", "/missing"), ("Blocked", "/blocked")]}
    definitions["Blocked"].update(errorType="message", errorMsg="Not Found")
    monkeypatch.setattr(worker, "site_catalog", lambda: definitions)
    events = []
    try:
        worker.run_scan({"username":"alice", "sites": list(definitions), "timeout":3}, events.append)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    assert events[0] == {"type":"started", "total":3}
    assert events[-1] == {"type":"done"}
    assert {e["site"]: e["status"] for e in events if e["type"] == "result"} == {"Found":"found", "Missing":"absent", "Blocked":"unknown"}
    assert definitions["Found"].get("request_future") is None


@pytest.mark.parametrize("status", ["UNKNOWN", "ILLEGAL", "WAF"])
def test_inconclusive_never_becomes_absent(monkeypatch, status):
    from sherlock_project.result import QueryResult, QueryStatus

    monkeypatch.setattr(worker, "site_catalog", lambda: {"Example": {}})

    def engine(username, data, notify, timeout):
        notify.update(QueryResult(username, "Example", "https://example.com/alice", getattr(QueryStatus, status)))

    monkeypatch.setattr(worker, "sherlock", engine)
    events = []
    worker.run_scan({"username":"alice", "sites":["Example"]}, events.append)
    assert events[1]["status"] == "unknown"


@pytest.mark.parametrize("code", [401, 403, 429, 500, 503])
def test_http_failures_are_inconclusive_with_real_engine(monkeypatch, code):
    class Handler(BaseHTTPRequestHandler):
        def do_HEAD(self):
            self.send_response(code)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setattr(worker, "site_catalog", lambda: {"Example": {"urlMain":base, "url":base + "/{}", "errorType":"status_code"}})
    events = []
    try:
        worker.run_scan({"username":"alice", "sites":["Example"], "timeout":3}, events.append)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    assert events[1]["status"] == "unknown"
    assert str(code) in events[1]["detail"]
