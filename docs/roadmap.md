# mcp-monorepo · roadmap & concepts

The shipped axes (Context, Security) solve point-in-time questions about a
single machine. The concepts below escalate the suite in three directions: a
**data network** (mcpcensus), **accountability** (ledger), and **economics**
(agentspense). All three inherit the house rules: plug-and-play, stdlib-only,
deterministic, report-card artifacts, findings-as-review-triggers.

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

**Why it's needed.** The question the org can't answer today ("is this
cohort of agents worth what it costs?") is the question keep up the budget.

---

## Sequencing

| phase | deliverable | milestone |
|---|---|---|
| 0 | `mcpaudit` / `mcpguard` shipped (done) | — |
| 1 | `--share` flag + registry + private cohort | mcpcensus private beta |
| 2 | first public *State of MCP* report | public dataset v1 |
| 3 | `mcpcensus suggest` feedback loop | sensor network self-feeds |
| 4 | `ledger` trail recording on both clients | incident dossiers |
| 5 | `agentspense` rate-card normalization | monthly agent P&L |

The order matters: the Observatory lands first because it converts the existing
suite into an irreplaceable data asset before any single feature can be
cloned.