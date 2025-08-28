"""Normalization: vendor rows -> comparable SpendLines with a filled rate-card cost."""

from __future__ import annotations

from typing import Dict, List, Optional

from agentspense.models import AgentLedger, SpendLine, normalize_team_feature
from agentspense.providers import RawRecord, read_export
from agentspense.rates import load_rates, lookup


def _rate_cost(rr: RawRecord, rates: Dict) -> tuple:
    """(in_rate, out_rate, recomputed) from the card, or (0,0,0)."""
    in_rate, out_rate = 0.0, 0.0
    hit = lookup(rr.provider, rr.model, rates)
    if hit:
        in_rate, out_rate = hit
    recomputed = rr.tokens_in * in_rate / 1e6 + rr.tokens_out * out_rate / 1e6
    return in_rate, out_rate, recomputed


def normalize_record(rr: RawRecord, rates: Optional[Dict] = None) -> SpendLine:
    rates = rates or load_rates()
    in_rate, out_rate, recomputed = _rate_cost(rr, rates)
    cost = rr.cost if rr.cost > 0 else round(recomputed, 6)
    line = SpendLine(
        provider=rr.provider or "generic",
        model=rr.model or "unknown",
        when=rr.when,
        tokens_in=rr.tokens_in,
        tokens_out=rr.tokens_out,
        cost=cost,
        listed_cost=rr.cost,
        rated_cost=round(recomputed, 6),
        session=rr.session,
        tags=rr.tags,
        source=rr.source,
    )
    normalize_team_feature(line)
    return line


def normalize_files(paths: List[str], rates: Optional[Dict] = None) -> AgentLedger:
    rates = rates or load_rates()
    ledger = AgentLedger()
    for p in paths:
        for rr in read_export(p):
            ledger.add(normalize_record(rr, rates))
    return ledger


def rate_card_report(rates: Optional[Dict] = None) -> Dict:
    rates = rates or load_rates()
    return {p: {m: {"in": i, "out": o} for m, (i, o) in models.items()}
            for p, models in rates.items()}