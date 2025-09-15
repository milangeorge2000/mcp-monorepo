"""The audit engine: static triage on the invocation, then a live tools/list
probe. Every finding is a review trigger, never a conviction.
"""
from __future__ import annotations

import json
from typing import List, Optional, Sequence

from mcpguard import __version__
from mcpguard.intel import IntelBundle
from mcpguard.mcpclient import MCPClientError, fetch_tools
from mcpguard.models import (
    Finding,
    GuardReport,
    Risk,
    ServerConfiguration,
    ServerResult,
    ToolAssessment,
)
from mcpguard.resolve import classify


def _finding(server: str, risk: Risk, kind: str, detail: str, tool: Optional[str] = None) -> Finding:
    return Finding(server=server, risk=risk, kind=kind, detail=detail, tool=tool)


def audit_servers(configs: Sequence[ServerConfiguration], intel: IntelBundle,
                  timeout: float = 10.0, live: bool = True) -> List[ServerResult]:
    results: List[ServerResult] = []
    for config in configs:
        results.append(audit_server(config, intel, timeout=timeout, live=live))
    return results


def audit_server(config: ServerConfiguration, intel: IntelBundle, timeout: float = 10.0,
                 live: bool = True) -> ServerResult:
    invite = classify(config)
    res = ServerResult(
        server=config.name,
        mode=invite.mode,
        remote_code=invite.remote_code,
        pinned=invite.pinned,
        raw_config=config.raw,
    )

    # -- static triage ------------------------------------------------------
    if invite.mode == "http":
        res.findings.append(_finding(
            config.name, Risk.HIGH, "remote_code",
            f"HTTP transport ({invite.target}); tool code runs out of your custody", tool=invite.target,
        ))
    elif invite.remote_code:
        risk = Risk.HIGH if not invite.pinned else Risk.MEDIUM
        detail = f"launcher `{invite.mode}` fetches and executes remote code"
        if invite.auto_install:
            detail += " with auto-install"
        if not invite.pinned:
            detail += "; version not pinned"
        res.findings.append(_finding(config.name, risk, "remote_code", detail, tool=invite.target))
    for flag in invite.flags:
        if "registry override" in flag:
            res.findings.append(_finding(config.name, Risk.MEDIUM, "registry_override", flag,
                                         tool=invite.target))

    if typosq := intel.typo_squat(invite.target):
        res.findings.append(_finding(
            config.name, Risk.HIGH, "typosquat",
            f"package name is {_dist_desc(invite.target, typosq)} of canonical `{typosq}`",
            tool=invite.target,
        ))
    if warn := intel.match_package_warning(invite.target):
        res.findings.append(_finding(config.name, Risk.CRITICAL, "known_bad_package",
                                     warn, tool=invite.target))

    for key, _val in config.env.items():
        if intel.match_env(key):
            res.findings.append(_finding(
                config.name, Risk.HIGH, "secret_env",
                f"key `{key}` looks like a credential that this server can read from its own env",
            ))

    # -- live probe ---------------------------------------------------------
    if live and config.command:
        try:
            tools = fetch_tools(config, timeout=timeout)
            res.live_probe = True
            res.tools_scanned = len(tools)
            for t in tools:
                name = str(t.get("name", ""))
                desc = str(t.get("description", ""))
                blob = json.dumps(t, ensure_ascii=False).lower()
                risk = Risk.INFO
                matched = None
                cat = intel.classify_name(name) or intel.classify_description(desc)
                if cat:
                    out = {
                        "critical": Risk.CRITICAL,
                        "high": Risk.HIGH,
                        "medium": Risk.MEDIUM,
                    }[cat]
                    risk, matched = out, cat
                dom = intel.match_exfil_domain(blob)
                if dom is not None and risk != Risk.CRITICAL:
                    risk, matched = Risk.CRITICAL, f"exfil_sink:{dom}"
                res.tool_assessments.append(ToolAssessment(name=name, risk=risk, matched=matched))
            _findings_from_tools(res)
        except (MCPClientError, OSError) as exc:
            res.probe_error = str(exc)
            res.findings.append(_finding(
                config.name, Risk.LOW, "probe_unreachable",
                f"could not handshake for tools/list: {exc}",
            ))
    elif live and config.url:
        res.findings.append(_finding(
            config.name, Risk.MEDIUM, "no_probe",
            "HTTP transport: skipped live tools/list probe (no command to spawn)",
        ))

    return res


def _findings_from_tools(res: ServerResult) -> None:
    worst = Risk.INFO
    for ta in res.tool_assessments:
        if ta.risk == Risk.CRITICAL:
            worst = Risk.CRITICAL
            if ta.matched and ta.matched.startswith("exfil_sink:"):
                res.findings.append(_finding(
                    res.server, Risk.CRITICAL, "exfil_sink",
                    f"tool `{ta.name}` mentions sink domain `{ta.matched.split(':', 1)[1]}` in its schema",
                    tool=ta.name,
                ))
            else:
                res.findings.append(_finding(
                    res.server, Risk.CRITICAL, "dangerous_tool",
                    f"tool `{ta.name}` matches critical capability rule `{ta.matched}`",
                    tool=ta.name,
                ))
    if worst != Risk.CRITICAL:
        for ta in res.tool_assessments:
            if ta.risk == Risk.HIGH:
                res.findings.append(_finding(
                    res.server, Risk.HIGH, "dangerous_tool",
                    f"tool `{ta.name}` matches high-risk capability rule `{ta.matched}`",
                    tool=ta.name,
                ))


def _dist_desc(target: str, canon: str) -> str:
    from mcpguard.intel import _edit_distance
    d = _edit_distance(target.lower(), canon.lower())
    return f"{d} edit(s)"