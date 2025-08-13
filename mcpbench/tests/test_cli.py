from __future__ import annotations

import io
import json
import sys

from mcpbench.cli import main


def _run(argv):
    old = sys.stdout
    buf = io.StringIO()
    sys.stdout = buf
    try:
        rc = main(argv)
    finally:
        sys.stdout = old
    return rc, buf.getvalue()


def test_list_subcommand():
    rc, out = _run(["list"])
    assert rc == 0
    assert "canonical" in out


def test_run_default_outputs_leaderboard():
    rc, out = _run(["run", "-o", ""])
    assert rc == 0
    assert "leaderboard" in out
    assert "canonical" in out


def test_run_json_parses(tmp_path):
    out_html = str(tmp_path / "r.html")
    rc, out = _run(["run", "--drivers", "canonical", "naive", "-o", out_html, "--json"])
    assert rc == 0
    data = json.loads(out)
    assert data["best_grade"] in "ABCDF"
    assert len(data["drivers"]) == 2
    with open(out_html, "r", encoding="utf-8") as fh:
        assert "mcpbench" in fh.read()


def test_run_share_fingerprint(tmp_path):
    share = str(tmp_path / "bench.json")
    rc, _ = _run(["run", "--drivers", "canonical", "-o", "", "--share", share])
    assert rc == 0
    with open(share, "r", encoding="utf-8") as fh:
        fp = json.load(fh)
    assert fp["sensor"] == "bench"


def test_run_unknown_driver_errors():
    rc, out = _run(["run", "--drivers", "not-a-driver", "-o", ""])
    assert rc != 0 or "unknown driver" in out


def test_version_flag():
    old = sys.stdout
    sys.stdout = io.StringIO()
    try:
        try:
            main(["--version"])
            raised = False
        except SystemExit:
            raised = True
    finally:
        sys.stdout = old
    assert raised