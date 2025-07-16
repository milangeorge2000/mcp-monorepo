# mcp-monorepo · roadmap & concepts

The shipped axes (Context, Security, Red team) solve point-in-time questions
about a single machine. The concepts below escalate the suite in three
directions: a **data network** (mcpcensus), **accountability** (ledger), and
**economics** (agentspense). All inherit the house rules: plug-and-play,
stdlib-only, deterministic, report-card artifacts,
findings-as-review-triggers.

**Status:** `mcpcensus/`, `ledger/`, `agentspense/` are implemented as
first-class monorepo members — each with tests and a CLI. **mcphazard** ships
too: an active red-team harness that fuzzes `tools/call` in a sandbox. The
table below marks the shipped surface and what remains "phase 2" of each
concept.

---

## mcphazard — the red-team harness *(hazard testing)*

**The problem.** `mcpaudit` and `mcpguard` read the *surface* of a server —
schemas, launchers, capabilities. Neither answers the question ops actually
asks before a risky integration goes to prod: **what happens if this server is
pushed?** A server can announce harmless tools and still be trivially
promptable into echoing, leaking, or exfiltrating when handed adversarial
input.

**The concept.** Actively *call* `tools/call` with a battery of adversarial
payloads — prompt injection, policy override, credential phish, argument
smuggling, exfiltration-with-sink, shell-shaped output — inside a throwaway
sandbox with a canary secret and inert egress. Deterministic signal detection
(echo / exfil / policy-leak / shell-shape) turns each response into a finding
and an A‑F posture without any LLM interpretation.

**Safety model.** Sandbox-first by default: default payloads are
inert-but-detective; weaponized payloads (real sink URLs, shell punctuation)
require an explicit `--live`. Findings are review triggers, never verdicts —
same house rule as the scanners.

**Shipped (this repo).** `mcphazard/`: payload bundle, deterministic sandbox,
stdlib MCP client that actually fires `tools/call`, signal analyzer,
harness + pentest-style HTML/JSON report, a `--share` hazard fingerprint
(`sensor=hazard`) for the census network, and a demo "toxic" MCP server.

**Phase 2.** A conformance/canary corpus of known-real vulnerabilities, corpus
regression tracking ("this newly shipped server still passes"), and hardware
batching to cut scan wall-time.

---

## mcpcensus — the MCP Observatory *(flagship)*

**The problem.** The industry makes MCP decisions on vibes. There is no
authoritative public data on how the MCP corpus actually looks — how many
servers the median setup runs, what they cost in context, how many are
dangerous, how fast the ecosystem grows. Vendors ship gateways off
speculative guesses; teams pick servers by README stars.

**The concept.** The shipped CLIs become *sensors*. Opt-in
`mcpaudit scan --share` / `mcpguard scan --share` upload an **anonymized
fingerprint** — tool counts, schema-token histograms, hashed server names,
risk-grade aggregates, launcher modes — never tool payloads, prompts, or raw
configs.

```
┌─ mcpaudit ──┐──┐
│  (context)  │  │  anonymous fingerprint         ┌────────────┐
└─────────────┘  │ ─────────────────────────────► │  mcpcensus │──► public API
┌─ mcpguard ──┐  │  (k-anonymity, LDP, no-IP)     │  registry  │──► monthly report
│ (security)  │──┘                                └────────────┘   + leaderboards
└─────────────┘
```

**Deliverables**

- **Publication engine** — a monthly *State of MCP* report: context-waste
  percentiles, dead-tool rates, dangerous-server prevalence by launcher,
  growth curves, cohort breakdowns. The shareable artifact is a one-page
  PDF + leaderboard ("10 worst context hogs"), not another CLI.
- **Privacy engineering** — local aggregation with k-anonymity grouping and
  small-cohort suppression, LDP-style noise, per-device salted hashes so a
  package's *prevalence* is public while *your config* is not.
- **Public API + dataset** — CI badges ("your grade vs global percentiles"),
  dataset releases, trending-server alerts.
- **Feedback loop** — `mcpcensus suggest` tells a user "your setup is in the
  bottom 5% of dead-tool waste; here's your cohort's median" — so sharing is
  self-serving, which is what makes the network grow.

