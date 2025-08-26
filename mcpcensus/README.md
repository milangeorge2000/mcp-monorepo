# mcpcensus — the MCP Observatory

**Bigger than any one server:** hundreds of machines run variations of the same
MCP configs. mcpcensus puts a *sensor in every one of them* and turns the
result into public knowledge — a monthly **State of MCP**.

`mcpaudit` and `mcpguard` stop measuring *your* setup and start measuring
*everyone's*, on real devices, from behind a privacy wall thin enough to be
inspectable but strong enough to be honest.

```
mcpaudit --share ~/.mcpcensus/mcpaudit-census.json   # you are a context sensor
mcpguard scan --share ~/.mcpcensus/mcpguard-census.json  # you are a security sensor
mcpcensus ingest ~/.mcpcensus/*.json --db registry.jsonl
mcpcensus aggregate --db registry.jsonl -o published.json --min-cohort 25 --noise 0.5
mcpcensus report published.json -o state-of-mcp.html
mcpcensus suggest published.json ~/.mcpcensus/mcpaudit-census.json
```

## The loop

1. **Sense.** `--share` on both tools writes a *fingerprint*: server counts,
   tool or risk counts, grade histograms. Raw names are HMAC-salted per field;
   no tool payloads, no config contents, ever.
2. **Store.** `mcpcensus ingest` appends fingerprints to a JSONL registry —
   append-only, like a ledger, so every published number is auditable.
3. **Publish.** `mcpcensus aggregate` runs the publishing pipeline:

   ```
   bucket  →  k-anonymize  →  Laplace noise  →  published.json
   ```

   Cohorts smaller than `-k` are suppressed; `--noise N` adds LDP-style noise
   to counts. **Only** the aggregated snapshot is ever shared — the raw
   registry stays on the authority.
4. **Report.** `state-of-mcp.html` renders ecosystem stats, grade
   distributions, submissions by month, and published cohorts. `mcpcensus
   badge` produces a shields-style SVG you can drop into any README.
5. **Deepen.** `mcpcensus suggest` tells any device its ecosystem percentile
   and the one change that moves its grade — the feedback loop that keeps a
   census honest (nobody spends intelligence on a database they don't read).

## The moat

A synthetic dataset can be gamed. A dataset measured from **real devices**,
each with a stable salted identity sending monthly snapshots, cannot — you
can't fake a million installs that keep coming back. The observation network
*is* the product.

## Privacy contract (the part to read)

| what | where it goes |
|---|---|
| server names, hosts, tool names | only `hmac(salt, name, field)[:24]` — salt never leaves your machine |
| counts / grades / tokens | plaintext in the fingerprint |
| tool payloads, config files | nowhere. dropped at the sensor |
| per-device stability | `device` id from `~/.mcpcensus/salt`, one submission per device/month |
| published | only cohorts with `>= min_cohort` members, optionally +LDP noise |

## Commands

```
mcpcensus serve [--port 8787] --db registry.jsonl        # stdlib HTTP observatory
mcpcensus ingest fp.json --db registry.jsonl
mcpcensus aggregate --db registry.jsonl -o published.json [--min-cohort N] [--noise S]
mcpcensus report published.json -o state-of-mcp.html [--title "..."]
mcpcensus badge published.json -o mcpcensus-badge.svg [--grade F]
mcpcensus suggest published.json fingerprint.json
mcpcensus fingerprint --report tool-report.json --sensor context --out census.json
```

The reference `serve` (Python stdlib only) exposes `POST /ingest`, `GET
/published`, `GET /report`, `GET /healthz` — enough to run the whole loop on a
VPS, and a drop-in contract for a production registry.

## Install

```
pip install -e mcpcensus
```