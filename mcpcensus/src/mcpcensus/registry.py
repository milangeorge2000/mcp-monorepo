"""The observatory's store + aggregation engine.

Fingerprints land as JSONL rows (append-only, like a ledger: every N is
auditable). Aggregation applies the publishing pipeline in order:

    bucket      -> assign each submission a coarse cohort
    k-anonymize -> suppress cohorts smaller than ``min_cohort``
    noise       -> add Laplace noise to published counts (LDP)
    emit        -> a ``published.json`` snapshot with provenance fields

The raw registry is *never* the dataset that ships; only ``published.json`` is
a "State of MCP" input.
"""

from __future__ import annotations

import json
import os
import random
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from mcpcensus import MIN_COHORT
from mcpcensus.privacy import cohort_bucket, is_valid_fingerprint, k_anonymize, clamp_noisy_count


def load_registry(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if is_valid_fingerprint(obj):
                out.append(obj)
    return out


def append_registry(path: str, fingerprints: List[Dict[str, Any]]) -> int:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    added = 0
    with open(path, "a", encoding="utf-8") as fh:
        for fp in fingerprints:
            if not is_valid_fingerprint(fp):
                continue
            fh.write(json.dumps(fp, sort_keys=True))
            fh.write("\n")
            added += 1
    return added


def published_name(sensor: str, month: Optional[str] = None) -> str:
    month = month or datetime.now(timezone.utc).strftime("%Y-%m")
    return f"{sensor}-{month}.published.json"


def _rows_for(fps: List[Dict[str, Any]], sensor: str) -> List[Dict[str, Any]]:
    rows = []
    for fp in fps:
        if fp.get("sensor") != sensor:
            continue
        axes = fp.get("axes", {})
        rows.append({
            "device": fp.get("device", ""),
            "submitted_at": fp.get("submitted_at", ""),
            "meta": fp.get("meta", {}),
            "axes": dict(axes),
            "cohort": cohort_bucket(axes, sensor),
        })
    return rows


def aggregate(
    fingerprint_rows: List[Dict[str, Any]],
    sensor: str,
    min_cohort: int = MIN_COHORT,
    noise_scale: float = 0.0,
    rng: Optional[random.Random] = None,
) -> Dict[str, Any]:
    """Aggregate fingerprints for one sensor into a ``published`` snapshot."""

    def _round(f):
        return round(float(f), 1)

    # -- distinct devices + cohorts
    rows = _rows_for(fingerprint_rows, sensor)
    kept, suppressed = k_anonymize(rows, min_cohort)
    device_ids = {r["device"] for r in rows}
    cohort_counts: Dict[str, int] = Counter(r["cohort"] for r in rows)

    stat = _sensor_stats(sensor, kept)
    noised = _noise_stats(stat, noise_scale, rng)

    return {
        "format": "mcpcensus/published",
        "sensor": sensor,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "min_cohort": min_cohort,
        "noise_scale": noise_scale,
        "devices_seen": len(device_ids),
        "submissions_raw": len(rows),
        "cohort_suppressed": suppressed,
        "cohorts": {c: n for c, n in sorted(cohort_counts.items())},
        "stats": noised,
        "series": _series(kept),
    }


def _sensor_stats(sensor: str, kept: List[Dict[str, Any]]) -> Dict[str, Any]:
    if sensor == "context":
        total_d = max(len(kept), 1)
        servers_total = sum(a["server_count"] for r in kept for a in [r["axes"]])
        tools_total = sum(m["tool_count"] for r in kept for a in [r["axes"]] for m in a.get("server_models", []))
        schema_total = sum(a["schema_tokens"] for r in kept for a in [r["axes"]])
        dead_total = sum(a["dead_tool_count"] for r in kept for a in [r["axes"]])
        avg_servers = round(servers_total / total_d, 2)
        avg_tools_per_server = round(tools_total / servers_total, 2) if servers_total else 0
        eff_waste = _avg(a.get("waste_percent", 0) for r in kept for a in [r["axes"]]) if kept else 0.0
        return {
            "avg_servers": avg_servers,
            "avg_tools_per_server": avg_tools_per_server,
            "avg_schema_tokens": int(schema_total / total_d),
            "avg_dead_tools": round(dead_total / total_d, 2),
            "avg_waste_percent": _round(eff_waste),
            "schema_tokens_total": schema_total,
            "dead_tools_total": dead_total,
            "grades": _grade_dict(kept, "grade"),
        }
    if sensor == "security":
        total_d = max(len(kept), 1)
        risk_totals: Dict[str, int] = Counter()
        kind_totals: Dict[str, int] = Counter()
        mode_totals: Dict[str, int] = Counter()
        remote = 0
        for r in kept:
            axes = r["axes"]
            risk_totals.update({k: v for k, v in axes.get("risk_counts", {}).items()})
            kind_totals.update({k: v for k, v in axes.get("kind_counts", {}).items()})
            mode_totals.update({k: v for k, v in axes.get("modes", {}).items()})
            remote += int(axes.get("remote_code_servers", 0) or 0)
        servers_total = sum(a["server_count"] for r in kept for a in [r["axes"]])
        avg_findings = round(sum(risk_totals.values()) / servers_total, 2) if servers_total else 0
        return {
            "servers_total": servers_total,
            "avg_servers": round(servers_total / total_d, 2),
            "risk_counts": dict(risk_totals),
            "kind_counts": dict(kind_totals),
            "modes": dict(mode_totals),
            "remote_code_servers": remote,
            "avg_findings_per_server": avg_findings,
            "grades": _grade_dict(kept, "grade_histogram"),
        }
    return {}


def _avg(gen):
    vals = list(gen)
    return round(sum(vals) / len(vals), 2) if vals else 0


def _round(f):
    return round(float(f), 1)


def _grade_dict(kept, key):
    c: Counter = Counter()
    for r in kept:
        g = r["axes"].get(key)
        if isinstance(g, dict):
            c.update({k: v for k, v in g.items() if v})
        elif isinstance(g, str):
            c[g] += 1
    return dict(sorted(c.items()))


def _series(kept: List[Dict[str, Any]]) -> Dict[str, int]:
    by_month: Dict[str, int] = Counter()
    for r in kept:
        at = r.get("submitted_at", "")
        by_month[at[:7]] += 1
    return dict(sorted(by_month.items()))


def _noise_stats(stat: Dict[str, Any], scale: float, rng: Optional[random.Random]) -> Dict[str, Any]:
    if not scale:
        return stat.copy()
    out: Dict[str, Any] = {}
    for k, v in stat.items():
        if isinstance(v, int):
            out[k] = clamp_noisy_count(v, scale, rng)
        elif isinstance(v, (float,)):
            out[k] = round(float(v) + _lap(scale, rng), 2)
        else:
            out[k] = v
    return out


def _lap(scale: float, rng: Optional[random.Random]) -> float:
    from mcpcensus.privacy import laplace_noise
    return laplace_noise(scale, rng)


# --------------------------------------------------------------------------
# mcpcensus suggest: percentile feedback loop
# --------------------------------------------------------------------------


def percentiles(vals: List[float]) -> Dict[int, float]:
    s = sorted(vals)
    n = len(s)
    if not n:
        return {}
    out = {}
    for p in (1, 5, 10, 25, 50, 75, 90, 95, 99):
        idx = max(0, min(n - 1, int(round((p / 100.0) * (n - 1)))))
        out[p] = s[idx]
    return out


def suggest(aggregate: Dict[str, Any], fingerprint: Dict[str, Any]) -> Dict[str, Any]:
    """Where does this device sit in the current State of MCP? + one suggestion."""
    sensor = fingerprint.get("sensor", "context")
    stats = aggregate.get("stats", {})
    axes = fingerprint.get("axes", {})
    if sensor == "context":
        metric = float(axes.get("waste_percent", 0) or 0)
        cohort_metric = "avg_waste_percent"
        hint = _context_hint(metric)
    else:
        metric = float(sum((axes.get("risk_counts") or {}).values()))
        cohort_metric = "avg_findings_per_server"
        hint = _security_hint(metric)
    pcts = percentiles([metric] + _all_metrics(aggregate, cohort_metric))
    p = _mirror(metric, pcts)
    return {
        "sensor": sensor,
        "metric": metric,
        "percentile": p,
        "ecosystem_median": pcts.get(50),
        "hint": hint,
        "cohort_metric": cohort_metric,
    }


def _all_metrics(aggregate, cohort_metric):
    series = aggregate.get("stats", {}).get(cohort_metric)
    if isinstance(series, dict):
        return [v for v in series.values() if isinstance(v, (int, float))]
    v = aggregate.get("stats", {}).get(cohort_metric)
    return [v] if isinstance(v, (int, float)) else []


def _mirror(metric, pcts: Dict[int, float]) -> int:
    if not pcts:
        return 50
    within = [(p, v) for p, v in pcts.items()]
    for i in range(len(within)):
        p, v = within[i]
        if metric <= v:
            nxt = within[i + 1][0] if i + 1 < len(within) else p
            prev = within[i - 1][0] if i else p
            return nxt if metric == v else round((prev + nxt) / 2)
    return 99


def _context_hint(metric):
    if metric <= 0:
        return "already lean enough to share: your setup is the model citizen."
    if metric < 20:
        return "trim dead tools and your grade climbs without touching live servers."
    if metric < 50:
        return "half of every schema request is waste — switch off the unused tooling."
    return "your context diet is catastrophic: shed schemas before adding anything."


def _security_hint(metric):
    if metric <= 0:
        return "clean scorecard — exactly the kind of baseline the network needs."
    if metric < 3:
        return "a couple of findings per server is common; pin + pin your launchers."
    if metric < 8:
        return "you're running notably riskier servers than the median peer."
    return "your guards are red for a reason — fix the criticals before next sprint."


def written_form(published: Dict[str, Any]) -> str:
    return json.dumps(published, indent=2, sort_keys=True)