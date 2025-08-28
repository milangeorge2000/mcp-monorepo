"""Translate each provider's spend export into one shape (a RawRecord), keeping
the original line around for forensics."""

from __future__ import annotations

import csv
import io
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentspense import PROVIDERS


@dataclass
class RawRecord:
    provider: str
    model: str = ""
    when: str = ""                 # ISO-ish datetime
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    session: str = ""
    tags: List[str] = field(default_factory=list)
    source: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"provider": self.provider, "model": self.model, "when": self.when,
                "tokens_in": self.tokens_in, "tokens_out": self.tokens_out,
                "cost": round(self.cost, 6), "session": self.session,
                "tags": self.tags, "source": self.source}


def path_is_csv(path: str) -> bool:
    return path.lower().endswith((".csv", ".tsv"))


def read_export(path: str) -> List[RawRecord]:
    name = os.path.basename(path)
    if path_is_csv(path):
        return _parse_csv(path)
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    obj = _json_document(text)
    provider = _guess_provider(name, obj)
    if provider == "claude":
        return _parse_claude(obj, name)
    if provider == "cursor":
        return _parse_cursor(obj, name)
    if provider == "codex":
        return _parse_codex(obj, name)
    if provider == "opencode":
        return _parse_opencode(obj, name)
    return _parse_generic(obj, name)


