from __future__ import annotations

import json

from mcphazard.client import call_tool, probe_tools
from mcphazard.sandbox import make_sandbox
from tests.conftest import toxicserver_env


def test_probe_tools_lists_three():
    sb = make_sandbox(live=False)
    try:
        tools = probe_tools(sb, toxicserver_env())
        names = {t.get("name") for t in tools}
        assert {"echo", "search", "fetch"} <= names
    finally:
        sb.cleanup()


def test_call_tool_echo_returns_text():
    sb = make_sandbox(live=False)
    try:
        res = call_tool(sb, toxicserver_env(), "echo", {"text": "ping"})
        assert res.ok
        assert "ping" in res.text
    finally:
        sb.cleanup()


def test_call_tool_unknown_tool_fails():
    sb = make_sandbox(live=False)
    try:
        res = call_tool(sb, toxicserver_env(), "bogus", {})
        assert not res.ok
        assert res.error
    finally:
        sb.cleanup()


def test_call_tool_returns_duration_ms():
    sb = make_sandbox(live=False)
    try:
        res = call_tool(sb, toxicserver_env(), "echo", {"text": "x"})
        assert res.duration_ms >= 0
    finally:
        sb.cleanup()


def test_flatten_structured_content():
    from mcphazard.client import _flatten_result
    res = _flatten_result({"content": [{"type": "text", "text": "alpha"}],
                           "structuredContent": {"n": 1}}, 3.0)
    assert res.ok
    assert "alpha" in res.text
    assert "1" in res.text