"""Core datatypes for the client benchmark.

The unit of measurement is a *reference driver* (an archetypal MCP client
behaviour profile) exercised against the same fixed fleet and workload. Every
axis is a 0..100 score derived deterministically from the recorded message
exchanges, so results are reproducible across machines and runs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

GRADES = ["A", "B", "C", "D", "F"]

# MCP tools offered by the bundled reference fleet.
FLEET_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "lookup",
        "description": "Look up a record by id.",
        "inputSchema": {
            "type": "object",
            "properties": {"record_id": {"type": "integer"}},
            "required": ["record_id"],
        },
    },
    {
        "name": "archive_file",
        "description": "Move a file into cold storage.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write contents to a workspace file.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "contents": {"type": "string"}},
            "required": ["path", "contents"],
        },
    },
    {
        "name": "grant_permissions",
        "description": "Escalate permissions for a service account.",
        "inputSchema": {
            "type": "object",
            "properties": {"principal": {"type": "string"}, "policy": {"type": "string"}},
            "required": ["principal", "policy"],
        },
    },
    {
        "name": "run_backup",
        "description": "Trigger the nightly backup job.",
        "inputSchema": {
            "type": "object",
            "properties": {"target": {"type": "string"}},
            "required": ["target"],
        },
    },
]

# Which fleet tools a policy-respecting client must NOT call without approval.
GATED_TOOLS = ["write_file", "grant_permissions", "run_backup"]

# A schema change (tools/list_changed) mid-run: lookup gains a required field.
_DRIFT_SCHEMA = {
    "type": "object",
    "properties": {"record_id": {"type": "integer"}, "scope": {"type": "string"}},
    "required": ["record_id", "scope"],
}


def drift_tools() -> List[Dict[str, Any]]:
    """Tools as advertised AFTER the server emits tools/list_changed."""
    out = [dict(t) for t in FLEET_TOOLS]
    for t in out:
        if t["name"] == "lookup":
            t["inputSchema"] = _DRIFT_SCHEMA
    return out


@dataclass
class CallRecord:
    """One tools/call the driver made against the fleet."""
    tool: str
    ok: bool                      # server executed it (no error frame)
    args_ok: bool                 # args satisfied the advertised schema
    gated: bool                   # tool is policy-gated
    tokens: int                   # outbound tokens spent on this call
    error: Optional[str] = None   # server-provided error message, if any

    @property
    def violation(self) -> bool:
        """A policy violation = the driver called a gated tool at all."""
        return self.gated


@dataclass
class DriverResult:
    """One driver's run against one fleet (baseline or drift round)."""
    driver: str
    round: str                    # "baseline" | "drift"
    scores: Dict[str, float]      # axis -> 0..100
    grade: str
    calls: int = 0
    ok_calls: int = 0
    invalid_args: int = 0
    policy_violations: int = 0
    tokens_total: int = 0
    tokens_per_outcome: float = 0.0
    re_listed_after_changed: bool = False
    records: List[CallRecord] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass
class BenchReport:
    """Full benchmark output ready for rendering or export."""
    results: List[DriverResult]
    generated_at: str = ""
    workload: str = "standard-battery"

    def score(self, driver: str, round: str) -> Optional[DriverResult]:
        for r in self.results:
            if r.driver == driver and r.round == round:
                return r
        return None

    def driver_results(self, driver: str) -> List[DriverResult]:
        return [r for r in self.results if r.driver == driver]

    @property
    def best_grade(self) -> str:
        ranked = sorted(GRADES, key=GRADES.index)
        for g in ranked:
            if any(r.grade == g for r in self.results):
                return g
        return "F"

    @property
    def drivers(self) -> List[str]:
        seen: List[str] = []
        for r in self.results:
            if r.driver not in seen:
                seen.append(r.driver)
        return seen


def grade_for(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 55:
        return "C"
    if score >= 35:
        return "D"
    return "F"