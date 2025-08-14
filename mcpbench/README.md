# mcpbench

**Benchmark the clients, not the servers.**

Every benchmark in the MCP ecosystem scores the *server* — how conformant a
tool server is, how fast, how many payloads it survives. Nobody scores the
*client*. `mcpbench` closes that gap: it drives **reference MCP client
behaviour profiles** against one fixed fleet + workload, inside a sandbox, and
produces an A-F **client leaderboard**.

Why reference profiles instead of real agents? Real agents (Claude Code,
Cursor, opencode) are non-deterministic, heavy, and impossible to run in CI.
`mcpbench` ships *deterministic* archetypes — `canonical`, `naive`, `chatty`,
`careless` — that differ only in the behaviour under test (policy respect,
schema care, drift adaptation, economy). The benchmark attributes a
leaderboard delta to *exactly which behaviour each client got wrong*, and the
full transcript is quoted in the report so you can verify every score by hand.

- **Same fleet, same workload, same sandbox.** Every driver runs the same
  intents against the same bundled reference fleet. Only the behaviour
  differs.
- **Scores come from the transcript, not self-report.** Conformance, policy,
  validity, economy, and drift are computed from the recorded frames and the
  fleet's replies — tamper-resistant and reproducible.
- **Deterministic.** Same drivers, same fleet, same numbers. Runs in CI.
- **No runtime deps.** Python stdlib only, like every tool in the health kit.
- **House rule intact.** A low grade is a *review trigger*, never a verdict on
  any specific agent product.

## Quick start

```bash
pipx install mcpbench
mcpbench run            # benchmark all reference drivers
mcpbench list           # see the available drivers
mcpbench run --drivers canonical,naive --json | jq .best_grade
mcpbench run --share ~/.mcpcensus/bench.json   # join the census network
```

The leaderboard lands in `mcpbench-report.html`.

## CLI

```
mcpbench run  [--drivers NAME [NAME ...]] [--timeout SEC]
              [-o report.html] [--json] [--share fingerprint.json]
mcpbench list
```

Exit codes: `0` ok, `2` bad args / unknown driver.

## The axes (all 0–100, computed from the transcript)

| axis | what it measures |
|---|---|
| **conformance** | did it initialize before talking, and speak well-formed JSON-RPC 2.0? |
| **policy** | did it consult the gate and refuse gated tools (`write_file`, `grant_permissions`, `run_backup`)? |
| **validity** | of the executed calls, how many satisfied the advertised schema? |
| **economy** | outbound tokens per useful outcome, scored relative to the cohort |
| **drift** | when the fleet announced `tools/list_changed`, did it re-list and adapt to the new schema? |

## The reference fleet

A bundled stdlib MCP stdio server (`python -m mcpbench.fleet`) advertises five
tools, validates arguments against their schemas, refuses policy-gated tools
with a distinct error code, and — after the first executed call — drifts its
`lookup` schema (adds a required `scope`) and announces
`notifications/tools/list_changed`. That makes drift a first-class, measurable
behaviour instead of a hand-wave.

## Drivers

| driver | policy | schema | drift | economy | story |
|---|---|---|---|---|---|
| `canonical` | ✓ consults | exact, fills required | re-lists | lean | the client every vendor wants to be |
| `naive` | ✗ calls gated tools | ships whatever's given | caches forever | thin | the client everyone ships first |
| `chatty` | ✓ | exact | re-lists | fat | protocol-correct, spends tokens |
| `careless` | ✗ | wrong keys entirely | never re-lists | flood | worst-case cohort anchor |

## Why this matters

Orgs standardize on an agent **client** and then discover, months later, that
it silently ignores the policy gate or burns 4× the context per task.
`mcpbench` makes "which client should we standardize on?" an answerable,
reproducible question — the same question every other benchmark refuses to
ask, because scoring a client means standing up a server and a workload and a
gate, which is exactly what this kit is good at.

## Development

mcpbench lives in the mcp-monorepo health kit:

```bash
git clone https://github.com/milangeorge2000/mcp-monorepo.git
cd mcpaudit/mcpbench
pip install -e .[dev]
pytest
```

## Roadmap

- [ ] Adapters for driving real agent CLIs (opencode, Claude Code) through the
      same workload, with output seeded for determinism
- [ ] Custom driver profiles via a small YAML/JSON spec
- [ ] Fleet variants (fault-injection, slow tools) as additional rounds
- [ ] Publish the reference fleet as a pip-installable, reusable fixture

## License

MIT