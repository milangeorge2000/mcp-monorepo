# Architecture

`mcpbench` is a small, dependency-free *client* benchmark. Every other
benchmark in the ecosystem scores the server; mcpbench stands a fleet up and
scores whoever drives it. The pipeline: spawn the bundled reference fleet in a
sandbox → drive a deterministic client *behaviour profile* against it through a
recording MCP client → score the recorded transcript → assemble the
leaderboard.

## Pipeline

```
 driver profile (canonical / naive / chatty / careless)
        │  drives the SAME workload intents
        ▼
 recording Client  (initialize → tools/list → tools/call, frames recorded)
        │
        ▼
 bundled reference fleet  (python -m mcpbench.fleet)
        • 5 tools, schema-validated calls
        • policy-gated tools refused with a distinct error code
        • schema drift + tools/list_changed after the first call
        │
        ▼
 scorer  (conformance / policy / validity / economy / drift — from transcript)
        │
        ▼
 leaderboard  (report.py HTML + JSON) · share.py (mcpcensus sensor=bench)
```

### Module map

| module | responsibility |
|---|---|
| `cli.py` | `run` / `list` subcommands, driver selection, `--share` |
| `drivers.py` | deterministic client behaviour profiles + the shared `Policy` gate |
| `fleet.py` | the bundled reference fleet server (`.fleet_server` = subprocess entry) |
| `client.py` | recording MCP stdio client; tolerates server→client notifications |
| `sandbox.py` | fresh temp cwd + scrubbed env per run |
| `scoring.py` | transcript → axis scores + grade |
| `models.py` | `FLEET_TOOLS`, `GATED_TOOLS`, `DriverResult`, `BenchReport`, grades |
| `report.py` | `render_html` leaderboard + `to_json` export |
| `share.py` | `--share` census fingerprint under `sensor=bench` |

## Design decisions

1. **Client up, not server down.** The fleet is small, fixed, and bundled so
   the *only* independent variable is the client. That is what makes the
   leaderboard a statement about clients.
2. **Deterministic drivers, honest scoring.** Reference profiles replace real
   agents, but every axis is still computed from the *recorded exchanges* and
   the fleet's replies — never from the driver's own claims. You can replay
   the transcript to verify a score by hand.
3. **Drift is a first-class axis.** The fleet changes its `lookup` schema mid
   run and announces `tools/list_changed`; a driver that re-lists adapts (its
   calls stay valid), one that caches forever keeps failing. Reproducible and
   auditable.
4. **Economy is cohort-relative.** Tokens per useful outcome are meaningless
   alone; scoring against the leanest driver on the same run keeps it honest
   without needing a tokenizer dependency.
5. **Zero runtime deps.** Stdlib only, exactly like the rest of the kit.
6. **Findings are review triggers.** A `D` on policy means "this behaviour
   profile ignores the gate" — a trigger to inspect, never an indictment of a
   vendor by name.

## Extending the benchmark

- **New driver** → subclass `BaseDriver` in `drivers.py`, register it in
  `DRIVER_REGISTRY`. Pick policy, schema, drift, and economy knobs.
- **New fleet behaviour** → adjust `fleet.py` (`Fleet.handle`); keep the error
  codes and the drift mechanic stable so scoring tests don't churn.
- **New axis** → add a scorer in `scoring.py` and surface it in `report.py`;
  keep weights in `_overall` documented.

## Guardrails

- `run_benchmark` refuses unknown drivers with a clean exit code 2.
- Every driver spawn gets a fresh sandbox; failure of one driver is isolated
  and recorded as a note, never fatal.
- The fleet is bundled and deterministic; mcpbench never contacts a real host.