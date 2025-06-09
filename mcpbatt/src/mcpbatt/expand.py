"""Battery expansion: turn a scenario template into concrete `tools/call`s.

This is the heart of 'a benchmark that writes its own benchmark'. Given a
template and a live server's `tools/list`, the engine synthesizes a fresh,
fully-concrete battery - every argument value is sampled from the tool's own
JSON schema, so the probes are tailored to this server, never copied from
another benchmark. Nothing here touches the network; expansion is pure.
"""
from __future__ import annotations

from typing import Any, Dict, List

from mcpbatt.models import CallSpec, Template, select_tools

_MAX_LIST_SAMPLE = 2

# A server that advertises a required string field of 10000 chars is borderline;
# only used for oversize probes.
_OVERSIZE = "x" * 1000


def _sample_for(schema: Dict[str, Any]) -> Any:
    """A small, well-typed value for a JSON-Schema property."""
    if not isinstance(schema, dict):
        return None
    t = schema.get("type")
    if isinstance(t, list):
        t = t[0] if t else None
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    if t == "integer":
        return 1
    if t == "number":
        return 1.5
    if t == "boolean":
        return False
    if t == "array":
        return []
    if t == "object":
        return {}
    if t == "string":
        return "v"
    if "anyOf" in schema and schema["anyOf"]:
        return _sample_for(schema["anyOf"][0])
    return "v"


def _wrong_for(schema: Dict[str, Any]) -> Any:
    """A value guaranteed to violate a property's declared type."""
    if not isinstance(schema, dict):
        return None
    t = schema.get("type")
    if isinstance(t, list):
        t = t[0] if t else None
    if t == "string":
        return 7
    if t in ("integer", "number", "boolean"):
        return "wrong"
    return {"kind": "wrong"}


def expand_template(template: Template, tools: List[Dict[str, Any]],
                    phase: str = "baseline") -> List[CallSpec]:
    """Expand a template against a concrete tool list into a concrete battery.

    `phase` tags the origin so the runner can separate pre/post-drift calls.
    """
    selected = select_tools(tools, template.select)
    battery: List[CallSpec] = []
    seq = 0
    for tool in selected:
        name = tool.get("name", "?")
        schema = tool.get("inputSchema") or {}
        props = schema.get("properties") or {}
        required = list(schema.get("required") or [])

        for spec in _build_for_mode(template, name, schema, props, required):
            seq += 1
            battery.append(CallSpec(
                seq=seq,
                tool=name,
                arguments=spec["args"],
                expect=spec["expect"],
                phase=phase,
                source=spec["source"],
            ))
    return battery


def _build_for_mode(template: Template, name: str, schema: Dict[str, Any],
                    props: Dict[str, Any], required: List[str]):
    mode = template.mode
    declared = list(props.keys())
    if not declared:
        declared = list(required)
    if not declared:
        declared = ["value"]

    if mode == "required":
        args = {k: _sample_for(props.get(k, {})) for k in required}
        return [{"args": args, "expect": "ok", "source": "required"}]

    if mode == "all":
        if not declared:
            return []
        return [{"args": {k: _sample_for(props.get(k, {})) for k in declared},
                 "expect": "ok", "source": "all:all"}]

    if mode == "missing":
        out = []
        for k in required:
            present = {j: _sample_for(props.get(j, {})) for j in required if j != k}
            out.append({"args": present, "expect": "invalid", "source": f"missing:{k}"})
        if not required:
            out.append({"args": {}, "expect": "ok", "source": "missing:none"})
        return out

    if mode == "wrong-type":
        if not props and not required:
            # nothing is declared; there is no field to type-violate
            return [{"args": {}, "expect": "ok", "source": "wrongtype:none"}]
        out = []
        for k in declared:
            args = {j: _sample_for(props.get(j, {})) for j in required}
            args[k] = _wrong_for(props.get(k, {}))
            out.append({"args": args, "expect": "invalid", "source": f"wrongtype:{k}"})
        return out

    if mode == "oversize":
        args = {}
        for k in declared:
            if (props.get(k, {}).get("type") or "string") == "string":
                args[k] = _OVERSIZE
            else:
                args[k] = _sample_for(props.get(k, {}))
        return [{"args": args, "expect": template.expect, "source": "oversize"}]

    # empty args
    return [{"args": {}, "expect": "invalid" if required else "ok", "source": "empty"}]