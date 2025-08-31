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
| **Data** | `mcpcensus` _roadmap_ | what does the MCP ecosystem really look like, measured on real devices? | State of MCP report + leaderboards |
| **Accountability** | `ledger` _roadmap_ | what did the agent actually do, in what order, at what cost? | incident dossier / Bill of Actions |
| **Economics** | `agentspense` _roadmap_ | what do agents cost per team, per PR, per resolved issue? | monthly agent P&L |
| Reliability | _roadmap_ | do my servers stay up and answer `tools/list` consistently? | uptime / replay corpus |
| Compliance | _roadmap_ | EU-AI-Act proportionality, model-usage policies | regulatory report |

Full concept notes: [`docs/roadmap.md`](docs/roadmap.md).

## The pitch

```
npx -y some-mcp-package        # you just ran remote code, unbounded
mcpaudit                       # ...how much context is that costing?
mcpguard                       # ...and what can it actually touch?
```

Two scorecards, one habit: **audit before you trust, guard before you scale.**
The report card (`A–F`) is the shareable artifact — teams post them, budgets
get renegotiated, and risky servers get dropped before they drop data.

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
```

Both auto-discover Claude Code / Cursor / opencode MCP configs and write a
report in the current directory.

## Layout

```
mcp-monorepo/
├── mcpaudit/     # context report card (token waste, dead tools, slim config)
├── mcpguard/     # security scorecard (launchers, capabilities, intel, hardened config)
├── LICENSE       # MIT, shared by all tools
```

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