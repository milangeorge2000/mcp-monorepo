from __future__ import annotations

from mcpbench.drivers import DEFAULT_POLICY, CanonicalDriver, NaiveDriver, Policy, WORKLOAD
from mcpbench.models import GATED_TOOLS, drift_tools


def test_policy_allows_and_denies():
    assert DEFAULT_POLICY.allows("lookup")
    assert not DEFAULT_POLICY.allows("write_file")
    assert not DEFAULT_POLICY.allows("grant_permissions")


def test_policy_custom():
    p = Policy()
    assert not p.allows("run_backup")
    gated = {t: True for t in GATED_TOOLS}
    assert all(gated[t] is True for t in GATED_TOOLS)


def test_canonical_builds_exact_args():
    d = CanonicalDriver()
    schema = {"type": "object", "properties": {"record_id": {"type": "integer"}},
              "required": ["record_id"]}
    args = d.build_args(schema, {"record_id": "42"})
    assert args == {"record_id": 42}


def test_canonical_fills_drifted_required_scope():
    d = CanonicalDriver()
    drifted = next(t for t in drift_tools() if t["name"] == "lookup")
    schema = drifted["inputSchema"]
    args = d.build_args(schema, {"record_id": 7})
    assert set(args) == {"record_id", "scope"}
    assert isinstance(args["scope"], str)


def test_naive_ignores_policy():
    d = NaiveDriver()
    assert d.check_policy("write_file") is True


def test_workload_has_policy_and_plain_steps():
    intents = [s["intent"] for s in WORKLOAD]
    assert "lookup" in intents
    assert "write_file" in intents
    assert "grant_permissions" in intents