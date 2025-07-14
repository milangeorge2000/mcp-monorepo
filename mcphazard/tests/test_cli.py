from __future__ import annotations

import io
import json
import sys

import pytest

from mcphazard.cli import main
from tests.conftest import toxicserver_env

CONFIG = "examples/demo-mcp.json"


def _run(argv, out=None):
    old = sys.stdout
    old_err = sys.stderr
    buf = io.StringIO()
    ebuf = io.StringIO()
    sys.stdout = buf
    sys.stderr = ebuf
    try:
        rc = main(argv)
    finally:
        sys.stdout = old
        sys.stderr = old_err
    if out is not None:
        out.write(buf.getvalue())
        out.write(ebuf.getvalue())
    return rc, (buf.getvalue(), ebuf.getvalue())


def test_payloads_nonlive():
    rc, (out, _err) = _run(["payloads"])
    assert rc == 0
    assert "payloads" in out


def test_payloads_live_json():
    rc, (out, _err) = _run(["payloads", "--live", "--json"])
    assert rc == 0
    data = json.loads(out)
    assert any(p["bespoke"] for p in data)


def test_scan_via_config():
    rc, (out, _err) = _run(["scan", "toxic-demo", "--config", CONFIG, "-o", "", "--json"])
    assert rc == 0
    assert json.loads(out)["server"] == "toxic-demo"


def test_scan_missing_target_fails():
    rc, (out, err) = _run(["scan", "nope"])
    assert rc == 2
    assert "target is required" in (out + err)


def test_scan_via_command():
    rc, (out, _err) = _run(["scan", "toxic-demo", "--command"] + toxicserver_env() + ["-o", "", "--json"])
    assert rc == 0
    data = json.loads(out)
    assert data["finding_count"] > 0


def test_scan_writes_report_html():
    import tempfile
    import os
    fd, path = tempfile.mkstemp(suffix=".html")
    os.close(fd)
    try:
        rc, (_out, _err) = _run(["scan", "toxic-demo", "--config", CONFIG, "-o", path])
        assert rc == 0
        with open(path, "r", encoding="utf-8") as fh:
            assert "mcphazard" in fh.read()
    finally:
        os.unlink(path)


def test_scan_share_fingerprint():
    import tempfile
    import os
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.unlink(path)
    try:
        rc, (_out, _err) = _run(["scan", "toxic-demo", "--config", CONFIG, "-o", "", "--share", path])
        assert rc == 0
        with open(path, "r", encoding="utf-8") as fh:
            fp = json.load(fh)
        assert fp["sensor"] == "hazard"
        assert "tool_hashes" in fp["axes"]
        assert fp["axes"]["tool_count"] >= 1
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_version_flag():
    with pytest.raises(SystemExit) as ei:
        main(["--version"])
    assert ei.value.code == 0