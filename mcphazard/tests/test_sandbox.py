from __future__ import annotations

from mcphazard.sandbox import Sandbox, CANARY_SECRET, make_sandbox


def test_sandbox_has_canary_secret():
    sb = make_sandbox(live=False)
    try:
        assert sb.read_secret() == CANARY_SECRET
    finally:
        sb.cleanup()


def test_env_scrubs_credentials():
    sb = Sandbox()
    base = {"PATH": "/usr/bin", "AWS_SECRET_ACCESS_KEY": "hunter2", "API_KEY": "x"}
    try:
        env = sb.env(base)
        assert "AWS_SECRET_ACCESS_KEY" not in env
        assert "API_KEY" not in env
        assert env["PATH"] == "/usr/bin"
        assert env.get("MCPHZ_SANDBOX") == "1"
    finally:
        sb.cleanup()


def test_nonlive_env_strands_proxies():
    sb = Sandbox(live=False)
    try:
        env = sb.env({"PATH": "/usr/bin"})
        assert env.get("HTTP_PROXY", "").startswith("http://127.0.0.1:1")
    finally:
        sb.cleanup()


def test_live_env_does_not_strand_proxy():
    sb = Sandbox(live=True)
    try:
        env = sb.env({"PATH": "/usr/bin", "HTTP_PROXY": "http://real:8080"})
        assert env.get("HTTP_PROXY") == "http://real:8080"
    finally:
        sb.cleanup()


def test_fresh_cwd_cleanup():
    sb = make_sandbox(live=False)
    import os
    cwd = sb.cwd
    assert os.path.isdir(cwd)
    sb.cleanup()
    assert not os.path.isdir(cwd)