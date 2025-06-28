import pytest

from mcpbatt.models import Template
from mcpbatt.schema import load_template, validate_template

VALID = {
    "name": "req-only",
    "description": "x",
    "select": "*",
    "mode": "required",
    "expect": "ok",
    "drift": {"tool": "lookup", "add_required": ["scope"]},
}


def test_valid_template_passes():
    assert validate_template(VALID) == []


def test_missing_name():
    raw = {k: v for k, v in VALID.items() if k != "name"}
    assert "name must be a non-empty string" in validate_template(raw)


def test_bad_mode():
    raw = dict(VALID, mode="explode")
    assert any("mode must be one of" in m for m in validate_template(raw))


def test_bad_expect():
    raw = dict(VALID, expect="maybe")
    assert any("expect must be one of" in m for m in validate_template(raw))


def test_bad_drift_shape():
    raw = dict(VALID, drift="not-an-object")
    assert any("drift must be an object" in m for m in validate_template(raw))


def test_drift_missing_tool():
    raw = dict(VALID, drift={"add_required": ["scope"]})
    assert any("drift.tool must be a non-empty string" in m for m in validate_template(raw))


def test_not_a_dict():
    assert validate_template(["nope"]) == ["template must be a JSON object"]


def test_load_template_builds_drift():
    t = load_template(VALID)
    assert t.name == "req-only"
    assert t.drift is not None
    assert t.drift.add_required == ["scope"]


def test_load_template_no_drift():
    raw = {k: v for k, v in VALID.items() if k != "drift"}
    t = load_template(raw)
    assert t.drift is None


def test_load_template_rejects_invalid():
    with pytest.raises(ValueError):
        load_template({"mode": "explode"})
