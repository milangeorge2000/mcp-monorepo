from __future__ import annotations

from mcphazard.harness import scan_server
from mcphazard.models import Finding, Risk, ToolKinematics
from mcphazard.report import render_html, to_json
from tests.conftest import toxicserver_env


def test_to_json_structure():
    report = scan_server(toxicserver_env(), server_name="toxic-demo", live=False)
    payload = to_json(report)
    assert payload["server"] == "toxic-demo"
    assert "tools" in payload
    assert "overall_grade" in payload
    for t in payload["tools"]:
        assert t["tool"] in {"echo", "search", "fetch"}
        assert "findings" in t


def test_render_html_contains_key_sections():
    report = scan_server(toxicserver_env(), server_name="toxic-demo", live=True)
    html = render_html(report)
    assert "mcphazard" in html
    assert "LIVE-FIRE" in html
    assert "Findings by tool" in html
    assert "SANDBOX" not in html.replace("LIVE-FIRE", "")


def test_render_html_escapes_evidence():
    kin = ToolKinematics(tool="<script>", calls=1)
    kin.findings.append(Finding("srv", "<script>", "prompt_injection", Risk.HIGH,
                                "echo", "<b>raw</b>", "<img onerror=1>", "payload"))
    report = type("R", (), {
        "results": [kin], "tool_count": 1, "payload_count": 1, "finding_count": 1,
        "risk_counts": {"critical": 0, "high": 1, "medium": 0, "low": 0, "info": 0},
        "overall_grade": "D", "server": "srv", "live": True, "generated_at": "t",
    })()
    html = render_html(report)
    assert "&lt;img onerror=1&gt;" in html
    assert "&lt;b&gt;raw&lt;/b&gt;" in html
    assert "&lt;script&gt;" in html


def test_json_jq_grade_single_token():
    report = scan_server(toxicserver_env(), server_name="toxic-demo", live=False)
    assert to_json(report)["overall_grade"] in "ABCDF"


def test_risk_counts_keyed():
    report = scan_server(toxicserver_env(), server_name="toxic-demo", live=False)
    for k in ("critical", "high", "medium", "low", "info"):
        assert k in report.risk_counts


def test_grade_reflects_worst_finding():
    from mcphazard.models import HazardReport, Risk, ToolKinematics, Finding
    kin = ToolKinematics(tool="x", calls=1)
    kin.findings.append(Finding("s", "x", "data_exfiltration", Risk.CRITICAL, "exfil", "", "", ""))
    kin.findings.append(Finding("s", "x", "prompt_injection", Risk.LOW, "echo", "", "", ""))
    report = HazardReport(results=[kin], server="s", live=False, payload_count=1, tool_count=1)
    assert report.overall_grade == "F"
    assert kin.grade == "F"