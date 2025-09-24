"""Report + hardened-config tests."""
import pytest

from mcpguard.models import Finding, GuardReport, Risk, ServerResult
from mcpguard.report import render_html, write_hardened_config


def _result(server, grade_f=None):
    findings = []
    if grade_f:
        findings.append(Finding(server=server, risk=Risk.CRITICAL, kind="dangerous_tool",
                                detail="tool `run_command` matches critical rule"))
    return ServerResult(
        server=server,
        mode="npx",
        remote_code=True,
        pinned=False,
        tools_scanned=grade_f and 4 or 2,
        findings=findings,
        raw_config={"command": "npx", "args": ["-y", "pkg"]},
    )


def _report(o=None):
    return GuardReport(
        results=[
            _result("safe-server"),
            _result("bad-server", grade_f=True),
        ],
        generated_at="2026-08-16 12:00",
        source_configs=["a", "b"],
        intel_bundle_version="2026.08.15",
    ) if o is None else o


def test_overall_grade_worst_wins():
    assert _report().overall_grade == "F"


def test_risk_counts():
    counts = _report().risk_counts
    assert counts["critical"] == 1


def test_hardened_config_drops_f_servers():
    hardened = write_hardened_config(_report())
    assert set(hardened["mcpServers"]) == {"safe-server"}
    assert hardened["mcpServers"]["safe-server"]["command"] == "npx"
    assert hardened["_review"][0]["server"] == "bad-server"


def test_render_html_contains_grade_and_copy():
    html = render_html(_report(), ["a", "b"])
    assert "mcpguard" in html
    assert "id=\"copy\"" in html
    assert "F" in html
    assert "bad-server" in html