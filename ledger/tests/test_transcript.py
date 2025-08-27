"""Transcript parsing + trail model tests."""

import json
from pathlib import Path

from ledger.models import Event, Trail, write_trail, read_trail
from ledger.transcript import (
    parse_claude_code,
    parse_generic_rows,
    record_transcripts,
    estimate_tokens,
    extract_files,
    detect_format,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_claude_code_builds_trail():
    trail = parse_claude_code((FIXTURES / "claude-code.jsonl").read_text(encoding="utf-8"))
    tools = [e for e in trail.events if e.kind == "tool_use"]
    assert [e.tool for e in tools] == ["Read", "Edit", "Bash"]
    assert tools[0].files == ["tests/test_login.py"]
    # the failing Edit result is flagged
    results = [e for e in trail.events if e.kind == "tool_result"]
    assert any(r.ok is True for r in results)   # Read result ok
    assert any(r.ok is False for r in results)  # Edit result error


def test_estimate_tokens_and_files():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abc") == 1
    assert extract_files({"file_path": "a.py", "paths": ["b.py"], "command": "ls"}) == ["a.py", "b.py"]
    assert extract_files({"command": "ls"}) == []


def test_parse_generic_rows():
    rows = [
        {"when": "2025-01-01", "kind": "tool_use", "tool": "Bash", "input": {"command": "ls"}, "tokens_in": 10},
        {"when": "2025-01-01", "kind": "tool_use", "tool": "Read", "input": {"file_path": "x.py"}},
    ]
    trail = parse_generic_rows(rows)
    assert trail.events[0].tool == "Bash"
    assert trail.events[1].files == ["x.py"]


def test_record_transcripts_merges_and_detects():
    trail = record_transcripts(
        [str(FIXTURES / "claude-code.jsonl"), str(FIXTURES / "generic.jsonl")], fmt="auto")
    assert trail.meta["formats"] == ["claude-code", "generic"]
    # seqs contiguous across files
    assert [e.seq for e in trail.events] == list(range(1, len(trail.events) + 1))
    assert any(e.kind == "tool_use" for e in trail.events)


def test_detect_format():
    assert detect_format('{"type":"user","message":"hi"}') == "claude-code"
    assert detect_format('{"when":"x","tool":"Bash"}') == "generic"


def test_trail_roundtrip(tmp_path):
    trail = record_transcripts([str(FIXTURES / "claude-code.jsonl")])
    path = str(tmp_path / "trail.json")
    write_trail(trail, path)
    restored = read_trail(path)
    assert restored.summary()["events"] == trail.summary()["events"]
    assert restored.events[0].tool == trail.events[0].tool