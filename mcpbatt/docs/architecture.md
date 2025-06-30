# mcpbatt · architecture

## What it is

A benchmark *generation* engine for MCP servers. The novel claim: **the
benchmark is derived from the subject, not authored for it.** A scenario
template is an intent; the expanded battery is a fact, printed in `expand`,
replayable from JSON, and specific to the server it was run against.

```
template (intent)
   │  select / mode / expect / drift
   ▼
expand_template(template, tools_from_live_tools_list)
   │  argument sampling from each tool's own inputSchema
   ▼
battery (ordered CallSpecs: tool, arguments, expect, phase)
   │
   ▼
run_battery: sandbox -> spawn server -> initialize -> list/master
             -> execute each CallSpec -> classify outcome
             -> [drift: apply_drift control, re-list, stale probe, re-expand]
   │
   ▼
score_server -> fidelity / discipline / stability / drift -> A-F
```

## Module map

| module | responsibility |
|---|---|
| `models.py` | `Template`, `CallSpec`, `CallRecord`, `ServerResult`, `BattReport`, grades, tool selection |
| `schema.py` | validate the template DSL; reject ambiguous or invalid templates |
| `expand.py` | pure expansion engine: template + tool list -> concrete battery |
| `client.py` | recording stdio MCP client; `RpcError(code)` vs `FrameError` for clean classification |
| `fleet.py` | bundled reference fleet (`python -m mcpbatt.fleet`): strict validation + drift control |
| `sandbox.py` | throwaway cwd + scrubbed env for every server spawn |
| `runner.py` | orchestrate a battery: spawn, list, expand, execute, drift, score |
| `scoring.py` | deterministic four-axis scoring, no LLM |
| `report.py` | HTML leaderboard + `mcpbatt/v1` JSON export |
| `share.py` | `mcpcensus/v1` fingerprint under `sensor=batt` (privacy-preserving) |
| `cli.py` | `run`, `expand`, `list`, `--version`, `--share` |

## The four axes (all 0..100, blended 30/30/20/20)

**fidelity** = `100 * expected_ok_landed / expected_ok`
**discipline** = `100 * expected_invalid_rejected / expected_invalid`
**stability** = `100 * well_formed_responses / all_calls` (EOF costs everything)
**drift** = `50 * relist_reflected + 30 * stale_rejected + 20 * drifted_landed`

Grade thresholds are the house A-F curve (90/75/55/35).

## Why expansion is the point

Hand-authored benchmarks have a hidden coupling: the author's mental model of
the server's schemas. Expansion removes that coupling:

- **argument sampling** reads required fields and types from the live schema,
  so `required` mode always sends a schema-valid call and `missing` mode always
  omits a schema-required field — for *this* server, today.
- **select** (`*`, name lists, `regex:`) keeps templates reusable across
  totally different fleets.
- **phases** (`baseline` / `stale` / `drifted`) let one template test both the
  static contract and the server's reaction to change, from the same intent.

The output of `expand` *is* a deliverable: a concrete, diffable, replayable
battery representation of what a given server claims, checked against what it
does.

## Safety model

- Every run happens inside `Sandbox`: fresh temp cwd, scrubbed env (credential
  vars dropped), stderr discarded.
- Batteries only target the stdio server command the user names. There is no
  discovery, no network scanning, no persistence beyond the user's own report
  files.
- The reference fleet's `mcpbatt/apply_drift` control method is a private,
  sandbox-only affordance; a real server simply returns `-32601`, and the
  runner records the battery without a drift phase.
- The `--share` fingerprint contains aggregates only (axes means, grade
  histogram, run counts) — never tool names, schemas, arguments, or text.

## Determinism

- No wall-clock in scoring; transcripts are the only input.
- Argument sampling is a pure function of the schema (first enum value,
  well-typed minima).
- The fleet mutates its schema only when instructed, so drift runs reproduce.
- Same server + same template => same battery => same grade.