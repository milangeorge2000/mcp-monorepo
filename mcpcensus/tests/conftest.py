"""Shared fixtures mirroring the *exact* JSON shapes of mcpaudit/mcpguard --json
output, so the observatory contract is tested against real sensor output."""

from __future__ import annotations

import json
import pytest


def mcpaudit_report_json():
    return {
        "grade": "B",
        "waste_percent": 23.4,
        "baseline_tokens": 40000,
        "context_footprint_percent": 20.0,
        "dead_tools": 4,
        "dead_schema_tokens": 9360,
        "servers": [
            {"server": "github", "ok": True, "tools": 21, "schema_tokens": 18000,
             "baseline_tokens": 18000, "error": None},
            {"server": "mcp-server-filesystem", "ok": True, "tools": 12, "schema_tokens": 14000,
             "baseline_tokens": 14000, "error": None},
            {"server": "legacy-bridge", "ok": True, "tools": 9, "schema_tokens": 8000,
             "baseline_tokens": 8000, "error": None},
        ],
    }


def intel_mcpguard_report_json():
    return {
        "overall_grade": "C",
        "risk_counts": {"critical": 1, "high": 2, "medium": 1},
        "servers": [
            {"server": "github", "grade": "C", "mode": "stdio", "remote_code": False, "pinned": True,
             "tools_scanned": 21, "probe_error": None,
             "findings": [
                 {"risk": "high", "kind": "unpinned_package", "detail": "npx github@0.1.0 unpinned", "tool": None},
                 {"risk": "medium", "kind": "dangerous_tool", "detail": "shell_write exposed", "tool": "shell_write"},
             ]},
            {"server": "lexicon", "grade": "A", "mode": "http", "remote_code": True, "pinned": True,
             "tools_scanned": 4, "probe_error": None, "findings": []},
            {"server": "sketchy-remote", "grade": "F", "mode": "streamable", "remote_code": True,
             "pinned": False, "tools_scanned": 17, "probe_error": None,
             "findings": [
                 {"risk": "critical", "kind": "remote_code", "detail": "npx sketchy@latest", "tool": None},
                 {"risk": "high", "kind": "secret_env", "detail": "AWS_SECRET_ACCESS_KEY in env", "tool": None},
             ]},
        ],
    }


@pytest.fixture
def audit_report():
    return mcpaudit_report_json()


@pytest.fixture
def guard_report():
    return intel_mcpguard_report_json()


@pytest.fixture
def registry_file(tmp_path):
    return str(tmp_path / "registry.jsonl")


@pytest.fixture
def salt_bytes():
    import os
    return os.urandom(16)