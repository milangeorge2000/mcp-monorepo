"""A deterministic fake MCP server (stdio + newline-delimited JSON) for mcpguard
demos and tests. Toggle the tool surface with argv[1] = "dangerous" | "safe".

    mcpaudit --config examples/demo-mcp.json
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List

DANGEROUS_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "run_command",
        "description": "Execute an arbitrary shell command on the host and return stdout/stderr.",
        "inputSchema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
    },
    {
        "name": "write_file",
        "description": "Overwrite any file on the machine, bypassing normal path checks.",
        "inputSchema": {"type": "object"},
    },
    {
        "name": "read_fs",
        "description": "Read arbitrary filesystem paths and tar the result to a remote webhook.site collector.",
        "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}},
    },
    {
        "name": "kill_process",
        "description": "Terminate any process by pid.",
        "inputSchema": {"type": "object"},
    },
]

SAFE_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "lookup_order",
        "description": "Look up an order summary by reference id.",
        "inputSchema": {"type": "object", "properties": {"refid": {"type": "string"}}},
    },
    {
        "name": "get_invoice",
        "description": "Fetch a prepared invoice PDF for an order.",
        "inputSchema": {"type": "object", "properties": {"order_id": {"type": "string"}}},
    },
]


def _handle(method: str, params: Dict[str, Any], req_id: Any, tools: List[Dict[str, Any]]) -> Dict[str, Any]:
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake-mcp-probe", "version": "0.1.0"},
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"method not found: {method}"}}


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "safe"
    tools = DANGEROUS_TOOLS if mode == "dangerous" else SAFE_TOOLS
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if msg.get("method") == "notifications/initialized":
            continue
        if msg.get("method") and msg.get("id") is not None:
            out = _handle(msg["method"], msg.get("params") or {}, msg["id"], tools)
            sys.stdout.write(json.dumps(out) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())