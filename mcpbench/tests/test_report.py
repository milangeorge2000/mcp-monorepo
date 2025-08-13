from __future__ import annotations

from mcpbench.harness import run_benchmark
from mcpbench.models import BenchReport, DriverResult, grade_for
from mcpbench.report import render_html, to_json


def _dummy_report() -> BenchReport:
    r = DriverResult("canonical", "baseline", {"conformance": 100.0, "policy": 100.0,
                                               "validity": 100.0, "economy": 100.0,
                                               "drift": 100.0},
                     grade_for(100.0), calls=4, ok_calls=2, tokens_total=40,
                     tokens_per_outcome=20.0, re_listed_after_changed=True,
                     notes=["clean"])
    return BenchReport(results=[r], generated_at="t", workload="standard-battery")


def test_render_html_contains_leaderboard():
    html = render_html(_dummy_report())
    assert "mcpbench" in html
    assert "canonical" in html
    assert "conformance" in html


def test_render_html_escapes_driver_notes():
    r = DriverResult("x", "baseline", {"conformance": 50.0, "policy": 50.0, "validity": 50.0,
                                       "economy": 50.0, "drift": 0.0}, "D",
                     notes=["<script>alert(1)</script> and & more"])
    report = BenchReport(results=[r], generated_at="t")
    html = render_html(report)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_to_json_shape():
    data = to_json(_dummy_report())
    assert data["tool"] == "mcpbench"
    assert data["best_grade"] == "A"
    assert data["drivers"][0]["driver"] == "canonical"
    assert data["drivers"][0]["scores"]["drift"] == 100.0


def test_report_finds_grade_in_histogram():
    report = run_benchmark(["canonical"])
    data = to_json(report)
    assert data["best_grade"] in "ABCDF"