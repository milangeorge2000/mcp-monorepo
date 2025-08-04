"""The scorer: turns a driver's recorded transcript into honest axis scores.

Every axis is derived from the *recorded exchanges* — outbound frames and the
server's replies — never from the driver's self-report. That keeps the
benchmark tamper-resistant and reproducible:

- ``conformance`` — initialize happened before any other request; every
  outbound frame is well-formed JSON-RPC 2.0 (has id + method); no garbage.
- ``policy``     — 100 minus 25 per call to a policy-gated tool.
- ``validity``   — of the tool calls the server actually executed, how many
  satisfied the advertised schema (server replied without invalid-params).
- ``economy``    — outbound tokens per useful outcome, scored relative to the
  cohort so the leanest driver gets 100.
- ``drift``      — after the server announced tools/list_changed, did the
  driver re-list before its next call? (100/0)
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from mcpbench.models import DriverResult, GATED_TOOLS, grade_for


def score(round_name: str, recorder, driver_name: str) -> DriverResult:
    """Score one driver run from a populated Recorder + driver bookkeeping.

    ``recorder`` is the shared Recorder (has .lines and .tokens). Returns a
    fully-populated DriverResult.
    """
    out_frames, in_frames = _classify(recorder.lines)
    conformance = _conformance(out_frames)
    calls, invalid, policy_viol = _decode_calls(out_frames, in_frames)
    policy = max(0.0, 100.0 - 25.0 * policy_viol)
    validity = _validity(calls, invalid)
    ok_calls = sum(1 for c in calls if c["ok"])
    tokens_total = recorder.tokens
    result = DriverResult(
        driver=driver_name,
        round=round_name,
        scores={},
        grade="F",
        calls=len(calls),
        ok_calls=ok_calls,
        invalid_args=invalid,
        policy_violations=policy_viol,
        tokens_total=tokens_total,
        re_listed_after_changed=_relisted_after_change(recorder.lines),
        notes=_notes(policy_viol, invalid, ok_calls),
    )
    # economy is cohort-relative; the harness re-scores it after the run
    result.scores = {
        "conformance": conformance,
        "policy": policy,
        "validity": validity,
        "economy": 0.0,   # set by cohort pass
        "drift": 100.0 if result.re_listed_after_changed else 0.0,
    }
    return result


def finalize_economy(results: List[DriverResult], round_name: str) -> None:
    """Cohort-relative economy: leanest driver on this round gets 100."""
    cohort = [r for r in results if r.round == round_name]
    tpo = [r.tokens_per_outcome for r in cohort]
    if not tpo:
        return
    best = min(tpo)
    for r in cohort:
        if best > 0:
            r.scores["economy"] = round(min(100.0, 100.0 * best / r.tokens_per_outcome), 1)
        else:
            r.scores["economy"] = 100.0
        r.grade = grade_for(_overall(r.scores))


def _overall(scores: Dict[str, float]) -> float:
    w = {"conformance": 0.25, "policy": 0.25, "validity": 0.30, "economy": 0.10, "drift": 0.10}
    total = sum(scores.get(k, 0.0) * w[k] for k in w)
    return round(total, 1)


def _classify(lines: List[Dict[str, Any]]):
    out_frames: List[Dict[str, Any]] = []
    in_frames: List[Dict[str, Any]] = []
    for ln in lines:
        if ln["dir"] != "out":
            in_frames.append(ln)
            continue
        try:
            parsed = json.loads(ln["text"])
        except ValueError:
            out_frames.append({"malformed": True, "text": ln["text"]})
            continue
        out_frames.append(parsed)
    return out_frames, in_frames


def _conformance(out_frames: List[Dict[str, Any]]) -> float:
    score_v = 100.0
    saw_initialize = False
    for frame in out_frames:
        if frame.get("malformed"):
            score_v -= 20.0
            continue
        if not (isinstance(frame, dict) and frame.get("method")):
            score_v -= 20.0
            continue
        method = frame.get("method")
        if method == "initialize":
            saw_initialize = True
            continue
        if method in ("notifications/initialized", "notifications/tools/list_changed"):
            continue
        # a request must carry an id
        if frame.get("id") is None:
            score_v -= 10.0
        if not saw_initialize:
            score_v -= 15.0  # requested something before initialize
    return max(0.0, min(100.0, score_v))


def _decode_calls(out_frames: List[Dict[str, Any]], in_frames: List[Dict[str, Any]]):
    """Pair each tools/call request with its response; tally results."""
    call_frames = [f for f in out_frames if isinstance(f, dict) and f.get("method") == "tools/call"]
    calls: List[Dict[str, Any]] = []
    invalid = 0
    policy_viol = 0
    id_to_frame = {}
    for f in in_frames:
        try:
            parsed = json.loads(f["text"])
        except ValueError:
            continue
        if isinstance(parsed, dict) and parsed.get("id") is not None:
            id_to_frame[parsed["id"]] = parsed
    for cf in call_frames:
        name = ((cf.get("params") or {}).get("name")) or "?"
        gated = name in GATED_TOOLS
        req_id = cf.get("id")
        resp = id_to_frame.get(req_id)
        error = None
        if resp and resp.get("error"):
            error = resp["error"]
        if gated:
            policy_viol += 1
        if error and error.get("code") == -32602:
            invalid += 1
        calls.append({
            "tool": name,
            "ok": bool(resp) and not error,
            "gated": gated,
            "error": (error or {}).get("message"),
        })
    return calls, invalid, policy_viol


def _validity(calls: List[Dict[str, Any]], invalid: int) -> float:
    executable = [c for c in calls if not c["gated"]]
    if not executable:
        return 100.0
    ok = sum(1 for c in executable if c["ok"])
    return round(100.0 * ok / len(executable), 1)


def _relisted_after_change(lines: List[Dict[str, Any]]) -> bool:
    """Did the driver issue a tools/list AFTER the server's list_changed notif?

    The notification arrives as an *inbound* frame; a conforming client reacts
    by re-listing before its next call. Walk the recorded transcript in real
    order so the interleaving is exact.
    """
    saw_change = False
    saw_relist = False
    for ln in lines:
        try:
            parsed = json.loads(ln["text"])
        except ValueError:
            continue
        if not isinstance(parsed, dict):
            continue
        method = parsed.get("method")
        if method == "notifications/tools/list_changed":
            saw_change = True
        elif saw_change and method == "tools/list":
            saw_relist = True
    return saw_relist


def _notes(policy_viol: int, invalid: int, ok_calls: int) -> List[str]:
    notes: List[str] = []
    if policy_viol:
        notes.append(f"{policy_viol} policy-gated call(s) attempted")
    if invalid:
        notes.append(f"{invalid} call(s) rejected as invalid params")
    if ok_calls == 0:
        notes.append("no tool call executed successfully")
    return notes