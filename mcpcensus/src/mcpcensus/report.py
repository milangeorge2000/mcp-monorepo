"""Publishing layer: a monthly "State of MCP" HTML report and an SVG badge.

Consumes a ``published.json`` snapshot (never the raw registry directly), so a
public deployment can publish only the aggregates.
"""

from __future__ import annotations

import html
import json
import os
from typing import Any, Dict, Optional

GRADE_COLORS = {
    "A": "#16a34a",
    "B": "#84cc16",
    "C": "#eab308",
    "D": "#f97316",
    "E": "#ef4444",
    "F": "#b91c1c",
    "OK": "#16a34a",
    "ERR": "#ef4444",
}


def _bar(v: float, peak: float) -> str:
    width = 0.0 if peak <= 0 else max(0.0, min(100.0, (float(v) / float(peak)) * 100.0))
    return f'<div class="bar"><div class="fill" style="width:{width:.1f}%"></div></div>'


def _grade_chips(grades: Dict[str, int]) -> str:
    if not grades:
        return "<span class=muted>—</span>"
    return "".join(
        f'<span class="chip" style="background:{GRADE_COLORS.get(g, "#64748b")}">{html.escape(str(g))} {n}</span>'
        for g, n in sorted(grades.items())
    )


def _kv(label: str, value, unit: str = "") -> str:
    return f'<div class="kv"><span class="k">{html.escape(label)}</span><span class="v">{value}{unit}</span></div>'


def _stat_grid(stats: Dict[str, Any], sensor: str) -> str:
    if sensor == "context":
        kv = [
            _kv("avg schema tokens", f"{stats.get('avg_schema_tokens', 0):,}"),
            _kv("avg servers", stats.get("avg_servers", 0)),
            _kv("avg tools / server", stats.get("avg_tools_per_server", 0)),
            _kv("avg dead tools", stats.get("avg_dead_tools", 0)),
            _kv("avg waste", f"{stats.get('avg_waste_percent', 0):.1f}", "%"),
        ]
    else:
        risk = stats.get("risk_counts", {})
        kv = [
            _kv("servers observed", f"{stats.get('servers_total', 0):,}"),
            _kv("avg servers", stats.get("avg_servers", 0)),
            _kv("findings / server", stats.get("avg_findings_per_server", 0)),
            _kv("critical", risk.get("critical", 0)),
            _kv("high", risk.get("high", 0)),
            _kv("remote-code servers", stats.get("remote_code_servers", 0)),
        ]
    return f'<div class="grid">{ "".join(kv) }</div>'


def _grade_bars(grades: Dict[str, int]) -> str:
    peak = max(grades.values(), default=1) or 1
    if not grades:
        return "<p class=muted>no grades recorded</p>"
    rows = []
    for g, n in sorted(grades.items()):
        color = GRADE_COLORS.get(g, "#64748b")
        rows.append(
            f'<div class="brow"><span class="g" style="color:{color}">{html.escape(str(g))}</span>'
            f"{_bar(n, peak)}<span class='n'>{n}</span></div>"
        )
    return "".join(rows)


def compose_report(published: Dict[str, Any], title: Optional[str] = None) -> str:
    """Render one sensor's published snapshot to a full HTML report."""
    sensor = published.get("sensor", "context")
    title = title or f"State of MCP · {sensor}"
    stats = published.get("stats", {})
    series = published.get("series", {})
    cohorts = published.get("cohorts", {})
    peak_series = max(series.values(), default=1) or 1
    max_cohort = max(cohorts.values(), default=1) or 1

    series_rows = "".join(
        f'<tr><td>{html.escape(m)}</td><td class="cell"><div class="hbar">'
        f'<div style="width:{n / peak_series * 100:.1f}%"></div></div></td><td>{n}</td></tr>'
        for m, n in series.items()
    ) or '<tr><td colspan="3" class="muted">no submissions yet</td></tr>'

    cohort_rows = "".join(
        f'<tr><td><code>{html.escape(c)}</code></td><td>{n}</td><td class="cell"><div class="hbar">'
        f'<div style="width:{n / max_cohort * 100:.1f}%"></div></div></td></tr>'
        for c, n in sorted(cohorts.items())[:12]
    ) or '<tr><td colspan="3" class="muted">no cohorts</td></tr>'

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: dark; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; font:15px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
      background:#0f172a; color:#e2e8f0; }}
