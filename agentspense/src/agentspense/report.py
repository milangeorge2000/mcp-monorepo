"""Monthly agent P&L: one ledger, many cuts."""

from __future__ import annotations

import html
import json
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional

from agentspense import DEFAULT_BUDGET
from agentspense.models import AgentLedger


def _esc(v) -> str:
    return html.escape(str(v if v is not None else ""))


def month_totals(ledger: AgentLedger, month: str) -> Dict[str, Any]:
    lines_in = [l for l in ledger.lines if l.when.startswith(month)] if month else ledger.lines
    by_provider: Dict[str, float] = defaultdict(float)
    by_team: Dict[str, float] = defaultdict(float)
    by_feature: Dict[str, float] = defaultdict(float)
    sessions: Dict[str, float] = defaultdict(float)
    tokens_i = tokens_o = 0
    for l in lines_in:
        by_provider[l.provider] += l.cost
        by_team[l.team or "unassigned"] += l.cost
        by_feature[l.feature or "unassigned"] += l.cost
        if l.session:
            sessions[l.session] += l.cost
        tokens_i += l.tokens_in
        tokens_o += l.tokens_out
    return {
        "lines": len(lines_in),
        "cost": round(sum(l.cost for l in lines_in), 2),
        "tokens_in": tokens_i,
        "tokens_out": tokens_o,
        "by_provider": dict(by_provider),
        "by_team": dict(by_team),
        "by_feature": dict(by_feature),
        "top_sessions": dict(sorted(sessions.items(), key=lambda kv: -kv[1])[:8]),
    }


