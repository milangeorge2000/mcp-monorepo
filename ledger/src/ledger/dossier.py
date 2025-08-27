"""Rendering: the incident dossier and the behavior diff.

The dossier is the auditable artifact — chronological action tape, cost ledger,
file surface, and whatever the policy gate flagged. The diff answers the "what
changed between attempt A and attempt B" question that makes retries legible.
"""

from __future__ import annotations

import html
import json
import os
import re
from collections import Counter
from typing import Any, Dict, List, Tuple

from ledger.models import Trail, read_trail

KIND_LABEL = {
    "tool_use": "tool call",
    "tool_result": "result",
    "text": "text",
    "edit": "edit",
    "bash": "bash",
    "think": "thinking",
    "approval": "approval",
    "state": "state",
}


def _esc(v) -> str:
    return html.escape(str(v if v is not None else ""))


def _timeline_rows(trail: Trail) -> str:
    rows = []
    for e in trail.events:
        if e.kind in ("text", "think"):
            rows.append(
                f'<tr class="{_esc(e.role)}"><td>{e.seq}</td>'
                f'<td>{_esc(e.when[:19])}</td><td>{_esc(KIND_LABEL.get(e.kind, e.kind))}</td>'
                f'<td colspan="3">{_esc(e.action)}</td></tr>'
            )
            continue
        ok = "ok" if e.ok is False else ("warn" if e.ok is None else "")
        files = ", ".join(_esc(f) for f in e.files[:4])
        rows.append(
            f'<tr class="{_esc(e.role)} {ok}"><td>{e.seq}</td><td>{_esc(e.when[:19])}</td>'
            f'<td>{_esc(KIND_LABEL.get(e.kind, e.kind))}</td>'
            f'<td>{_esc(e.tool or "")}</td><td>{files}</td>'
            f'<td class="num">{e.tokens_in and f"+{e.tokens_in:,}" or "—"} / {e.tokens_out and f"+{e.tokens_out:,}" or "—"}</td>'
            f'<td class="num">${e.cost_usd:.4f}</td></tr>'
        )
    return "".join(rows) or '<tr><td colspan="7" class="muted">empty trail</td></tr>'


def _file_surface(trail: Trail) -> str:
    counts: Counter = Counter()
    for e in trail.events:
        for f in e.files:
            counts[f] += 1
    if not counts:
        return "<p class=muted>no file references</p>"
    rows = "".join(
        f'<tr><td><code>{_esc(f)}</code></td><td>{n}</td></tr>'
        for f, n in sorted(counts.items())
    )
    return f"<table><tr><th>file</th><th>touches</th></tr>{rows}</table>"


def _tool_usage(trail: Trail) -> str:
    usage = trail.summary().get("tools", {})
    if not usage:
        return "<p class=muted>no tool calls</p>"
    peak = max(usage.values(), default=1) or 1
    rows = "".join(
        f'<tr><td><code>{_esc(t)}</code></td><td>{n}</td><td class="cell"><div class="hbar">'
        f'<div style="width:{n / peak * 100:.1f}%"></div></div></td></tr>'
        for t, n in usage.items()
    )
    return f"<table><tr><th>tool</th><th>calls</th><th></th></tr>{rows}</table>"


def _violations(violations: List[Any]) -> str:
    if not violations:
        return '<p class="ok">no policy violations</p>'
    rows = "".join(
        f'<tr><td>{_esc(v.rule)}</td><td>{_esc(v.reason)}</td>'
        f'<td>{v.seq or "—"}</td><td>{_esc(v.tool)}</td><td>{_esc(v.file)}</td></tr>'
        for v in violations
    )
    return f'<table><tr><th>rule</th><th>reason</th><th>seq</th><th>tool</th><th>file</th></tr>{rows}</table>'


