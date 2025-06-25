"""``mcpbatt run --share``: emit an mcpcensus fingerprint for the observatory.

Privacy contract is the same as the sibling tools: no tool schemas, no call
arguments, no transcripts. Just the generated-battery surface - templates run,
per-axis cohort aggregates, grade histogram - under ``sensor=batt``.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import List

from mcpbatt import __version__
from mcpbatt.models import BattReport

FORMAT = "mcpcensus/v1"


def emit_batt_fingerprint(report: BattReport, path: str) -> str:
    grade_histogram = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    for r in report.results:
        if r.grade in grade_histogram:
            grade_histogram[r.grade] += 1

    axis_means = {"fidelity": [], "discipline": [], "stability": [], "drift": []}
    for r in report.results:
        for k in axis_means:
            axis_means[k].append(r.scores.get(k, 0.0))

    fingerprint = {
        "format": FORMAT,
        "sensor": "batt",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "axes": {
            "runs": len(report.results),
            "templates": _templates(report.results),
            "best_grade": report.best_grade,
            "grade_histogram": grade_histogram,
            "axis_means": {k: round(sum(v) / len(v), 1) if v else 0.0 for k, v in axis_means.items()},
            "calls_total": sum(r.calls_total for r in report.results),
            "mode": "sandbox",
        },
        "meta": {"tool": "mcpbatt", "version": __version__},
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(fingerprint, fh, indent=2, sort_keys=True)
    return path


def _templates(results) -> List[str]:
    seen: List[str] = []
    for r in results:
        if r.template not in seen:
            seen.append(r.template)
    return seen