"""Token estimation utilities.

We intentionally avoid pulling in tiktoken or similar heavy dependencies at
runtime. For schema-size measurement, a character-based approximation
(~4 chars/token) is more than adequate — the goal is relative waste, and the
report card always labels figures as estimates.
"""
from __future__ import annotations

import json
from typing import Any, Dict


def estimate_tokens(text: str) -> int:
    """Rough token count: ~4 chars per token, minimum 1."""
    return max(1, len(text) // 4)


def json_tokens(obj: Dict[str, Any], sort_keys: bool = True) -> int:
    """Token weight of a stable JSON serialization of an object."""
    dumped = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=sort_keys)
    return estimate_tokens(dumped)


def compact_schema(tool: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize the tool definition the way an agent client would load it.

    Clients inject {name, description, inputSchema, annotations} into context;
    we mirror the essentials so the token weight is comparable.
    """
    out: Dict[str, Any] = {
        "name": tool.get("name", ""),
        "description": tool.get("description", ""),
        "inputSchema": tool.get("inputSchema", tool.get("input_schema", {})),
    }
    if tool.get("annotations"):
        out["annotations"] = tool["annotations"]
    return out