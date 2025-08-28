"""Anomaly detection + P&L report tests."""

import json
from pathlib import Path

from agentspense.anomaly import detect, session_spikes, daily_totals
from agentspense.models import SpendLine, AgentLedger, write_ledger, read_ledger
from agentspense.normalize import normalize_files, normalize_record
from agentspense.providers import read_export
from agentspense.report import compose_month, console_summary, month_totals, write_month
from agentspense.rates import load_rates

FIXTURES = Path(__file__).parent / "fixtures"


def _spike_ledger():
    baseline = [1.0, 1.2, 0.8, 1.1, 0.9, 1.0, 1.1, 0.8, 1.2]
    lines = []
    for i, cost in enumerate(baseline, 1):
        lines.append(SpendLine(provider="claude", model="m", when=f"2025-08-{i:02d}T00:00:00",
                               tokens_in=0, tokens_out=0, cost=cost, session=f"s{i}",
                               tags=["team:platform"], team="platform"))
    lines.append(SpendLine(provider="claude", model="m", when="2025-08-10T00:00:00",
                           tokens_in=0, tokens_out=0, cost=50.0, session="s10",
                           tags=["team:platform"], team="platform"))
    return AgentLedger(lines)


def test_detect_finds_spike():
    alerts = detect(_spike_ledger(), k=4.0, window=5)
    assert any(a["day"] == "2025-08-10" for a in alerts)
    assert all(a["z"] > 4.0 for a in alerts)


def test_detect_clean_when_flat():
    lines = [SpendLine(provider="p", model="m", when=f"2025-08-{d:02d}", cost=1.0)
             for d in range(1, 20)]
    assert detect(AgentLedger(lines), k=4.0, window=5) == []


def test_session_spikes():
    lines = [
        SpendLine(provider="p", model="m", when="2025-08-01", cost=25.0, session="bad-session", tags=["team:a"], team="a"),
        SpendLine(provider="p", model="m", when="2025-08-01", cost=0.5, session="fine", tags=["team:b"], team="b"),
    ]
    spikes = session_spikes(AgentLedger(lines), threshold=10.0)
    assert [s["session"] for s in spikes] == ["bad-session"]


def test_daily_totals_agg():
    lines = [
        SpendLine(provider="p", model="m", when="2025-08-01T00:00", cost=1.0, team="a"),
        SpendLine(provider="p", model="m", when="2025-08-01T12:00", cost=2.0, team="a"),
    ]
    assert daily_totals(AgentLedger(lines)) == {"2025-08-01": 3.0}


def test_ledger_roundtrip(tmp_path):
    ledger = normalize_files([str(FIXTURES / "claude-export.json")])
    path = str(tmp_path / "ledger.json")
    write_ledger(ledger, path)
    restored = read_ledger(path)
    assert len(restored.lines) == 2
    assert restored.lines[0].cost == ledger.lines[0].cost
    assert restored.lines[0].team == "platform"


def test_month_report_compose():
    ledger = normalize_files([str(FIXTURES / "claude-export.json"),
                              str(FIXTURES / "cursor-audit.json"),
                              str(FIXTURES / "codex-export.csv")])
    t = month_totals(ledger, month="2025-08")
    assert t["lines"] == 6
    assert t["cost"] > 0
    assert "platform" in t["by_team"]
    assert "codex" in t["by_provider"]
    doc = compose_month(ledger, month="2025-08", title="Profit test")
    assert "Profit test" in doc
    assert "by provider" in doc
    assert isinstance(console_summary(t), str)


def test_month_report_budget_flag(tmp_path):
    ledger = normalize_files([str(FIXTURES / "codex-export.csv")])
    path = tmp_path / "pnl.html"
    write_month(ledger, str(path), month="2025-08", budgets={"team": 0.01}, title="flag")
    doc = path.read_text(encoding="utf-8")
    assert "flag" in doc