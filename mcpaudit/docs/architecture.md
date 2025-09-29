# Architecture

`mcpaudit` is deliberately small: three data flows (config in, measure, probe)
converge on one report object, then two outputs (HTML, slim JSON). No async, no
database, no framework. Only the Python standard library at runtime; pytest for
tests.

## Pipeline

```
┌─────────────┐   ┌──────────────┐   ┌──────────────┐
│  config.py  │──▶│  measure.py  │──▶│ AuditReport  │──▶ report.html
│  discovery  │   │  (stdio)     │   │  (models.py) │──▶ slim mcp.json
└─────────────┘   └──────────────┘   └──────────────┘
                        ▲                    ▲
                  mcpclient.py         probe.py
                  (JSON-RPC)          (session logs)
```

### Module map

| module | responsibility |
|---|---|
| `cli.py` | arg parsing, orchestration, `--json`, browser open |
| `config.py` | discover + parse `.mcp.json`, `~/.claude.json`, Cursor, opencode configs; normalizes `command`/`commandPath`+`args` → argv, honors `enabled` |
| `models.py` | dataclasses: `MCPServerConfig`, `ToolSchema`, `ServerMeasurement`, `UsageStats`, `AuditReport` (+ computed grade/waste properties) |
| `mcpclient.py` | minimal MCP stdio client: `initialize`, `notifications/initialized`, `tools/list`; error-tolerant `measure_server` |
| `measure.py` | per-server measurement orchestration → `ServerMeasurement` |
| `tokens.py` | char-based token estimator (~4 chars/token), stable JSON serialization, client-shaped schema compaction |
| `probe.py` | scans session JSONL transcripts for `mcp__server__tool` calls, normalizes to `server:tool` |
| `report.py` | renders self-contained HTML report card + `write_slim_config` recommender |
| `_webbrowser_open.py` | thin indirection so CLI is testable without launching a browser |

## Design decisions

1. **Char-count token estimate.** Pulling tiktoken per-architecture weights would
   make cold starts slow and leak model assumptions into a tool whose output is
   explicitly "relative, not billing-grade." ~4 chars/token tracks OpenAI-ish
   tokenization closely enough for ranking and waste math.
2. **No async MCP client.** Servers are short-lived measurement targets with a
   timeout cap. A threaded pool is easy to add later; sequential keeps the
   output deterministic and error reporting simple.
3. **Tool name normalization.** Transcripts store tools as `mcp__server__tool`;
   configs expose `server` with tools. We normalize to `server:tool` on both
   sides of the join so dead-tool math is a set difference.
4. **One process, one report.** Every run produces a single self-contained HTML
   file (inline CSS/JS) — trivially shareable, no serving required.
5. **Failure is data, not an error.** A server that won't `initialize` renders
   as an `err` row instead of aborting the audit. Missing logs make the probe
   empty but the measurement half still reports.

## Session-log formats probed

- Claude Code: `~/.claude/projects/**/*.jsonl` (`tool_use` blocks)
- Codex CLI: `~/.codex/sessions/**/*.jsonl` (`function_call` / `tool_call`)
- opencode: `<project>/.opencode/sessions/**/*.jsonl`

Only files modified within `--window` days are read; oversized files are
skipped defensively.

## Extension points

- **New client config**: add a candidate path + JSON shape in `config._candidate_paths` / `_parse_mcp_servers`.
- **New transcript shape**: add a branch to `probe._walk_record`.
- **New report target** (Slack/OTEL): consume `AuditReport` directly.