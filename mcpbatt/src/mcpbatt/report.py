"""Rendering for the generated benchmark: HTML leaderboard + JSON export."""
from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any, Dict, List

from mcpbatt.models import BattReport, ServerResult

GRADE_COLORS = {"A": "#2e7d32", "B": "#8bc34a", "C": "#f9a825", "D": "#ef6c00", "F": "#c62828"}


def render_html(report: BattReport) -> str:
    rows = []
    for r in sorted(report.results, key=lambda r: (-_overall(r.scores))):
        cols = []
        cols.append(f"<td><strong>{html.escape(r.template)}</strong><br>"
                    f"{html.escape(getattr(r, 'server', ''))}</td>")
        cols.append(f"<td style='background:{GRADE_COLORS.get(r.grade, '#666')};color:#fff'>"
                    f"{r.grade}</td>")
        for axis in ("fidelity", "discipline", "stability", "drift", "overall"):
            cols.append(f"<td>{r.scores.get(axis, 0):.0f}</td>")
        cols.append(f"<td>{r.calls_total}</td>")
        notes = "<br>".join(html.escape(n) for n in r.notes[:4])
        cols.append(f"<td>{notes}</td>")
        rows.append("<tr>" + "".join(cols) + "</tr>")

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>mcpbatt | generated leaderboard</title>
<style>
body {{ font: 14px/1.5 -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem; background: #fafafa; }}
table {{ border-collapse: collapse; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.15); }}
th, td {{ border: 1px solid #ddd; padding: .5rem .75rem; text-align: left; }}
th {{ background: #f0f0f0; }}
.badge {{ font-size: 14px; font-weight: 700; }}
</style></head><body>
<h1>mcpbatt | generated batteries</h1>
<p>Template <strong>{html.escape(report.template)}</strong> | best grade {report.best_grade}
 | {len(report.results)} run(s)</p>
<table>
<tr><th>run</th><th>grade</th><th>fidelity</th><th>discipline</th><th>stability</th>
<th>drift</th><th>overall</th><th>calls</th><th>notes</th></tr>
{''.join(rows)}
</table>
</body></html>
"""


def to_json(report: BattReport) -> Dict[str, Any]:
    return {
        "format": "mcpbatt/v1",
        "generated_at": report.generated_at or datetime.now(timezone.utc).isoformat(),
        "template": report.template,
        "best_grade": report.best_grade,
        "results": [
            {
                "template": r.template,
                "server": r.server,
                "grade": r.grade,
                "scores": r.scores,
                "calls_total": r.calls_total,
                "drift_seen": r.drift_seen,
                "notes": r.notes,
            }
            for r in report.results
        ],
    }


def _overall(scores: Dict[str, float]) -> float:
    return scores.get("overall", sum(scores.get(k, 0.0) for k in ("fidelity", "discipline", "stability", "drift")) / 4)