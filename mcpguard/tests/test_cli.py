"""CLI integration tests (no browser launch, state dir redirected)."""
import json
import os
import sys
from pathlib import Path

import pytest

from mcpguard.cli import main

from conftest import DEMO_CONFIG, FIXTURES


def _with_state(tmp_path, args):
    os.environ["MCPGUARD_STATE_DIR"] = str(tmp_path)
    try:
        return main(args)
    finally:
        os.environ.pop("MCPGUARD_STATE_DIR", None)


def test_scan_json_on_fixture(capsys):
    rc = main(["scan", "--config", str(FIXTURES / "mcp.json"), "--no-live", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    names = {s["server"] for s in out["servers"]}
    assert "github" in names
    assert "public-relay" in names


def test_scan_missing_config_exits_2(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["scan", "--config", str(FIXTURES / "nope.json"), "--json"])
    assert exc.value.code == 2


def test_scan_writes_report_stubs_browser(monkeypatch, tmp_path):
    from mcpguard import _webbrowser_open

    calls = {}
    monkeypatch.setattr(_webbrowser_open, "open_html", lambda p: calls.setdefault("opened", p))
    rp = tmp_path / "rep.html"
    rc = main(["scan", "--config", DEMO_CONFIG, "--report", str(rp)])
    assert rc == 0
    assert rp.exists()
    assert "mcpguard" in rp.read_text(encoding="utf-8")
    assert calls.get("opened") == str(rp)


def test_scan_share_writes_anonymized_fingerprint(tmp_path):
    out = tmp_path / "census.json"
    rc = main(["scan", "--config", str(FIXTURES / "mcp.json"), "--no-live", "--share", str(out)])
    assert rc == 0
    fp = json.loads(out.read_text(encoding="utf-8"))
    assert fp["format"] == "mcpcensus/v1"
    assert fp["sensor"] == "security"
    assert fp["device"]
    raw = out.read_text(encoding="utf-8")
    for leaked in ("github", "public-relay", "AWS"):
        assert leaked not in raw


def test_watch_stable_on_fixture(tmp_path, capsys):
    rc1 = _with_state(tmp_path, ["watch", "--config", str(FIXTURES / "mcp.json"), "--no-live", "--json"])
    assert rc1 in (0, 3)
    rc2 = _with_state(tmp_path, ["watch", "--config", str(FIXTURES / "mcp.json"), "--no-live", "--json"])
    assert rc2 == 0  # second pass sees no new criticals


def test_intel_show(capsys):
    rc = main(["intel", "show"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert "version" in out


def test_version():
    from mcpguard.cli import main

    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0