"""Tests for session-log probing and report logic."""
import pytest

from mcpaudit.models import AuditReport, ServerMeasurement, ToolSchema, UsageStats
from mcpaudit.probe import _normalize, scan_usage
from mcpaudit.report import render_html, write_slim_config

from conftest import FIXTURES


def test_normalize_mcp_tool():
    assert _normalize("mcp__github__create_issue") == "github:create_issue"
    assert _normalize("plain_tool") == "plain_tool"


def test_scan_usage_against_fixture():
    # scan_usage looks at real dirs; force it at our fixture by monkeypatch-free probe
    import mcpaudit.probe as probe

    orig = probe._scan_dirs
    probe._scan_dirs = lambda: [FIXTURES / "sessions"]
    try:
        stats = scan_usage(window_days=90)
    finally:
        probe._scan_dirs = orig
    calls = stats.calls
    assert calls.get("github:create_issue") == 1
    assert calls.get("github:list_issues") == 3
    assert calls.get("github:get_issue") == 1
    assert calls.get("filesystem:read_file") == 1
    assert calls.get("filesystem:write_file") == 1
    assert "not an mcp tool" not in calls


def _report_fixture():
    tool_schema = [
        ToolSchema(server="github", name="create_issue", description="d", raw_tokens=40),
        ToolSchema(server="github", name="list_issues", description="d", raw_tokens=40),
        ToolSchema(server="github", name="get_issue", description="d", raw_tokens=40),
        ToolSchema(server="filesystem", name="read_file", description="d", raw_tokens=60),
        ToolSchema(server="filesystem", name="write_file", description="d", raw_tokens=60),
        ToolSchema(server="filesystem", name="list_directory", description="d", raw_tokens=60),
    ]
    usage = UsageStats(
        calls={
            "github:create_issue": 2,
            "github:list_issues": 5,
            "github:get_issue": 1,
            "filesystem:read_file": 3,
            "filesystem:write_file": 1,
        },
        window_days=30,
    )
    servers = [
        ServerMeasurement(
            server="github", ok=True, tools=tool_schema[:3],
            schema_tokens=120, baseline_tokens=120,
        ),
        ServerMeasurement(
            server="filesystem", ok=True, tools=tool_schema[3:],
            schema_tokens=180, baseline_tokens=180,
        ),
    ]
    return AuditReport(
        servers=servers, usage=usage, context_limit=200_000,
        generated_at="2026-08-16 12:00", source_configs=["x"],
    )


def test_report_computed_fields():
    report = _report_fixture()
    assert report.baseline_tokens == 300
    assert report.dead_tools == ["list_directory"]
    assert report.dead_schema_tokens == 60
    assert report.waste_percent == pytest.approx(20.0)
    assert report.grade == "B"


def test_slim_config_keeps_used_servers_only():
    report = _report_fixture()
    slim = write_slim_config(report)
    assert set(slim["mcpServers"]) == {"github", "filesystem"}


def test_render_html_contains_grade_and_copy_button():
    report = _report_fixture()
    html = render_html(report)
    assert "Grade" in html
    assert "id=\"copy\"" in html
    assert "github" in html


def test_slim_config_when_no_logs_keeps_everything():
    report = _report_fixture()
    report.usage = UsageStats(calls={}, window_days=30)
    slim = write_slim_config(report)
    assert set(slim["mcpServers"]) == {"github", "filesystem"}