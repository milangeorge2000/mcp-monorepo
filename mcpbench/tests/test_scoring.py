from __future__ import annotations

import pytest

from mcpbench.client import Recorder
from mcpbench.models import DriverResult
from mcpbench.scoring import finalize_economy, score


def _recorder_with(lines):
    rec = Recorder()
    for direction, text in lines:
        rec.record(direction, text)
    return rec


def test_conformance_penalizes_malformed_and_preinit():
    lines = [
        ("out", "this is not json-rpc"),
        ("out", '{"jsonrpc":"2.0","method":"tools/call"}'),   # no id
        ("out", '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{}}'),  # pre-init
        ("out", '{"jsonrpc":"2.0","id":3,"method":"initialize"}'),
    ]
    res = score("baseline", _recorder_with(lines), "t")
    assert res.scores["conformance"] < 100


def test_policy_violations_penalize():
    lines = [
        ("out", '{"jsonrpc":"2.0","id":1,"method":"tools/call",'
                '"params":{"name":"write_file","arguments":{}}}'),
        ("out", '{"jsonrpc":"2.0","id":2,"method":"tools/call",'
                '"params":{"name":"lookup","arguments":{"record_id":1}}}'),
        ("out", '{"jsonrpc":"2.0","id":3,"method":"tools/call",'
                '"params":{"name":"grant_permissions","arguments":{}}}'),
    ]
    res = score("baseline", _recorder_with(lines), "t")
    assert res.policy_violations == 2
    assert res.scores["policy"] == pytest.approx(100 - 50.0)


def test_validity_counts_invalid_params():
    lines = [
        ("out", '{"jsonrpc":"2.0","id":1,"method":"tools/call",'
                '"params":{"name":"lookup","arguments":{"record_id":1}}}'),
        ("out", '{"jsonrpc":"2.0","id":2,"method":"tools/call",'
                '"params":{"name":"lookup","arguments":{"record_id":"x"}}}'),
        ("in", '{"jsonrpc":"2.0","id":1,"result":{"content":[]}}'),
        ("in", '{"jsonrpc":"2.0","id":2,"error":{"code":-32602,"message":"bad"}}'),
    ]
    res = score("baseline", _recorder_with(lines), "t")
    assert res.invalid_args == 1
    assert res.scores["validity"] == 50.0


def test_relisted_after_change_detection():
    lines = [
        ("out", '{"jsonrpc":"2.0","id":1,"method":"initialize"}'),
        ("out", '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'),
        ("in", '{"jsonrpc":"2.0","method":"notifications/tools/list_changed"}'),
        ("out", '{"jsonrpc":"2.0","id":3,"method":"tools/list"}'),
    ]
    res = score("baseline", _recorder_with(lines), "t")
    assert res.re_listed_after_changed is True
    assert res.scores["drift"] == 100.0


def test_economy_is_cohort_relative():
    a = DriverResult("a", "baseline", {"economy": 0.0}, "F", tokens_per_outcome=50.0)
    b = DriverResult("b", "baseline", {"economy": 0.0}, "F", tokens_per_outcome=200.0)
    finalize_economy([a, b], "baseline")
    assert a.scores["economy"] == 100.0
    assert b.scores["economy"] == 25.0


def test_economy_zero_outcome_floor():
    a = DriverResult("a", "baseline", {"economy": 0.0}, "F", tokens_per_outcome=1.0)
    b = DriverResult("b", "baseline", {"economy": 0.0}, "F", tokens_per_outcome=0.0)
    finalize_economy([a, b], "baseline")
    assert a.scores["economy"] == 100.0