**Why it's the moat.** A scanner can be rewritten by anyone; a *network of
real devices submitting measurements* cannot. Whichever project owns the first
credible public corpus becomes the reference dataset — the `CVE`/`npmsecurity`
position of the MCP era. Longitudinally compounding: every additional device
raises the value of the whole.

**Shipped (this repo).** `mcpcensus/`: sensor flags on both tools
(`mcpaudit --share`, `mcpguard scan --share`), fingerprint builders around a
single public format, a JSONL registry, full publishing pipeline (bucket →
k-anonymize → Laplace noise → `published.json`), a stdlib HTTP reference
server (`POST /ingest`, `GET /published`, `GET /report`), the State-of-MCP
HTML report, and the `suggest` percentile feedback loop.

**Phase 2.** A hosted public deployment of the reference server, signed
dataset releases, per-package trendline API, and the one-page PDF report
format.

---

## ledger — agent action forensics *(accountability)*

**The problem.** Autonomous agents write code, merge PRs, touch data, and buy
things. When one does something bad or expensive, reconstructing exactly what
happened — which tools fired, on which files, in what order, for what
billable cost — is a manual nightmare across disjoint client logs.

**The concept.** A chain-of-custody layer: record every agent action
(tool calls, file diffs, token/latency metrics, timestamps) into a
queryable, replayable trail. On demand, produce an **incident dossier** —
"what the agent did, in what order, what it cost, what changed" — plus a
behavior diff against a prior session ("this run touched 3 files you never
allow").

**Sophistication.** Trace graph + replay able to a fresh sandbox; causal
attribution of picks/rejections; SBOM-style "Bill of Actions" export; policy
gates ("no run touches `prod/db/` without a human signature").

**Shipped (this repo).** `ledger/`: transcript → replayable trail
(`claude-code` JSONL or generic rows), incident dossier HTML, behavior
diff between attempts, and a `policy.json` gate (deny by tool/file/input,
`require_human_approval`, budgets) with a CI-friendly exit code.

**Phase 2.** Streaming capture from live clients (no post-hoc replays), tool
trace graphs, and sandbox replay of a recorded trail.

**Why it's needed.** Org adoption of autonomous agents is gated on *can we
audit what it did*. This turns "trust the agent" into "verify the agent".

---

## agentspense — agent cost intelligence *(economics)*

**The problem.** Finance and leadership block agent programs for one reason:
nobody can say what the agents actually cost, let alone what they bought.

**The concept.** Unify spend across Claude, Cursor, opencode, Copilot,
self-hosted gateways into a single ledger with a rate-card normalization
engine. Answer: spend by team/feature-ticket, $/merged-PR, $/resolved-issue,
spike anomaly alerts, and a monthly one-page **agent P&L**.

**Shipped (this repo).** `agentspense/`: provider exporters (claude, cursor,
codex, opencode, generic rows, csv/tsv) folded into one ledger, bundled +
overridable rate card, team/feature attribution, z-score + session spend-spike
alerts (`agentspense alerts` exits nonzero), and the monthly agent P&L HTML.

**Phase 2.** Jira/GitHub integration for `$/merged-PR`, `$/resolved-issue`,
scheduled report delivery, and Copilot/self-hosted gateway exporters.

**Why it's needed.** The question the org can't answer today ("is this
cohort of agents worth what it costs?") is the question that keeps (or cuts)
the budget.

---

## Sequencing

| phase | deliverable | milestone |
|---|---|---|
| 0 | `mcpaudit` / `mcpguard` shipped | — |
| 0b | `mcphazard` red-team harness *(done)* | attack tested before you trust |
| 1 | `--share` sensors + registry + `mcpcensus` engine *(done)* | private beta |
| 2 | first public *State of MCP* report | public dataset v1 |
| 3 | `mcpcensus suggest` feedback loop *(done)* | sensor network self-feeds |
| 4 | `ledger` trail recording + dossier + policy gate *(done)* | incident dossiers |
| 5 | `agentspense` rate-card normalization + agent P&L *(done)* | monthly agent P&L |
| 6 | Reliability / Compliance axes | suite complete |

The order matters: the Observatory lands first because it converts the existing
suite into an irreplaceable data asset before any single feature can be
cloned.