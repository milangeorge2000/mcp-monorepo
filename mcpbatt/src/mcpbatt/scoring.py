"""Deterministic scoring of a battery: four axes into an A-F grade.

- **fidelity** - of calls expected to *work*, how many actually landed a result.
  A server that advertises a schema and then rejects its own required fields
  every time gets a low fidelity.
- **discipline** - of calls expected to be *rejected*, how many got a clean
  ``-32602 invalid params`` error rather than a silent success, a generic
  error, or a crash.
- **stability** - did the server survive the whole battery? Any EOF / dead
  subprocess / malformed reply costs full points on this axis.
- **drift** - when the battery declares a schema change, did the server honor
  it: emit tools/list_changed, reflect the new schema on re-list, and reject
  its own formerly-valid arguments?

Overall is a fixed weighted blend; no LLM anywhere in the loop.
"""
from __future__ import annotations

from typing import Any, Dict, List

from mcpbatt.models import CallRecord, ServerResult, grade_for

WEIGHTS = {"fidelity": 0.30, "discipline": 0.30, "stability": 0.20, "drift": 0.20}


def _ratio(num: int, den: int) -> float:
    return 100.0 if den == 0 else round(100.0 * num / den, 1)


def score_server(template, server_label: str, records: List[CallRecord],
                 drift_seen: bool, drifted_tools: Dict[str, Any],
                 baseline_tools: List[Dict[str, Any]] = None) -> ServerResult:
    total = len(records)
    expected_ok = [r for r in records if r.spec.expect == "ok"]
    expected_invalid = [r for r in records if r.spec.expect == "invalid"]
    ok_landed = sum(1 for r in expected_ok if r.outcome == "ok")
    invalid_rejected = sum(1 for r in expected_invalid if r.outcome == "invalid")
    stable = sum(1 for r in records if r.outcome in ("ok", "invalid", "other-error"))

    fidelity = _ratio(ok_landed, len(expected_ok))
    discipline = _ratio(invalid_rejected, len(expected_invalid))
    stability = _ratio(stable, total)

    has_drift = any(r.spec.phase in ("stale", "drifted") for r in records)
    if has_drift:
        stale = [r for r in records if r.spec.phase == "stale"]
        drifted = [r for r in records if r.spec.phase == "drifted"]
        drifted_ok = sum(1 for r in drifted if r.outcome == "ok")
        stale_rejected = sum(1 for r in stale if r.outcome == "invalid")
        relist_ok = bool(drifted_tools.get("tools")) and drift_seen
        drift = _ratio(1 if relist_ok else 0, 1) * 0.5 \
            + 0.3 * _ratio(stale_rejected, len(stale)) + 0.2 * _ratio(drifted_ok, len(drifted))
        drift = round(drift, 1)
    else:
        drift = 100.0

    scores = {"fidelity": fidelity, "discipline": discipline,
              "stability": stability, "drift": drift}
    overall = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)

    notes = _notes(records, fidelity, discipline, stability, drift)
    return ServerResult(
        template=template.name,
        server=server_label,
        scores={**scores, "overall": round(overall, 1)},
        grade=grade_for(overall),
        calls_total=total,
        ok_calls=ok_landed,
        invalid_calls=invalid_rejected,
        drift_seen=drift_seen,
        drifted_schema=drifted_tools,
        records=records,
        notes=notes,
    )


def _notes(records: List[CallRecord], fidelity: float, discipline: float,
           stability: float, drift: float) -> List[str]:
    out: List[str] = []
    if stability < 100:
        bad = [r for r in records if r.outcome == "eof"]
        out.append(f"{len(bad)} call(s) hit EOF - server died mid-battery")
    if fidelity < 100:
        bad = [r.spec.tool for r in records if r.spec.expect == "ok" and r.outcome != "ok"]
        out.append(f"{len(bad)} expected-ok call(s) did not land: {', '.join(sorted(set(bad)))}")
    if discipline < 100:
        bad = [r for r in records if r.spec.expect == "invalid" and r.outcome != "invalid"]
        out.append(f"{len(bad)} expected-reject call(s) were not rejected with -32602")
    if drift < 100:
        out.append("schema drift was not fully honored (missing list_changed / stale args accepted)")
    return out