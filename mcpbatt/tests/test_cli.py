import json
import os
import sys

import pytest

from mcpbatt.cli import cmd_expand, cmd_run, list_templates, _load_named


def test_list_templates_finds_bundled():
    names = [t["name"] for t in list_templates()]
    assert "required-only" in names
    assert "drift-honesty" in names


def test_load_named_template():
    t = _load_named("required-only")
    assert t.name == "required-only"
    assert t.mode == "required"


def test_load_named_missing_template_raises():
    with pytest.raises(ValueError):
        _load_named("does-not-exist")


def test_expand_prints_battery(capsys, tmp_path):
    rc = cmd_expand(__import__("argparse").Namespace(
        template="required-only", server=None, timeout=8.0, output=None))
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["format"] == "mcpbatt-battery/v1"
    assert data["template"] == "required-only"
    assert len(data["calls"]) == 4


def test_run_json_parses(capsys):
    rc = cmd_run(__import__("argparse").Namespace(
        template="drift-honesty", server=None, timeout=8.0,
        output=None, json=True, share=None))
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["results"][0]["grade"] == "A"
    assert data["results"][0]["drift_seen"] is True


def test_run_writes_report(capsys, tmp_path):
    out_path = str(tmp_path / "report.html")
    rc = cmd_run(__import__("argparse").Namespace(
        template="required-only", server=None, timeout=8.0,
        output=out_path, json=False, share=None))
    assert rc == 0
    assert os.path.exists(out_path)
    with open(out_path, encoding="utf-8") as fh:
        assert "mcpbatt" in fh.read()


def test_run_share_fingerprint(capsys, tmp_path):
    share_path = str(tmp_path / "fp.json")
    rc = cmd_run(__import__("argparse").Namespace(
        template="required-only", server=None, timeout=8.0,
        output=None, json=False, share=share_path))
    assert rc == 0
    assert os.path.exists(share_path)
    with open(share_path, encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["sensor"] == "batt"


def test_run_unknown_template_returns_2(capsys):
    rc = cmd_run(__import__("argparse").Namespace(
        template="nope", server=None, timeout=8.0,
        output=None, json=False, share=None))
    assert rc == 2


def test_version_flag():
    from mcpbatt.cli import main
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0