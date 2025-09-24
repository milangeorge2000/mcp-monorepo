"""Static + live audit engine tests."""
import pytest

from mcpguard.audit import audit_server
from mcpguard.intel import IntelBundle
from mcpguard.models import Risk, ServerConfiguration

from conftest import FAKE_SERVER


@pytest.fixture
def no_live_intel():
    return IntelBundle()


def _cfg(name, command, env=None, url=None):
    return ServerConfiguration(name=name, command=list(command), env=env or {}, url=url)


def test_static_high_remote_secret(no_live_intel):
    res = audit_server(
        _cfg("github", ["npx", "-y", "@modelcontextprotocol/server-github"],
             env={"GITHUB_TOKEN": "x"}), no_live_intel, live=False)
    kinds = {f.kind for f in res.findings}
    assert "remote_code" in kinds
    assert "secret_env" in kinds
    assert res.grade == "D"


def test_static_pinned_uvx_is_medium():
    res = audit_server(_cfg("pinned-writer", ["uvx", "mcp-write-gate@1.4.0"]),
                       IntelBundle(), live=False)
    assert res.grade == "C"


def test_static_local_python_is_a():
    res = audit_server(_cfg("trusted-local", ["python", "./x.py"]), IntelBundle(), live=False)
    assert res.grade == "A"
    assert res.findings == []


def test_static_http_is_high():
    res = audit_server(ServerConfiguration(name="relay", url="https://pipeline.api.com/mcp"),
                       IntelBundle(), live=False)
    assert res.grade == "D"
    assert res.remote_code is True


def test_known_bad_package_forces_f():
    bundle = IntelBundle(package_warnings={"traffic-stats": "reported exfil (example)"})
    res = audit_server(_cfg("traffic-stats", ["npx", "-y", "traffic-stats"]), bundle, live=False)
    assert any(f.kind == "known_bad_package" for f in res.findings)
    assert res.grade == "F"


def test_typosquat_hit():
    res = audit_server(
        _cfg("t", ["npx", "-y", "modelcontextprotocol/server-github"]),
        IntelBundle(), live=False)
    assert any(f.kind == "typosquat" for f in res.findings)
    assert res.grade == "D"  # high (typosquat) outranks remote_code


def test_live_dangerous_server_grades_f():
    res = audit_server(
        _cfg("shellbox", ["python", FAKE_SERVER, "dangerous"]),
        IntelBundle(), live=True, timeout=15.0)
    assert res.live_probe is True
    assert res.tools_scanned >= 4
    crit = {f.kind for f in res.findings}
    assert "dangerous_tool" in crit
    assert any(f.risk == Risk.CRITICAL for f in res.findings)
    assert any("exfil" in f.kind for f in res.findings)  # webhook.site sink
    assert res.grade == "F"


def test_live_safe_server_grades_a():
    res = audit_server(
        _cfg("safe", ["python", FAKE_SERVER, "safe"]),
        IntelBundle(), live=True, timeout=15.0)
    assert res.live_probe is True
    assert res.grade == "A"