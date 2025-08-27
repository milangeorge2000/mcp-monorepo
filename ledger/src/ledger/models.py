"""Trail data model + serialization."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

TrailSchema = "ledger/trail/v1"


@dataclass
class Event:
    """One normalized action on the tape."""

    seq: int
    when: str = ""
    role: str = "assistant"        # user | assistant | tool
    kind: str = "tool_use"         # see EVENT_KINDS
    tool: Optional[str] = None     # tool name for tool_use / bash
    action: str = ""               # short human label
    input: Dict[str, Any] = field(default_factory=dict)
    files: List[str] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    ok: Optional[bool] = None
    approved: bool = False         # explicitly human-approved gate action
    source: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seq": self.seq,
            "when": self.when,
            "role": self.role,
            "kind": self.kind,
            "tool": self.tool,
            "action": self.action,
            "input": self.input,
            "files": self.files,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cost_usd": self.cost_usd,
            "ok": self.ok,
            "approved": self.approved,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Event":
        return cls(
            seq=int(d.get("seq", 0)),
            when=str(d.get("when", "")),
            role=str(d.get("role", "assistant")),
            kind=str(d.get("kind", "tool_use")),
            tool=d.get("tool"),
            action=str(d.get("action", "")),
            input=d.get("input") or {},
            files=list(d.get("files") or []),
            tokens_in=int(d.get("tokens_in", 0) or 0),
            tokens_out=int(d.get("tokens_out", 0) or 0),
            cost_usd=float(d.get("cost_usd", 0.0) or 0.0),
            ok=d.get("ok") if isinstance(d.get("ok"), bool) else None,
            approved=bool(d.get("approved", False)),
            source=str(d.get("source", "unknown")),
        )


@dataclass
class Trail:
    """A full replay of one (or more) sessions."""

    events: List[Event] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> Dict[str, Any]:
        tools: Dict[str, int] = {}
        files = []
        tokens_in = sum(e.tokens_in for e in self.events)
        tokens_out = sum(e.tokens_out for e in self.events)
        cost = round(sum(e.cost_usd for e in self.events), 4)
        for e in self.events:
            if e.tool and e.kind == "tool_use":
                tools[e.tool] = tools.get(e.tool, 0) + 1
            files.extend(e.files)
        return {
            "events": len(self.events),
            "tool_calls": sum(tools.values()),
            "files_touched": len(set(files)),
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd": cost,
            "tools": dict(sorted(tools.items(), key=lambda kv: -kv[1])),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {"format": TrailSchema, "meta": self.meta,
                "events": [e.to_dict() for e in self.events]}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Trail":
        return cls(
            events=[Event.from_dict(e) for e in d.get("events", []) if isinstance(e, dict)],
            meta=dict(d.get("meta") or {}),
        )


def write_trail(trail: Trail, path: str) -> str:
    import os
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(trail.to_dict(), fh, indent=2, sort_keys=True)
    return path


def read_trail(path: str) -> Trail:
    with open(path, "r", encoding="utf-8") as fh:
        return Trail.from_dict(json.load(fh))