"""Rendering: the viral artifact — a shareable report.html, plus a ready-to-apply
slimmed MCP config (the servers/tools worth keeping).
"""
from __future__ import annotations

import datetime
import json
from typing import Any, Dict, List

from mcpaudit.models import AuditReport, MCPServerConfig


def render_html(report: AuditReport) -> str:
    """Render the whole audit as a self-contained HTML report card."""
    rows = []
    for s in report.servers:
        if not s.ok:
            rows.append(
                f"<tr class='err'><td class='mono'>{s.server}</td>"
                f"<td>unreachable</td><td>0</td><td>0.0%</td>"
                f"<td class='dim'>{s.error}</td></tr>"
            )
            continue
        pct = report.baseline_tokens and s.baseline_tokens / report.baseline_tokens * 100.0
        rows.append(
            f"<tr><td class='mono'>{s.server}</td>"
            f"<td>{len(s.tools)} tools</td>"
            f"<td>{s.baseline_tokens:,}</td>"
            f"<td>{pct:.1f}%</td>"
            f"<td class='mono dim'>{_dead_for_server(report, s.server)}</td></tr>"
        )

    used = sorted(report.used_tools)
    dead_tools = report.dead_tools

    header_js = json.dumps(
        {
            "grade": report.grade,
            "waste_pct": round(report.waste_percent, 1),
            "baseline_tokens": report.baseline_tokens,
            "context_pct": round(report.context_footprint_percent, 1),
            "dead_tools": len(dead_tools),
            "total_tools": sum(len(s.tools) for s in report.servers if s.ok),
            "window_days": report.usage.window_days,
            "generated_at": report.generated_at,
        }
    )

    slim = write_slim_config(report)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>mcpaudit — MCP context report card</title>
