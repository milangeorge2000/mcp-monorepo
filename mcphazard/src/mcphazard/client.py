"""Minimal MCP stdio client that can actually **call** tools.

Where mcpguard/mcpaudit handshake and read `tools/list` only, mcphazard must
invoke `tools/call` against the sandboxed server under test. Same JSON-RPC
over stdin/stdout, same "never touches a real host" posture enforced by the
Sandbox that spawns the process.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Tuple

from mcphazard.sandbox import Sandbox


class MCPClientError(Exception):
    pass


class CallResult:
    __slots__ = ("ok", "text", "duration_ms", "error")

    def __init__(self, ok: bool, text: str, duration_ms: float, error: str = ""):
        self.ok = ok
        self.text = text
        self.duration_ms = duration_ms
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {"ok": self.ok, "text": self.text, "duration_ms": self.duration_ms, "error": self.error}


def probe_tools(sandbox: Sandbox, argv: List[str], timeout: float = 10.0,
                clear_env: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """Spawn, handshake, list tools, tear down. Returns the tools array."""
    proc = sandbox.spawn(argv, timeout=timeout, env=clear_env)
    try:
        _exchange(proc, 1, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "mcphazard", "version": "0.1.0"},
        })
        _notify(proc, "notifications/initialized")
        result = _exchange(proc, 2, "tools/list", {})
        tools = result.get("tools") or []
        return [t for t in tools if isinstance(t, dict)]
    except (OSError, ValueError, MCPClientError):
        return []
    finally:
        _kill(proc)


def call_tool(sandbox: Sandbox, argv: List[str], tool_name: str, args: Dict[str, Any],
              timeout: float = 15.0, clear_env: Optional[Dict[str, str]] = None) -> CallResult:
    """Fire one `tools/call` and capture the response text with timing."""
    proc = sandbox.spawn(argv, timeout=timeout, env=clear_env)
    try:
        _exchange(proc, 1, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "mcphazard", "version": "0.1.0"},
        })
        _notify(proc, "notifications/initialized")
        start = time.monotonic()
        try:
            result = _exchange(proc, 2, "tools/call", {"name": tool_name, "arguments": args or {}},
                               timeout=timeout)
        except MCPClientError as exc:
            return CallResult(False, "", (time.monotonic() - start) * 1000.0, str(exc))
        duration = (time.monotonic() - start) * 1000.0
        return _flatten_result(result, duration)
    except (OSError, ValueError) as exc:
        return CallResult(False, "", 0.0, str(exc))
    finally:
        _kill(proc)


def _flatten_result(result: Dict[str, Any], duration_ms: float) -> CallResult:
    """Fold MCP result (structuredContent / content[] / text) into one string."""
    parts: List[str] = []
    content = result.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                txt = item.get("text") or item.get("content")
                if txt:
                    parts.append(str(txt))
    structured = result.get("structuredContent")
    if isinstance(structured, dict) and structured:
        parts.append(json.dumps(structured, ensure_ascii=False))
    if not parts:
        # server returned a bare text walk
        parts.append(json.dumps(result, ensure_ascii=False))
    return CallResult(True, "\n".join(parts), duration_ms)


def _send(proc, msg: Dict[str, Any]) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()


def _notify(proc, method: str, params: Optional[Dict[str, Any]] = None) -> None:
    msg: Dict[str, Any] = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    _send(proc, msg)


def _exchange(proc, req_id: int, method: str, params: Optional[Dict[str, Any]] = None,
              timeout: float = 10.0) -> Dict[str, Any]:
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


def _kill(proc) -> None:
    try:
        proc.terminate()
        proc.wait(timeout=2)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass