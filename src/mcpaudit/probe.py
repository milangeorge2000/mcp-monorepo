"""Probe recent agent session logs for which MCP tools were actually called.

Supports the JSONL transcript formats written by:
  - Claude Code        ~/.claude/projects/<project>/<session>.jsonl
  - Codex CLI          ~/.codex/sessions/<session>.jsonl
  - opencode           <project>/.opencode/sessions/**/*.jsonl

Tool names in transcripts look like `mcp__<server>__<tool>`. We normalize them
to `<server>:<tool>` so they line up with the exposed-tool set from configs.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from mcpaudit.models import UsageStats

_MCP_TOOL_RE = re.compile(r"mcp__([^_].*?)__([A-Za-z0-9_.-]+)")


def _is_mcp_tool(name: str) -> bool:
    return bool(_MCP_TOOL_RE.match(name))


def _home() -> Path:
    return Path.home()


def _scan_dirs() -> list:
    home = _home()
    return [home / ".claude" / "projects", home / ".codex" / "sessions", Path.cwd() / ".opencode" / "sessions"]


def _iter_logs(base: Path):
    if not base.exists():
        return
    for path in base.rglob("*.jsonl"):
        yield path


def _normalize(tool: str) -> str:
    # mcp__server__tool -> server:tool
    m = _MCP_TOOL_RE.match(tool)
    if m:
        return f"{m.group(1)}:{m.group(2)}"
    return tool


def _scan_file(path: Path, counts: "dict[str, int]") -> None:
    try:
        size = path.stat().st_size
        if size > 200 * 1024 * 1024:
            return
    except OSError:
        return
    try:
        handle = path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return
    with handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            _walk_record(record, counts)


def _walk_record(record: dict, counts: "dict[str, int]") -> None:
    _bump = lambda name: counts.__setitem__(  # noqa: E731
        _normalize(str(name)), counts.get(_normalize(str(name)), 0) + 1
    )

    # Common transcript shapes: message blocks / tool_use objects
    content = record.get("content")
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            name = None
            if block.get("type") == "tool_use":
                name = block.get("name")
            elif block.get("type") == "function_call":
                name = block.get("name")
            if name and _is_mcp_tool(name):
                _bump(name)
    if record.get("type") in ("tool_call", "function_call", "tool_use"):
        name = record.get("name") or record.get("tool")
        if name and _is_mcp_tool(name):
            _bump(name)


def scan_usage(window_days: int = 30) -> UsageStats:
    counts: dict[str, int] = {}
    cutoff = datetime.now() - timedelta(days=window_days)
    for base in _scan_dirs():
        for path in _iter_logs(base):
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime)
            except OSError:
                continue
            if mtime < cutoff:
                continue
            _scan_file(path, counts)
    return UsageStats(calls=counts, window_days=window_days)