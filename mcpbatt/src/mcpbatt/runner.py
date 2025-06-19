"""The battery runner: generate, execute, mutate, score.

Orchestrates one template against one stdio server in a fresh sandbox:
1. spawn + initialize + list tools,
2. expand the template into a concrete battery,
3. execute every generated call and record the outcome,
4. if the template declares a drift spec, mutate the server via its control
   method, re-list, re-expand against the *new* schema, and replay a stale
   probe (its formerly-valid args) to see whether the change is honored.
Everything is deterministic and fully contained.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from mcpbatt.client import Client, FrameError, RpcError
from mcpbatt.expand import expand_template
from mcpbatt.fleet import CODE_INVALID_PARAMS
from mcpbatt.models import CallRecord, CallSpec, DriftSpec, ServerResult, Template
from mcpbatt.sandbox import Sandbox
from mcpbatt.scoring import score_server

FLEET_ARGV = [sys.executable, "-m", "mcpbatt.fleet"]


def _run_spec(client: Client, spec: CallSpec) -> CallRecord:
    try:
        client.call_tool(spec.tool, spec.arguments)
        return CallRecord(spec=spec, ok=True, outcome="ok", tokens=client.rec.tokens)
    except RpcError as exc:
        ok = exc.code == CODE_INVALID_PARAMS
        return CallRecord(spec=spec, ok=ok, outcome="invalid" if ok else "other-error",
                          message=exc.message, tokens=client.rec.tokens)
    except FrameError as exc:
        return CallRecord(spec=spec, ok=False, outcome="eof",
                          message=str(exc), tokens=client.rec.tokens)


def _stale_probe(template: Template, drift: DriftSpec, baseline: List[CallSpec]) -> Optional[CallSpec]:
    """Pre-drift args for the drifted tool, expected to be invalid afterwards.

    The field the drift adds is deliberately omitted, so a server honoring its
    announced change must reject it with -32602.
    """
    prev = next((c for c in baseline if c.tool == drift.tool), None)
    if prev is None:
        return None
    args = dict(prev.arguments)
    for field in drift.add_required:
        args.pop(field, None)
    return CallSpec(seq=9999, tool=drift.tool, arguments=args,
                    expect="invalid", phase="stale",
                    source="drift:stale-args")


def run_battery(template: Template, server_argv: Optional[List[str]] = None,
                timeout: float = 8.0) -> ServerResult:
    argv = server_argv if server_argv is not None else FLEET_ARGV
    server_label = " ".join(argv[-1:]) if argv else "?"

    sb = Sandbox()
    try:
        proc = sb.spawn(argv)
        from mcpbatt.client import Recorder
        rec = Recorder()
        client = Client(proc, rec, timeout=timeout)

        client.initialize()
        baseline_tools = client.list_tools()
        baseline = expand_template(template, baseline_tools, phase="baseline")

        records: List[CallRecord] = [_run_spec(client, c) for c in baseline]

        drift_seen = False
        drifted_tools: Dict[str, Any] = {}
        if template.drift is not None:
            drift = template.drift
            client.apply_drift(drift.tool, drift.add_required)
            drifted_tools_list = client.list_tools()
            drifted_tools = {"tools": drifted_tools_list}
            drift_seen = client.saw_list_changed
            stale = _stale_probe(template, drift, baseline)
            if stale is not None:
                records.append(_run_spec(client, stale))
            drifted = expand_template(template, drifted_tools_list, phase="drifted")
            records.extend(_run_spec(client, c) for c in drifted)

        return score_server(template, server_label, records, drift_seen, drifted_tools,
                            baseline_tools=baseline_tools)
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        sb.cleanup()


def run_benchmark(template: Template, timeout: float = 8.0) -> ServerResult:
    """Alias kept for CLI symmetry with the sibling tools."""
    return run_battery(template, timeout=timeout)