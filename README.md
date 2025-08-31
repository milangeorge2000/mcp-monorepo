# mcp-monorepo · the MCP Health Kit

Agent workstations now run a stack of MCP servers with **zero operational
data** — nobody knows how much context they burn per prompt, what they can
reach, or whether the code they pulled at startup is worth trusting.

`mcp-monorepo` is a small suite of standalone diagnostics — one per axis of MCP
health — that scan your configs, measure the thing, and hand you a *shareable
report card*. Each tool is plug-and-play, stdlib-only, deterministic, and
treats findings as **review triggers**, never verdicts.

| axis | tool | question it answers | artifact |
|---|---|---|---|
| **Context** | [`mcpaudit/`](mcpaudit/) | how many tokens do my tool schemas burn per request, and which tools are dead? | report.html + slimmed `mcp.json` |
| **Security** | [`mcpguard/`](mcpguard/) | what can these servers touch — risky launchers, dangerous tools, credential env, known-bad packages? | report.html + hardened `mcp.json` |
| **Data** | [`mcpcensus/`](mcpcensus/) | what does the MCP ecosystem really look like, measured on real devices? | State of MCP report + leaderboards |
| **Accountability** | [`ledger/`](ledger/) | what did the agent actually do, in what order, at what cost? | incident dossier / Bill of Actions |
| **Economics** | [`agentspense/`](agentspense/) | what do agents cost per team, per PR, per resolved issue? | monthly agent P&L |
| Reliability | _roadmap_ | do my servers stay up and answer `tools/list` consistently? | uptime / replay corpus |
| Compliance | _roadmap_ | EU-AI-Act proportionality, model-usage policies | regulatory report |

Full concept notes: [`docs/roadmap.md`](docs/roadmap.md).

## The pitch

```
npx -y some-mcp-package          # you just ran remote code, unbounded
mcpaudit                         # ...how much context is that costing?   -> context report card
mcpguard scan                    # ...and what can it actually touch?     -> security scorecard
mcpaudit --share ~/.mcpcensus/ctx.json        # + mcpguard scan --share  -> you are a census sensor
mcpguard scan --share ~/.mcpcensus/sec.json   # (names salted on the device)
mcpcensus ingest ~/.mcpcensus/*.json          # monthly State-of-MCP dataset
ledger record session.jsonl                   # what the agent actually did, on tape
ledger gate trail.json --rules policy.json    # did it stay inside the rules?
agentspense normalize export.csv              # what did that month actually cost?
```

Scorecards first, then the observatory, the forensics tape, and the money.
Same habit throughout: **audit before you trust, guard before you scale,
account for what ran.**

## House rules

- **Plug-and-play:** `pipx install <tool>` then run it in your repo.
- **No runtime deps:** Python stdlib only — installs into any agent dev box.
- **Deterministic:** same config, same numbers.
- **Honest output:** every figure is an estimate; every finding a review
  trigger, never a conviction.

## Quick start

```bash
# context diet
pipx install mcpaudit && mcpaudit

# security scorecard
pipx install mcpguard && mcpguard scan

# be a sensor
mcpaudit --share ~/.mcpcensus/mcpaudit-census.json
mcpguard scan --share ~/.mcpcensus/mcpguard-census.json

# observe the ecosystem
mcpcensus ingest ~/.mcpcensus/*.json && mcpcensus report published.json

# tape + gate an agent session
ledger record session.jsonl && ledger gate trail.json --rules policy.json

# price the month
agentspense normalize claude-export.json cursor-audit.csv -l ledger.json && agentspense ledger
```

The first two auto-discover Claude Code / Cursor / opencode MCP configs and
write a report in the current directory; the rest operate on what they
produce.

## Layout

```
mcp-monorepo/
├── mcpaudit/     # context report card (token waste, dead tools, slim config)
├── mcpguard/     # security scorecard (launchers, capabilities, intel, hardened config)
├── mcpcensus/    # MCP Observatory (sensor registry, k-anonymity + LDP, State-of-MCP report)
├── ledger/       # action forensics (transcript -> trail, incident dossier, policy gate)
├── agentspense/  # cost intelligence (rate cards, provider normalization, agent P&L)
├── LICENSE       # MIT, shared by all tools
```

## The loop (all five tools, one habit)

```
audit → guard → share → observe → record → gate → bill
  1     2       3        4        5       6      7
```

`mcpaudit` and `mcpguard` scan; their `--share` flags make you a census
sensor; `mcpcensus` aggregates the anonymized stream; `ledger` tapes what the
agent did and gates it; `agentspense` prices the month.

## Contributing

Each tool is self-contained in its subfolder with its own tests:

```bash
pip install -e mcpaudit/[dev]
pytest mcpaudit/

pip install -e mcpguard/[dev]
pytest mcpguard/
```

## License

MIT