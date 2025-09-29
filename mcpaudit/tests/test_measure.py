"""End-to-end live test: spawn the fake MCP server and measure it through the
real stdio client. This exercises the full stdio/JSON-RPC path on Windows.
"""
from mcpaudit.config import load_servers
from mcpaudit.measure import measure_servers
from mcpaudit.mcpclient import MCPClient

from conftest import FAKE_SERVER


def test_live_measure_fake_server():
    import json
    from pathlib import Path

    config_path = Path(__file__).parent.parent / "examples" / "demo-mcp.json"
    servers = load_servers(str(config_path))
    assert len(servers) == 1
    (server,) = servers
    assert server.name == "shipments"

    measurements = measure_servers(servers, timeout=15.0)
    m = measurements[0]
    assert m.ok, m.error
    names = {t.name for t in m.tools}
    assert {"create_shipment", "get_tracking", "cancel_shipment", "list_rates"} <= names
    assert m.schema_tokens > 100
    assert m.baseline_tokens == m.schema_tokens


def test_live_start_requires_config():
    import subprocess
    from mcpaudit.models import MCPServerConfig
    from mcpaudit.mcpclient import MCPClient

    bad = MCPServerConfig(name="nope", command=["definitely-not-a-real-command-xyz"])
    client = MCPClient(bad, timeout=5.0)
    try:
        client.start()
    except Exception as exc:
        assert "could not launch" in str(exc)


def test_mcp_client_initialize_and_list_tools():
    from mcpaudit.mcpclient import MCPClient
    from mcpaudit import models

    servers = models.MCPServerConfig(
        name="shipments",
        command=["python", FAKE_SERVER],
    )
    client = MCPClient(servers, timeout=15.0)
    try:
        client.start()
        info = client.initialize()
        assert info["serverInfo"]["name"] == "fake-shipment"
        tools = client.list_tools()
        assert len(tools) >= 4
    finally:
        client.close()