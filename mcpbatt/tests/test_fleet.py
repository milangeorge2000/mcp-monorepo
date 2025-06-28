"""End-to-end tests against the bundled reference fleet (real subprocesses)."""
import sys

from mcpbatt.fleet import ReferenceFleet, _validate, CODE_INVALID_PARAMS
from mcpbatt.models import Template
from mcpbatt.runner import run_battery, FLEET_ARGV


def test_reference_fleet_validate_missing():
    tool = {"name": "lookup", "inputSchema": {
        "type": "object", "properties": {"record_id": {"type": "integer"}},
        "required": ["record_id"]}}
    assert "missing required argument: record_id" in _validate(tool, {})


def test_reference_fleet_validate_wrong_type():
    tool = {"name": "lookup", "inputSchema": {
        "type": "object", "properties": {"record_id": {"type": "integer"}},
        "required": ["record_id"]}}
    assert "must be integer" in _validate(tool, {"record_id": "oops"})


def test_reference_fleet_validate_ok():
    tool = {"name": "lookup", "inputSchema": {
        "type": "object", "properties": {"record_id": {"type": "integer"}},
        "required": ["record_id"]}}
    assert _validate(tool, {"record_id": 7}) is None


def test_reference_fleet_call_unknown_tool():
    fleet = ReferenceFleet()
    frames = fleet.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": "ghost", "arguments": {}}})
    err = frames[0]["error"]
    assert err["code"] == -32601


def test_reference_fleet_invalid_params_code():
    fleet = ReferenceFleet()
    frames = fleet.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": "lookup", "arguments": {}}})
    assert frames[0]["error"]["code"] == CODE_INVALID_PARAMS


def test_reference_fleet_apply_drift_emits_changed():
    fleet = ReferenceFleet()
    frames = fleet.handle({"jsonrpc": "2.0", "id": 9, "method": "mcpbatt/apply_drift",
                           "params": {"tool": "search", "add_required": ["locale"]}})
    assert frames[0]["result"]["tool"] == "search"
    assert "locale" in frames[0]["result"]["added_required"]
    assert frames[1]["method"] == "notifications/tools/list_changed"
    assert fleet.drifted is True


def test_reference_fleet_drift_rejects_stale_args():
    fleet = ReferenceFleet()
    fleet.handle({"jsonrpc": "2.0", "id": 9, "method": "mcpbatt/apply_drift",
                  "params": {"tool": "search", "add_required": ["locale"]}})
    frames = fleet.handle({"jsonrpc": "2.0", "id": 10, "method": "tools/call",
                           "params": {"name": "search", "arguments": {"query": "x"}}})
    assert frames[0]["error"]["code"] == CODE_INVALID_PARAMS
    assert "locale" in frames[0]["error"]["message"]


# ---------------------------------------------------------------------------
# full battery runs (spawn the real server)
# ---------------------------------------------------------------------------

def test_required_only_battery_scores_A():
    t = Template(name="required-only", select="*", mode="required", expect="ok")
    r = run_battery(t, server_argv=FLEET_ARGV)
    assert r.grade == "A"
    assert r.scores["fidelity"] == 100.0
    assert r.calls_total == 4


def test_missing_required_battery_rejects():
    t = Template(name="missing-required", select="*", mode="missing", expect="invalid")
    r = run_battery(t, server_argv=FLEET_ARGV)
    assert r.scores["discipline"] == 100.0
    # lookup(1) + search(1) + create_entry(2 required fields) = 4 rejections
    assert r.invalid_calls == 4


def test_wrong_type_battery():
    t = Template(name="wrong-type", select="*", mode="wrong-type", expect="invalid")
    r = run_battery(t, server_argv=FLEET_ARGV)
    assert r.scores["discipline"] == 100.0


def test_drift_honesty_battery_sees_change():
    from mcpbatt.models import DriftSpec
    t = Template(name="drift-honesty", select="search", mode="required",
                 expect="ok", drift=DriftSpec(tool="search", add_required=["locale"]))
    r = run_battery(t, server_argv=FLEET_ARGV)
    assert r.drift_seen is True
    assert r.scores["drift"] == 100.0
    # baseline ok + stale rejected + drifted ok = 3 calls
    assert r.calls_total == 3
