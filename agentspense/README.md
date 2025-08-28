# agentspense — agent cost intelligence

**Every AI coding provider invoices its own dialect.** agentspense normalizes
spend exports from all of them into *one accountable ledger*, attributes it to
teams and features, renders a monthly **agent P&L**, and screams when a
runaway retry loop is eating the budget.

```
agentspense normalize claude-export.json cursor-audit.csv codex-export.csv \
  -l agent-ledger.json
agentspense ledger agent-ledger.json --month 2025-08 -o agent-pnl.html \
  --budget budget.json
agentspense alerts agent-ledger.json          # exit 1 on a spend spike
```

## What you get

```
agentspense ledger agent-ledger.json --month 2025-08
  total      $     4.14
  lines               6
  tokens in     595,000
  tokens out    145,000
  by team:
    checkout               $    2.78
    platform               $    1.36
```

## The pipeline

1. **Parse.** Provider exporters are distinct dialects:
   `claude` (cost breakdown), `cursor` (monthly dumps), `codex`
   (session exports), `opencode`, and anything else via generic rows, plus
   `csv`/`tsv`. Provider is detected from the filename or the payload.
2. **Normalize.** Every row becomes one `SpendLine`. If the vendor didn't
   bill (or you want to sanity-check them), the rate card fills the cost:
   `agentspense rates` shows the bundled pricing (`--rates` overrides merge
   on top).
3. **Attribute.** `team:`/`feature:` tags — or CSV columns — bucket spend per
   team and feature; heavy sessions get their own line.
4. **Report.** `agent-pnl.html` puts totals, per-team budget cards (red when
   over), provider/feature/session breakdowns, and spike alerts on one page.
5. **Alert.** z-score tripwire over the trailing window + per-session
   threshold; `alerts` exits nonzero so cron/monitoring take notice.

## Rate card

Bundled, overridable, honest baseline:

```
claude   claude-3-5-sonnet            in $3.00/M  out $15.00/M
opencode deepseek-v4-flash            in $0.07/M  out $0.27/M
```

`--rates rates.json` merges your negotiated prices over the defaults.

## Where it fits

The ledger is the money layer over **ledger's** trails: same tool calls, one
for forensics and one for the invoice. agentspense answers the question every
tech lead actually asks on Friday: *what did the agents cost us this month,
and which team just tripled their spend?*

## Install

```
pip install -e agentspense
```