"""Discover and parse MCP server configs from common AI client locations.

Supported sources (checked in priority order):
  1. Explicit path via --config / MCPAUDIT_CONFIG
  2. .mcp.json in the current project directory (Claude Code project scope)
  3. ~/.claude.json (Claude Code user scope)
  4. ~/.cursor/mcp.json (Cursor project scope)
  5. .cursor/mcp.json in the current project directory
  6. ~/.config/opencode/opencode.json (opencode user scope)
  7. opencode.json / opencode.jsonc in the current project directory
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from mcpaudit.models import MCPServerConfig


def _home() -> Path:
    return Path.home()


def _cwd() -> Path:
    return Path.cwd()


def _enabled(entry: dict) -> bool:
    return bool(entry.get("enabled", True))


def _command_from(entry: dict) -> Optional[List[str]]:
    """Build an argv list from 'command'/'commandPath' plus 'args'."""
    args = entry.get("args", [])
    args = [str(a) for a in args] if isinstance(args, list) else []
    if "command" in entry:
        cmd = entry["command"]
        base = list(cmd) if isinstance(cmd, (list, tuple)) else [str(cmd)]
        return [*base, *args]
    if "commandPath" in entry:
        return [str(entry["commandPath"]), *args]
    return None


def _parse_mcp_servers(blob: dict, source: str) -> List[MCPServerConfig]:
    out: List[MCPServerConfig] = []
    servers = blob.get("mcpServers") or blob.get("mcp") or {}
    if not isinstance(servers, dict):
        return out
    for name, entry in servers.items():
        if not isinstance(entry, dict) or not _enabled(entry):
            continue
        command = _command_from(entry)
        if not command:
            continue
        env = {k: str(v) for k, v in (entry.get("env") or {}).items()}
        out.append(
            MCPServerConfig(
                name=name,
                command=command,
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
    """Minimal JSONC support: strip // and /* */ comments before parsing."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    import re

    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"(^|\s)//.*?$", "", text, flags=re.M)
    try:
        return json.loads(text)
    except ValueError:
        return None


def _candidate_paths() -> List[Path]:
    home = _home()
    cwd = _cwd()
    candidates: List[Path] = []

    project_scoped = [cwd / ".mcp.json", cwd / ".cursor" / "mcp.json"]
    user_scoped = [
        home / ".claude.json",
        home / ".cursor" / "mcp.json",
        home / ".config" / "opencode" / "opencode.json",
    ]

    # Prefer project scope over user scope.
    for c in [*project_scoped, *user_scoped]:
        if c.exists():
            candidates.append(c)

    # opencode project configs
    for name in ("opencode.json", "opencode.jsonc"):
        p = cwd / name
        if p.exists():
            candidates.append(p)

    return candidates


def discover_configs(explicit_path: Optional[str] = None) -> List[Path]:
    """Return the config files we will parse, in order."""
    if explicit_path:
        return [Path(explicit_path)]
    return _candidate_paths()


def load_servers(explicit_path: Optional[str] = None) -> List[MCPServerConfig]:
    """Parse all discovery candidates and return merged, deduped server configs."""
    merged: Dict[str, MCPServerConfig] = {}

    for path in discover_configs(explicit_path):
        blob = _read_jsonc(path) if path.suffix == ".jsonc" else _read_json(path)
        if blob is None:
            continue
        for server in _parse_mcp_servers(blob, str(path)):
            merged.setdefault(server.name, server)

    return list(merged.values())