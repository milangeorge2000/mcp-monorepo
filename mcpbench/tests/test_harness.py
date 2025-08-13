from __future__ import annotations

from mcpbench.harness import list_drivers, run_benchmark


def test_list_drivers_has_core_set():
    drivers = list_drivers()
    assert {"canonical", "naive", "chatty", "careless"} <= set(drivers)


def test_run_benchmark_reports_all_drivers():
    report = run_benchmark(["canonical", "naive", "careless"])
    assert len(report.results) == 3
    for r in report.results:
        assert r.grade in "ABCDF"
        assert set(r.scores) >= {"conformance", "policy", "validity", "economy", "drift"}


def test_canonical_beats_naive_and_careless():
    report = run_benchmark(["canonical", "naive", "careless"])
    canon = report.score("canonical", "baseline")
    naive = report.score("naive", "baseline")
    careless = report.score("careless", "baseline")
    assert canon is not None and naive is not None and careless is not None
    assert canon.scores["policy"] >= naive.scores["policy"]
    assert canon.scores["validity"] >= careless.scores["validity"]
    assert canon.grade <= naive.grade  # A < F alphabetically => canonical better


def test_canonical_adapts_to_drift():
    report = run_benchmark(["canonical"])
    canon = report.score("canonical", "baseline")
    assert canon is not None
    assert canon.re_listed_after_changed
    assert canon.scores["drift"] == 100.0


def test_naive_fails_drift():
    report = run_benchmark(["naive"])
    naive = report.score("naive", "baseline")
    assert naive is not None
    assert not naive.re_listed_after_changed
    assert naive.scores["drift"] == 0.0