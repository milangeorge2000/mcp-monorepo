from __future__ import annotations

from mcphazard.models import Risk, inject_payload
from mcphazard.payloads import bundled_payloads, CANARY, SINK_URL


def test_bundle_shape():
    items = bundled_payloads(live=False)
    assert items
    for p in items:
        assert p.klass
        assert p.name
        assert p.payload
        assert isinstance(p.risk, Risk)


def test_bespoke_excluded_by_default():
    plain = bundled_payloads(live=False)
    full = bundled_payloads(live=True)
    assert len(full) > len(plain)
    assert not any(p.bespoke for p in plain)
    assert any(p.bespoke for p in full)


def test_exfil_payload_targets_sink():
    url_payloads = [p for p in bundled_payloads(live=True) if p.klass == "data_exfiltration"]
    assert url_payloads
    assert all(SINK_URL in p.payload or "mcphazard-canary.example" in p.payload for p in url_payloads)


def test_canary_is_stable():
    assert CANARY == "mcphz-7f3a9c1e"


def test_inject_payload_targets_first_string_key():
    schema = {"type": "object",
              "properties": {"text": {"type": "string"}, "n": {"type": "integer"}},
              "required": ["text"]}
    args = inject_payload(schema, "INJECT", None, CANARY)
    assert args["text"] == "INJECT"
    assert args["n"] == 0


def test_inject_payload_respects_target_key():
    schema = {"type": "object",
              "properties": {"query": {"type": "string"}},
              "required": ["query"]}
    args = inject_payload(schema, "X", "query", CANARY)
    assert args["query"] == "X"


def test_inject_payload_empty_schema_shorthand():
    args = inject_payload({}, "X", None, CANARY)
    assert args == {"input": "X"}


def test_bundle_has_all_expected_classes():
    klasses = {p.klass for p in bundled_payloads(live=True)}
    assert {"prompt_injection", "prompt_leak", "policy_bypass", "data_exfiltration",
            "tool_confusion", "resource_exhaustion"}.issubset(klasses)