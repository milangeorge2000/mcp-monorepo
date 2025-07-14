from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

EXAMPLE_SERVER = str(
    Path(__file__).resolve().parents[1] / "examples" / "fake_toxic_server.py"
)


def toxicserver_env() -> list:
    conf = Path(__file__).resolve().parents[1] / "examples" / "demo-mcp.json"
    return [sys.executable, EXAMPLE_SERVER, "toxic"]