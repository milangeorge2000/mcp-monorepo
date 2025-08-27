# ledger — agent action forensics

**You approved a prompt, not every action.** ledger turns the session
transcript into a **replayable trail** — every tool call, file it touched,
tokens it burned, what it cost, whether it succeeded — and then tells you the
story plainly: dossier, policy gate, behavior diff.

```
ledger record ~/.claude/projects/*/*.jsonl -o trail.json        # transcript → trail
ledger dossier trail.json --rules policy.json -o dossier.html   # incident report + gate
ledger gate trail.json --rules policy.json                      # pass/fail + reasons
ledger diff trail-a.json trail-b.json                           # what changed in the retry
```

## The three forensics questions

**1. What happened, in what order?**
`ledger record` normalizes Claude Code JSONL (tolerantly — layout drift is
absorbed, raw lines kept) into a structured tape. `dossier` renders it as an
action timeline with cost and file surface. This is the artifact you attach to
a postmortem.

**2. Did it stay inside the rules?**
`policy.json` is plain JSON — deny by tool / file / input fragment, require
explicit human approval on gate patterns, cap budgets:

```json
{
  "deny": [
    {"tool": "Bash", "input_has": "rm -rf"},
    {"file": "src/**/prod/**", "tool": "shell_write"}
  ],
  "require_human_approval": ["*deploy*", "git_push"],
  "allow": [{"tool": "Read"}],
  "budget_tokens_in": 200000,
  "max_cost_usd": 10.0
}
```

No "risk score" decoder ring: every hit is one named rule with the reason, the
sequence number, and the file. `ledger gate` exits nonzero on any violation,
so it slots straight into a CI retry loop.

**3. What changed between attempts?**
`ledger diff` compares the *behavior fingerprint* of two trails — tools added
or dropped, files entered or left, tokens and cost deltas. Retries stop being
a mystery.

## Where it fits

The trail is the raw tape between **agentspense** (which does the real money
accounting over the same tool calls) and **mcpcensus** (which blurs them into
anonymous ecosystem stats). ledger is the subpoena-ready middle: precise, but
never shared.

## Install

```
pip install -e ledger
```