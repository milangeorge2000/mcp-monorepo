# mcpguard

**The security scorecard for your MCP servers.**

Every MCP server you configure gets shell, filesystem, network, and environment
access on the machine your agent runs from — often via a single one-liner that
downloads and executes code at startup. Most of that is invisible until
something bad happens.

`mcpguard` grades every server in your config **A–F** based on how it's
launched, the tool capabilities it exposes over `tools/list`, the environment it
touches, and a crowd-updatable threat-intel bundle — then hands you a shareable
`report.html` and a **hardened `mcp.json`** you can apply in seconds.

- **10-second scan.** One command, no setup changes.
- **Launcher triage.** `npx -y` / unpinned pipx / `docker run` / URL transports
  flagged before anything executes.
- **Live capability probe.** Handshakes the server, scans tool names +
  descriptions for shell/FS/write/exfil sinks. None of the tools are *run*.
- **Credential exposure.** Flags env keys that look like tokens/secrets the
  server can read.
- **Typosquat + known-bad intel.** Edit-distance vs canonical packages, plus an
  updatable bundle (the real moat — any codegen can be rewritten, a curated
  threat database can't).
- **Hardened config export.** An `mcp.json` containing only servers with no
  critical findings, plus a `_review` list of what was dropped and why.

## Quick start

```bash
pipx install mcpguard        # or: uv tool install mcpguard
mcpguard scan
```

Auto-discovers the same configs as other MCP tooling:

- `.mcp.json` in the current project, `~/.claude.json` (Claude Code)
- `~/.cursor/mcp.json`, `.cursor/mcp.json` (Cursor)
- `~/.config/opencode/opencode.json`, `opencode.json[c]`

Explicit config if you keep one elsewhere:

```bash
mcpguard scan --config ~/dotfiles/mcp.json
```

Writes `mcpguard-report.html` and opens it. For CI:

```bash
mcpguard scan --json | jq .overall_grade
mcpguard watch --json     # exit code 3 when NEW critical findings appear
```

## CLI

```
mcpguard scan   [--config PATH] [--timeout SEC] [--report PATH] [--json] [--no-live]
mcpguard watch  [--config PATH] [--json]
mcpguard intel  show | update [--from URL]
```

| command | meaning |
|---|---|
| `scan` | grade everything, write report.html |
| `watch` | baseline state in `~/.mcpguard/state.json`; alert on newly-introduced criticals |
| `intel show` | dump the loaded intel bundle |
| `intel update` | pull a signed intel bundle from your URL |

Exit codes: `0` ok, `2` no config (or bad args), `3` watch found new criticals.

## Grading model

A server's grade is set by its **highest-severity** finding:

| severity | triggers | grade |
|---|---|---|
| critical | shell/exec-capable tools, known-bad packages, exfil sinks | F |
| high | write/delete/db tools, credential-like env keys, unpinned remote code, typosquats, URL transports | D |
| medium | file-read/fetch tools, pinned-but-remote launchers, registry overrides | C |
| low | benign findings (unreachable probes) | B |
| none | clean | A |

All findings are **review triggers, not proof** — a hit means "look closer",
never "this is malware".

## Why this matters

The MCP ecosystem exploded faster than its supply-chain security caught up:
servers are installed by `npx -y pkg`, run with broad fs/env/shell access, and
security researchers are already cataloging live abuses. First-party
diagnostics and gateway controls exist; a standalone, crowdsourced *inner-loop
security scanner* for the agent's config surface was still unowned. `mcpguard`
owns that measurement layer.

## Development

mcpguard lives in the mcpaudit monorepo:

```bash
git clone https://github.com/milangeorge2000/mcpaudit.git
cd mcpaudit/mcpguard
pip install -e .[dev]
pytest
```

Try it against the bundled demo surface:

```
python examples/fake_mcp_server.py dangerous    # terminal 1 style repeater
mcpguard scan --config examples/demo-mcp.json
```

## Roadmap

- [ ] Signed intel bundles + auto-update with diff alerts
- [ ] GitHub Actions status check (`mcpguard watch` gates)
- [ ] HTTP-transport session replay for remote servers
- [ ] OpenTelemetry security metrics

## License

MIT