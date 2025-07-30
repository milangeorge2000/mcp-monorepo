"""The bundled reference fleet: a deterministic MCP stdio server.

Runs ``python -m mcpbench.fleet`` (or as a subprocess by the harness). It
advertises a small fixed set of tools, enforces schema validity on
``tools/call``, refuses policy-gated tools with a distinct error code, and —
after the first tool call — switches to a *drifted* schema and emits
``notifications/tools/list_changed`` so the benchmark can measure which driver
re-negotiates. Everything is deterministic and stdlib-only.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional

from mcpbench.models import FLEET_TOOLS, drift_tools

PROTOCOL_VERSION = "2024-11-05"

CODE_POLICY_GATE = -32001
CODE_INVALID_PARAMS = -32602
CODE_METHOD_NOT_FOUND = -32601


class Fleet:
    def __init__(self) -> None:
        self.tools: List[Dict[str, Any]] = list(FLEET_TOOLS)
        self.drifted: bool = False
        self.calls: int = 0

    def handle(self, msg: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process one inbound frame; may emit zero or more outbound frames."""
        method = msg.get("method")
        if method == "initialize":
            return [{"jsonrpc": "2.0", "id": msg.get("id"),
                     "result": {
                         "protocolVersion": PROTOCOL_VERSION,
                         "capabilities": {"tools": {"listChanged": True}},
                         "serverInfo": {"name": "mcpbench-fleet", "version": "0.1.0"},
                     }}]
        if method == "notifications/initialized":
            return []
        if method == "notifications/tools/list_changed":
            return []

        # notifications carry no id and expect no response
        if msg.get("id") is None:
            return []

        if method == "tools/list":
            return [{"jsonrpc": "2.0", "id": msg.get("id"), "result": {"tools": self.tools}}]

        if method == "tools/call":
            return self._call(msg)

        return [{"jsonrpc": "2.0", "id": msg.get("id"),
                 "error": {"code": CODE_METHOD_NOT_FOUND, "message": f"method not found: {method}"}}]

    # -- internals ---------------------------------------------------------

    def _call(self, msg: Dict[str, Any]) -> List[Dict[str, Any]]:
        params = msg.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        # The FIRST executed call is validated against the CURRENT (old) schema
        # so it lands; immediately after, the schema drifts and the change is
        # announced. Subsequent calls/listings see the new required 'scope'.
        announce = []
        tool = next((t for t in self.tools if t["name"] == name), None)
        if tool is None:
            return announce + [{"jsonrpc": "2.0", "id": msg.get("id"),
                                "error": {"code": CODE_METHOD_NOT_FOUND, "message": f"no such tool: {name}"}}]
        problem = _validate(tool, args)
        if problem:
            return announce + [{"jsonrpc": "2.0", "id": msg.get("id"),
                                "error": {"code": CODE_INVALID_PARAMS, "message": problem}}]
        if name in ("write_file", "grant_permissions", "run_backup"):
            return announce + [{"jsonrpc": "2.0", "id": msg.get("id"),
                                "error": {"code": CODE_POLICY_GATE,
                                          "message": f"policy gate: {name} requires approval"}}]
        self.calls += 1
        if self.calls == 1:
            self.drifted = True
            self.tools = drift_tools()
            announce = [self.emit_list_changed()]
        return announce + [{"jsonrpc": "2.0", "id": msg.get("id"),
                            "result": {"content": [{"type": "text", "text": _ok_text(name, args)}]}}]

    def emit_list_changed(self) -> Dict[str, Any]:
        """Server->client notification, used by some drivers to re-list."""
        return {"jsonrpc": "2.0", "method": "notifications/tools/list_changed"}


def _ok_text(name: str, args: Dict[str, Any]) -> str:
    if name == "lookup":
        return f"record {args.get('record_id')}: ok scope={args.get('scope', 'global')}"
    if name == "archive_file":
        return f"archived {args.get('path')}"
    return f"{name} ok"


def _validate(tool: Dict[str, Any], args: Dict[str, Any]) -> Optional[str]:
    schema = tool.get("inputSchema") or {}
    props = schema.get("properties") or {}
    required = schema.get("required") or []
    for key in required:
        if key not in args:
            return f"missing required argument: {key}"
    for key, value in args.items():
        meta = props.get(key)
        if not meta:
            continue
        typ = meta.get("type")
        if typ == "integer" and not isinstance(value, int):
            return f"argument {key} must be integer"
        if typ == "string" and not isinstance(value, str):
            return f"argument {key} must be string"
        if typ == "boolean" and not isinstance(value, bool):
            return f"argument {key} must be boolean"
    return None


def _loop() -> int:
    fleet = Fleet()
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except ValueError:
            sys.stdout.write(json.dumps({
                "jsonrpc": "2.0",
                "error": {"code": CODE_INVALID_PARAMS, "message": "malformed request"}}) + "\n")
            sys.stdout.flush()
            continue
        for frame in fleet.handle(msg):
            sys.stdout.write(json.dumps(frame, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(_loop())