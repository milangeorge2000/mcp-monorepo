"""Provider parsing + normalization + rate lookup tests."""

import json
from pathlib import Path

from agentspense.providers import read_export, read_export_file_or_text, path_is_csv
from agentspense.normalize import normalize_record, normalize_files, rate_card_report
from agentspense.rates import load_rates, lookup
from agentspense.models import AgentLedger, team_of, feature_of

FIXTURES = Path(__file__).parent / "fixtures"


def test_lookup_bundled():
    rates = load_rates()
    assert lookup("claude", "claude-3-5-sonnet", rates) == (3.0, 15.0)
    assert lookup("opencode", "deepseek-v4-flash", rates) == (0.07, 0.27)
    assert lookup("claude", "does-not-exist", rates) is None


def test_lookup_truncation_alias():
    rates = load_rates()
    # vendor-suffixed model names still resolve
    assert lookup("claude", "claude-3-5-sonnet-20241022", rates) == (3.0, 15.0)


def test_claude_export_parses():
    rows = read_export(str(FIXTURES / "claude-export.json"))
    assert len(rows) == 2
    assert rows[0].provider == "claude"
    assert rows[0].cost == 0.63
    assert rows[0].tokens_in == 120000
    assert "team:platform" in rows[0].tags


def test_cursor_and_opencode():
    rows = read_export(str(FIXTURES / "cursor-audit.json"))
    assert {r.provider for r in rows} == {"cursor"}
    rows_o = read_export(str(FIXTURES / "opencode-export.json"))
    assert {r.provider for r in rows_o} == {"opencode"}
    assert rows_o[0].tokens_out == 120000


def test_csv_parses():
    assert path_is_csv("x.csv") and path_is_csv("y.tsv")
    rows = read_export(str(FIXTURES / "codex-export.csv"))
    assert {r.provider for r in rows} == {"codex"}
    assert rows[0].model == "gpt-5-codex"


def test_normalization_fills_rated_cost():
    rates = load_rates()
    rows = read_export(str(FIXTURES / "claude-export.json"))
    line = normalize_record(rows[0], rates)
    # vendor listed cost wins
    assert line.cost == 0.63
    # rate card recompute sanity: 120k*3 + 18k*15 per M = 0.36+0.27 = 0.63
    assert abs(line.rated_cost - 0.63) < 0.01
    assert line.team == "platform"


def test_normalize_rates_when_missing():
    rates = load_rates()
    rows = read_export(str(FIXTURES / "opencode-export.json"))
    line = normalize_record(rows[0], rates)
    # opencode export has cost_usd but a listed cost exists too -> wins
    assert max(line.listed_cost, line.rated_cost) > 0


def test_team_feature_derivation():
    assert team_of(["team:platform"]) == "platform"
    assert team_of(["x", "y"]) == "x"
    assert feature_of(["feature:auth"]) == "auth"
    assert feature_of(["nothing"]) == "unassigned"


def test_multifile_fold(tmp_path):
    ledger = normalize_files([str(FIXTURES / "claude-export.json"),
                              str(FIXTURES / "codex-export.csv")])
    assert len(ledger.lines) == 4
    total = round(sum(l.cost for l in ledger.lines), 4)
    assert total > 1.0
    assert {"claude", "codex"} <= {l.provider for l in ledger.lines}


def test_rate_card_report_shape():
    card = rate_card_report(load_rates())
    assert "claude" in card and "deepseek-v4-flash" in card["opencode"]