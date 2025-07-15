# Architecture

`mcphazard` is a small, dependency-free red-team pipeline: config in → fresh
sandbox → enumerate tools → fire payload battery → analyze responses → findings
→ pentest report. Only the Python standard library at runtime; pytest for tests.

## Pipeline

```
 mcp.json / argv ──▶ Sandbox (temp cwd, canary secret, scrubbed env)
                          │  spawn server under test
                          ▼
                    client.py   (initialize → tools/list → tools/call)
                          │
           ┌──────────────┴───────────────┐
           │  payloads.py (13-class bundle)│  per tool × per payload
           └──────────────┬───────────────┘
                          ▼
                    analyze.py  (echo / exfil / policy_leak / shell_shape / timeout)
                          │
                          ▼
                    models.ToolKinematics + Finding
                          │
                          ▼
              report.py (pentest HTML + JSON) · share.py (mcpcensus)
```

### Module map

| module | responsibility |
|---|---|
| `cli.py` | `scan` / `payloads` subcommands, target resolution from argv or config, `--live` gate, `--share` |
| `payloads.py` | the adversarial bundle: `AttackClass` per payload, `bespoke` flag for weaponized (UR-only) ones |
| `sandbox.py` | throwaway cwd, canary secret file, scrubbed env, proxy-stranding (non-live), process spawn |
| `client.py` | MCP stdio client that actually calls `tools/call` (mcpguard only reads `tools/list` — this is the delta) |
| `analyze.py` | deterministic signal detection: echo, exfil, policy leak, shell shape, timeout |
| `models.py` | `AttackClass`, `ToolKinematics` (per-tool posture), `Finding`, `HazardReport` (grade by worst severity) |
| `report.py` | pentest-style `render_html` + `to_json` export |
| `share.py` | `--share` census fingerprint under `sensor=hazard`, trimmed to counts + hashed tool ids |

## Design decisions

1. **Active, in a sandbox.** Unlike mcpguard (which touches nothing), mcphazard
   *must* call tools to see if attacks land. The sandbox is what makes that
   safe: fresh workdir per scan, canary secret that only exists inside the box,
   scrubbed env, network stranded unless `--live`.
2. **Bespoke payloads are opt-in.** Weaponized payloads (real URLs, shell
   punctuation, nested-template bombs) are `bespoke=True` and excluded until
   `--live` is passed. The default bundle is detector-grade: it shapes text the
   way an attack would, but never ships an armed URL.
3. **Signals, not interpretation.** No LLM scoring of responses. Detection is
   string/URL/timeout checks — explainable in the report, testable in pytest,
   deterministic across runs.
4. **Worst-severity posture.** A tool's grade is set by its most severe finding,
   so `scan --json | jq .overall_grade` is unambiguous and CI-friendly.
5. **Zero runtime deps.** Same rule as the rest of the kit: stdlib only.
6. **Findings are review triggers.** An echo is evidence of behavior, not proof
   of compromise; the report quotes the payload and the evidence so humans can
   decide.

## Extending the bundle

Add a payload in `payloads.py`:

- `klass` — machine tag (`prompt_injection`, `data_exfiltration`, ...)
- `bespoke=True` for anything with real URLs / destructive syntax
- keep it *observability-grade*: shaped like an attack, harmless to a box you own

Tests for signal wiring live in `tests/test_analyze.py`.

## Live-fire guardrails

- `--live` does not disable the sandbox (temp workdir + canary remain).
- Only the operator passing `--live` authorizes the weaponized bundle.
- The demo server (`examples/fake_toxic_server.py`) is the reference target for
  both modes and the test suite.

## Extension points

- New attack class → `payloads.py` + (if new signal) `analyze.py`.
- HTTP transport → new client module replicating `client.py` over urllib.
- LLM second-opinion pass → optional post-processing on `HazardReport`.