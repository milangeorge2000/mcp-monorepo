"""Shared test helpers and path keepers."""
from __future__ import annotations

import sys
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
if str(EXAMPLES) not in sys.path:
    sys.path.insert(0, str(EXAMPLES))

FAKE_SERVER = str(EXAMPLES / "fake_mcp_server.py")
DEMO_CONFIG = str(EXAMPLES.parent / "examples" / "demo-mcp.json")


def fixture(*names: str) -> Path:
    return Path(FIXTURES, *names)