from __future__ import annotations

import json

from mcpbench.harness import run_benchmark
from mcpbench.share import emit_bench_fingerprint


def test_fingerprint_shape(tmp_path):
    report = run_benchmark(["canonical", "naive"])
    path = str(tmp_path / "bench.json")
    emit_bench_fingerprint(report, path)
    with open(path, "r", encoding="utf-8") as fh:
        fp = json.load(fh)
    assert fp["sensor"] == "bench"
    assert fp["format"] == "mcpcensus/v1"
    assert fp["axes"]["drivers"] == 2
    assert set(fp["axes"]["axis_means"]) == {"conformance", "policy", "validity", "economy", "drift"}
    assert fp["axes"]["best_grade"] in "ABCDF"