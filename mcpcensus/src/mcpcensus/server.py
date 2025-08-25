"""A reference observatory server on the Python standard library.

No Postgres, no queue, no auth provider — just enough HTTP for the full loop to
run on a laptop or a small VPS: sensors POST anonymized fingerprints to
``/ingest``, anyone can pull a ``published`` snapshot from ``/published``, and
``/report`` renders a State-of-MCP page.

A production-grade deployment would swap the JSONL store for real storage and
put a proper rate-limiter in front of the same public contract.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional

from mcpcensus.privacy import is_valid_fingerprint
from mcpcensus.registry import aggregate, append_registry, load_registry
from mcpcensus.report import compose_report


class CensusHandler(BaseHTTPRequestHandler):
    server_version = "mcpcensus/0.1"

    # -- helpers ----------------------------------------------------------
    def _json(self, obj: Any, status: int = 200) -> None:
        body = json.dumps(obj, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _store(self) -> "RegistryState":
        return self.server.registry_state  # type: ignore[attr-defined]

    def _read_body(self, max_bytes: int = 2 * 1024 * 1024) -> bytes:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length > max_bytes:
            self._json({"error": "payload too large"}, 413)
            return b""
        return self.rfile.read(length)

    # -- routes -----------------------------------------------------------
    def do_GET(self):
        if self.path.startswith("/healthz"):
            return self._json({"ok": True, "version": "0.1.0"})
        if self.path.startswith("/published"):
            sensor = self._query_param("sensor", "context")
            pub = self._store().published(sensor)
            return self._json(pub)
        if self.path.startswith("/report"):
            sensor = self._query_param("sensor", "context")
            reporter = self._store().report(sensor)
            chunk = compose_report(reporter, "State of MCP · live")
            body = chunk.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        if not self.path.startswith("/ingest"):
            return self._json({"error": "not found"}, 404)
        raw = self._read_body()
        if not raw:
            return
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return self._json({"error": "invalid json"}, 400)

        if isinstance(payload, list):
            fps: List[Dict[str, Any]] = [p for p in payload if is_valid_fingerprint(p)]
        elif is_valid_fingerprint(payload):
            fps = [payload]
        else:
            return self._json({"error": "not a valid mcpcensus/v1 fingerprint",
                               "needed": "format/device/submitted_at/sensor/axes"}, 400)

        added = self._store().ingest(fps)
        return self._json({"ok": True, "added": added, "duplicates": len(fps) - added}, 201)

    def do_OPTIONS(self):  # pragma: no cover - minimal CORS for badges on pages
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _query_param(self, name: str, default: str) -> str:
        query = self.path.split("?", 1)[1] if "?" in self.path else ""
        for pair in query.split("&"):
            if not pair:
                continue
            try:
                k, v = pair.split("=", 1)
            except ValueError:
                continue
            if k == name:
                return _unquote_simple(v)
        return default

    def log_message(self, fmt, *args):  # quieter console for local runs
        pass


def _unquote_simple(value: str) -> str:
    return value.replace("+", " ")


class RegistryState:
    """Shared state mounted on the server: an append-only JSONL registry plus
    a small write-lock so concurrent ingests never corrupt a line."""

    def __init__(self, db_path: str, min_cohort: int, noise_scale: float):
        self.db_path = db_path
        self.min_cohort = min_cohort
        self.noise_scale = noise_scale
        self._lock = _FileLock(db_path)

    def ingest(self, fps: List[Dict[str, Any]]) -> int:
        added = 0
        for fp in fps:
            dev = fp.get("device", "")
            sensor = fp.get("sensor", "")
            month = str(fp.get("submitted_at", ""))[:7]
            if not (dev and sensor and month):
                continue
            if self._has_month(dev, sensor, month):
                continue
            self._lock.acquire()
            try:
                if self._has_month(dev, sensor, month):
                    continue
                append_registry(self.db_path, [fp])
                added += 1
            finally:
                self._lock.release()
        return added

    def _has_month(self, device: str, sensor: str, month: str) -> bool:
        for fp in load_registry(self.db_path):
            if fp.get("device") == device and fp.get("sensor") == sensor:
                if str(fp.get("submitted_at", ""))[:7] == month:
                    return True
        return False

    def fingerprints(self, sensor: str) -> List[Dict[str, Any]]:
        return [fp for fp in load_registry(self.db_path) if fp.get("sensor") == sensor]

    def published(self, sensor: str) -> Dict[str, Any]:
        return aggregate(self.fingerprints(sensor), sensor,
                         min_cohort=self.min_cohort, noise_scale=self.noise_scale)

    def report(self, sensor: str) -> Dict[str, Any]:
        return self.published(sensor)


class _FileLock:
    """Atomic mkdir-based lock (works on POSIX + Windows, zero deps)."""

    def __init__(self, db_path: str):
        self._lock_dir = db_path + ".lock"

    def acquire(self) -> None:
        for _ in range(1000):
            try:
                os.mkdir(self._lock_dir)
                return
            except FileExistsError:
                import time
                time.sleep(0.01)
        raise RuntimeError(f"could not acquire lock {self._lock_dir}")

    def release(self) -> None:
        try:
            os.rmdir(self._lock_dir)
        except OSError:
            pass


def run_server(db: str, port: int = 8787, min_cohort: int = 5, noise_scale: float = 0.0) -> int:
    state = RegistryState(db, min_cohort, noise_scale)
    server = ThreadingHTTPServer(("127.0.0.1", port), CensusHandler)
    server.registry_state = state  # type: ignore[attr-defined]
    print(f"mcpcensus observatory listening on http://127.0.0.1:{port} (db {db})")
    print("  POST /ingest           sensors drop anonymized fingerprints here")
    print("  GET  /published        k-anonymized aggregate JSON")
    print("  GET  /report           State-of-MCP HTML")
    print("  GET  /healthz")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        server.server_close()
    return 0