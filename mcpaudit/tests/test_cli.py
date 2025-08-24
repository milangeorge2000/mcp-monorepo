"""CLI integration tests (no browser launch)."""
import json
from pathlib import Path

from conftest import FIXTURES

DEMO = str(Path(FIXTURES.parent.parent) / "examples" / "demo-mcp.json")


def test_cli_share_writes_anonymized_fingerprint(tmp_path):
    from mcpaudit.cli import main

    out = tmp_path / "census.json"
    rc = main(["--config", DEMO, "--window", "9999", "--share", str(out)])
    assert rc == 0
    fp = json.loads(out.read_text(encoding="utf-8"))
    assert fp["format"] == "mcpcensus/v1"
    assert fp["sensor"] == "context"
    assert fp["device"]
    assert fp["axes"]["server_count"] >= 0
    # raw server names must stay off the file
    assert "github" not in out.read_text(encoding="utf-8")


def test_cli_json_report(monkeypatch):
    from mcpaudit.cli import main

    monkeypatch.setattr("sys.argv", ["mcpaudit", "--config", DEMO, "--json"])
    assert main() == 0


def test_cli_rejects_missing_config(capsys):
    import pytest

    from mcpaudit.cli import main

    with pytest.raises(SystemExit) as exc:
        main(["--config", str(FIXTURES / "does-not-exist.json"), "--json"])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "no MCP servers found" in err


def test_cli_writes_report_and_stubs_browser(monkeypatch, tmp_path):
    from mcpaudit import _webbrowser_open
    from mcpaudit.cli import main

    calls = {}
    monkeypatch.setattr(_webbrowser_open, "open_html", lambda p: calls.setdefault("opened", p))
    report_path = tmp_path / "rep.html"
    rc = main(
        [
            "--config", DEMO,
            "--window", "9999",
            "--report", str(report_path),
        ]
    )
    assert rc == 0
    assert report_path.exists()
    assert calls.get("opened") is not None
    html = report_path.read_text(encoding="utf-8")
    assert "mcpaudit" in html