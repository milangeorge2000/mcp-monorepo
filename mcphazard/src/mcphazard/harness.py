"""Harness: orchestrates the red-team scan.

Pipeline: config -> spawn server under a fresh Sandbox -> enumerate tools ->
for each tool, fire the payload battery -> analyze each response -> emit
ToolKinematics + Findings. Deterministic given the same server and bundle.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from mcphazard.analyze import analyze
from mcphazard.client import call_tool, probe_tools
from mcphazard.models import Finding, HazardReport, Risk, ToolKinematics
from mcphazard.payloads import CANARY, bundled_payloads
from mcphazard.sandbox import Sandbox, make_sandbox


def scan_server(argv: Sequence[str], server_name: str = "demo",
                live: bool = False, payload_provider=None,
                timeout: float = 10.0, config: Optional[str] = None,
                inventory: Optional[Sequence[Dict[str, Any]]] = None,
                sandbox: Optional[Sandbox] = None) -> HazardReport:
    """Run the full battery against one server command (argv).

    - ``inventory``: precomputed tools list (tests reuse it; production probes).
    - ``payload_provider``: callable(live) -> List[AttackClass]; defaults to the
      built-in bundle.
    """
    sb = sandbox or make_sandbox(live=live)
    own_sandbox = sandbox is None
    payloads = (payload_provider or bundled_payloads)(live)
    argv = _abs_argv(argv)
    try:
        if inventory is None:
            inventory = probe_tools(sb, list(argv), timeout=timeout)
        results: List[ToolKinematics] = []
        for tool in inventory:
            name = tool.get("name") or "?"
            schema = tool.get("inputSchema") or {}
            kin = ToolKinematics(tool=name)
            for att in payloads:
                args = att.as_args(schema, CANARY)
                out = call_tool(sb, list(argv), name, args, timeout=timeout,
                                clear_env=_env_from_config(config))
                kin.calls += 1
                if not out.ok and out.error:
                    if "timeout" in out.error.lower():
                        kin.timeouts += 1
                        continue
                finding = analyze(
                    server_name, name, out.text, att, CANARY,
                    sandbox_secret=sb.read_secret(),
                    duration_ms=out.duration_ms,
                )
                if finding is not None:
                    kin.findings.append(finding)
                    if _echoed(finding):
                        kin.echoes += 1
                    if finding.risk == Risk.CRITICAL and "exfil" in finding.title.lower():
                        kin.exfil_signals += 1
            results.append(kin)
        return HazardReport(
            results=results,
            server=server_name,
            generated_at=datetime.now(timezone.utc).isoformat(),
            live=live,
            payload_count=len(payloads),
            tool_count=len(results),
            source_config=config,
        )
    finally:
        if own_sandbox:
            sb.cleanup()


def _abs_argv(argv: Sequence[str]) -> List[str]:
    """Make relative server paths robust to the sandbox's temp cwd.

    The server under test is spawned with ``cwd=sandbox.cwd`` for isolation, so
    any relative path in the command (e.g. ``examples/fake_toxic_server.py``)
    is resolved against the caller's working directory first.
    """
    cwd = os.getcwd()
    out: List[str] = []
    for i, tok in enumerate(argv):
        if i > 0 and not os.path.isabs(tok) and os.path.exists(os.path.join(cwd, tok)):
            tok = os.path.abspath(os.path.join(cwd, tok))
        out.append(tok)
    return out


def _echoed(finding: Finding) -> bool:
    return "echoed" in finding.title.lower() or "reflected" in finding.title.lower()


def _env_from_config(config: Optional[str]) -> Optional[Dict[str, str]]:
    """Sandbox env override for the server under test."""
    if not config:
        return None
    try:
        with open(config, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    servers = data.get("mcpServers", data)
    envs: Dict[str, str] = {}
    if isinstance(servers, dict):
        for entry in servers.values():
            if isinstance(entry, dict) and isinstance(entry.get("env"), dict):
                envs.update({k: str(v) for k, v in entry["env"].items()})
    return envs or None