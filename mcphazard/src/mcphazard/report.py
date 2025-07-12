"""Rendering: a pentest-style HTML report plus a JSON export for CI."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from mcphazard.models import HazardReport, Risk

_BADGE = {"A": "b-a", "B": "b-b", "C": "b-c", "D": "b-d", "F": "b-f"}


def render_html(report: HazardReport) -> str:
    rows = "".join(_row(r) for r in report.results)
    cards = (
        _card("Posture", f'<span class="badge {_BADGE[report.overall_grade]}">{report.overall_grade}</span>'),
        _card("Tools", str(report.tool_count)),
        _card("Payloads", str(report.payload_count)),
        _card("Findings", str(report.finding_count)),
        _card("Critical", str(report.risk_counts["critical"])),
        _card("High", str(report.risk_counts["high"])),
    )
    header = json.dumps({
        "server": report.server, "grade": report.overall_grade, "live": report.live,
        "payloads": report.payload_count, "tools": report.tool_count,
        "findings": report.finding_count, "generated_at": report.generated_at,
        "critical": report.risk_counts["critical"], "high": report.risk_counts["high"],
    })
    mode = "LIVE-FIRE" if report.live else "SANDBOX"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>mcphazard — MCP red-team report · {report.server}</title>
<style>
  :root {{ --fg:#e2e8f0; --dim:#8a96a5; --bg:#0d1117; --card:#151b26; --line:#232c3b; --accent:#f43f5e; --ok:#3ddc84; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif; background:var(--bg); color:var(--fg); }}
  .wrap {{ max-width:980px; margin:0 auto; padding:32px 20px; }}
  h1 {{ font-size:26px; margin:0 0 4px; }}
  .sub {{ color:var(--dim); font-size:14px; margin-bottom:24px; }}
  .score {{ display:flex; gap:16px; flex-wrap:wrap; margin-bottom:28px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:18px 20px; flex:1; min-width:130px; }}
  .card .label {{ color:var(--dim); font-size:12px; text-transform:uppercase; letter-spacing:.05em; }}
  .card .value {{ font-size:26px; font-weight:700; margin-top:6px; }}
  table {{ width:100%; border-collapse:collapse; background:var(--card); border:1px solid var(--line); border-radius:12px; overflow:hidden; }}
  th, td {{ text-align:left; padding:10px 12px; border-bottom:1px solid var(--line); font-size:13px; vertical-align:top; }}
  th {{ background:#1a2230; color:var(--dim); font-size:11px; text-transform:uppercase; letter-spacing:.05em; }}
  .mono {{ font-family:ui-monospace,'Cascadia Mono',Consolas,monospace; }}
  .badge {{ display:inline-block; padding:2px 9px; border-radius:999px; font-size:13px; font-weight:700; }}
  .b-a {{ background:#0f2e1e; color:#3ddc84; }} .b-b {{ background:#16321f; color:#66e295; }}
  .b-c {{ background:#322a10; color:#ffd166; }} .b-d {{ background:#322012; color:#ffaa5e; }}
  .b-f {{ background:#321014; color:#ff6b6b; }}
  details {{ background:#0a0f17; border:1px solid var(--line); border-radius:10px; padding:8px 12px; margin:6px 0; }}
  summary {{ cursor:pointer; font-weight:600; }}
  pre {{ white-space:pre-wrap; font-family:ui-monospace,monospace; font-size:12px; color:var(--dim); margin:6px 0 0; }}
  .mode-tag {{ display:inline-block; padding:2px 9px; border-radius:999px; font-size:11px; font-weight:700; letter-spacing:.05em;
              {{ 'background:#321014; color:#ff6b6b;' if report.live else 'background:#0f2e1e; color:#3ddc84;' }} }}
</style>
</head>
<body>
<div class="wrap">
  <h1>mcphazard · MCP red-team report <span class="mode-tag">{mode}</span></h1>
  <div class="sub">target {report.server} · generated {report.generated_at}</div>

  <div class="score">{''.join(cards)}</div>

  <h2>Findings by tool</h2>
  <table>
    <thead><tr><th>Tool</th><th>Calls</th><th>Echo</th><th>Exfil</th><th>Timeout</th><th>Findings</th><th>Posture</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>

  <h2>What each signal means</h2>
  <p class="sub">Echo = server reflected the injected payload. Exfil = response carried the sink URL or sandbox secret. Timeout = server failed to answer in budget. Findings are review triggers, never convictions on their own.</p>
</div>
<script>
  const d = {header};
  document.querySelector('.score .card .value').innerHTML =
    `<span class="badge b-${{d.grade.toLowerCase()}}">${{d.grade}}</span>`;
</script>
</body>
</html>
"""


def _row(kin) -> str:
    worst = kin.grade
    rows = ""
    for f in kin.findings:
        payload = (f.payload or "—")
        rows += (f"<details><summary><b>[{f.risk.value}]</b> {_esc(f.title)} — {_esc(f.tool)}</summary>"
                 f"<pre>{_esc(f.detail)}\n\npayload: {_esc(payload)}\n\nevidence: {_esc(f.evidence)}</pre></details>")
    if not rows:
        rows = "<span class='sub'>clean</span>" if not kin.timeouts else f"<span class='sub'>{kin.timeouts} timeout(s)</span>"
    sumry = "".join(f"<div>{r.value} ×{sum(1 for x in kin.findings if x.risk == r)}</div>"
                    for r in {x.risk for x in kin.findings}) or "none"
    return (
        f"<tr><td class='mono'>{_esc(kin.tool)}</td><td>{kin.calls}</td>"
        f"<td>{kin.echoes}</td><td>{kin.exfil_signals}</td><td>{kin.timeouts}</td>"
        f"<td>{sumry}{rows}</td>"
        f"<td><span class='badge {_BADGE[worst]}'>{worst}</span></td></tr>"
    )


def _card(label: str, value: str) -> str:
    return f'<div class="card"><div class="label">{label}</div><div class="value">{value}</div></div>'


def to_json(report: HazardReport) -> Dict[str, Any]:
    return {
        "server": report.server,
        "generated_at": report.generated_at,
        "live": report.live,
        "payload_count": report.payload_count,
        "tool_count": report.tool_count,
        "overall_grade": report.overall_grade,
        "risk_counts": report.risk_counts,
        "finding_count": report.finding_count,
        "tools": [
            {
                "tool": t.tool,
                "calls": t.calls,
                "echoes": t.echoes,
                "exfil_signals": t.exfil_signals,
                "timeouts": t.timeouts,
                "grade": t.grade,
                "findings": [
                    {"klass": f.klass, "risk": f.risk.value, "title": f.title,
                     "detail": f.detail, "evidence": f.evidence, "payload": f.payload}
                    for f in t.findings
                ],
            }
            for t in report.results
        ],
    }


def _esc(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")