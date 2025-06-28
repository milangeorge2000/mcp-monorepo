from mcpbatt.models import CallRecord, CallSpec, ServerResult, Template
from mcpbatt.scoring import score_server


def _spec(tool, expect, phase="baseline", args=None):
    return CallSpec(seq=1, tool=tool, arguments=args or {}, expect=expect, phase=phase)


def _rec(tool, expect, outcome, phase="baseline"):
    return CallRecord(spec=_spec(tool, expect, phase), ok=outcome == "ok",
                      outcome=outcome, message="")


def test_perfect_server_scores_100():
    t = Template(name="t", select="*", mode="required", expect="ok")
    records = [
        _rec("lookup", "ok", "ok"),
        _rec("search", "ok", "ok"),
        _rec("lookup", "invalid", "invalid"),
    ]
    r = score_server(t, "srv", records, drift_seen=False, drifted_tools={})
    assert r.scores["fidelity"] == 100.0
    assert r.scores["discipline"] == 100.0
    assert r.scores["stability"] == 100.0
    assert r.grade == "A"


def test_discipline_penalizes_silent_success():
    t = Template(name="t", select="*", mode="missing", expect="invalid")
    records = [
        _rec("lookup", "invalid", "ok"),  # expected to be rejected, server accepted
    ]
    r = score_server(t, "srv", records, drift_seen=False, drifted_tools={})
    assert r.scores["discipline"] == 0.0


def test_eof_costs_stability():
    t = Template(name="t", select="*", mode="required", expect="ok")
    records = [_rec("lookup", "ok", "eof")]
    r = score_server(t, "srv", records, drift_seen=False, drifted_tools={})
    assert r.scores["stability"] == 0.0
    assert any("died mid-battery" in n for n in r.notes)


def test_fidelity_penalizes_expected_ok_not_landing():
    t = Template(name="t", select="*", mode="required", expect="ok")
    records = [_rec("search", "ok", "invalid")]
    r = score_server(t, "srv", records, drift_seen=False, drifted_tools={})
    assert r.scores["fidelity"] == 0.0
    assert any("did not land" in n for n in r.notes)


def test_drift_honored_scores_100():
    t = Template(name="t", select="search", mode="required", expect="ok")
    records = [
        _rec("search", "ok", "ok", phase="baseline"),
        _rec("search", "invalid", "invalid", phase="stale"),
        _rec("search", "ok", "ok", phase="drifted"),
    ]
    r = score_server(t, "srv", records, drift_seen=True,
                     drifted_tools={"tools": [{"name": "search"}]})
    assert r.scores["drift"] == 100.0


def test_drift_missing_notification_reduces_score():
    t = Template(name="t", select="search", mode="required", expect="ok")
    records = [
        _rec("search", "ok", "ok", phase="baseline"),
        _rec("search", "ok", "ok", phase="drifted"),
    ]
    r = score_server(t, "srv", records, drift_seen=False,
                     drifted_tools={"tools": [{"name": "search"}]})
    assert r.scores["drift"] < 100.0


def test_no_drift_template_drift_neutral():
    t = Template(name="t", select="*", mode="required", expect="ok")
    records = [_rec("lookup", "ok", "ok")]
    r = score_server(t, "srv", records, drift_seen=False, drifted_tools={})
    assert r.scores["drift"] == 100.0


def test_result_carries_fields():
    t = Template(name="t", select="*", mode="required", expect="ok")
    records = [_rec("lookup", "ok", "ok")]
    r = score_server(t, "srv", records, drift_seen=False, drifted_tools={})
    assert isinstance(r, ServerResult)
    assert r.template == "t"
    assert r.server == "srv"
    assert r.calls_total == 1
    assert r.ok_calls == 1
    assert "overall" in r.scores