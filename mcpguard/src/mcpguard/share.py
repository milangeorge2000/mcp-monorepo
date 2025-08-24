"""``mcpguard --share``: emit an mcpcensus fingerprint for the observatory.

Same contract and privacy rules as mcpaudit's ``--share``: raw server names and
hosts are salted-hashed, details/package names never appear, only counts and
blurred structure leave the device.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

FORMAT = "mcpcensus/v1"
GRADES = tuple("ABCDEF")


def _hash(salt: bytes, value: str, tag: str) -> str:
    return hmac.new(salt, f"{tag}\x00{value}".encode("utf-8"), hashlib.sha256).hexdigest()[:24]


def _device_id(salt: bytes) -> str:
    return _hash(salt, "device-salt-install", "device")[:16]


def load_or_create_salt(path: str) -> bytes:
    try:
        with open(path, "rb") as fh:
            raw = fh.read().strip()
        if len(raw) == 16:
            return raw
    except OSError:
        pass
    salt = os.urandom(16)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(salt)
    return salt


def emit_security_fingerprint(result: Dict[str, Any], path: str) -> str:
    salt = load_or_create_salt(os.path.join(os.path.expanduser("~"), ".mcpcensus", "salt"))
    device = _device_id(salt)
    servers = result.get("servers", []) if isinstance(result.get("servers"), list) else []

    risk_counts: Dict[str, int] = {k: 0 for k in ("critical", "high", "medium", "low", "info")}
    kind_counts: Dict[str, int] = {}
    mode_counts: Dict[str, int] = {}
    tool_hashes = []
    grades = {g: 0 for g in GRADES}
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
                    tool_hashes.append(_hash(salt, t, "tool"))

    axes = {
        "server_count": len(servers),
        "risk_counts": {k: v for k, v in risk_counts.items() if v},
        "kind_counts": kind_counts,
        "modes": mode_counts,
        "remote_code_servers": remote_code_servers,
        "tool_hashes": sorted(set(tool_hashes)),
        "grade_histogram": grades,
    }
    fingerprint = {
        "format": FORMAT,
        "device": device,
        "sensor": "security",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "axes": axes,
        "meta": {"tool": "mcpguard", "version": str(result.get("intel_version", ""))},
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(fingerprint, fh, indent=2, sort_keys=True)
    return path