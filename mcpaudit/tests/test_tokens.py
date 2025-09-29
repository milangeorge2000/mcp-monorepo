"""Token estimation tests."""
from mcpaudit.tokens import compact_schema, estimate_tokens, json_tokens


def test_estimate_tokens_floor_and_scale():
    assert estimate_tokens("") == 1
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 40) == 10


def test_json_tokens_stable_and_sorted():
    a = {"z": 1, "a": {"b": 2, "x": "yyyy"}}
    b = {"a": {"x": "yyyy", "b": 2}, "z": 1}
    assert json_tokens(a) == json_tokens(b)


def test_compact_schema_mirrors_client_shape():
    tool = {
        "name": "n",
        "description": "d",
        "inputSchema": {"type": "object"},
        "annotations": {"readOnlyHint": True},
        "extra": "ignored",
    }
    out = compact_schema(tool)
    assert out == {
        "name": "n",
        "description": "d",
        "inputSchema": {"type": "object"},
        "annotations": {"readOnlyHint": True},
    }