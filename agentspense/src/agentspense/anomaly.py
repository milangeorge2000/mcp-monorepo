"""Spend anomaly detection: per-team daily totals vs. a rolling mean + std.

Fires on any day whose spend is > ``k`` standard deviations above the trailing
window — the classic z-score tripwire that catches runaway retry loops before a
weekend invoice does.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import mean, pstdev
from typing import Any, Dict, List

from agentspense.models import AgentLedger, SpendLine


def daily_totals(ledger: AgentLedger) -> Dict[str, float]:
    by_day = defaultdict(float)
    for line in ledger.lines:
        by_day[line.when[:10]] += line.cost
    return dict(by_day)


def per_team_daily(ledger: AgentLedger) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for line in ledger.lines:
        day = line.when[:10]
        bucket = out.setdefault(line.team, {})
        bucket[day] = bucket.get(day, 0.0) + line.cost
    return out


def detect(ledger: AgentLedger, k: float = 4.0, window: int = 7) -> List[Dict[str, Any]]:
    """Per-team z-score alerts; empty list = nothing weird."""
    alerts: List[Dict[str, Any]] = []
    for team, by_day in per_team_daily(ledger).items():
        days = sorted(by_day)
        for i, day in enumerate(days):
            value = by_day[day]
            start = max(0, i - window)
            baseline = [by_day[d] for d in days[start:i]] if i > start else []
            if not baseline:
                continue
            m = mean(baseline)
            sd = pstdev(baseline)
            if value > 0 and sd > 0 and (value - m) / sd > k:
                alerts.append({
                    "team": team, "day": day, "cost": round(value, 2),
                    "baseline_mean": round(m, 2), "baseline_std": round(sd, 2),
                    "z": round((value - m) / sd, 2),
                })
    return alerts


def session_spikes(ledger: AgentLedger, threshold: float = 10.0) -> List[Dict[str, Any]]:
    """Sessions that blew past the per-session threshold."""
    by_session: Dict[str, float] = defaultdict(float)
    meta: Dict[str, SpendLine] = {}
    for line in ledger.lines:
        by_session[line.session or line.when] += line.cost
        meta[line.session or line.when] = line
    out = []
    for sess, cost in by_session.items():
        if cost > threshold:
            line = meta.get(sess)
            out.append({"session": sess[:60], "team": line.team if line else "",
                        "feature": line.feature if line else "", "cost": round(cost, 2)})
    return sorted(out, key=lambda a: -a["cost"])