def _json_document(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _guess_provider(name: str, obj: Any) -> str:
    lower = name.lower()
    if "claude" in lower or "anthropic" in lower:
        return "claude"
    if "cursor" in lower:
        return "cursor"
    if "codex" in lower:
        return "codex"
    if "opencode" in lower:
        return "opencode"
    if isinstance(obj, dict):
        blob = json.dumps(obj).lower()
        for probe, prov in (("claude", "claude"), ("cursor", "cursor"), ("codex", "codex"),
                            ("opencode", "opencode"), ("cost_bt_usd", "claude"),
                            ("cost_usd", "codex")):
            if probe in blob:
                return prov
    return "generic"


# -- claude (Anthropic cost breakdown: {api_requests: [{request, tokens_in,
#    tokens_out, cost_usd, model, team?}], ...}) -------------------------------


def _parse_claude(obj: Any, name: str) -> List[RawRecord]:
    out: List[RawRecord] = []
    for key in ("api_requests", "requests", "rows"):
        items = obj.get(key) if isinstance(obj, dict) else None
        if isinstance(items, list):
            for r in items:
                if not isinstance(r, dict):
                    continue
                out.append(RawRecord(
                    provider="claude",
                    model=str(r.get("model", "") or ""),
                    when=str(r.get("ts", r.get("when", r.get("usage_start_time", "")))),
                    tokens_in=int(r.get("tokens_in", r.get("input_tokens", 0)) or 0),
                    tokens_out=int(r.get("tokens_out", r.get("output_tokens", 0)) or 0),
                    cost=float(r.get("cost_usd", 0) or 0),
                    session=str(r.get("session_id", r.get("conversation_id", ""))),
                    tags=_tags(r),
                    source=name,
                    raw=r,
                ))
            if out:
                return out
    # flat map form
    if isinstance(obj, dict) and "tokens_in" in obj:
        return [RawRecord(provider="claude", model=str(obj.get("model", "")),
                          when=str(obj.get("when", "")),
                          tokens_in=int(obj.get("tokens_in", 0) or 0),
                          tokens_out=int(obj.get("tokens_out", 0) or 0),
                          cost=float(obj.get("cost_usd", 0) or 0),
                          session=str(obj.get("session_id", "")),
                          tags=_tags(obj), source=name, raw=obj)]
    return out


# -- cursor (monthly audit dump) -----------------------------------------------


def _parse_cursor(obj: Any, name: str) -> List[RawRecord]:
    out: List[RawRecord] = []
    items = obj.get("rows") if isinstance(obj, dict) else obj
    if isinstance(items, list):
        for r in items:
            if not isinstance(r, dict):
                continue
            out.append(RawRecord(
                provider="cursor",
                model=str(r.get("model", "") or ""),
                when=str(r.get("date", r.get("timestamp", ""))),
                tokens_in=int(r.get("tokens_in", r.get("input_tokens", 0)) or 0),
                tokens_out=int(r.get("tokens_out", r.get("output_tokens", 0)) or 0),
                cost=float(r.get("cost_usd", r.get("cost", 0)) or 0),
                session=str(r.get("session_id", "")),
                tags=_tags(r),
                source=name,
                raw=r,
            ))
    return out


def _parse_codex(obj: Any, name: str) -> List[RawRecord]:
    out: List[RawRecord] = []
    items = obj.get("sessions") if isinstance(obj, dict) else None
    if isinstance(items, list):
        for r in items:
            if not isinstance(r, dict):
                continue
            out.append(RawRecord(
                provider="codex",
                model=str(r.get("model", "") or ""),
                when=str(r.get("created_at", r.get("timestamp", ""))),
                tokens_in=int(r.get("input_tokens", r.get("tokens_in", 0)) or 0),
                tokens_out=int(r.get("output_tokens", r.get("tokens_out", 0)) or 0),
                cost=float(r.get("cost_usd", r.get("cost", 0)) or 0),
                session=str(r.get("session_id", r.get("id", ""))),
                tags=_tags(r),
                source=name,
                raw=r,
            ))
    return out


def _parse_opencode(obj: Any, name: str) -> List[RawRecord]:
    out: List[RawRecord] = []
    if isinstance(obj, list):
        for r in obj:
            if isinstance(r, dict):
                out.append(RawRecord(
                    provider="opencode",
                    model=str(r.get("model", "") or ""),
                    when=str(r.get("timestamp", r.get("when", ""))),
                    tokens_in=int(r.get("input_tokens", r.get("tokens_in", 0)) or 0),
                    tokens_out=int(r.get("output_tokens", r.get("tokens_out", 0)) or 0),
                    cost=float(r.get("cost_usd", r.get("cost", 0)) or 0),
                    session=str(r.get("session_id", r.get("session", ""))),
                    tags=_tags(r),
                    source=name,
                    raw=r,
                ))
        return out
    if isinstance(obj, dict):
        items = obj.get("sessions") or obj.get("rows") or obj.get("entries")
        if isinstance(items, list):
            return _parse_opencode(items, name)
        if "cost" in obj or "cost_usd" in obj:
            return [RawRecord(provider="opencode", model=str(obj.get("model", "")),
                              when=str(obj.get("when", obj.get("timestamp", ""))),
                              tokens_in=int(obj.get("tokens_in", 0) or 0),
                              tokens_out=int(obj.get("tokens_out", 0) or 0),
                              cost=float(obj.get("cost_usd", obj.get("cost", 0)) or 0),
                              session=str(obj.get("session_id", "")),
                              tags=_tags(obj), source=name, raw=obj)]
    return out


def _parse_generic(obj: Any, name: str) -> List[RawRecord]:
    if isinstance(obj, list):
        items = obj
    elif isinstance(obj, dict) and isinstance(obj.get("rows"), list):
        items = obj["rows"]
    else:
        items = [obj]
    out = []
    for r in items:
        if not isinstance(r, dict):
            continue
        out.append(RawRecord(
            provider=str(r.get("provider", "generic")),
            model=str(r.get("model", "") or ""),
            when=str(r.get("when", r.get("timestamp", ""))),
            tokens_in=int(r.get("tokens_in", r.get("input_tokens", 0)) or 0),
            tokens_out=int(r.get("tokens_out", r.get("output_tokens", 0)) or 0),
            cost=float(r.get("cost_usd", r.get("cost", 0)) or 0),
            session=str(r.get("session_id", r.get("session", ""))),
            tags=_tags(r),
            source=name,
            raw=r,
        ))
    return out


def _tags(r: Dict[str, Any]) -> List[str]:
    out = []
    for key in ("team", "feature", "project", "category"):
        v = r.get(key)
        if isinstance(v, str) and v:
            out.append(f"{key}:{v}")
        elif isinstance(v, dict):
            out.extend(f"{k}:{val}" for k, val in v.items() if isinstance(val, (str, int, float)))
    for key in ("tag", "tags"):
        v = r.get(key)
        if isinstance(v, str) and v:
            out.append(v)
        elif isinstance(v, list):
            out.extend(x for x in v if isinstance(x, str))
    return sorted(set(out))


def _parse_csv(path: str) -> List[RawRecord]:
    sep = "\t" if path.lower().endswith(".tsv") else ","
    out = []
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh, delimiter=sep)
        for row in reader:
            if not row:
                continue
            out.append(RawRecord(
                provider=_pick(row, "provider", "team") or "generic",
                model=_pick(row, "model"),
                when=_pick(row, "when", "date", "timestamp"),
                tokens_in=_int(row, "tokens_in", "input_tokens"),
                tokens_out=_int(row, "tokens_out", "output_tokens"),
                cost=_float(row, "cost_usd", "cost"),
                session=_pick(row, "session_id", "session"),
                tags=[v for v in (_pick(row, "team", "feature", "project") or "").split(",") if v],
                source=os.path.basename(path),
                raw=dict(row),
            ))
    return out


def _pick(row: Dict[str, str], *keys: str) -> str:
    for k in keys:
        v = row.get(k)
        if v:
            return str(v).strip()
    return ""


def _int(row: Dict[str, str], *keys: str) -> int:
    for k in keys:
        v = row.get(k)
        if v:
            try:
                return int(float(str(v).strip()))
            except ValueError:
                continue
    return 0


def _float(row: Dict[str, str], *keys: str) -> float:
    for k in keys:
        v = row.get(k)
        if v:
            try:
                return float(str(v).strip())
            except ValueError:
                continue
    return 0.0


def read_export_file_or_text(path: str) -> List[RawRecord]:
    return read_export(path)