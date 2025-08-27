"""Policy gate: check a Trail against a JSON rule-set.

Rules file (``policy.json``):

.. code-block:: json

    {
      "deny": [
        {"tool": "bash_command"},
        {"tool": "bash_*", "file": "src/**/prod/**"},
        {"file_pattern": "*.secret"},
        {"input_has": "rm -rf"},
        {"tool": "shell_write"}
      ],
      "require_human_approval": ["bash_*", "GitTool_push", "deploy_*"],
      "allow": [{"tool": "Read"}],
      "budget_tokens_in": 200000,
      "budget_tokens_out": 50000,
      "max_cost_usd": 10.0
    }

Evaluation order per event: ``allow`` (skip) -> ``deny`` (violation) ->
``require_human_approval`` (warning unless the event is marked approved).
Budgets act as cumulative gates over the whole trail.
"""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from ledger.models import Trail


@dataclass
class Violation:
    rule: str
    reason: str
    seq: int = 0
    tool: str = ""
    file: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"rule": self.rule, "reason": self.reason, "seq": self.seq,
                "tool": self.tool, "file": self.file}


@dataclass
class GateResult:
    ok: bool
    violations: List[Violation] = field(default_factory=list)
    budgets: Dict[str, Any] = field(default_factory=dict)
    scanned_events: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "violations": [v.to_dict() for v in self.violations],
            "budgets": self.budgets,
            "scanned_events": self.scanned_events,
        }


def load_policy(path: str) -> Dict[str, Any]:
    if not Path(path).exists():
        raise FileNotFoundError(f"policy file not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, dict):
        raise ValueError("policy file must be a JSON object")
    return raw


def _match_glob(pattern: str, value: str) -> bool:
    if not value:
        return False
    return fnmatch.fnmatch(value, pattern) or fnmatch.fnmatch(
        _norm(value), _norm(pattern))


def _norm(v: str) -> str:
    return v.replace("\\", "/")


def _matches(rule: Dict[str, Any], event: Any, seq: int) -> str:
    """Return a human reason if ``event`` matches ALL constraints of ``rule``."""

    def _tool_ok() -> bool:
        pat = rule.get("tool")
        return pat is None or bool(event.tool and _match_glob(str(pat), event.tool))

    def _file_ok() -> bool:
        pat = rule.get("file", rule.get("file_pattern"))
        if pat is None:
            return True
        return any(_match_glob(str(pat), _norm(f)) for f in event.files)

    def _input_ok() -> bool:
        ih = rule.get("input_has")
        return ih is None or (isinstance(ih, str) and ih in json.dumps(event.input, default=str))

    if not _tool_ok() or not _file_ok() or not _input_ok():
        return ""
    bits = []
    if "tool" in rule and event.tool:
        bits.append(f"tool {rule['tool']!r} matched {event.tool!r}")
    if "file" in rule and event.files:
        bits.append(f"file {rule['file']!r} matched {', '.join(event.files)}")
    if "input_has" in rule:
        bits.append(f"input contains {rule['input_has']!r}")
    return "; ".join(bits)


def gate(trail: Trail, policy: Dict[str, Any]) -> GateResult:
    deny = policy.get("deny", []) or []
    allow = policy.get("allow", []) or []
    approvals = policy.get("require_human_approval", []) or []

    violations: List[Violation] = []
    for e in trail.events:
        if e.kind != "tool_use":
            continue
        tool = e.tool or ""
        if any(_matches(a, e, e.seq) for a in _allowed(allow)):
            continue
        for rule in deny:
            if not isinstance(rule, dict):
                continue
            reason = _matches(rule, e, e.seq)
            if reason:
                violations.append(Violation("deny", reason, e.seq, tool,
                                            _norm(e.files[0]) if e.files else ""))
                break
        if any(fnmatch.fnmatch(_norm2(tool), _norm2(p)) for p in approvals):
            if not e.approved:
                violations.append(Violation("require_human_approval",
                                            f"{tool!r} needs human approval", e.seq, tool,
                                            _norm(e.files[0]) if e.files else ""))

    # budgets
    budgets: Dict[str, Any] = {}
    ok = not violations
    if "budget_tokens_in" in policy or "budget_tokens_out" in policy or "max_cost_usd" in policy:
        tin = sum(e.tokens_in for e in trail.events)
        tout = sum(e.tokens_out for e in trail.events)
        cost = round(sum(e.cost_usd for e in trail.events), 4)
        limits = [("budget_tokens_in", tin, "input tokens"),
                  ("budget_tokens_out", tout, "output tokens")]
        for key, used, label in limits:
            limit = policy.get(key)
            if limit is not None:
                over = used > int(limit)
                budgets[f"{key}_used"] = used
                budgets[f"{key}_limit"] = limit
                if over:
                    violations.append(Violation("budget", f"{label} {used:,} > {int(limit):,}", 0, "", ""))
        if "max_cost_usd" in policy:
            limit = float(policy["max_cost_usd"])
            budgets["cost_usd_used"] = cost
            budgets["cost_usd_limit"] = limit
            if cost > limit:
                violations.append(Violation("budget", f"cost ${cost:.2f} > ${limit:.2f}", 0, "", ""))

    return GateResult(ok=not violations, violations=violations,
                      budgets=budgets, scanned_events=sum(1 for e in trail.events if e.kind == "tool_use"))


def budgets_over(budgets: Dict[str, Any]) -> bool:
    return any("_used" in k and v is not None and budgets.get(f"{k}_limit", None) is not None
               and v > budgets[f"{k}_limit"] for k, v in budgets.items())


def _allowed(allow: List[Any]) -> List[Dict[str, Any]]:
    return [a for a in allow if isinstance(a, dict)]


def _norm2(v: str) -> str:
    return (v or "").replace("\\", "/")