def compose_month(ledger: AgentLedger, month: str = "", title: str = "Agent P&L",
                  budgets: Optional[Dict[str, float]] = None,
                  anomalies=None, session_spikes=None) -> str:
    t = month_totals(ledger, month)
    budgets = budgets or DEFAULT_BUDGET

    def rows(d):
        peak = max(d.values(), default=0.0) or 1.0
        out = []
        for k, v in sorted(d.items(), key=lambda kv: -kv[1]):
            pct = min(100.0, (v / peak) * 100.0)
            out.append(f'<tr><td>{_esc(k)}</td><td>${v:.2f}</td>'
                       f'<td class="cell"><div class="hbar"><div style="width:{pct:.1f}%"></div></div></td></tr>')
        return "".join(out) or '<tr><td colspan="3" class="muted">no spend</td></tr>'

    def budget_grid(d, key):
        cards = []
        for name, cost in sorted(d.items(), key=lambda kv: -kv[1])[:6]:
            limit = budgets.get(key, 0)
            cls = "over" if limit and cost > limit else ""
            cards.append(f'<div class="card mini {cls}"><div class="k">{_esc(name)}</div>'
                         f'<div class="v">${cost:.2f}</div>'
                         f'<div class="sub">budget ${limit:.2f}</div></div>')
        return "".join(cards) or '<p class="muted">no spend</p>'

    alert_html = ""
    if anomalies:
        rows_a = "".join(
            f'<tr><td>{_esc(a["team"])}</td><td>{_esc(a["day"])}</td><td>${a["cost"]:.2f}</td>'
            f'<td>{a["z"]:.1f}σ</td></tr>' for a in anomalies)
        alert_html += f'<div class="card alert"><h2>spend spikes</h2><table><tr><th>team</th><th>day</th><th>spend</th><th>z</th></tr>{rows_a}</table></div>'
    if session_spikes:
        rows_s = "".join(
            f'<tr><td>{_esc(s["session"])}</td><td>{_esc(s["team"])}</td><td>${s["cost"]:.2f}</td></tr>'
            for s in session_spikes)
        alert_html += f'<div class="card alert"><h2>session overruns</h2><table><tr><th>session</th><th>team</th><th>cost</th></tr>{rows_s}</table></div>'

    cards = (
        f'<div class="card mini"><div class="k">period</div><div class="v">{_esc(month or "all")}</div></div>'
        f'<div class="card mini"><div class="k">total spend</div><div class="v">${t["cost"]:.2f}</div></div>'
        f'<div class="card mini"><div class="k">lines</div><div class="v">{t["lines"]:,}</div></div>'
        f'<div class="card mini"><div class="k">tokens in/out</div><div class="v">{t["tokens_in"]:,} / {t["tokens_out"]:,}</div></div>'
        f'<div class="card mini"><div class="k">avg $/session</div><div class="v">${(t["cost"] / max(len(t["top_sessions"]), 1)):.2f}</div></div>'
    )

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title><style>
:root {{ color-scheme: dark; }} * {{ box-sizing: border-box; }}
body {{ margin:0; font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace; background:#0f172a; color:#e2e8f0; }}
.wrap {{ max-width:1000px; margin:0 auto; padding:28px 20px 56px; }}
h1 {{ font-size:20px; margin:0 0 2px; }} .sub {{ color:#94a3b8; font-size:12px; margin-bottom:16px; }}
.minis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:10px; }}
.card {{ background:#1e293b; border:1px solid #334155; border-radius:10px; padding:15px 17px; margin:12px 0; }}
.card.mini {{ margin:0; }} .card h2 {{ margin:0 0 10px; font-size:12px; text-transform:uppercase; letter-spacing:.08em; color:#7dd3fc; }}
.card.mini.over {{ border-color:#f87171; }} .card.alert {{ border-color:#f97316; }}
.k {{ color:#94a3b8; font-size:11px; }} .v {{ font-size:18px; font-weight:700; }}
table {{ width:100%; border-collapse:collapse; font-size:12.5px; }}
th,td {{ text-align:left; padding:5px 8px; border-bottom:1px solid #334155; }}
.muted {{ color:#64748b; }}
.hbar {{ background:#0f172a; border-radius:3px; height:9px; width:110px; overflow:hidden; }}
.hbar div {{ background:#38bdf8; height:100%; }} .cell {{ width:120px; }}
.foot {{ color:#64748b; font-size:11px; margin-top:18px; }}
</style></head><body><div class="wrap">
<h1>{_esc(title)}</h1>
<div class="sub">agentspense · generated from the normalized agent spend ledger</div>
<div class="minis">{cards}</div>
{alert_html}
<div class="card"><h2>by team</h2><div class="minis">{budget_grid(t["by_team"], "team")}</div></div>
<div class="card"><h2>by provider</h2><table><tr><th>provider</th><th>cost</th><th></th></tr>{rows(t["by_provider"])}</table></div>
<div class="card"><h2>by feature</h2><table><tr><th>feature</th><th>cost</th><th></th></tr>{rows(t["by_feature"])}</table></div>
<div class="card"><h2>heavy sessions</h2><table><tr><th>session</th><th>cost</th></tr>
{''.join(f'<tr><td><code>{_esc(s)}</code></td><td>${c:.2f}</td></tr>' for s, c in t["top_sessions"].items()) or '<tr><td colspan="2" class="muted">none</td></tr>'}
</table></div>
<div class="foot">agentspense ledger · numbers are normalized across providers; listed vendor costs win where present.</div>
</div></body></html>"""


def write_month(ledger: AgentLedger, path: str, month: str = "", title: str = "Agent P&L",
                budgets=None, anomalies=None, session_spikes=None) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(compose_month(ledger, month, title, budgets, anomalies, session_spikes))
    return path


def console_summary(t: Dict[str, Any]) -> str:
    lines = [f"  total      ${t['cost']:>10.2f}", f"  lines      {t['lines']:>10,}",
             f"  tokens in  {t['tokens_in']:>10,}", f"  tokens out {t['tokens_out']:>10,}"]
    lines.append("  by team:")
    for k, v in sorted(t["by_team"].items(), key=lambda kv: -kv[1]):
        lines.append(f"    {k:<22} ${v:>8.2f}")
    return "\n".join(lines)