"""Dataclasses shared across mcpaudit modules."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MCPServerConfig:
    """One MCP server entry parsed from a client config file."""
    name: str
    command: List[str]                # argv, e.g. ["npx", "@modelcontextprotocol/server-foo"]
    env: Dict[str, str] = field(default_factory=dict)
    source: str = "unknown"           # config file path it came from
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolSchema:
    """A single tool definition fetched from an MCP server's tools/list."""
    server: str
    name: str
    description: str = ""
    input_schema: Dict[str, Any] = field(default_factory=dict)
    annotations: Dict[str, Any] = field(default_factory=dict)
    raw_tokens: int = 0               # serialized JSON size in tokens


@dataclass
class ServerMeasurement:
    """Result of measuring one server's tools/list schema."""
    server: str
    ok: bool
    error: Optional[str] = None
    tools: List[ToolSchema] = field(default_factory=list)
    schema_tokens: int = 0            # total token weight of all tool schemas
    baseline_tokens: int = 0          # tokens this server contributes per request
    raw_config: Dict[str, Any] = field(default_factory=dict)   # original config entry


@dataclass
class UsageStats:
    """How often each tool appeared in recent agent session logs."""
    calls: Dict[str, int] = field(default_factory=dict)   # full tool name -> call count
    window_days: int = 30


@dataclass
class AuditReport:
    """Full result of an audit run, ready for rendering or export."""
    servers: List[ServerMeasurement] = field(default_factory=list)
    usage: UsageStats = field(default_factory=UsageStats)
    context_limit: int = 200_000
    generated_at: str = "unknown"
    source_configs: List[str] = field(default_factory=list)

    # computed helpers
    @property
    def baseline_tokens(self) -> int:
        return sum(s.baseline_tokens for s in self.servers if s.ok)

    @property
    def context_footprint_percent(self) -> float:
        if self.context_limit <= 0:
            return 0.0
        return self.baseline_tokens / self.context_limit * 100.0

    @property
    def used_tools(self) -> set:
        return set(self.usage.calls)

    @property
    def dead_tools(self) -> List[str]:
        # tools exposed by servers (bare names) but never called in the window
        exposed = {t.name for s in self.servers if s.ok for t in s.tools}
        used = {t.split(":", 1)[-1] for t in self.used_tools}
        return sorted(exposed - used)

    @property
    def dead_schema_tokens(self) -> int:
        exposed = {t.name: t.raw_tokens for s in self.servers if s.ok for t in s.tools}
        used = {t.split(":", 1)[-1] for t in self.used_tools}
        return sum(tok for name, tok in exposed.items() if name not in used)

    @property
    def waste_percent(self) -> float:
        if self.baseline_tokens <= 0:
            return 0.0
        return self.dead_schema_tokens / self.baseline_tokens * 100.0

    @property
    def grade(self) -> str:
        wp = self.waste_percent
        if wp < 20:
            return "A"
        if wp < 35:
            return "B"
        if wp < 50:
            return "C"
        if wp < 70:
            return "D"
        return "F"