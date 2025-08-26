"""Live-server smoke test against the stdlib reference observatory."""

import json
import threading
import urllib.request

from mcpcensus.fingerprint import build_context_fingerprint
from mcpcensus.server import run_server


def _start(tmp_path):
    db = str(tmp_path / "srv.jsonl")
    import socket
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    t = threading.Thread(target=lambda: run_server(db, port=port, min_cohort=1, noise_scale=0.0),
                         daemon=True)
    t.start()
    import time
    for _ in range(50):
        try:
            _http("GET", f"http://127.0.0.1:{port}/healthz")
            break
        except Exception:
            time.sleep(0.05)
    return port, db


def _http(method, url, body=None):
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_ingest_publish_loop(tmp_path, audit_report, salt_bytes):
    import os, sys
    port, db = _start(tmp_path)
    fp = build_context_fingerprint(audit_report, salt_bytes, "srv-device")

    status, body = _http("POST", f"http://127.0.0.1:{port}/ingest",
                         json.dumps(fp).encode("utf-8"))
    assert status == 201 and body["added"] == 1

    # duplicate submission is idempotent (same device, same month)
    status, body = _http("POST", f"http://127.0.0.1:{port}/ingest",
                         json.dumps(fp).encode("utf-8"))
    assert status == 201 and body["added"] == 0

    status, pub = _http("GET", f"http://127.0.0.1:{port}/published?sensor=context")
    assert status == 200
    assert pub["sensor"] == "context"
    assert pub["devices_seen"] == 1
    assert pub["stats"]["avg_servers"] == 3.0

    status, _ = _http("GET", f"http://127.0.0.1:{port}/healthz")
    assert status == 200


def test_ingest_rejects_garbage(tmp_path):
    port, db = _start(tmp_path)
    status, body = _http("POST", f"http://127.0.0.1:{port}/ingest",
                         json.dumps({"format": "nope"}).encode("utf-8"))
    assert status == 400
    assert "valid mcpcensus/v1" in body["error"]