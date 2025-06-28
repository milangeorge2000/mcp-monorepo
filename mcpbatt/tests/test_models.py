from mcpbatt.models import (
    CallSpec,
    DriftSpec,
    Template,
    grade_for,
    select_tools,
    GRADES,
    PHASES,
)

FLEET_TOOLS = [
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


def test_grades_monotonic():
    assert grade_for(100) == "A"
    assert grade_for(90) == "A"
    assert grade_for(80) == "B"
    assert grade_for(60) == "C"
    assert grade_for(40) == "D"
    assert grade_for(10) == "F"


def test_grades_exhaustive():
    assert set(GRADES) == {"A", "B", "C", "D", "F"}
    assert len(GRADES) == len(set(GRADES))


def test_phases_ordered():
    assert PHASES == ["baseline", "stale", "drifted"]


def test_select_all():
    tools = select_tools(FLEET_TOOLS, "*")
    assert [t["name"] for t in tools] == ["lookup", "search", "flag"]


def test_select_names():
    tools = select_tools(FLEET_TOOLS, "lookup,search")
    assert [t["name"] for t in tools] == ["lookup", "search"]


def test_select_regex():
    tools = select_tools(FLEET_TOOLS, "regex:^sea")
    assert [t["name"] for t in tools] == ["search"]


def test_select_unknown_is_empty():
    assert select_tools(FLEET_TOOLS, "nonexistent") == []


def test_template_dataclass_defaults():
    t = Template(name="t")
    assert t.select == "*"
    assert t.mode == "required"
    assert t.expect == "ok"
    assert t.drift is None


def test_template_with_drift():
    t = Template(name="t", drift=DriftSpec(tool="lookup", add_required=["scope"]))
    assert t.drift.tool == "lookup"
    assert t.drift.add_required == ["scope"]


def test_call_spec():
    c = CallSpec(seq=1, tool="lookup", arguments={"record_id": 1}, expect="ok", phase="baseline")
    assert c.source == ""
