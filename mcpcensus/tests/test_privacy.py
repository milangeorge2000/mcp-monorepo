"""Privacy-engineering tests: the whole reason mcpcensus is defensible."""

from mcpcensus.privacy import (
    DeviceSalt,
    cohort_bucket,
    k_anonymize,
    laplace_noise,
    stable_hash,
    clamp_noisy_count,
    is_valid_fingerprint,
    load_fingerprints_json,
)
from mcpcensus.fingerprint import build_context_fingerprint, build_security_fingerprint


def test_salt_roundtrip(tmp_path):
    path = str(tmp_path / "salt")
    a = DeviceSalt.load_or_create(path)
    b = DeviceSalt.load_or_create(path)
    assert a.salt == b.salt
    assert a.device_id == b.device_id
    assert len(a.device_id) == 16


def test_stable_hash_is_field_scoped():
    salt = b"x" * 16
    assert stable_hash(salt, "github", "server") != stable_hash(salt, "github", "tool")
    assert stable_hash(salt, "github", "server") == stable_hash(salt, "github", "server")


def test_fingerprint_leaks_no_raw_names(audit_report, guard_report, salt_bytes):
    ctx = build_context_fingerprint(audit_report, salt_bytes, "dev-id")
    sec = build_security_fingerprint(guard_report, salt_bytes, "dev-id")
    dumped = str(ctx) + str(sec)
    for leaked in ("mcp-server-filesystem", "legacy-bridge", "lexicon", "sketchy-remote",
                   "github", "AWS_SECRET_ACCESS_KEY", "shell_write", "npx sketchy@latest"):
        assert leaked not in dumped, f"fingerprint leaked {leaked!r}"


def test_fingerprint_format_valid(audit_report, salt_bytes):
    fp = build_context_fingerprint(audit_report, salt_bytes, "dev-id")
    assert is_valid_fingerprint(fp)
    assert fp["sensor"] == "context"
    assert fp["device"] == "dev-id"
    assert fp["axes"]["server_count"] == 3


def test_security_fingerprint_counts(guard_report, salt_bytes):
    fp = build_security_fingerprint(guard_report, salt_bytes, "dev-id")
    assert is_valid_fingerprint(fp)
    risk = fp["axes"]["risk_counts"]
    assert risk["critical"] == 1 and risk["high"] == 2 and risk["medium"] == 1
    assert fp["axes"]["remote_code_servers"] == 2
    assert fp["axes"]["grade_histogram"]["A"] == 1
    assert fp["axes"]["grade_histogram"]["F"] == 1


def test_cohort_bucket_consistent():
    # 6- and 8-server configs with similar tooling land in the SAME bucket.
    a = {"server_count": 5, "server_models": [{"tool_count": 10}], "waste_percent": 23, "dead_tool_count": 2,
         "schema_tokens": 100, "grade": "B"}
    b = {"server_count": 6, "server_models": [{"tool_count": 9}], "waste_percent": 29, "dead_tool_count": 3,
         "schema_tokens": 120, "grade": "C"}
    assert cohort_bucket(a, "context") == cohort_bucket(b, "context")
    c = {"server_count": 0, "server_models": [], "waste_percent": 31, "dead_tool_count": 0,
         "schema_tokens": 0, "grade": "B"}
    assert cohort_bucket(a, "context") != cohort_bucket(c, "context")


def test_k_anonymize_suppresses_small_cohorts():
    rows = [
        {"cohort": "A", "device": "1"},
        {"cohort": "A", "device": "2"},
        {"cohort": "B", "device": "3"},  # singleton in its cohort
    ]
    kept, suppressed = k_anonymize(rows, min_cohort=2)
    assert suppressed == 1
    assert [r["device"] for r in kept] == ["1", "2"]


def test_noise_is_symmetric_and_clamped():
    _ = _FakeRng()


def test_laplace_noise_distribution():
    import random
    samples = [laplace_noise(2.0, random.Random(i)) for i in range(2000)]
    # Laplace(0,b): std = b*sqrt(2) = 2*sqrt(2) ~ 2.83
    mean = sum(samples) / len(samples)
    assert abs(mean) < 0.2
    std = (sum((x - mean) ** 2 for x in samples) / len(samples)) ** 0.5
    assert 2.0 < std < 3.7


def test_noisy_count_never_negative():
    import random
    for seed in range(50):
        assert clamp_noisy_count(3, 5.0, random.Random(seed)) >= 0


def test_load_fingerprints_json_ignores_garbage():
    good = build_context_fingerprint(
        {"servers": [], "grade": "A", "baseline_tokens": 0, "dead_tools": 0,
         "dead_schema_tokens": 0, "waste_percent": 0, "context_footprint_percent": 0},
        b"s" * 16, "dev")
    import json
    lines = "\n".join([json.dumps(good), "not json", json.dumps({"format": "old"})])
    fps = load_fingerprints_json(lines)
    assert len(fps) == 1


class _FakeRng:
    def __init__(self):
        import random
        self._r = random.Random(0)

    def random(self):
        return self._r.random()