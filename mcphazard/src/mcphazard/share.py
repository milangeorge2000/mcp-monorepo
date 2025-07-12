"""``mcphazard scan --share``: emit an mcpcensus fingerprint for the observatory.

Same privacy contract as mcpguard/mcpaudit: no tool names, no evidence text, no
raw findings — only hashed tool identifiers and counts of attack-class signals
leave the device.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone

FORMAT = "mcpcensus/v1"
GRADES = tuple("ABCDF")


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


def emit_hazard_fingerprint(report, path: str) -> str:
    salt = load_or_create_salt(os.path.join(os.path.expanduser("~"), ".mcpcensus", "salt"))
    device = _device_id(salt)
    klass_counts: dict = {}
    risk_counts: dict = {k: 0 for k in ("critical", "high", "medium", "low", "info")}
    tool_hashes = []
    grade_histogram = {g: 0 for g in GRADES}

    for res in report.results:
        tool_hashes.append(_hash(salt, res.tool, "tool"))
        grade_histogram[res.grade] = grade_histogram.get(res.grade, 0) + 1
        for f in res.findings:
            if f.risk.value in risk_counts:
                risk_counts[f.risk.value] += 1
            klass_counts[f.klass] = klass_counts.get(f.klass, 0) + 1

    axes = {
        "tool_count": len(report.results),
        "payload_count": report.payload_count,
        "finding_count": report.finding_count,
        "attack_class_counts": klass_counts,
        "risk_counts": {k: v for k, v in risk_counts.items() if v},
        "tool_hashes": sorted(set(tool_hashes)),
        "grade_histogram": grade_histogram,
        "mode": "live" if report.live else "sandbox",
    }
    fingerprint = {
        "format": FORMAT,
        "device": device,
        "sensor": "hazard",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "axes": axes,
        "meta": {"tool": "mcphazard", "version": ""},
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(fingerprint, fh, indent=2, sort_keys=True)
    return path