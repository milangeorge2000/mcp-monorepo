"""A deliberately naive MCP server for mcphazard demos.

It's a *toxic* server: it echoes tool arguments verbatim, accepts shell
punctuation in string args, and — when asked to fetch — will happily return
whatever URL content shape you hand it. This is what a red-team harness is for:
mcphazard finds these behaviors so you find them on real servers first.

Modes (argv[1]): "toxic" | "stub". Run it through mcphazard:

    mcphazard scan --config examples/demo-mcp.json      # sandbox, non-bespoke
    mcphazard scan --command python examples/fake_toxic_server.py --live
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "echo",
        "description": "Repeat the user's text back to them (naive validator).",
        "inputSchema": {"type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"]},
    },
    {
        "name": "search",
        "description": "Search a doc corpus and return matching snippets.",
        "inputSchema": {"type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"]},
    },
    {
        "name": "fetch",
        "description": "Fetch a URL and return its content to the user.",
        "inputSchema": {"type": "object",
                        "properties": {"url": {"type": "string"}},
                        "required": ["url"]},
    },
]


def handle(method: str, params: Dict[str, Any], req_id: Any) -> Dict[str, Any]:
    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "demo-toxic-mcp", "version": "0.1.0"},
            },
        }
    if method == "notifications/initialized":
        return {"jsonrpc": "2.0"}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        return _call(params)
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"method not found: {method}"}}


def _call(params: Dict[str, Any]) -> Dict[str, Any]:
    name = (params or {}).get("name", "")
    args = (params or {}).get("arguments") or {}
    text = str(args.get("text") or args.get("query") or args.get("url") or "")
    if name == "echo":
        return _ok({"echoed": text})
    if name == "search":
        # naive: returns the query verbatim as a "result" — a real leakage signal
        # when the query contains an injected payload.
        return _ok({"results": [{"snippet": f"Snippet for: {text}"}]})
    if name == "fetch":
        # toxic fetch: just echoes the URL back as if it fetched the target —
        # exactly the shape mcphazard's exfil signal watches for.
        return _ok({"content": f"Fetched {text}"})
    return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": f"unknown tool: {name}"}}


def _ok(payload: Dict[str, Any], req_id: Any = 1) -> Dict[str, Any]:
    return {
        "jsonrpc": "2.0", "id": req_id,
        "result": {"content": [{"type": "text", "text": json.dumps(payload)}]},
    }


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        method = msg.get("method")
        if method == "notifications/initialized":
            continue
        if msg.get("id") is not None:
            out = handle(method, msg.get("params") or {}, msg.get("id"))
            sys.stdout.write(json.dumps(out) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())