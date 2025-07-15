# mcphazard

**The red-team harness for your MCP servers.**

`mcpguard` told you *what your servers can touch*. `mcphazard` asks the sharper
question: **if I actually attack them, what lands?**

It spawns each MCP server in a throwaway sandbox, enumerates every tool, then
**fires real adversarial payloads** — prompt injection, tool confusion,
policy bypass, data exfiltration, resource exhaustion — through `tools/call`.
Then it analyzes the responses for concrete signals: did the server *echo* the
payload? Did a response carry an exfiltration sink or the sandbox's own secret?
Did it shell out? Every signal becomes a finding in a pentest-style report.

- **Sandbox-first.** Fresh temp workdir, a canary secret file, scrubbed env,
  network stranded at localhost in default mode. Even a *successful* exfil
  attempt cannot escape the box.
- **You keep the mcpguard habit.** Same "findings are review triggers, never
  convictions" rule. A firewall-grade report, not a verdict.
- **Deterministic.** Same server, same payload bundle, same numbers. Runs in
  CI as a repeatable check.
- **No runtime deps.** Python stdlib only, like every tool in the health kit.

## Quick start

```bash
pipx install mcphazard
cd mcphazard/examples

# sandbox red-team of the demo "toxic" server
mcphazard scan --config demo-mcp.json

# list the payload bundle
mcphazard payloads

# escalate to full bundle (URL sinks, shell punctuation) — you asked for it
mcphazard scan --command python fake_toxic_server.py --live
```

Write the pentest report and read posture:

```bash
mcphazard scan --config demo-mcp.json --json | jq .overall_grade
```

## CLI

```
mcphazard scan    [LABEL] [--command ARG... | --config mcp.json]
                          [--live] [--timeout SEC] [--output report.html]
                          [--json] [--share fingerprint.json]
mcphazard payloads [--live] [--json]
```

| command | meaning |
|---|---|
| `scan` | enumerate a server's tools and fire the battery in a sandbox |
| `payloads` | inspect the adversarial payload bundle (13 core + weaponized) |

Exit codes: `0` ok, `2` bad args / missing target.

## Default vs. `--live`

Defense in depth for an offensive tool:

| | default | `--live` |
|---|---|---|
| payload set | 10 inert-but-detective payloads | full 13 incl. URL sinks + shell punctuation |
| network | proxies stranded at localhost | allowed outbound |
| secret files | sandbox canary only | sandbox canary only |
| posture of demo `toxic-demo` | finds echoes + exfil shapes | same, armed |

Weaponized payloads (`bespoke=True`) are never shipped in a default scan. Even
`--live` keeps the sandbox temp workdir and canary secret; the flag only means
"this operator authorized intrusive testing of their own endpoint."

## Signals (all deterministic, no LLM interpretation)

- **echo** — the response reflected the injected payload or the canary token.
- **exfil** — the response carried the sink URL or the sandbox's own secret.
- **policy_leak** — the response surfaced configured-policy or auth material.
- **shell_shape** — the response shows command-execution-shaped output.
- **timeout** — the server failed to answer within budget.

Findings map back to *payload* and *evidence* in the report, so a human can
verify each signal by reading the raw exchange.

## Why this matters

Prompt-injection and tool-confusion attacks against agent tool servers are a
live, growing category (see the wider series in this repo's `docs/`). Most
teams find out their server reflects injected text when someone's *test* does
it to them. `mcphazard` turns that discovery into a repeatable, sandboxed,
CI-able check — the active half of the health kit's "guard before you scale"
rule. Without it you only know your servers *can* be attacked; with it you know
what actually *lands*.

## Development

mcphazard lives in the mcp-monorepo health kit:

```bash
git clone https://github.com/milangeorge2000/mcp-monorepo.git
cd mcpaudit/mcphazard
pip install -e .[dev]
pytest
```

## Roadmap

- [ ] HTTP(S) transport harness (cookie/token replay for remote servers)
- [ ] GPT/LLM-as-analyzer pass as an *optional* second opinion
- [ ] OWASP LLM-01/LLM-02 + MITRE ATLAS technique tags on findings
- [ ] Mutation fuzzing of payloads from seed grammar
- [ ] OpenTelemetry security metrics on findings

## License

MIT