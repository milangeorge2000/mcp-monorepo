"""Policy gate + dossier + diff tests."""

import json
from pathlib import Path

from ledger.models import Event, Trail
from ledger.policy import gate, load_policy, _matches
from ledger.dossier import compose_dossier, diff_trails, format_diff, manifest
from ledger.transcript import record_transcripts, parse_generic_rows

FIXTURES = Path(__file__).parent / "fixtures"


def _trail():
    return record_transcripts([str(FIXTURES / "generic.jsonl")])


def test_gate_flags_denied_tool(tmp_path):
    trail = _trail()
    policy = load_policy(str(FIXTURES / "policy.json"))
    result = gate(trail, policy)
    rules = {v.rule for v in result.violations}
    # shell_write is denied outright
    assert any(v.reason and "shell_write" in v.reason for v in result.violations)
    assert result.ok is False


def test_gate_approval_required():
    trail = _trail()
    ev = Event(seq=1, when="", kind="tool_use", tool="deploy",
               input={"target": "prod"}, files=[])
    gate2 = gate(Trail(events=[ev]), {"require_human_approval": ["*deploy*"]})
    assert any(v.rule == "require_human_approval" for v in gate2.violations)
    approved = Event(seq=1, when="", kind="tool_use", tool="deploy", approved=True,
                     input={}, files=[])
    gate3 = gate(Trail(events=[approved]), {"require_human_approval": ["*deploy*"]})
    assert gate3.ok


def test_gate_allow_overrides_deny():
    ev = Event(seq=1, when="", kind="tool_use", tool="Read", input={"file_path": "a.py"}, files=["a.py"])
    result = gate(Trail(events=[ev]), {"allow": [{"tool": "Read"}], "deny": [{"tool": "Read"}]})
    assert result.ok


def test_gate_budget():
    ev = Event(seq=1, when="", kind="tool_use", tool="Bash", input={}, tokens_in=100)
    result = gate(Trail(events=[ev]), {"budget_tokens_in": 50})
    assert any(v.rule == "budget" for v in result.violations)


def test_deny_input_has():
    ev = Event(seq=1, when="", kind="tool_use", tool="Bash",
               input={"command": "rm -rf /tmp/x"})
    assert _matches({"tool": "Bash", "input_has": "rm -rf"}, ev, 1)


def test_dossier_html_renders():
    trail = record_transcripts([str(FIXTURES / "claude-code.jsonl")])
    doc = compose_dossier(trail, "login flake incident")
    assert "action tape" in doc
    assert "tests/test_login.py" in doc
    assert "$" in doc


def test_diff_detects_change():
    rows_a = [
        {"when": "t", "kind": "tool_use", "tool": "Read", "input": {"file_path": "a.py"}},
        {"when": "t", "kind": "tool_use", "tool": "Bash", "input": {"command": "pytest"}},
    ]
    rows_b = [
        {"when": "t", "kind": "tool_use", "tool": "Edit", "input": {"file_path": "a.py"}},
    ]
    ta, tb = parse_generic_rows(rows_a), parse_generic_rows(rows_b)
    d = diff_trails(ta, tb)
    assert sorted(d["tools_removed"]) == ["Bash", "Read"]
    assert d["tools_added"] == ["Edit"]
    assert d["events_delta"] == -1
    assert isinstance(format_diff(d), str)
    assert d["a"]["events"] == 2


def test_manifest_counts():
    trail = record_transcripts([str(FIXTURES / "claude-code.jsonl")])
    m = manifest(trail)
    assert m["tools"]["Read"] == 1
    assert "tests/test_login.py" in m["files"]