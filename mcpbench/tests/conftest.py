from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def fleet_argv() -> list:
    import mcpbench.harness as h
    return list(h.FLEET_ARGV)