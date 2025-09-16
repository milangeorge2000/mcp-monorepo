"""Rendering: a shareable security scorecard (report.html) plus a ready-to-apply
hardened mcp.json (only servers with no critical findings).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from mcpguard.models import GuardReport, Risk, ServerResult

_BADGE = {"A": "b-a", "B": "b-b", "C": "b-c", "D": "b-d", "F": "b-f"}


def render_html(report: GuardReport, sources: List[str]) -> str:
    rows = []
    for res in report.results:
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for f in res.findings:
            counts[f.risk.value] += 1
        top = sorted(res.findings, key=lambda f: ["critical", "high", "medium", "low", "info"].index(f.risk.value))[:2]
        detail = "; ".join(f.detail for f in top) or (res.probe_error or "ok")
        rows.append(_row(res, counts, detail))

    cards = (
        _card("Grade", f'<span class="badge {_BADGE[report.overall_grade]}">{report.overall_grade}</span>', "overall"),
        _card("Servers", str(len(report.results)), "count"),
        _card("Critical", str(report.risk_counts["critical"]), "critical"),
        _card("High", str(report.risk_counts["high"]), "high"),
        _card("Medium", str(report.risk_counts["medium"]), "medium"),
    )
    hardened = write_hardened_config(report)
    header_js = json.dumps({
        "grade": report.overall_grade,
        "servers": len(report.results),
        "critical": report.risk_counts["critical"],
        "high": report.risk_counts["high"],
        "medium": report.risk_counts["medium"],
        "intel": report.intel_bundle_version,
        "generated_at": report.generated_at,
    })

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>mcpguard — MCP server security scorecard</title>
<style>
  :root {{ --fg:#e2e8f0; --dim:#8a96a5; --bg:#0d1117; --card:#151b26; --line:#232c3b; --accent:#f59e0b; --bad:#ff6b6b; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif; background:var(--bg); color:var(--fg); }}
  .wrap {{ max-width:980px; margin:0 auto; padding:32px 20px; }}
  h1 {{ font-size:26px; margin:0 0 4px; }}
  .sub {{ color:var(--dim); font-size:14px; margin-bottom:24px; }}
  .score {{ display:flex; gap:16px; flex-wrap:wrap; margin-bottom:28px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:18px 20px; flex:1; min-width:150px; }}
  .card .label {{ color:var(--dim); font-size:12px; text-transform:uppercase; letter-spacing:.05em; }}
  .card .value {{ font-size:26px; font-weight:700; margin-top:6px; }}
  table {{ width:100%; border-collapse:collapse; background:var(--card); border:1px solid var(--line); border-radius:12px; overflow:hidden; }}
  th, td {{ text-align:left; padding:10px 12px; border-bottom:1px solid var(--line); font-size:13px; vertical-align:top; }}
  th {{ background:#1a2230; color:var(--dim); font-size:11px; text-transform:uppercase; letter-spacing:.05em; }}
  .mono {{ font-family:ui-monospace,'Cascadia Mono','JetBrains Mono',Consolas,monospace; }}
  .badge {{ display:inline-block; padding:2px 9px; border-radius:999px; font-size:13px; font-weight:700; }}
  .b-a {{ background:#0f2e1e; color:#3ddc84; }} .b-b {{ background:#16321f; color:#66e295; }}
  .b-c {{ background:#322a10; color:#ffd166; }} .b-d {{ background:#322012; color:#ffaa5e; }}
  .b-f {{ background:#321014; color:#ff6b6b; }}
  .rid {{ font-size:11px; color:var(--dim); }}
  .grab {{ margin:0; padding:8px 14px; border:0; border-radius:10px; font-weight:700; font-size:14px; cursor:pointer; background:#202b40; color:var(--fg); }}
  .grab:hover {{ background:#26334c; }}
  pre.hard {{ background:#0a0f17; border:1px solid var(--line); border-radius:12px; padding:16px; overflow-x:auto; font-family:ui-monospace,monospace; font-size:12px; line-height:1.6; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>mcpguard · MCP server security scorecard</h1>
  <div class="sub">generated {report.generated_at} · intel {report.intel_bundle_version} · <a id="sources" style="color:var(--dim)" href="#">{len(sources)}</a> config file(s)</div>

  <div class="score">
    {''.join(cards)}
  </div>

  <h2>Per-server</h2>
  <table>
    <thead><tr><th>Server</th><th>Launch</th><th>Remote code</th><th>Pinned</th><th>Tools probed</th><th>Findings</th><th>Grade</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>

  <h2>Hardened config (apply me)</h2>
  <button class="grab" id="copy">Copy JSON</button>
  <pre class="hard" id="hard">{json.dumps(hardened, indent=2)}</pre>

  <h2>Rules</h2>
  <p class="rid">Critical = shell/exec-capable tools, known-bad packages, exfil sinks · High = write/db/delete tools, credential-like env keys, unpinned remote code · Medium = file-read/fetch tools, registry overrides · A–F by highest-severity finding. All findings are review triggers, not proof.</p>
</div>
<script>
  const data = {header_js};
  const g = data.grade;
  document.querySelector('.score .card .value').innerHTML =
    `<span class="badge b-${{g.toLowerCase()}}">${{g}}</span>`;
  document.querySelectorAll('.card .value')[1].textContent = data.servers;
  document.querySelectorAll('.card .value')[2].textContent = data.critical;
  document.querySelectorAll('.card .value')[3].textContent = data.high;
  document.querySelectorAll('.card .value')[4].textContent = data.medium;
  document.getElementById('copy').onclick = () => {{
    const el = document.getElementById('hard');
    navigator.clipboard.writeText(el.textContent).then(() => {{
      el.style.outline = '2px solid var(--accent)';
      setTimeout(() => el.style.outline = '', 800);
    }});
  }};
</script>
</body>
</html>
"""