<style>
  :root {{ --fg:#d7e0ea; --dim:#8a96a5; --bg:#0e1420; --card:#151d2c; --line:#253047; --accent:#4fd1c5; --bad:#ff6b6b; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif; background:var(--bg); color:var(--fg); }}
  .wrap {{ max-width:980px; margin:0 auto; padding:32px 20px; }}
  h1 {{ font-size:26px; margin:0 0 4px; }}
  .sub {{ color:var(--dim); font-size:14px; margin-bottom:24px; }}
  .score {{ display:flex; gap:16px; flex-wrap:wrap; margin-bottom:28px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:18px 20px; flex:1; min-width:180px; }}
  .card .label {{ color:var(--dim); font-size:12px; text-transform:uppercase; letter-spacing:.05em; }}
  .card .value {{ font-size:28px; font-weight:700; margin-top:6px; }}
  .grab {{ margin:0 auto; padding:8px; border:0; border-radius:10px; font-weight:700; font-size:14px; cursor:pointer; background:#202b40; color:var(--fg); }}
  .grab:hover {{ background:#26334c; }}
  table {{ width:100%; border-collapse:collapse; background:var(--card); border:1px solid var(--line); border-radius:12px; overflow:hidden; }}
  th, td {{ text-align:left; padding:10px 12px; border-bottom:1px solid var(--line); font-size:13px; }}
  th {{ background:#182136; color:var(--dim); font-size:11px; text-transform:uppercase; letter-spacing:.05em; }}
  td.mono, .mono {{ font-family:ui-monospace,'Cascadia Mono','JetBrains Mono',monospace; }}
  .badge {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px; font-weight:600; }}
  .b-a {{ background:#12331f; color:#3ddc84; }} .b-b {{ background:#1b3b24; color:#66e295; }}
  .b-c {{ background:#3d3312; color:#ffd166; }} .b-d {{ background:#3d1f12; color:#ffaa5e; }}
  .b-f {{ background:#3d1212; color:#ff6b6b; }}
  .err td {{ color:var(--bad); }}
  .dim {{ color:var(--dim); }}
  pre.slim {{ background:#0b1019; border:1px solid var(--line); border-radius:12px; padding:16px; overflow-x:auto; font-family:ui-monospace,monospace; font-size:12px; line-height:1.6; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>mcpaudit · MCP context report card</h1>
  <div class="sub">generated {report.generated_at} · <span id="meta"></span></div>

  <div class="score" id="cards">
    <div class="card"><div class="label">Grade</div><div class="value"><span id="grade">—</span></div></div>
    <div class="card"><div class="label">Schema waste</div><div class="value" id="waste">—</div></div>
    <div class="card"><div class="label">Baseline / request</div><div class="value" id="baseline">—</div></div>
    <div class="card"><div class="label">Context footprint</div><div class="value" id="ctx">—</div></div>
    <div class="card"><div class="label">Dead tools</div><div class="value" id="dead">—</div></div>
  </div>

  <h2>Servers</h2>
  <table>
    <thead><tr><th>Server</th><th>Exposed</th><th>Schema tokens</th><th>Share</th><th>Never called</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>

  <h2>Recently used tools ({len(used)})</h2>
  <table>
    <thead><tr><th>Tool</th><th>Calls (last {report.usage.window_days}d)</th></tr></thead>
    <tbody>{''.join(f"<tr><td class='mono'>{t}</td><td>{report.usage.calls[t]}</td></tr>" for t in used[:100])}</tbody>
  </table>

  <h2>Slim config (apply me)</h2>
  <button class="grab" id="copy">Copy JSON</button>
  <pre class="slim" id="slim">{json.dumps(slim, indent=2)}</pre>
</div>
<script>
  const data = {header_js};
  document.getElementById('meta').textContent =
    `window: last \u00a0${{data.window_days}}d \u00b7 context limit: 200k \u00b7 figures are estimates`;
  document.getElementById('grade').innerHTML =
    `<span class="badge b-${{data.grade.toLowerCase()}}">${{data.grade}}</span>`;
  document.getElementById('waste').textContent = data.waste_pct + '%';
  document.getElementById('baseline').textContent = data.baseline_tokens.toLocaleString() + ' tok';
  document.getElementById('ctx').textContent = data.context_pct + '%';
  document.getElementById('dead').textContent = data.dead_tools + ' tools';
  document.getElementById('copy').onclick = () => {{
    const el = document.getElementById('slim');
    navigator.clipboard.writeText(el.textContent).then(() => {{
      el.style.outline = '2px solid var(--accent)';
      setTimeout(() => el.style.outline = '', 800);
    }});
  }};
</script>
</body>
</html>
"""


def _dead_for_server(report: AuditReport, server: str) -> str:
    exposed = {t.name for s in report.servers if s.ok and s.server == server for t in s.tools}
    used = {t.split(":", 1)[-1] for t in report.used_tools}
    dead = sorted(exposed - used)
    if not dead:
        return "none"
    return ", ".join(dead[:6]) + (" …" if len(dead) > 6 else "")


def _command_entry(s) -> Dict[str, Any]:
    raw = s.raw_config or {}
    cmd = raw.get("command") or raw.get("commandPath") or s.server
    return {"command": cmd}


def write_slim_config(report: AuditReport) -> Dict[str, Any]:
    """Recommend a minimal mcp.json: servers that saw real usage."""
    used_prefixes = {t.split(":", 1)[0] for t in report.used_tools if ":" in t}
    slim: Dict[str, Any] = {"mcpServers": {}}

    if used_prefixes:
        for s in report.servers:
            if s.ok and s.server in used_prefixes:
                slim["mcpServers"][s.server] = _command_entry(s)

    if not slim["mcpServers"]:
        # No usage evidence (or it referenced servers we can't map): keep everything,
        # but label it so the human knows the recommendation is unverified.
        for s in report.servers:
            if s.ok:
                slim["mcpServers"][s.server] = _command_entry(s)
        slim["_note"] = (
            "No usage logs matched a configured server; kept every healthy server. "
            "Point MCPAUDIT_LOGS at your session dir for a data-driven cut."
        )
    return slim