.wrap {{ max-width:880px; margin:0 auto; padding:32px 20px 64px; }}
h1 {{ font-size:22px; margin:0 0 4px; }}
.sub {{ color:#94a3b8; font-size:12px; margin-bottom:24px; }}
.card {{ background:#1e293b; border:1px solid #334155; border-radius:10px; padding:18px 20px; margin:14px 0; }}
.card h2 {{ margin:0 0 12px; font-size:13px; text-transform:uppercase; letter-spacing:.08em; color:#7dd3fc; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; }}
.kv .k {{ display:block; color:#94a3b8; font-size:11px; }}
.kv .v {{ font-size:20px; font-weight:700; }}
.brow {{ display:grid; grid-template-columns:30px 1fr 44px; gap:10px; align-items:center; padding:4px 0; }}
.g {{ font-weight:800; }}
.bar {{ background:#0f172a; border-radius:4px; height:12px; overflow:hidden; }}
.fill {{ background:#38bdf8; height:100%; }}
.n {{ text-align:right; color:#94a3b8; }}
.chip {{ display:inline-block; padding:2px 8px; border-radius:10px; margin-right:6px; color:#fff; font-size:12px; font-weight:700; }}
.muted {{ color:#64748b; }}
table {{ width:100%; border-collapse:collapse; }}
th,td {{ text-align:left; padding:6px 8px; border-bottom:1px solid #334155; font-size:13px; }}
.hbar {{ background:#0f172a; border-radius:3px; height:10px; overflow:hidden; width:120px; }}
.hbar div {{ background:#64748b; height:100%; }}
.cell {{ width:130px; }}
.foot {{ color:#64748b; font-size:11px; margin-top:24px; }}
</style></head><body><div class="wrap">
<h1>State of MCP · {html.escape(sensor)}</h1>
<div class="sub">mcpcensus observatory · generated {html.escape(published.get("generated_at", ""))}<br>
devices {published.get("devices_seen", 0)} · submissions {published.get("submissions_raw", 0)} ·
cohorts suppressed (k-anonymity &lt; {published.get("min_cohort", 5)}) {published.get("cohort_suppressed", 0)} ·
laplace noise {published.get("noise_scale", 0)}</div>
<div class="card"><h2>ecosystem stats</h2>{_stat_grid(stats, sensor)}</div>
<div class="card"><h2>grade distribution</h2>{_grade_bars(stats.get("grades", {}))}</div>
<div class="card"><h2>submissions by month</h2><table><tr><th>month</th><th></th><th>devices</th></tr>{series_rows}</table></div>
<div class="card"><h2>cohorts (published)</h2><table><tr><th>bucket</th><th>devices</th><th></th></tr>{cohort_rows}</table></div>
<div class="foot">Only aggregated cohorts &ge; k are published; the raw registry stays on-authority. <code>{html.escape(published.get("format", ""))}</code></div>
</div></body></html>"""


def write_report(published: Dict[str, Any], path: str, title: Optional[str] = None) -> str:
    content = compose_report(published, title)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


def compose_badge(published: Dict[str, Any], grade: Optional[str] = None) -> str:
    """Shields.io-style SVG badge: ``mcpcensus | vX.XX`` with a grade color."""
    stats = published.get("stats", {})
    grades = stats.get("grades", {})
    grade = grade or (max(grades, key=grades.get) if grades else "B")
    hashv = f"{published.get('devices_seen', 0):,} devices · {published.get('sensor', '')}"
    color = GRADE_COLORS.get(str(grade).upper()[:1], "#64748b")
    w1, w2 = _text_width("mcpcensus", 110), _text_width(hashv, 110)
    total = w1 + w2
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="20" role="img" aria-label="mcpcensus: {html.escape(hashv)}">
  <linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
  <stop offset="1" stop-opacity=".1"/></linearGradient>
  <rect width="{total}" height="20" fill="#555"/><rect x="{w1}" width="{w2}" height="20" fill="{color}"/>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,DejaVu Sans,sans-serif" font-size="11">
  <text x="{w1 / 2}" y="15" fill="#010101" fill-opacity=".3">mcpcensus</text>
  <text x="{w1 / 2}" y="14">mcpcensus</text>
  <text x="{w1 + w2 / 2}" y="15" fill="#010101" fill-opacity=".3">{html.escape(hashv)}</text>
  <text x="{w1 + w2 / 2}" y="14">{html.escape(hashv)}</text>
  </g>
</svg>"""


def _text_width(text: str, base: int = 110) -> int:
    w = base
    for ch in text:
        w += 7 if ord(ch) > 127 else 6
    return max(int(w), base)


def write_badge(published: Dict[str, Any], path: str, grade: Optional[str] = None) -> str:
    svg = compose_badge(published, grade)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(svg)
    return path