def _row(res: ServerResult, counts: Dict[str, int], detail: str) -> str:
    parts = []
    for label, key in (("critical", Risk.CRITICAL), ("high", Risk.HIGH), ("medium", Risk.MEDIUM), ("low", Risk.LOW)):
        if counts[label]:
            parts.append(f"{label} {counts[label]}")
    sumry = ", ".join(parts) or "none"
    mode = res.mode + ("+pinned" if res.pinned else "")
    remote = "yes" if res.remote_code else "no"
    return (
        f"<tr><td class='mono'>{res.server}</td>"
        f"<td class='mono'>{mode}</td><td>{remote}</td>"
        f"<td>{'yes' if res.pinned else 'no'}</td>"
        f"<td>{res.tools_scanned}</td>"
        f"<td>{sumry}<div class='rid'>{detail}</div></td>"
        f"<td><span class='badge {_BADGE[res.grade]}'>{res.grade}</span></td></tr>"
    )


def _card(label: str, value: str, key: str) -> str:
    return (
        f'<div class="card" data-key="{key}"><div class="label">{label}</div>'
        f'<div class="value">{value}</div></div>'
    )


def _cmd_entry(res: ServerResult) -> Dict[str, Any]:
    raw = res.raw_config or {}
    if raw.get("command"):
        return {"command": raw["command"], "args": raw.get("args", [])}
    if raw.get("commandPath"):
        return {"commandPath": raw["commandPath"], "args": raw.get("args", [])}
    if raw.get("url"):
        return {"url": raw["url"]}
    return {"command": res.server}


def write_hardened_config(report: GuardReport) -> Dict[str, Any]:
    """Emit an mcp.json containing only servers with no critical findings,
    plus a `_review` list describing what was dropped and why."""
    hardened: Dict[str, Any] = {"mcpServers": {}}
    review: List[Dict[str, str]] = []
    for res in report.results:
        if res.grade == "F":
            reasons = "; ".join(f.detail for f in res.findings if f.risk == Risk.CRITICAL)
            review.append({
                "server": res.server,
                "reason": f"critical findings: {reasons}",
                "fix": "pin the package version, drop shell-capable tools, or remove the server",
            })
            continue
        hardened["mcpServers"][res.server] = _cmd_entry(res)
    if review:
        hardened["_review"] = review
    return hardened