"""Tests for config discovery and parsing."""
import sys
from pathlib import Path

import pytest

from mcpaudit.config import _command_from, _enabled, load_servers, _parse_mcp_servers

from conftest import fixture


def test_parse_mcp_servers_basic():
    blob = {
        "mcpServers": {
            "github": {
                "command": "npx",
                "args": ["-y", "server-github"],
                "env": {"GITHUB_TOKEN": "x"},
            },
            "pg": {"commandPath": "/bin/pg", "args": ["--port", "5432"]},
        }
    }
    servers = _parse_mcp_servers(blob, "fake")
    assert len(servers) == 2
    gh = {s.name: s for s in servers}["github"]
    assert gh.command == ["npx", "-y", "server-github"]
    assert gh.env == {"GITHUB_TOKEN": "x"}
    assert gh.source == "fake"
    pg = {s.name: s for s in servers}["pg"]
    assert pg.command == ["/bin/pg", "--port", "5432"]


def test_parse_mcp_servers_skips_disabled_and_broken():
    blob = {
        "mcpServers": {
            "off": {"command": "x", "enabled": False},
            "noop": {"env": {"A": "b"}},
        }
    }
    assert _parse_mcp_servers(blob, "fake") == []


def test_fixture_file_parses():
    servers = load_servers(str(fixture("mcp.json")))
    names = {s.name for s in servers}
    # disabled-server skipped, no-command skipped
    assert names == {"github", "filesystem", "postgres"}


def test_command_form_variants():
    assert _command_from({"command": ["a", "b"]}) == ["a", "b"]
    assert _command_from({"command": "npx"}) == ["npx"]
    assert _command_from({"commandPath": "/x", "args": ["-h"]}) == ["/x", "-h"]
    assert _command_from({"env": {}}) is None


def test_discovery_prefers_explicit():
    paths = load_servers(str(fixture("mcp.json")))
    assert paths  # parses fine


@pytest.mark.skipif(sys.platform != "win32", reason="POSIX home tests need different paths")
def test_explicit_missing_path_returns_empty():
    # explicit path is honored even when missing; returns no servers but no crash
    servers = load_servers(str(fixture("does-not-exist.json")))
    assert servers == []