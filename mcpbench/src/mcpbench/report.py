"""Leaderboard rendering: HTML report + JSON export.

The HTML is a ranked table (grade badge per driver, per-axis bars, transcript
notes). JSON is the machine-readable payload for CI or the census pipeline.
"""
from __future__ import annotations

from typing import Any, Dict, List

from mcpbench.models import BenchReport, GRADES


def _esc(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _badge(grade: str) -> str:
    colors = {"A": "#1a7f37", "B": "#9a6700", "C": "#bf8700", "D": "#cf222e", "F": "#cf222e"}
    return f"<span class='badge' style='background:{colors.get(grade,'#57606a')}'>{grade}</span>"


def _rows(report: BenchReport) -> str:
    rows: List[str] = []
    for driver in report.drivers:
        res = report.score(driver, "baseline")
        if res is None:
            continue
        s = res.scores
        bars = "".join(
            f"<div class='axis'><span>{k}</span>"
            f"<div class='bar'><i style='width:{s.get(k,0)}%'></i></div><b>{s.get(k,0):.0f}</b></div>"
            for k in ("conformance", "policy", "validity", "economy", "drift")
        )
        notes = "".join(f"<li>{_esc(n)}</li>" for n in res.notes) or "<li>clean</li>"
        rows.append(
            f"<tr><td class='mono'>{_esc(driver)}</td><td>{_badge(res.grade)}</td>"
            f"<td>{res.calls} / {res.ok_calls}</td><td>{res.policy_violations}</td>"
            f"<td>{res.invalid_args}</td><td>{res.tokens_total}</td>"
            f"<td>{res.tokens_per_outcome}</td><td>{bars}<ul class='notes'>{notes}</ul></td></tr>"
        )
    return "".join(rows)


def render_html(report: BenchReport) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>mcpbench · client leaderboard</title>
<style>
body{{font-family:ui-monospace,Menlo,Consolas,monospace;margin:2rem;color:#24292f;background:#fff}}
h1{{font-size:1.3rem}} h2{{font-size:1rem;margin-top:2rem}}
table{{border-collapse:collapse;width:100%;margin-top:1rem}}
th,td{{border-bottom:1px solid #d8dee4;padding:.5rem .6rem;text-align:left;vertical-align:top}}
th{{background:#f6f8fa;font-size:.75rem;text-transform:uppercase}}
.mono{{font-family:inherit}} .badge{{color:#fff;border-radius:3px;padding:.1rem .45rem;font-weight:700}}
.axis{{display:flex;align-items:center;gap:.35rem;font-size:.68rem;color:#57606a;white-space:nowrap}}
.bar{{width:56px;height:6px;background:#eaeef2;border-radius:3px;overflow:hidden}}
.bar i{{display:block;height:100%;background:#0969da}}
.notes{{margin:.35rem 0 0;padding-left:1rem;font-size:.72rem;color:#57606a}}
.meta{{color:#57606a;font-size:.75rem}}
</style></head><body>
<h1>mcpbench — benchmark the clients, not the servers</h1>
<div class="meta">workload: <b>{_esc(report.workload)}</b> · generated {_esc(report.generated_at)} ·
drivers ranked best-first · each against the same reference fleet</div>
<table>
<tr><th>driver</th><th>grade</th><th>calls / ok</th><th>policy viol.</th><th>invalid args</th>
<th>tokens</th><th>tokens/outcome</th><th>axes</th><th>notes</th></tr>
{_rows(report)}
</table>
<h2>How to read this</h2>
<ul>
<li><b>conformance</b> — did it initialize before talking, and speak well-formed JSON-RPC 2.0?</li>
<li><b>policy</b> — did it consult the gate and refuse gated tools?</li>
<li><b>validity</b> — did its calls satisfy the advertised schema?</li>
<li><b>economy</b> — outbound tokens per useful outcome (cohort-relative).</li>
<li><b>drift</b> — when the fleet announced tools/list_changed, did it re-list and adapt?</li>
</ul>
<p class="meta">Scores are deterministic per driver+fleet; they benchmark client *behaviour*,
not a specific agent binary. Findings are review triggers, never verdicts.</p>
</body></html>"""


def to_json(report: BenchReport) -> Dict[str, Any]:
    return {
        "tool": "mcpbench",
        "workload": report.workload,
        "generated_at": report.generated_at,
        "grades": {g: report.best_grade == g for g in GRADES},
        "best_grade": report.best_grade,
        "drivers": [
            {
                "driver": r.driver,
                "round": r.round,
                "grade": r.grade,
                "scores": {k: v for k, v in r.scores.items()},
                "calls": r.calls,
                "ok_calls": r.ok_calls,
                "invalid_args": r.invalid_args,
                "policy_violations": r.policy_violations,
                "tokens_total": r.tokens_total,
                "tokens_per_outcome": r.tokens_per_outcome,
                "re_listed_after_changed": r.re_listed_after_changed,
                "notes": r.notes,
            }
            for r in report.results
        ],
    }