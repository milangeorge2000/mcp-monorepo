"""Minimal MCP stdio (JSON-RPC over stdin/stdout) client.

Enough of the protocol to speak to any real MCP server, plus a deterministic
fake server for tests and demos:
  - initialize
  - notifications/initialized
  - tools/list

Only stdlib is required. Transport is newline-delimited JSON over the process
stdio pipes. Errors are surfaced as results rather than raising, so one broken
server does not abort the whole audit.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
from typing import Any, Dict, List, Optional, Sequence

from mcpaudit.models import MCPServerConfig


class MCPClientError(Exception):
    pass


class MCPClient:
    """Spawn an MCP server and speak JSON-RPC to it over stdio."""

    def __init__(self, config: MCPServerConfig, timeout: float = 10.0):
        self.config = config
        self.timeout = timeout
        self._proc: Optional[subprocess.Popen] = None
        self._seq = 0
        self._pending: Dict[int, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        env = dict(os.environ)
        env.update(self.config.env)
        try:
            self._proc = subprocess.Popen(
                self.config.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=env,
                text=True,
                encoding="utf-8",
            )
        except OSError as exc:
            raise MCPClientError(f"could not launch {self.config.command!r}: {exc}")

    def close(self) -> None:
        if self._proc is None:
            return
        try:
            self._proc.terminate()
            self._proc.wait(timeout=2)
        except (subprocess.TimeoutExpired, OSError):
            try:
                self._proc.kill()
            except OSError:
                pass
        self._proc = None

    # -- protocol ----------------------------------------------------------
    def _request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        if self._proc is None or self._proc.stdin is None or self._proc.stdout is None:
            raise MCPClientError("client not started")
        with self._lock:
            self._seq += 1
            req_id = self._seq
            msg = {"jsonrpc": "2.0", "id": req_id, "method": method}
            if params is not None:
                msg["params"] = params
            self._proc.stdin.write(json.dumps(msg) + "\n")
            self._proc.stdin.flush()
            raw = self._proc.stdout.readline()
        if not raw:
            raise MCPClientError(f"server closed stdout during {method}")
        try:
            resp: Dict[str, Any] = json.loads(raw)
        except ValueError as exc:
            raise MCPClientError(f"non-JSON response: {raw[:200]!r}") from exc
        if resp.get("id") != req_id:
            raise MCPClientError("mismatched json-rpc id")
        if "error" in resp:
            raise MCPClientError(f"{method} error: {resp['error']}")
        return resp.get("result")

    def _notify(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise MCPClientError("client not started")
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self._proc.stdin.write(json.dumps(msg) + "\n")
        self._proc.stdin.flush()

    def initialize(self) -> Dict[str, Any]:
        result = self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcpaudit", "version": "0.1.0"},
            },
        )
        self._notify("notifications/initialized")
        return result or {}

    def list_tools(self) -> List[Dict[str, Any]]:
        result = self._request("tools/list", {}) or {}
        tools = result.get("tools") or []
        return [t for t in tools if isinstance(t, dict)]


def measure_server(config: MCPServerConfig, timeout: float = 10.0) -> Dict[str, Any]:
    """Return normalized result dict for one server (never raises)."""
    client = MCPClient(config, timeout=timeout)
    try:
        client.start()
        client.initialize()
        tools = client.list_tools()
        return {"ok": True, "server": config.name, "tools": tools}
    except MCPClientError as exc:
        return {"ok": False, "server": config.name, "error": str(exc)}
    except OSError as exc:
        return {"ok": False, "server": config.name, "error": f"os error: {exc}"}
    finally:
        client.close()