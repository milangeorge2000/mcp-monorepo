#!/usr/bin/env python3
"""Reference fleet entry point: ``python -m mcpbench.fleet`` (stdio server).

Standalone so the harness can spawn it as a subprocess inside the sandbox.
"""
from mcpbench.fleet import _loop

if __name__ == "__main__":
    raise SystemExit(_loop())