"""Harness: spawn the fleet, run each driver, score, assemble the report.

For every driver in the registry: fresh sandbox -> spawn `python -m
mcpbench.fleet` -> drive the workload through the recording client -> score the
transcript. Deterministic given the same drivers and fleet, so the leaderboard
is reproducible and CI-able.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import List, Optional, Sequence

from mcpbench.client import Client, Recorder
from mcpbench.drivers import BaseDriver, WORKLOAD, make_driver
from mcpbench.models import BenchReport, DriverResult
from mcpbench.sandbox import make_sandbox
from mcpbench.scoring import finalize_economy, score

FLEET_ARGV = [sys.executable, "-m", "mcpbench.fleet"]


def run_benchmark(drivers: Sequence[str], timeout: float = 8.0) -> BenchReport:
    """Run every named driver against the reference fleet and return a report."""
    results: List[DriverResult] = []
    for name in drivers:
        try:
            driver = make_driver(name)
        except KeyError as exc:
            raise ValueError(f"unknown driver: {name} (use 'list')") from exc
        res = _run_one(driver, timeout=timeout)
        results.append(res)
    finalize_economy(results, round_name="baseline")
    return BenchReport(
        results=results,
        generated_at=datetime.now(timezone.utc).isoformat(),
        workload="standard-battery",
    )


def _run_one(driver: BaseDriver, timeout: float = 8.0) -> DriverResult:
    sb = make_sandbox()
    try:
        proc = sb.spawn(FLEET_ARGV)
        rec = Recorder()
        client = Client(proc, rec, timeout=timeout)
        try:
            client.initialize()
            driver.run(client, WORKLOAD)
        except Exception as exc:  # a driver bug must not kill the benchmark
            driver.notes.append(f"driver raised: {exc}")
        finally:
            _kill(proc)
        res = score("baseline", rec, driver.name)
        ok = res.ok_calls or 1
        res.tokens_per_outcome = round(res.tokens_total / ok, 1)
        res.notes = driver.notes + res.notes
        return res
    finally:
        sb.cleanup()


def _kill(proc) -> None:
    try:
        proc.terminate()
        proc.wait(timeout=2)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def list_drivers() -> List[str]:
    from mcpbench.drivers import DRIVER_REGISTRY
    return sorted(DRIVER_REGISTRY)