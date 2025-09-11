"""Minimal MCP stdio (JSON-RPC over stdin/stdout) probe client.

Enough of the protocol to handshake and fetch tools/list without executing any
server tool. Inherits the proven implementation from mcpaudit (MIT).
"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, List, Optional

from mcpguard.models import ServerConfiguration


class MCPClientError(Exception):
    pass


def fetch_tools(config: ServerConfiguration, timeout: float = 10.0) -> List[Dict[str, Any]]:
    """Spawn, handshake, list tools, then tear down. Never raises."""
    env = dict(os.environ)
    env.update(config.env)
    proc: Optional[subprocess.Popen] = None
    try:
        proc = subprocess.Popen(
            config.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
            text=True,
            encoding="utf-8",
        )
        out = _exchange(proc, 1, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "mcpguard", "version": "0.1.0"},
        })
        _notify(proc, "notifications/initialized")
        result = _exchange(proc, 2, "tools/list", {})
        tools = result.get("tools") or []
        return [t for t in tools if isinstance(t, dict)]
    except (OSError, MCPClientError, ValueError) as exc:
        raise MCPClientError(str(exc))
    finally:
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    proc.kill()
                except OSError:
                    pass


def _send(proc: subprocess.Popen, msg: Dict[str, Any]) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()


def _notify(proc: subprocess.Popen, method: str, params: Optional[Dict[str, Any]] = None) -> None:
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    _send(proc, msg)


def _exchange(proc: subprocess.Popen, req_id: int, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    msg: Dict[str, Any] = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        msg["params"] = params
    _send(proc, msg)
    assert proc.stdout is not None
    raw = proc.stdout.readline()
    if not raw:
        raise MCPClientError(f"server closed stdout during {method}")
    try:
        resp: Dict[str, Any] = json.loads(raw)
    except ValueError as exc:
        raise MCPClientError(f"non-JSON response: {raw[:200]!r}") from exc
    if resp.get("error"):
        raise MCPClientError(f"{method} error: {resp['error']}")
    return resp.get("result") or {}