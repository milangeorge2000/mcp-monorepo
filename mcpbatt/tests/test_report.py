import json

from mcpbatt.models import BattReport, ServerResult
from mcpbatt.report import render_html, to_json


def _result(name="x", grade="A"):
    return ServerResult(template=name, server="srv", scores={
        "fidelity": 100.0, "discipline": 90.0, "stability": 100.0,
        "drift": 100.0, "overall": 97.0}, grade=grade,
        calls_total=4, ok_calls=3, invalid_calls=1, drift_seen=True,
        notes=["note one"])


def test_html_contains_grade_and_axes():
    report = BattReport(results=[_result()], template="t")
    html = render_html(report)
    assert "A" in html
    assert "fidelity" in html
    assert "drift" in html
    assert "note one" in html


def test_html_grade_badge_colored():
    report = BattReport(results=[_result(grade="F")], template="t")
    html = render_html(report)
    assert "#c62828" in html  # F color


def test_to_json_shape():
    report = BattReport(results=[_result()], template="t")
    data = to_json(report)
    assert data["format"] == "mcpbatt/v1"
    assert data["best_grade"] == "A"
    assert data["results"][0]["grade"] == "A"
    assert data["results"][0]["calls_total"] == 4


def test_to_json_roundtrips():
    report = BattReport(results=[_result()], template="t")
    data = json.loads(json.dumps(to_json(report)))
    assert data["results"][0]["scores"]["overall"] == 97.0


def test_best_grade_over_multiple_results():
    report = BattReport(results=[_result("a", "B"), _result("b", "A")], template="t")
    assert report.best_grade == "A"


def test_servers_dedupe():
    report = BattReport(results=[_result("a"), _result("b", "C")], template="t")
    assert report.servers == ["srv"]