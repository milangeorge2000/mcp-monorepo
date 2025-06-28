from mcpbatt.expand import expand_template
from mcpbatt.models import Template

TOOLS = [
    {"name": "lookup", "inputSchema": {
        "type": "object",
        "properties": {"record_id": {"type": "integer"}},
        "required": ["record_id"]}},
    {"name": "search", "inputSchema": {
        "type": "object",
        "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
        "required": ["query"]}},
    {"name": "flag", "inputSchema": {
        "type": "object", "properties": {}, "required": []}},
]


def test_required_mode_expands_one_call_per_tool():
    t = Template(name="t", mode="required", expect="ok", select="*")
    battery = expand_template(t, TOOLS)
    assert len(battery) == 3
    lookup = next(c for c in battery if c.tool == "lookup")
    assert lookup.arguments == {"record_id": 1}
    assert lookup.expect == "ok"
    assert lookup.phase == "baseline"


def test_missing_mode_omits_each_required_field():
    t = Template(name="t", mode="missing", expect="invalid", select="*")
    battery = expand_template(t, TOOLS)
    search_calls = [c for c in battery if c.tool == "search"]
    assert len(search_calls) == 1
    assert search_calls[0].arguments == {}  # query omitted
    assert search_calls[0].expect == "invalid"


def test_flag_has_no_required_fields():
    t = Template(name="t", mode="missing", expect="invalid", select="flag")
    battery = expand_template(t, TOOLS)
    assert len(battery) == 1
    assert battery[0].expect == "ok"  # nothing to omit


def test_all_mode_fills_every_field():
    t = Template(name="t", mode="all", expect="ok", select="search")
    battery = expand_template(t, TOOLS)
    assert battery[0].arguments == {"query": "v", "limit": 1}


def test_wrong_type_violates_each_field():
    t = Template(name="t", mode="wrong-type", expect="invalid", select="search")
    battery = expand_template(t, TOOLS)
    by_source = {c.source: c for c in battery}
    assert by_source["wrongtype:query"].arguments["query"] == 7
    assert by_source["wrongtype:limit"].arguments["limit"] == "wrong"


def test_wrong_type_empty_schema_is_ok():
    t = Template(name="t", mode="wrong-type", expect="invalid", select="flag")
    battery = expand_template(t, TOOLS)
    assert battery[0].expect == "ok"


def test_oversize_uses_big_strings():
    t = Template(name="t", mode="oversize", expect="ok", select="search")
    battery = expand_template(t, TOOLS)
    args = battery[0].arguments
    assert len(args["query"]) > 900
    assert args["limit"] == 1  # non-string field stays small


def test_empty_mode():
    t = Template(name="t", mode="empty", expect="any", select="*")
    battery = expand_template(t, TOOLS)
    lookup = next(c for c in battery if c.tool == "lookup")
    assert lookup.arguments == {}
    assert lookup.expect == "invalid"  # has required fields


def test_selection_limits_expansion():
    t = Template(name="t", mode="required", select="lookup")
    battery = expand_template(t, TOOLS)
    assert [c.tool for c in battery] == ["lookup"]


def test_drifted_phase_tag():
    t = Template(name="t", mode="required", select="search")
    battery = expand_template(t, TOOLS, phase="drifted")
    assert battery[0].phase == "drifted"
