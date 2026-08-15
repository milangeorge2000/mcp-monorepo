# mcpaudit

**The report card for your agent's MCP context diet.**

Every MCP server you configure gets its entire `tools/list` schema injected
into your agent's context window on every single turn — before any work
happens. Most servers are used for a **fraction** of what they expose, and old
servers quietly keep costing you tokens forever.

`mcpaudit` scans your MCP configs, talks to each server, weighs the tool
schemas in tokens, cross-references how often each tool was **actually called**
in your recent session transcripts, and hands you a shareable `report.html`
with a hard grade — plus a slimmed `mcp.json` you can apply in seconds.

- **10-second scan.** One command, no changes to your setup.
- **Per-server waste.** Exact token cost each server contributes *per request*.
- **Dead-tool detection.** Tools exposed but never called in the last 30 days.
- **Slim config export.** The config that keeps your toolset lean.
- **$ / monthly cost framing.** Token waste you're paying for on every reply.

## Quick start

```bash
pipx install mcpaudit        # or: uv tool install mcpaudit
mcpaudit
```

The tool auto-discovers:

- `.mcp.json` in the current project (Claude Code project scope)
- `~/.claude.json` (Claude Code user scope)
- `~/.cursor/mcp.json`, `.cursor/mcp.json` (Cursor)
- `~/.config/opencode/opencode.json`, `opencode.json[c]` (opencode)

Pass an explicit config if you keep one elsewhere:

```bash
mcpaudit --config ~/dotfiles/mcp.json
```

`mcpaudit` writes `mcpaudit-report.html` in the current directory and opens it.
For CI or scripting use `--json`:

```bash
mcpaudit --json | jq .grade
```

## What you get

A single-page report card with:

| Metric | What it means |
|---|---|
| **Grade** | A–F from your waste percentage |
| **Schema waste** | % of schema tokens never referenced by any call |
| **Baseline / request** | tokens every server injects on every turn |
| **Dead tools** | exposed but unused in the window |
| **Slim config** | ready-to-paste `mcpServers` subset |

All figures are labeled **estimates** — the point is the *relative* picture,
not a billing-grade audit.

## How it works

```
mcp.json ──► config discovery ──► per-server stdio handshake ──► tools/list
                                      │
session transcripts ◄─── usage probe  │ (JSON-RPC, initialize → tools/list)
                                      ▼
                weigh schemas (compact JSON token estimate)
                                      ▼
        render report.html + slim mcp.json (dead tools elided)
```

### Why this matters (research notes)

- MCP server definitions consume a large share of baseline context before any
  work happens; tool-selection accuracy collapses as catalogs grow
  (43% → <14% reported at scale)· At integration scale, standalone diagnosis is
  still unowned — compression and gateway tooling exists (Headroom, Bifrost,
  Atlassian), but nobody ships a plain "what am I wasting" scanner.
- Real-world reports: token waste as high as ~90% of input during tool-heavy
  work; consolidating unused toolsets cut tens of thousands of tokens per
  request.

`mcpaudit` is that missing measurement layer: it tells you **what** to cut, in
numbers, before you touch anything.

## CLI

```
usage: mcpaudit [--config PATH] [--context N] [--window N] [--timeout SEC]
                [--report PATH] [--json] [--version]
```

| flag | default | meaning |
|---|---|---|
| `--config PATH` | auto | explicit MCP config file |
| `--context N` | 200000 | context window for footprint % |
| `--window N` | 30 | usage window in days |
| `--timeout SEC` | 10 | per-server MCP stdio timeout |
| `--report PATH` | `mcpaudit-report.html` | output path |
| `--json` | off | machine-readable summary to stdout |

Exit codes: `0` ok, `2` no config found.

## Development

```bash
git clone https://github.com/you/mcpaudit.git
cd mcpaudit
pip install -e .[dev]
pytest
```

Try it against the bundled demo server:

```bash
python examples/fake_mcp_server.py          # terminal 1
mcpaudit --config examples/demo-mcp.json    # terminal 2
```

## Roadmap

- [ ] GitHub Actions badge (`mcpaudit --json` in CI)
- [ ] Slack report posting
- [ ] OpenTelemetry metrics
- [ ] EU-AI-Act §proportionality report template

## License

MIT