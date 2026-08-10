"""Run the meaningful measurement pass: fetch tools/list per server and compute
the baseline token footprint each server injects into the context window.
"""
from __future__ import annotations

from typing import List, Optional, Sequence

from mcpaudit.mcpclient import measure_server
from mcpaudit.models import MCPServerConfig, ServerMeasurement, ToolSchema
from mcpaudit.tokens import compact_schema, json_tokens


def _build_measurement(config: MCPServerConfig, raw: dict) -> ServerMeasurement:
    name = config.name
    if not raw.get("ok"):
        return ServerMeasurement(
            server=name,
            ok=False,
            error=raw.get("error"),
            schema_tokens=0,
            baseline_tokens=0,
            raw_config=config.raw,
        )

    tools: List[ToolSchema] = []
    total = 0
    for t in raw.get("tools") or []:
        compacted = compact_schema(t)
        weight = json_tokens(compacted)
        total += weight
        tools.append(
            ToolSchema(
                server=name,
                name=str(t.get("name", "")),
                description=str(t.get("description", "")),
                input_schema=t.get("inputSchema", {}),
                annotations=t.get("annotations", {}),
                raw_tokens=weight,
            )
        )
    return ServerMeasurement(
        server=name,
        ok=True,
        tools=tools,
        schema_tokens=total,
        baseline_tokens=total,
        raw_config=config.raw,
    )


def measure_servers(configs: Sequence[MCPServerConfig], timeout: float = 10.0) -> List[ServerMeasurement]:
    results: List[ServerMeasurement] = []
    for config in configs:
        raw = measure_server(config, timeout=timeout)
        results.append(_build_measurement(config, raw))
    return results