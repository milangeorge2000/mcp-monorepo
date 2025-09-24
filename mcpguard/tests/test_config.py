"""Config parsing tests."""
from mcpguard.config import load_servers

from conftest import fixture


def test_fixture_parses_eight_servers():
    servers = load_servers(str(fixture("mcp.json")))
    names = {s.name for s in servers}
    assert names == {
        "github", "filesystem-pinned", "traffic-stats", "legacy-db",
        "pinned-writer", "db-container", "trusted-local", "public-relay",
    }


def test_command_and_url_split():
    servers = {s.name: s for s in load_servers(str(fixture("mcp.json")))}
    assert servers["github"].command == ["npx", "-y", "@modelcontextprotocol/server-github"]
    assert servers["github"].env == {"GITHUB_TOKEN": "ghp_placeholder"}
    assert servers["public-relay"].command == []
    assert servers["public-relay"].url.startswith("https://")
    assert servers["trusted-local"].command[0] == "python"


def test_explicit_missing_path_is_empty():
    assert load_servers(str(fixture("nope.json"))) == []