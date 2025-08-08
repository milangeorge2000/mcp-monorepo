"""``mcpbench run --share``: emit an mcpcensus fingerprint for the observatory.

Same privacy contract as the other tools: no tool names, no transcripts, no raw
driver notes. Just the leaderboard shape — grades, per-axis cohort aggregates,
and token-economy stats — under ``sensor=bench``.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from mcpbench import __version__

FORMAT = "mcpcensus/v1"


def emit_bench_fingerprint(report, path: str) -> str:
    grade_histogram = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    for r in report.results:
        if r.grade in grade_histogram:
            grade_histogram[r.grade] += 1

    axis_means = {"conformance": [], "policy": [], "validity": [], "economy": [], "drift": []}
    for r in report.results:
        for k in axis_means:
            axis_means[k].append(r.scores.get(k, 0.0))

    axes = {
        "drivers": len(report.results),
        "grade_histogram": grade_histogram,
        "best_grade": report.best_grade,
        "axis_means": {k: round(sum(v) / len(v), 1) if v else 0.0 for k, v in axis_means.items()},
        "calls_total": sum(r.calls for r in report.results),
        "policy_violations": sum(r.policy_violations for r in report.results),
        "tokens_per_outcome_median": _median([r.tokens_per_outcome for r in report.results]),
        "mode": "sandbox",
    }
    fingerprint = {
        "format": FORMAT,
        "sensor": "bench",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "axes": axes,
        "meta": {"tool": "mcpbench", "version": __version__},
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(fingerprint, fh, indent=2, sort_keys=True)
    return path


def _median(values):
    if not values:
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return round(ordered[mid], 2)
    return round((ordered[mid - 1] + ordered[mid]) / 2.0, 2)