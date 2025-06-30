# mcpbatt · the benchmark that writes its own benchmark

Every benchmark in the MCP ecosystem ships a **hand-authored workload**: someone
sat down, wrote a fixed list of calls, and called it a test. The moment your
server's schemas change — or the moment you point the benchmark at a different
server — that corpus is stale.

`mcpbatt` inverts the model. You author a tiny **scenario template** (a
declarative intent: "call every tool with exactly its required fields", "omit
each required field one at a time", "send values that violate every declared
type"). The engine then:

1. connects to a live stdio server and reads its actual `tools/list`,
2. **expands** the template into a fully-concrete battery — every argument value
   is sampled from that server's own JSON schemas,
3. executes the whole battery inside a throwaway, scrubbed sandbox,
4. grades the server on four deterministic axes, and
5. lets you print, diff, and replay the **generated battery** — the benchmark is
   *created*, not pasted.

## The pitch

```
mcpbatt list                          # what can I probe?
mcpbatt expand --template required-only    # see the generated battery (no run)
mcpbatt run --template missing-required    # execute it, get a grade
mcpbatt run --template drift-honesty -o batt.html --share ~/.mcpcensus/batt.json
```

```
mcpbatt: required-only | mcpbatt.fleet | grade A
  fidelity    100.0
  discipline  100.0
  stability   100.0
  drift       100.0
  overall     100.0
  calls 4 | ok 4 | rejected 0 | drift-honored False
```

## Scenario templates

Templates are plain JSON in `src/mcpbatt/templates/` (they ship with the
package). One field is the *intent*, the rest is the *how*:

```json
{
  "name": "missing-required",
  "description": "For each tool, omit each required field one at a time.",
  "select": "*",              // "*" | "a,b" | "regex:^fetch"
  "mode": "missing",          // required | all | missing | wrong-type | oversize | empty
  "expect": "invalid",        // the expected outcome for these calls
  "drift": null               // optional: {"tool": "search", "add_required": ["locale"]}
}
```

`select` picks which live tools to probe. `mode` chooses how arguments are
built:

| mode | generates | expect |
|---|---|---|
| `required` | only required fields, well-typed | `ok` |
| `all` | every declared field | `ok` |
| `missing` | each required field omitted in turn | `invalid` |
| `wrong-type` | each field filled with a type-violating value | `invalid` |
| `oversize` | oversized strings into string fields | `ok` |
| `empty` | no arguments at all | `invalid` when required fields exist |

`drift` declares a **mid-run schema change**: the runner mutates the named
tool (adding required fields), confirms `tools/list_changed` fires, re-reads
`tools/list`, then re-probes — including a *stale* probe that sends the
pre-drift arguments to see whether the server rejects its own former
contract.

## The score card

Four deterministic axes, 0..100 each, blended into a weighted overall and an
A-F grade:

- **fidelity** — of calls expected to *work*, how many actually landed. A
  server that rejects its own advertised required fields scores badly.
- **discipline** — of calls expected to be *rejected*, how many got a clean
  `-32602 invalid params` instead of a silent success or a crash.
- **stability** — the server survived the whole battery: no EOF, no dead
  subprocess, no malformed replies.
- **drift** — when a schema mutation was declared, did the server honor it:
  emit `tools/list_changed`, reflect the new schema, and reject stale args?

No LLM anywhere in the loop. Same config, same grade, every run.

## The bundled reference fleet

The default `--server` is a bundled, deterministic reference fleet
(`python -m mcpbatt.fleet`) that validates schemas strictly, answers with
`-32602` on deviation, and understands the private `mcpbatt/apply_drift`
control method so drift templates run deterministically. Point `--server` at
*your own* stdio server command to grade it against the same generated
batteries (drift templates degrade gracefully: they re-list and report when a
server has no control method).

## House rules

- **Plug-and-play:** `pipx install mcpbatt` then run it in your repo.
- **No runtime deps:** Python stdlib only.
- **Deterministic:** same server + same template = same battery = same grade.
- **Honest output:** generated batteries are inspectable (`expand` prints
  every call, every argument); grades are estimates, never verdicts.
- **Scoped:** executes only against the stdio server you name, in a fresh
  scrubbed sandbox. No network inbound, no real-host scanning.

## Development

```bash
pip install -e .[dev]
pytest
```

## License

MIT