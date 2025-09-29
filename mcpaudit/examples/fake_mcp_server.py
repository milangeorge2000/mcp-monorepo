"""A deterministic fake MCP server (stdio + newline-delimited JSON) for tests and demos.

Speaks just enough of the protocol: initialize / notifications/initialized /
tools/list. Exposes tools with purposefully verbose descriptions so mcpaudit can
report them as waste. Run it yourself:

    python examples/fake_mcp_server.py
    mcpaudit --config examples/demo-mcp.json --report demo-report.html
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "create_shipment",
        "description": (
            "Create a new shipment in the fulfillment system. Provide the origin warehouse id, "
            "destination region code, the carrier service class, insurance level, and estimated "
            "weight in kilograms. This endpoint validates stock availability, computes a rate quote, "
            "and reserves inventory for 30 minutes before yielding a tracking number. Returns a "
            "shipment object with the full lifecycle state."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "origin_warehouse": {
                    "type": "string",
                    "enum": ["SEA-1", "DFW-2", "CHI-1"],
                    "description": "Three-letter warehouse code where the goods currently sit.",
                },
                "destination_region": {"type": "string", "enum": ["US-W", "US-E", "CN", "EU"]},
                "weight_kg": {"type": "number", "minimum": 0},
                "service_class": {"type": "string", "enum": ["standard", "expedited", "next-day"]},
            },
            "required": ["origin_warehouse", "destination_region", "weight_kg"],
        },
    },
    {
        "name": "get_tracking",
        "description": "Fetch the current tracking status of an existing shipment by its id.",
        "inputSchema": {
            "type": "object",
            "properties": {"shipment_id": {"type": "string"}},
            "required": ["shipment_id"],
        },
    },
    {
        "name": "cancel_shipment",
        "description": "Cancel a shipment that has not yet been dispatched.",
        "inputSchema": {
            "type": "object",
            "properties": {"shipment_id": {"type": "string"}},
            "required": ["shipment_id"],
        },
    },
    {
        "name": "list_rates",
        "description": "List available rate quotes between two regions for a given weight.",
        "inputSchema": {
            "type": "object",
            "properties": {"origin": {"type": "string"}, "destination": {"type": "string"}},
            "required": ["origin", "destination"],
        },
    },
]


def _handle(method: str, params: Dict[str, Any], req_id: Any) -> Dict[str, Any]:
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake-shipment", "version": "0.1.0"},
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"method not found: {method}"}}


def main() -> int:
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
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
            out = _handle(msg["method"], msg.get("params") or {}, msg["id"])
            sys.stdout.write(json.dumps(out) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())