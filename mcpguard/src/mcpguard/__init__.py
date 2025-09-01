"""mcpguard — a security scorecard for your MCP servers.

Grades every MCP server in your config (A–F) based on how it is launched, the
tool capabilities it exposes, the environment it touches, and known-bad package
intel. Produces a shareable report.html plus a hardened config to apply.
"""

__version__ = "0.1.0"