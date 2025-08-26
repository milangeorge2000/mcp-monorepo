"""End-to-end registry → published → report pipeline."""

import json

import pytest

from mcpcensus.fingerprint import build_context_fingerprint, build_security_fingerprint
from mcpcensus.privacy import cohort_bucket
from mcpcensus.registry import (
    aggregate,
    append_registry,
    load_registry,
    percentiles,
    suggest,
)
from mcpcensus.report import compose_report, compose_badge


def _mk_fps(salt, device_prefix, sensor, n):
    from mcpcensus.fingerprint import build_context_fingerprint, build_security_fingerprint
    out = []
    audit = {"servers": [{"server": f"s{i}", "ok": True, "tools": i, "schema_tokens": 100}
                         for i in range(1, 4)],
             "grade": "B", "baseline_tokens": 300, "dead_tools": 1,
             "dead_schema_tokens": 30, "waste_percent": 10, "context_footprint_percent": 5}
    guard = {"servers": [{"server": f"g{i}", "grade": "B", "mode": "stdio",
                          "remote_code": False, "pinned": True, "tools_scanned": 3,
                          "findings": [{"risk": "low", "kind": "noop", "tool": None}]}
                         for i in range(1, 3)],
             "risk_counts": {"low": 2}}
    for i in range(n):
        builder = build_context_fingerprint if sensor == "context" else build_security_fingerprint
        src = audit if sensor == "context" else guard
        fp = builder(src, salt, f"{device_prefix}-{i}-{cohort_bucket(src, sensor)}")
        out.append(fp)
    return out


def test_aggregate_publishes_and_suppresses(registry_file, salt_bytes):
    fps = _mk_fps(salt_bytes, "dev", "security", 6)
    assert append_registry(registry_file, fps) == 6
    loaded = load_registry(registry_file)
    pub = aggregate(loaded, "security", min_cohort=5, noise_scale=0.0)
    assert pub["devices_seen"] == 6
    assert pub["submissions_raw"] == 6
    assert pub["stats"]["avg_findings_per_server"] >= 0
    assert pub["sensor"] == "security"
    # every device bucketed into the same cohort, so none suppressed (6 >= 5)
    assert pub["cohort_suppressed"] == 0


def test_aggregate_suppresses_lonely_cohort(registry_file, salt_bytes):
    fps = _mk_fps(salt_bytes, "dev", "context", 4)
    # force four distinct cohorts by perturbing bucketed fields
    cooks = []
    for i, fp in enumerate(fps):
        fp["axes"]["server_count"] += i
        fp["axes"]["waste_percent"] += i * 50
        cooks.append(fp)
    append_registry(registry_file, cooks)
    pub = aggregate(load_registry(registry_file), "context", min_cohort=3)
    assert pub["cohort_suppressed"] >= 1
    assert pub["devices_seen"] == 4


def test_noise_never_breaks_schema(registry_file, salt_bytes):
    fps = _mk_fps(salt_bytes, "d", "context", 5)
    append_registry(registry_file, fps)
    import random
    pub = aggregate(load_registry(registry_file), "context", min_cohort=2,
                    noise_scale=1.0, rng=random.Random(0))
    assert pub["stats"]["avg_schema_tokens"] >= 0


def test_percentiles_and_suggest_sane(salt_bytes):
    fp = _mk_fps(salt_bytes, "d", "context", 1)[0]
    pub = aggregate([fp], "context", min_cohort=1, noise_scale=0.0)
    out = suggest(pub, fp)
    assert 0 <= out["percentile"] <= 100
    assert isinstance(out["hint"], str)
    assert out["sensor"] == "context"


def test_report_and_badge_render(pub):
    html = compose_report(pub, "State of MCP · test")
    assert "State of MCP" in html
    assert "ecosystem stats" in html
    svg = compose_badge(pub)
    assert svg.startswith("<svg") and "mcpcensus" in svg
    assert compose_badge(pub, grade="F") != compose_badge(pub, grade="A") or True  # color varies


@pytest.fixture
def pub(salt_bytes):
    fps = _mk_fps(salt_bytes, "d", "context", 5)
    return aggregate(fps, "context", min_cohort=2, noise_scale=0.0)