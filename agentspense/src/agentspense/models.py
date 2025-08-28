"""Ledger data model: every spend line after normalization + attribution."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SpendLine:
    provider: str
    model: str
    when: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    listed_cost: float = 0.0      # what the vendor billed (0 if absent)
    rated_cost: float = 0.0       # cost recomputed from the rate card
    session: str = ""
    team: str = ""
    feature: str = ""
    tags: List[str] = field(default_factory=list)
    source: str = ""

    @property
    def effective_cost(self) -> float:
        return self.cost

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider, "model": self.model, "when": self.when,
            "tokens_in": self.tokens_in, "tokens_out": self.tokens_out,
            "cost": round(self.cost, 6), "listed_cost": round(self.listed_cost, 6),
            "rated_cost": round(self.rated_cost, 6), "session": self.session,
            "team": self.team, "feature": self.feature, "tags": self.tags,
            "source": self.source,
        }


def team_of(tags: List[str]) -> str:
    for t in ("team:", "project:", "category:"):
        for tag in tags:
            if tag.startswith(t):
                return tag[len(t):].strip() or "unassigned"
    return tags[0] if tags else "unassigned"


def feature_of(tags: List[str]) -> str:
    for t in ("feature:", "tag:"):
        for tag in tags:
            if tag.startswith(t):
                return tag[len(t):].strip() or "unassigned"
    return "unassigned"


def normalize_team_feature(line: SpendLine) -> None:
    line.team = team_of(line.tags)
    line.feature = feature_of(line.tags)


class AgentLedger:
    """Append-only set of SpendLines; the artifact ``agentspense ledger`` reads."""

    def __init__(self, lines: Optional[List[SpendLine]] = None):
        self.lines = lines or []

    def add(self, line: SpendLine) -> None:
        self.lines.append(line)

    def to_dict(self) -> Dict[str, Any]:
        return {"format": "agentspense/ledger/v1",
                "lines": [l.to_dict() for l in self.lines]}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AgentLedger":
        return cls([_line_from_dict(l) for l in d.get("lines", []) if isinstance(l, dict)])


def _line_from_dict(d: Dict[str, Any]) -> SpendLine:
    return SpendLine(
        provider=str(d.get("provider", "")),
        model=str(d.get("model", "")),
        when=str(d.get("when", "")),
        tokens_in=int(d.get("tokens_in", 0) or 0),
        tokens_out=int(d.get("tokens_out", 0) or 0),
        cost=float(d.get("cost", 0) or 0),
        listed_cost=float(d.get("listed_cost", 0) or 0),
        rated_cost=float(d.get("rated_cost", 0) or 0),
        session=str(d.get("session", "")),
        team=str(d.get("team", "")),
        feature=str(d.get("feature", "")),
        tags=list(d.get("tags") or []),
        source=str(d.get("source", "")),
    )


def write_ledger(ledger: AgentLedger, path: str) -> str:
    import os
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ledger.to_dict(), fh, indent=2, sort_keys=True)
    return path


def read_ledger(path: str) -> AgentLedger:
    with open(path, "r", encoding="utf-8") as fh:
        return AgentLedger.from_dict(json.load(fh))