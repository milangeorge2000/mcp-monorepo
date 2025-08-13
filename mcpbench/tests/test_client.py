from __future__ import annotations

import json

import pytest

from mcpbench.client import Client, Recorder
from mcpbench.sandbox import make_sandbox


def _spawn():
    import mcpbench.harness as h
    sb = make_sandbox()
    proc = sb.spawn(h.FLEET_ARGV)
    rec = Recorder()
    return sb, Client(proc, rec, timeout=5.0)


def test_initialize_list_call_roundtrip():
    sb, client = _spawn()
    try:
        result = client.initialize()
        assert result["protocolVersion"] == "2024-11-05"
        tools = client.list_tools()
        assert len(tools) == 5
        assert client.initialized
    finally:
        sb.cleanup()


def test_call_tool_gets_result():
    sb, client = _spawn()
    try:
        client.initialize()
        out = client.call_tool("archive_file", {"path": "a.pdf"})
        assert "archived a.pdf" in out["content"][0]["text"]
    finally:
        sb.cleanup()


def test_recorder_counts_tokens():
    rec = Recorder()
    rec.record("out", "x" * 40)
    assert rec.tokens == 10
    assert len(rec.lines) == 1


def test_notification_skipped_in_response_loop():
    """tools/list_changed arrives as a notification frame; the client must
    keep reading until the real response, and the recorder captures both."""
    sb, client = _spawn()
    try:
        client.initialize()
        client.call_tool("lookup", {"record_id": 1})  # triggers drift notify
        saw = client.saw_list_changed
        assert saw
    finally:
        sb.cleanup()


def test_frame_recording_captures_both_directions():
    sb, client = _spawn()
    try:
        client.initialize()
        client.list_tools()
        dirs = {ln["dir"] for ln in client.rec.lines}
        assert dirs == {"out", "in"}
    finally:
        sb.cleanup()