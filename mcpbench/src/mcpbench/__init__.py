"""mcpbench — benchmark the clients, not the servers.

Every benchmark in the ecosystem scores the server. Ours drives *reference MCP
agent clients* against a fixed reference fleet + workload inside a sandbox and
measures who: speaks the protocol correctly (conformance), respects a policy
gate (policy), lands schema-valid tool calls (validity), and spends the least
context per useful outcome (economy). Results are a deterministic, repeatable
A-F leaderboard.

Scope rule: `mcpbench run` executes only against the bundled sandboxed
reference fleet. It never touches a real host, never requires a real agent, and
runs on the stdlib alone.
"""

__version__ = "0.1.0"