# Architecture

`mcpguard` is a small, dependency-free pipeline: config in → launcher
classification → (optional) live `tools/list` probe → findings → grade → two
outputs. Only the Python standard library at runtime; pytest for tests.

## Pipeline

```
                    ┌────────────┐   static triage      ┌──────────────┐
 mcp.json ──config──▶  config.py ──▶  resolve.py  ──────▶              │
                    └────────────┘   (launcher mode,     │   audit.py  │
                    ┌────────────┐    pin, flags, env)   │  ServerResult│
 stdout ──stdio────▶ mcpclient.py +─────────────────────▶ │  (grade)    │
                    └────────────┘   live tools/list     └──────────────┘
                    ┌────────────┐        ▲                      │
 intel bundle ──────▶  intel.py  ├────────┘                      ▼
                    └────────────┘   matchers            ┌──────────────┐
                                                        │  report.py   │
                                                        │ html+hardened│
                                                        └──────────────┘
```

### Module map

| module | responsibility |
|---|---|
| `cli.py` | `scan` / `watch` / `intel` subcommands, JSON output, browser open |
| `config.py` | discovery + parsing for Claude/Cursor/opencode; stdio argv **and** HTTP(S) transports |
| `resolve.py` | classify launcher → mode (`npx`/`pipx`/`uvx`/`docker`/`python`/`shell-pipe`/`http`/`binary`), flag auto-install, pin detection, registry overrides, curl-pipe patterns |
| `models.py` | `ServerConfiguration`, `Finding`, `ToolAssessment`, `ServerResult` (grade by worst severity), `GuardReport` |
| `intel.py` | seed bundle + matchers: tool-risk categories, credential env keys, exfil domains, edit-distance typosquat vs canonical packages, package warnings |
| `mcpclient.py` | MCP stdio handshake + `tools/list` (reused from mcpaudit, MIT) — never invokes a tool |
| `audit.py` | orchestrate static + live passes into `ServerResult` findings |
| `report.py` | `render_html` scorecard + `write_hardened_config` (drops F servers, emits `_review`) |
| `_webbrowser_open.py` | testable browser-open indirection |

## Design decisions

1. **No contact with tools, only `tools/list`.** The live probe handshakes and
   reads the capability surface; it never calls a tool. This keeps the scanner
   side-effect-free on the machine it audits.
2. **Grade = worst severity, not a scorecard average.** Matches how humans
   actually read security findings and makes `mcpguard watch` semantics crisp:
   "a critical appeared" is unambiguous.
3. **Findings are review triggers.** Static analysis can't prove package
   intent; the UI and intel docs say so explicitly. This is what keeps the tool
   honest and defensible.
4. **Intel is data, decoupled from code.** Matchers read a bundle; the seed is
   an *example/structure* bundle, production data ships as `intel.json`
   (MCPGUARD_INTEL) and updates without a code release. The bundle is the moat.
   Note: the seed intentionally does **not** level real-world accusations; that
   data belongs in the crowd/curated bundle, not source.
5. **Static pass works offline.** `--no-live` gives a deterministic,
   no-network assessment (CI-friendly); the live pass is an enhancement.
6. **Zero runtime deps.** Like mcpaudit: stdlib only, trivial to install into
   agent dev environments.

## Watch semantics

`watch` stores per-server critical finding *kinds* in
`~/.mcpguard/state.json` (override with `MCPGUARD_STATE_DIR` for tests/CI).
A rerun exits `3` if a server's critical finding set changed — new or louder.
Runs cleanly in CI as a status check.

## Extension points

- **New launcher** → `resolve.py` classification branch.
- **New risk keywords** → edit the bundle (`intel.py` seed or external `intel.json`).
- **New report target / gate** → consume `GuardReport` directly.
- **Transport auditing** → capture a replay of an HTTP server's tool list.