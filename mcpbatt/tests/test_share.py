import json
import os

from mcpbatt.models import BattReport, ServerResult
from mcpbatt.share import emit_batt_fingerprint


def _report():
    results = [
        ServerResult(template="required-only", server="srv",
                     scores={"fidelity": 100.0, "discipline": 100.0, "stability": 100.0,
                             "drift": 100.0, "overall": 100.0}, grade="A"),
        ServerResult(template="missing-required", server="srv",
                     scores={"fidelity": 100.0, "discipline": 90.0, "stability": 100.0,
                             "drift": 100.0, "overall": 97.0}, grade="A"),
    ]
    return BattReport(results=results, template="battery")


def test_fingerprint_shape(tmp_path):
    path = emit_batt_fingerprint(_report(), str(tmp_path / "b.json"))
    assert os.path.exists(path)
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["format"] == "mcpcensus/v1"
    assert data["sensor"] == "batt"
    assert data["meta"]["tool"] == "mcpbatt"
    assert data["axes"]["runs"] == 2
    assert data["axes"]["best_grade"] == "A"
    assert data["axes"]["grade_histogram"]["A"] == 2
    assert data["axes"]["mode"] == "sandbox"
    assert "fidelity" in data["axes"]["axis_means"]
    assert "required-only" in data["axes"]["templates"]


def test_fingerprint_no_arguments_leak(tmp_path):
    path = emit_batt_fingerprint(_report(), str(tmp_path / "c.json"))
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    assert "arguments" not in text
    assert "record_id" not in text