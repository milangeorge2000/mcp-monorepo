"""The bundled reference fleet: a strict, deterministic MCP stdio server.

It validates ``tools/call`` arguments against advertised schemas and answers
with ``-32602`` on any deviation; on request it *mutates* a tool's schema via
the private ``mcpbatt/apply_drift`` control method and emits
``notifications/tools/list_changed`` - which is what lets the battery test a
server's drift honesty deterministically. Runs as ``python -m mcpbatt.fleet``.
Everything is stdlib-only and reproducible.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional

PROTOCOL_VERSION = "2024-11-05"

CODE_INVALID_PARAMS = -32602
CODE_METHOD_NOT_FOUND = -32601

_FLEET_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "lookup",
        "description": "Look up a record by id.",
        "inputSchema": {
            "type": "object",
            "properties": {"record_id": {"type": "integer"}},
            "required": ["record_id"],
        },
    },
    {
        "name": "search",
        "description": "Full-text search over the corpus.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "create_entry",
        "description": "Create a key/value entry.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "flag",
        "description": "Request no arguments; marks a review flag.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


class ReferenceFleet:
    def __init__(self) -> None:
        self.tools: List[Dict[str, Any]] = json.loads(json.dumps(_FLEET_TOOLS))
        self.drifted: bool = False

    def handle(self, msg: Dict[str, Any]) -> List[Dict[str, Any]]:
        method = msg.get("method")
        rid = msg.get("id")

        if method == "initialize":
            return [{"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": True}},
                "serverInfo": {"name": "mcpbatt-fleet", "version": "0.1.0"},
            }}]
        if method in ("notifications/initialized", "notifications/tools/list_changed"):
            return []
        if rid is None:  # unfiled client notification
            return []

        if method == "tools/list":
            return [{"jsonrpc": "2.0", "id": rid, "result": {"tools": self.tools}}]

        if method == "tools/call":
            return self._call(msg)

        if method == "mcpbatt/apply_drift":
            return self._apply_drift(msg)

        return [{"jsonrpc": "2.0", "id": rid,
                 "error": {"code": CODE_METHOD_NOT_FOUND, "message": f"method not found: {method}"}}]

    # -- internals ---------------------------------------------------------

    def _apply_drift(self, msg: Dict[str, Any]) -> List[Dict[str, Any]]:
        params = msg.get("params") or {}
        tool_name = params.get("tool")
        add_required = list(params.get("add_required") or [])
        target = next((t for t in self.tools if t["name"] == tool_name), None)
        if target is None:
            return [{"jsonrpc": "2.0", "id": msg.get("id"),
                     "error": {"code": CODE_METHOD_NOT_FOUND, "message": f"no such tool: {tool_name}"}}]
        schema = dict(target.get("inputSchema") or {"type": "object", "properties": {}, "required": []})
        props = dict(schema.get("properties") or {})
        required = list(schema.get("required") or [])
        out = []
        for field in add_required:
            if field not in props:
                props[field] = {"type": "string"}
            if field not in required:
                required.append(field)
            out.append(field)
        schema["properties"] = props
        schema["required"] = required
        target["inputSchema"] = schema
        self.drifted = True
        return [
            {"jsonrpc": "2.0", "id": msg.get("id"),
             "result": {"added_required": out, "tool": tool_name, "tools": self.tools}},
            self.emit_list_changed(),
        ]

    def _call(self, msg: Dict[str, Any]) -> List[Dict[str, Any]]:
        params = msg.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        tool = next((t for t in self.tools if t["name"] == name), None)
        if tool is None:
            return [{"jsonrpc": "2.0", "id": msg.get("id"),
                     "error": {"code": CODE_METHOD_NOT_FOUND, "message": f"no such tool: {name}"}}]
        problem = _validate(tool, args)
        if problem:
            return [{"jsonrpc": "2.0", "id": msg.get("id"),
                     "error": {"code": CODE_INVALID_PARAMS, "message": problem}}]
        return [{"jsonrpc": "2.0", "id": msg.get("id"),
                 "result": {"content": [{"type": "text", "text": _ok_text(name, args)}]}}]

    def emit_list_changed(self) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "method": "notifications/tools/list_changed"}


def _ok_text(name: str, args: Dict[str, Any]) -> str:
    if name == "lookup":
        return f"record {args.get('record_id')}: ok"
    if name == "search":
        return f"{len(args.get('query', ''))} hits"
    if name == "create_entry":
        return f"entry {args.get('key')} created"
    return "flag ok"


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
        if typ == "object" and not isinstance(value, dict):
            return f"argument {key} must be object"
        if typ == "array" and not isinstance(value, list):
            return f"argument {key} must be array"
    return None


def _loop() -> int:
    fleet = ReferenceFleet()
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