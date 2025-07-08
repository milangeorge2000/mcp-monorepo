"""Dataclasses shared across mcphazard modules."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Risk(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


RISK_ORDER = [Risk.CRITICAL, Risk.HIGH, Risk.MEDIUM, Risk.LOW, Risk.INFO]
RISK_WEIGHT = {Risk.CRITICAL: 25, Risk.HIGH: 10, Risk.MEDIUM: 3, Risk.LOW: 1, Risk.INFO: 0}

GRADES = ["A", "B", "C", "D", "F"]


@dataclass
class AttackClass:
    """One adversarial payload in the bundle."""
    klass: str                # machine tag, e.g. 'prompt_injection'
    name: str
    payload: str              # the exact text/args sent to the tool
    bespoke: bool = False     # False = safe generic for the schema; True = weaponized, only in --live
    risk: Risk = Risk.HIGH
    target_key: Optional[str] = None    # which tool arg key this payload targets
    note: str = ""

    def as_args(self, schema: Dict[str, Any], canary: str) -> Dict[str, Any]:
        """Produce a tools/call argument map from this payload for a tool schema."""
        return inject_payload(schema, self.payload, self.target_key, canary)


@dataclass
class ToolKinematics:
    """How one tool handled the full battery."""
    tool: str
    calls: int = 0
    echoes: int = 0               # responses that reflected the canary or payload markers
    exfil_signals: int = 0        # response contacted a URL / drew on the sandbox secret
    timeouts: int = 0
    findings: List["Finding"] = field(default_factory=list)

    @property
    def worst(self) -> Risk:
        if self.timeouts:
            return Risk.HIGH if not self.findings else self.findings[0].risk
        worst = Risk.INFO
        for f in self.findings:
            if RISK_ORDER.index(f.risk) < RISK_ORDER.index(worst):
                worst = f.risk
        return worst

    @property
    def risk_points(self) -> int:
        return sum(RISK_WEIGHT[f.risk] for f in self.findings)

    @property
    def grade(self) -> str:
        worst = self.worst
        if worst == Risk.CRITICAL:
            return "F"
        if worst == Risk.HIGH:
            return "D"
        if worst == Risk.MEDIUM:
            return "C"
        if worst == Risk.LOW:
            return "B"
        return "A"


@dataclass
class Finding:
    server: str
    tool: str
    klass: str
    risk: Risk
    title: str
    detail: str = ""
    evidence: str = ""            # truncated sanitized response excerpt
    payload: str = ""


@dataclass
class HazardReport:
    """Full red-team scan output, ready for rendering or export."""
    results: List[ToolKinematics]
    server: str = "demo"
    generated_at: str = ""
    live: bool = False
    payload_count: int = 0
    tool_count: int = 0
    source_config: Optional[str] = None

    @property
    def finding_count(self) -> int:
        return sum(len(r.findings) for r in self.results)

    @property
    def risk_counts(self) -> Dict[str, int]:
        counts = {r.value: 0 for r in RISK_ORDER}
        for res in self.results:
            for f in res.findings:
                counts[f.risk.value] += 1
        return counts

    @property
    def overall_grade(self) -> str:
        worst = "A"
        for res in self.results:
            g = res.grade
            if GRADES.index(g) >= GRADES.index(worst):
                worst = g
        return worst


def inject_payload(schema: Dict[str, Any], payload: str, target_key: Optional[str], canary: str) -> Dict[str, Any]:
    """Build a tools/call argument map that plants a payload into a tool schema.

    - If the schema declares arguments, target the first required/string key
      (or ``target_key`` if given) so the payload lands where a legit value would.
    - Otherwise fall back to a `{"input": payload}` shorthand, which many
      servers accept as their single prompt channel.
    """
    props = schema.get("properties") or {}
    required = schema.get("required") or []
    if not props and not required:
        return {"input": payload}
    key = target_key
    if key is None or key not in props:
        candidates = [k for k in required if k in props] or [k for k in props]
        key = candidates[0] if candidates else "input"
    arg = _sample(props)
    args = {k: v for k, v in arg.items() if k != key}
    args[key] = payload
    return args


def _sample(props: Dict[str, Any]) -> Dict[str, Any]:
    """Fill non-target args with inert placeholder values of the right type."""
    sample: Dict[str, Any] = {}
    for key, meta in props.items():
        typ = meta.get("type") or "string"
        if typ == "string":
            sample[key] = "placeholder"
        elif typ == "integer" or typ == "number":
            sample[key] = 0
        elif typ == "boolean":
            sample[key] = False
        elif typ == "array":
            sample[key] = []
        elif typ == "object":
            sample[key] = {}
        else:
            sample[key] = ""
    return sample