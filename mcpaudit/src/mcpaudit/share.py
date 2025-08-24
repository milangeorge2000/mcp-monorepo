"""``mcpaudit --share``: emit an mcpcensus fingerprint so this device acts as a
sensor in the MCP Observatory.

The fingerprint is defined by the mcpcensus *public format* (it is the data
contract, not implementation detail), so a copy lives here to keep mcpaudit
installable standalone. Every raw server name is salted-hashed before it is
written; no tool payloads and no config contents ever touch the file.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

FORMAT = "mcpcensus/v1"
_SALT = b"mcpcensus-pub"


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


def emit_context_fingerprint(result: Dict[str, Any], path: str) -> str:
    """Build + write an anonymized context-axis fingerprint from an mcpaudit summary."""
    salt = load_or_create_salt(os.path.join(os.path.expanduser("~"), ".mcpcensus", "salt"))
    device = _device_id(salt)
    servers = result.get("servers", []) if isinstance(result.get("servers"), list) else []
    axes = {
        "server_count": len(servers),
        "server_models": [
            {
                "name_hash": _hash(salt, str(s.get("server", "")), "server"),
                "tool_count": int(s.get("tools", 0) or 0),
                "schema_tokens": int(s.get("schema_tokens", 0) or 0),
                "ok": bool(s.get("ok", False)),
                "sgrade": "OK" if s.get("ok") else ("ERR" if s.get("error") else "?"),
            }
            for s in servers
            if isinstance(s, dict)
        ],
        "dead_tool_count": int(result.get("dead_tools", 0) or 0),
        "schema_tokens": int(result.get("baseline_tokens", 0) or 0),
        "waste_tokens": int(result.get("dead_schema_tokens", 0) or 0),
        "waste_percent": round(float(result.get("waste_percent", 0) or 0), 1),
        "context_footprint_percent": round(float(result.get("context_footprint_percent", 0) or 0), 1),
        "grade": str(result.get("grade", "?")),
    }
    fingerprint = {
        "format": FORMAT,
        "device": device,
        "sensor": "context",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "axes": axes,
        "meta": {"tool": "mcpaudit", "version": _version()},
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(fingerprint, fh, indent=2, sort_keys=True)
    return path


def _version() -> str:
    try:
        from mcpaudit import __version__
        return str(__version__)
    except Exception:  # pragma: no cover
        return "0"