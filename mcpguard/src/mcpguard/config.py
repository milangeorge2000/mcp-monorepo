"""Discover and parse MCP server configs from common AI client locations.

Sources (priority order):
  1. Explicit path (--config / MCPGUARD_CONFIG)
  2. .mcp.json in the project directory (Claude Code project scope)
  3. ~/.claude.json (Claude Code user scope)
  4. ~/.cursor/mcp.json and .cursor/mcp.json (Cursor)
  5. ~/.config/opencode/opencode.json, opencode.json[c] (opencode)

Also recognizes HTTP(S) transport servers (remote_code by definition).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from mcpguard.models import ServerConfiguration


def _home() -> Path:
    return Path.home()


def _cwd() -> Path:
    return Path.cwd()


def _enabled(entry: dict) -> bool:
    return bool(entry.get("enabled", True))


def _command_from(entry: dict) -> List[str]:
    args = entry.get("args", [])
    args = [str(a) for a in args] if isinstance(args, list) else []
    if "command" in entry:
        cmd = entry["command"]
        base = list(cmd) if isinstance(cmd, (list, tuple)) else [str(cmd)]
        return [*base, *args]
    if "commandPath" in entry:
        return [str(entry["commandPath"]), *args]
    return []


def _url_from(entry: dict) -> Optional[str]:
    for key in ("url", "endpoint", "uri"):
        val = entry.get(key)
        if isinstance(val, str) and val:
            return val
    transport = entry.get("transport")
    if isinstance(transport, str) and transport.lower() == "http":
        return f"http transport (no url in config)"
    return None


def _parse_mcp_servers(blob: dict, source: str) -> List[ServerConfiguration]:
    out: List[ServerConfiguration] = []
    servers = blob.get("mcpServers") or blob.get("mcp") or {}
    if not isinstance(servers, dict):
        return out
    for name, entry in servers.items():
        if not isinstance(entry, dict) or not _enabled(entry):
            continue
        command = _command_from(entry)
        url = _url_from(entry)
        if not command and not url:
            continue
        env = {k: str(v) for k, v in (entry.get("env") or {}).items()}
        out.append(
            ServerConfiguration(
                name=name,
                command=command,
                url=url,
                env=env,
                source=source,
                raw=entry,
            )
        )
    return out


def _read_json(path: Path) -> Optional[dict]:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _read_jsonc(path: Path) -> Optional[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"(^|\s)//.*?$", "", text, flags=re.M)
    try:
        return json.loads(text)
    except ValueError:
        return None


def discover_configs(explicit_path: Optional[str] = None) -> List[Path]:
    if explicit_path:
        return [Path(explicit_path)]
    home = _home()
    cwd = _cwd()
    candidates: List[Path] = []
    for c in [cwd / ".mcp.json", cwd / ".cursor" / "mcp.json",
              home / ".claude.json", home / ".cursor" / "mcp.json",
              home / ".config" / "opencode" / "opencode.json"]:
        if c.exists():
            candidates.append(c)
    for name in ("opencode.json", "opencode.jsonc"):
        p = cwd / name
        if p.exists():
            candidates.append(p)
    return candidates


def load_servers(explicit_path: Optional[str] = None) -> List[ServerConfiguration]:
    merged: Dict[str, ServerConfiguration] = {}
    for path in discover_configs(explicit_path):
        blob = _read_jsonc(path) if path.suffix == ".jsonc" else _read_json(path)
        if blob is None:
            continue
        for server in _parse_mcp_servers(blob, str(path)):
            merged.setdefault(server.name, server)
    return list(merged.values())