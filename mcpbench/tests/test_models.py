from __future__ import annotations

import pytest

from mcpbench.models import FLEET_TOOLS, GATED_TOOLS, drift_tools, grade_for


def test_fleet_tools_are_fixed():
    assert len(FLEET_TOOLS) == 5
    names = [t["name"] for t in FLEET_TOOLS]
    assert names == ["lookup", "archive_file", "write_file", "grant_permissions", "run_backup"]


def test_gated_tools_are_gated():
    assert set(GATED_TOOLS) == {"write_file", "grant_permissions", "run_backup"}
    for name in GATED_TOOLS:
        assert any(t["name"] == name for t in FLEET_TOOLS)


def test_drift_tools_add_scope_to_lookup():
    drifted = drift_tools()
    lookup = next(t for t in drifted if t["name"] == "lookup")
    assert "scope" in lookup["inputSchema"]["required"]
    assert "scope" in lookup["inputSchema"]["properties"]


def test_grade_for_thresholds():
    assert grade_for(95) == "A"
    assert grade_for(90) == "A"
    assert grade_for(80) == "B"
    assert grade_for(60) == "C"
    assert grade_for(40) == "D"
    assert grade_for(0) == "F"