def compose_dossier(trail: Trail, title: str = "Incident dossier", violations=None,
                    gate_note: str = "") -> str:
    s = trail.summary()
    cards = (
        f'<div class="card mini"><div class="k">events</div><div class="v">{s["events"]:,}</div></div>'
        f'<div class="card mini"><div class="k">tool calls</div><div class="v">{s["tool_calls"]:,}</div></div>'
        f'<div class="card mini"><div class="k">files touched</div><div class="v">{s["files_touched"]:,}</div></div>'
        f'<div class="card mini"><div class="k">tokens in/out</div><div class="v">{s["tokens_in"]:,} / {s["tokens_out"]:,}</div></div>'
        f'<div class="card mini"><div class="k">estimated cost</div><div class="v">${s["cost_usd"]:.4f}</div></div>'
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title><style>
:root {{ color-scheme: dark; }} * {{ box-sizing: border-box; }}
body {{ margin:0; font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace; background:#0f172a; color:#e2e8f0; }}
.wrap {{ max-width:1040px; margin:0 auto; padding:28px 20px 60px; }}
h1 {{ font-size:20px; margin:0 0 2px; }} .sub {{ color:#94a3b8; font-size:12px; margin-bottom:18px; }}
.minis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; }}
.card {{ background:#1e293b; border:1px solid #334155; border-radius:10px; padding:16px 18px; margin:12px 0; }}
.card.mini {{ margin:0; }} .card h2 {{ margin:0 0 10px; font-size:12px; text-transform:uppercase; letter-spacing:.08em; color:#7dd3fc; }}
.k {{ color:#94a3b8; font-size:11px; }} .v {{ font-size:18px; font-weight:700; }}
table {{ width:100%; border-collapse:collapse; font-size:12.5px; }}
th,td {{ text-align:left; padding:5px 8px; border-bottom:1px solid #334155; }}
.user {{ color:#93c5fd; }} .tool {{ color:#fdba74; }}
tr.warn td {{ background:rgba(234,179,8,.08); }} tr.ok td {{ background:rgba(239,68,68,.12); }}
.num {{ text-align:right; color:#94a3b8; }} .muted {{ color:#64748b; }} .ok {{ color:#4ade80; }}
.hbar {{ background:#0f172a; border-radius:3px; height:9px; width:110px; overflow:hidden; }}
.hbar div {{ background:#38bdf8; height:100%; }} .cell {{ width:120px; }}
.foot {{ color:#64748b; font-size:11px; margin-top:20px; }}
</style></head><body><div class="wrap">
<h1>{_esc(title)}</h1>
<div class="sub">ledger trail · {_esc(trail.meta.get("format", ""))} · sources: {_esc(", ".join(trail.meta.get("sources", [])))}</div>
<div class="minis">{cards}</div>
<div class="card"><h2>policy gate</h2>{gate_note or _violations(violations or [])}</div>
<div class="card"><h2>action tape</h2><table>
<tr><th>#</th><th>when</th><th>kind</th><th>tool</th><th>files</th><th class="num">tokens ↑/↓</th><th class="num">$</th></tr>
{_timeline_rows(trail)}</table></div>
<div class="card"><h2>tool usage</h2>{_tool_usage(trail)}</div>
<div class="card"><h2>file surface</h2>{_file_surface(trail)}</div>
<div class="foot">Cost is an estimate from a flat token rate card — agentspense does the real accounting.</div>
</div></body></html>"""


def write_dossier(trail: Trail, path: str, title: str = "Incident dossier",
                  violations=None, gate_note: str = "") -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(compose_dossier(trail, title, violations, gate_note))
    return path


# --------------------------------------------------------------------------
# Behavior diff
# --------------------------------------------------------------------------


def manifest(trail: Trail) -> Dict[str, Any]:
    """'fingerprint' of the trail: tool-call counts, file-set, tokens, cost."""
    s = trail.summary()
    return {
        "tools": s["tools"],
        "files": sorted({f for e in trail.events if e.kind == "tool_use" for f in e.files}),
        "tokens_in": s["tokens_in"],
        "tokens_out": s["tokens_out"],
        "cost_usd": s["cost_usd"],
        "events": s["events"],
    }


def diff_trails(a: Trail, b: Trail) -> Dict[str, Any]:
    ma, mb = manifest(a), manifest(b)
    tools_a, tools_b = set(ma["tools"]), set(mb["tools"])
    files_a, files_b = set(ma["files"]), set(mb["files"])
    return {
        "tools_added": sorted(tools_b - tools_a),
        "tools_removed": sorted(tools_a - tools_b),
        "tools_shared": sorted(tools_b & tools_a),
        "files_added": sorted(files_b - files_a),
        "files_removed": sorted(files_a - files_b),
        "tokens_in_delta": mb["tokens_in"] - ma["tokens_in"],
        "tokens_out_delta": mb["tokens_out"] - ma["tokens_out"],
        "cost_delta": round(mb["cost_usd"] - ma["cost_usd"], 4),
        "events_delta": mb["events"] - ma["events"],
        "a": {"events": ma["events"], "tokens_in": ma["tokens_in"], "cost": ma["cost_usd"]},
        "b": {"events": mb["events"], "tokens_in": mb["tokens_in"], "cost": mb["cost_usd"]},
    }


def format_diff(diff: Dict[str, Any]) -> str:
    def block(label, items, arrow="+"):
        if not items:
            return ""
        head = f"{label}:"
        return head + "\n" + "\n".join(f"  {arrow} {i}" for i in items) + "\n"

    out = [
        f"behavior diff  A(n={diff['a']['events']})  ->  B(n={diff['b']['events']})",
        f"  tokens in    {diff['a']['tokens_in']:,} -> {diff['b']['tokens_in']:,}  ({diff['tokens_in_delta']:+,})",
        f"  tokens out   {diff['tokens_out_delta']:+,}",
        f"  cost         ${diff['a']['cost']:.4f} -> ${diff['b']['cost']:.4f}  ({diff['cost_delta']:+.4f})",
        f"  events delta {diff['events_delta']:+,}",
        block("files added", diff["files_added"]),
        block("files removed", diff["files_removed"], "-"),
        block("tools added", diff["tools_added"]),
        block("tools removed", diff["tools_removed"], "-"),
    ]
    return "\n".join(x for x in out if x).rstrip() + "\n"


def write_diff(a: str, b: str, out: str) -> str:
    text = format_diff(diff_trails(read_trail(a), read_trail(b)))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    return out