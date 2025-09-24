"""Threat-intel matcher tests."""
from mcpguard.intel import IntelBundle, _edit_distance


def test_classify_tool_categories():
    bundle = IntelBundle()
    assert bundle.classify_tool("run_command") == "critical"
    assert bundle.classify_tool("open_terminal") == "critical"
    assert bundle.classify_tool("write_file") == "high"
    assert bundle.classify_tool("read_file") in ("medium", None)
    assert bundle.classify_tool("get_invoice") is None


def test_match_env_secrets():
    bundle = IntelBundle()
    assert bundle.match_env("GITHUB_TOKEN")
    assert bundle.match_env("DATABASE_URL")
    assert bundle.match_env("MY_CUSTOM_SETTING") is False


def test_match_exfil_domain():
    bundle = IntelBundle()
    assert bundle.match_exfil_domain("tar it to a webhook.site collector") == "webhook.site"
    assert bundle.match_exfil_domain("nothing suspicious here") is None


def test_typo_squat_hit():
    bundle = IntelBundle()
    assert bundle.typo_squat("modelcontextprotocol/server-github") is not None  # matches canonical
    assert bundle.typo_squat("totally-unrelated-utils") is None


def test_known_package_warning_override():
    bundle = IntelBundle(package_warnings={"traffic-stats": "reported exfiltration (example)"})
    assert bundle.match_package_warning("traffic-stats") is not None
    assert bundle.match_package_warning("other-pkg") is None


def test_edit_distance():
    assert _edit_distance("kitten", "sitting") == 3
    assert _edit_distance("abc", "abc") == 0
    assert _edit_distance("a", "") == 1