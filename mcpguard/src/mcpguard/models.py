"""Dataclasses shared across mcpguard modules."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


@dataclass
class ServerConfiguration:
    """One MCP server entry parsed from a client config file."""
    name: str
    command: List[str] = field(default_factory=list)  # stdio argv, empty for http
    url: Optional[str] = None                          # set for http(s) transport
    env: Dict[str, str] = field(default_factory=dict)
    source: str = "unknown"
    raw: Dict[str, Any] = field(default_factory=dict)


class Risk(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


RISK_WEIGHT = {
    Risk.CRITICAL: 25,
    Risk.HIGH: 10,
    Risk.MEDIUM: 3,
    Risk.LOW: 1,
    Risk.INFO: 0,
}

RISK_ORDER = [Risk.CRITICAL, Risk.HIGH, Risk.MEDIUM, Risk.LOW, Risk.INFO]


@dataclass
class Finding:
    """A single security finding attached to a server."""
    server: str
    risk: Risk
    kind: str                 # machine tag, e.g. 'remote_code' | 'dangerous_tool' | 'secret_env'
    detail: str = ""
    tool: Optional[str] = None          # tool name if finding is about a specific tool
    reference: Optional[str] = None     # e.g. tool name in config


@dataclass
class ToolAssessment:
    name: str
    risk: Risk
    matched: Optional[str] = None       # which rule matched


@dataclass
class ServerResult:
    """Security assessment for one configured server."""
    server: str
    mode: str = "unknown"               # npx | pipx | uvx | docker | python | binary | other
    remote_code: bool = False           # launcher executes code fetched from a registry
    pinned: bool = False                # target version is pinned
    live_probe: bool = False            # tools/list handshake succeeded
    probe_error: Optional[str] = None
    tools_scanned: int = 0
    findings: List[Finding] = field(default_factory=list)
    tool_assessments: List[ToolAssessment] = field(default_factory=list)
    raw_config: Dict[str, Any] = field(default_factory=dict)   # original config entry

    def _severity(self) -> Optional[Risk]:
        worst = None
        for f in self.findings:
            if worst is None or RISK_ORDER.index(f.risk) < RISK_ORDER.index(worst):
                worst = f.risk
        return worst

    @property
    def risk_points(self) -> int:
        return sum(RISK_WEIGHT[f.risk] for f in self.findings)

    @property
    def grade(self) -> str:
        worst = self._severity()
        if worst == Risk.CRITICAL:
            return "F"
        if worst == Risk.HIGH:
            return "D"
        if worst == Risk.MEDIUM:
            return "C"
        if worst == Risk.LOW:
            return "B"
        return "A"


GRADE_ORDER = ["A", "B", "C", "D", "F"]


@dataclass
class GuardReport:
    """Full audit output, ready for rendering or export."""
    results: List[ServerResult]
    generated_at: str
    source_configs: List[str] = field(default_factory=list)
    intel_bundle_version: str = "unknown"
    intel_updated_at: str = "unknown"

    @property
    def risk_counts(self) -> Dict[str, int]:
        counts = {r.value: 0 for r in RISK_ORDER}
        for res in self.results:
            for f in res.findings:
                counts[f.risk.value] += 1
        return counts

    @property
    def overall_grade(self) -> str:
        # worst grade governs the bundle
        worst = "A"
        for res in self.results:
            g = res.grade
            if GRADE_ORDER.index(g) >= GRADE_ORDER.index(worst):
                worst = g
        return worst