"""mcphazard — red-team harness for MCP servers.

Actively fuzzes every tool an MCP server exposes with adversarial payloads
(prompt injection, tool confusion, data exfiltration, policy bypass, data
poisoning) under a throwaway sandbox, detects whether the payloads "landed"
via echo/exfil/side-effect signals, and produces a pentest-style report.

Scope rule: `mcphazard scan` is sandbox-first. Live-fire into a real host
requires an explicit `--live` flag, and even then only non-destructive payloads
ship in the default bundle.
"""

__version__ = "0.1.0"