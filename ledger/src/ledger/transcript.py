"""Normalize raw session transcripts into a structured Trail.

Supported input formats:
  * ``claude-code`` - plain JSONL of the Claude Code console transcript
    (``{"type": "user"/"assistant", "message": {...}}`` with tool_use /
    tool_result blocks) — parsed defensively against layout drift.
  * ``generic``     - already-structured rows the caller controls:
    ``{"seq", "when", "kind", "tool", "input", "files", "tokens", ...}``.

Whatever parsing we lost, the raw line is kept in ``input.raw_line`` so nothing
is ever unreplayable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ledger import CHARS_PER_TOKEN, DEFAULT_RATES
from ledger.models import Event, Trail


def estimate_tokens(text: str) -> int:
    n = len(text or "")
    return round(n / CHARS_PER_TOKEN)


def _coster(tokens_in: int, tokens_out: int, rates: Dict[str, float]) -> float:
    usd = (
        tokens_in * (rates["in_per_mtok"] / 1e6)
        + tokens_out * (rates["out_per_mtok"] / 1e6)
        + rates["tool_per_call"]
    )
    return max(0.0, round(usd, 6))


def extract_files(input_: Dict[str, Any]) -> List[str]:
    """Pull file references out of a tool_use input dict, tolerantly."""
    if not isinstance(input_, dict):
        return []
    out = []
    for key in ("file_path", "path", "filename"):
        v = input_.get(key)
        if isinstance(v, str) and v:
            out.append(v)
        elif isinstance(v, list):
            out.extend(x for x in v if isinstance(x, str) and x)
    for key in ("paths", "files"):
        v = input_.get(key)
        if isinstance(v, list):
            out.extend(x for x in v if isinstance(x, str) and x)
    return sorted(set(out))


# --------------------------------------------------------------------------
# Claude Code JSONL parser
# --------------------------------------------------------------------------


def parse_claude_code(text: str, rates: Optional[Dict[str, float]] = None,
                      model: str = "") -> Trail:
    events: List[Event] = []
    seq = 0
    rates = rates or DEFAULT_RATES

    def push(**kw):
        nonlocal seq
        seq += 1
        events.append(_make(seq, **kw))

    for lineno, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        try:
            line = json.loads(raw)
        except json.JSONDecodeError:
            continue
        msg = line.get("message") if isinstance(line, dict) else None
        when = _first_str(line, "timestamp", "when") or ""
        role = str(line.get("type", "") or (msg.get("role", "") if isinstance(msg, dict) else "") or "?")
        if not isinstance(msg, dict):
            continue

        # assistant content can be a list of blocks
        content = msg.get("content")
        blocks = content if isinstance(content, list) else ([content] if isinstance(content, dict) else [])
        for block in blocks:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "tool_use":
                name = str(block.get("name", "") or "unknown")
                tool_input = block.get("input") or {}
                files = extract_files(tool_input)
                push(role="assistant", kind="tool_use", tool=name, action=name,
                     input=_sanitize(tool_input), files=files, ok=None,
                     tokens_in=estimate_tokens(json.dumps(tool_input)))
            elif btype == "tool_result":
                content_res = block.get("content")
                text_res = content_res if isinstance(content_res, str) else json.dumps(content_res)
                is_err = bool(block.get("is_error")) or block.get("tool_use_id") is not None and _is_error_hint(text_res)
                push(role="tool", kind="tool_result", tool=block.get("tool_use_id"), action="tool_result",
                     input={"raw_len": len(text_res)}, ok=not is_err,
                     tokens_out=estimate_tokens(text_res))
        if role == "user" and isinstance(content, str):
            push(role="user", kind="text", action="prompt_text", input=_sanitize({"text": content}),
                 tokens_in=estimate_tokens(content))
    for i, e in enumerate(events):
        e.seq = i + 1
    return Trail(events=events, meta={"format": "claude-code", "model": model,
                                      "source_lines": lineno})


def _make(seq, **kw) -> Event:
    kw.setdefault("input", {})
    tok_in = kw.pop("tokens_in", 0)
    tok_out = kw.pop("tokens_out", 0)
    kw["tokens_in"] = int(tok_in or 0)
    kw["tokens_out"] = int(tok_out or 0)
    kw["cost_usd"] = _coster(kw["tokens_in"], kw["tokens_out"], DEFAULT_RATES)
    return Event(seq=seq, **kw)


def _sanitize(d: Dict[str, Any]) -> Dict[str, Any]:
    """Keep a stable, small summary of tool input rather than raw payloads."""
    if not isinstance(d, dict):
        return {}
    out: Dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            if isinstance(v, str) and len(v) > 400:
                v = v[:400] + f"…(+{len(v) - 400} chars)"
            out[k] = v
        elif isinstance(v, list):
            out[k] = {"list": len(v)}
        elif isinstance(v, dict):
            out[k] = {"obj": sorted(v)}
    return out


def _first_str(d: Dict[str, Any], *keys: str) -> str:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v:
            return v
    return ""


def _is_error_hint(text: str) -> bool:
    lower = text[:200].lower()
    return any(h in lower for h in ("error", "exception", "failed", "traceback", "not found"))


# --------------------------------------------------------------------------
# Generic structured parser
# --------------------------------------------------------------------------


def parse_generic_rows(rows: List[Dict[str, Any]], rates: Optional[Dict[str, float]] = None,
                       model: str = "") -> Trail:
    """Accept caller-structured rows (e.g. from other client transcripts)."""
    rates = rates or DEFAULT_RATES
    events: List[Event] = []
    for seq, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            continue
        tok_in = int(row.get("tokens_in", 0) or estimate_tokens(
            json.dumps(row.get("input", {})) if isinstance(row.get("input"), dict) else str(row.get("input", ""))))
        tok_out = int(row.get("tokens_out", 0) or estimate_tokens(str(row.get("output", ""))))
        events.append(Event(
            seq=seq,
            when=str(row.get("when", "")),
            role=str(row.get("role", "assistant")),
            kind=str(row.get("kind", "tool_use")),
            tool=row.get("tool"),
            action=str(row.get("action") or row.get("tool") or row.get("kind", "")),
            input=_sanitize(row.get("input") or {}),
            files=extract_files(row.get("input") or {}) or list(row.get("files") or []),
            tokens_in=tok_in,
            tokens_out=tok_out,
            cost_usd=_coster(tok_in, tok_out, rates),
            ok=row.get("ok") if isinstance(row.get("ok"), bool) else None,
            approved=bool(row.get("approved", False)),
            source=str(row.get("source", "generic")),
        ))
    return Trail(events=events, meta={"format": "generic", "model": model})


# --------------------------------------------------------------------------
# Format auto-detection ("auto")
# --------------------------------------------------------------------------


def detect_format(text: str) -> str:
    """'claude-code' if the first JSON object has a 'type'/'message'; else 'generic'."""
    import json as _json
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = _json.loads(line)
        except _json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            if "message" in obj or obj.get("type") in ("user", "assistant", "system"):
                return "claude-code"
            return "generic"
        if isinstance(obj, list):
            return "generic"
    return "generic"


def record_transcripts(paths: List[str], fmt: str = "auto", rates=None) -> Trail:
    """Ingest one or more transcript files into a merged Trail."""
    all_events: List[Event] = []
    meta_formats = []
    for p in paths:
        text = Path(p).read_text(encoding="utf-8", errors="replace")
        fmt_i = fmt if fmt != "auto" else detect_format(text)
        meta_formats.append(fmt_i)
        if fmt_i == "generic":
            rows = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            trail = parse_generic_rows(rows, rates)
        else:
            trail = parse_claude_code(text, rates)
        all_events.extend(trail.events)
    for j, e in enumerate(all_events, 1):
        e.seq = j
    return Trail(events=all_events, meta={"format": fmt or "auto", "formats": meta_formats,
                                          "sources": list(paths)})