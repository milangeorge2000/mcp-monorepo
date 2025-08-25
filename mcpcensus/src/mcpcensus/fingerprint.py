"""Turn an mcpaudit or mcpguard JSON report (their exact ``--json`` shapes)
into an mcpcensus *fingerprint*.

The ``--share`` flags of the two tools call exactly these builders, so the
observatory's data contract is defined in one place and tested against copied
real output shapes. No tool payloads, no config files, no raw server names:
everything sensitive is salted-hashed and coarsened before it leaves the device.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

from mcpcensus import FORMAT
from mcpcensus.privacy import stable_hash

_PUB_SALT_RAND = b"mcpcensus-pub"

RISK_ORDER = ("critical", "high", "medium", "low", "info")
GRADE_ORDER = ("A", "B", "C", "D", "E", "F")


def build_context_fingerprint(audit_report: Dict[str, Any], salt: bytes, device_id: str) -> Dict[str, Any]:
    """Context-axis fingerprint. Expects mcpaudit's ``--json`` dict shape:

    servers[] = {server, ok, tools: int, schema_tokens, baseline_tokens, error}
    """
    servers = audit_report.get("servers", [])
    if not isinstance(servers, list):
        servers = []
    baseline = audit_report.get("baseline_tokens", 0) or 0
    waste = audit_report.get("dead_schema_tokens", 0) or 0

    server_models = []
    for s in servers:
        if not isinstance(s, dict):
            continue
        name = s.get("server", "") or ""
        ok = bool(s.get("ok", False))
        grade = "OK" if ok else "ERR"
        server_models.append({
            "name_hash": stable_hash(salt, name, "server"),
            "tool_count": int(s.get("tools", 0) or 0),
            "schema_tokens": int(s.get("schema_tokens", 0) or 0),
            "ok": ok,
            "sgrade": grade,
        })

    waste_pct = min(float(audit_report.get("waste_percent", 0) or 0), 100.0)
    axes = {
        "server_count": len(server_models),
        "server_models": server_models,
        "dead_tool_count": int(audit_report.get("dead_tools", 0) or 0),
        "schema_tokens": int(baseline),
        "waste_tokens": int(waste),
        "waste_percent": round(waste_pct, 1),
        "context_footprint_percent": round(float(audit_report.get("context_footprint_percent", 0) or 0), 1),
        "grade": str(audit_report.get("grade", "?")),
    }
    return _shell("context", device_id, axes, audit_report)


def build_security_fingerprint(guard_report: Dict[str, Any], salt: bytes, device_id: str) -> Dict[str, Any]:
    """Security-axis fingerprint. Expects mcpguard's ``--json`` dict shape:

    servers[] = {server, grade, mode, remote_code, pinned, tools_scanned,
                 probe_error, findings[] = {risk, kind, detail, tool}}
    """
    servers = guard_report.get("servers", [])
    if not isinstance(servers, list):
        servers = []

    risk_counts: Dict[str, int] = {k: 0 for k in RISK_ORDER}
    kind_counts: Dict[str, int] = {}
    mode_counts: Dict[str, int] = {}
    tool_hashes = []
    grades: Dict[str, int] = {g: 0 for g in GRADE_ORDER}
    remote_code_servers = 0

    for s in servers:
        if not isinstance(s, dict):
            continue
        mode = str(s.get("mode", "") or "unknown")
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
        if s.get("remote_code"):
            remote_code_servers += 1
        g = str(s.get("grade", "?"))
        if g in grades:
            grades[g] += 1
        findings = s.get("findings", [])
        if isinstance(findings, list):
            for f in findings:
                if not isinstance(f, dict):
                    continue
                risk = str(f.get("risk", "info"))
                if risk in risk_counts:
                    risk_counts[risk] += 1
                kind = str(f.get("kind", "unknown"))
                kind_counts[kind] = kind_counts.get(kind, 0) + 1
                t = f.get("tool")
                if isinstance(t, str) and t:
                    tool_hashes.append(stable_hash(salt, t, "tool"))

    axes = {
        "server_count": len(servers),
        "risk_counts": {k: v for k, v in risk_counts.items() if v},
        "kind_counts": kind_counts,
        "modes": mode_counts,
        "remote_code_servers": remote_code_servers,
        "tool_hashes": sorted(set(tool_hashes)),
        "grade_histogram": grades,
    }
    return _shell("security", device_id, axes, guard_report)


def _shell(sensor: str, device_id: str, axes: dict, source: dict) -> dict:
    """Assemble + stamp the fingerprint with submission metadata."""
    tool = None
    if isinstance(source, dict):
        for key in ("tool", "tool_version"):
            v = source.get(key)
            if isinstance(v, str) and v:
                tool = v
                break
        if tool is None:
            iv = source.get("intel_version")
            if isinstance(iv, (str, int)):
                tool = f"mcpguard@{iv}"
    return {
        "format": FORMAT,
        "device": device_id,
        "sensor": sensor,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "axes": axes,
        "meta": {"tool": tool} if tool else {},
    }


def default_share_path(prefix: str) -> str:
    """``.mcpcensus/<prefix>-census.json`` under the user home; stable dir."""
    return os.path.join(os.path.expanduser("~"), ".mcpcensus", f"{prefix}-census.json")


def write_fingerprint(fingerprint: Dict[str, Any], path: str) -> str:
    dirpath = os.path.dirname(os.path.abspath(path))
    os.makedirs(dirpath, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(fingerprint, fh, indent=2, sort_keys=True)
    return path