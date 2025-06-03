"""mcpbatt - a benchmark that writes its own benchmark.

Every other bench in the ecosystem ships a hand-authored workload. mcpbatt
inverts that: you author small *scenario templates* (a tiny DSL), and the
engine expands them into a concrete battery tailored to a live server's actual
`tools/list` schemas - then runs that battery in a sandbox and grades the
server on whether it honors its own schema (fidelity), rejects malformed input
with proper JSON-RPC errors (discipline), stays up under load (stability), and
reacts truthfully to a mid-run schema change (drift). The generated battery is
an artifact you can print, diff, and replay - the benchmark is *created*, not
pasted.

Scope rule: `mcpbatt run` executes only against the stdio server command you
name (default: the bundled reference fleet) in a fresh, scrubbed sandbox. It
never talks to a remote host on its own and runs on the stdlib alone.
"""

__version__ = "0.1.0"
