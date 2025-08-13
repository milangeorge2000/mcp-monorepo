from __future__ import annotations

from mcpbench.fleet import CODE_INVALID_PARAMS, CODE_POLICY_GATE, Fleet


def test_initialize_and_list():
    fleet = Fleet()
    out = fleet.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2024-11-05"}})
    assert out[0]["result"]["protocolVersion"] == "2024-11-05"
    listed = fleet.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert len(listed[0]["result"]["tools"]) == 5


def test_executes_lookup_and_archives():
    fleet = Fleet()
    fleet.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    out = fleet.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                        "params": {"name": "lookup", "arguments": {"record_id": 42}}})
    assert "record 42" in out[-1]["result"]["content"][0]["text"]


def test_policy_gate_refuses_gated_tools():
    fleet = Fleet()
    fleet.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    out = fleet.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                        "params": {"name": "grant_permissions",
                                   "arguments": {"principal": "svc", "policy": "admin"}}})
    assert out[-1]["error"]["code"] == CODE_POLICY_GATE


def test_invalid_params_rejected():
    fleet = Fleet()
    fleet.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": "lookup", "arguments": {"record_id": "not-an-int"}}})
    # first call triggers drift; validate the error type on second call after re-list
    fleet.tools = fleet.tools  # keep drifted schema in place
    out = fleet.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                        "params": {"name": "lookup", "arguments": {}}})
    assert out[-1]["error"]["code"] == CODE_INVALID_PARAMS


def test_unknown_tool_errors():
    fleet = Fleet()
    fleet.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    out = fleet.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                        "params": {"name": "nope", "arguments": {}}})
    assert out[-1]["error"]["code"] == -32601


def test_first_call_announces_drift():
    fleet = Fleet()
    fleet.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    out = fleet.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                        "params": {"name": "lookup", "arguments": {"record_id": 1}}})
    assert any(f.get("method") == "notifications/tools/list_changed" for f in out)
    assert fleet.drifted


def test_after_drift_lookup_needs_scope():
    fleet = Fleet()
    fleet.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    fleet.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                  "params": {"name": "lookup", "arguments": {"record_id": 1}}})
    out = fleet.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                        "params": {"name": "lookup", "arguments": {"record_id": 2}}})
    assert out[-1]["error"]["code"] == CODE_INVALID_PARAMS  # missing scope