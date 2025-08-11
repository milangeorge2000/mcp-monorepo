"""mcpbench command-line interface."""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional, Sequence

from mcpbench import __version__
from mcpbench.harness import list_drivers, run_benchmark
from mcpbench.models import BenchReport
from mcpbench.report import render_html, to_json


def cmd_run(args) -> int:
    drivers = args.drivers or list_drivers()
    try:
        report = run_benchmark(drivers, timeout=args.timeout)
    except ValueError as exc:
        print(f"mcpbench: {exc}", file=sys.stderr)
        return 2

    glut = bool(args.json)

    def say(msg: str) -> None:
        (sys.stdout if not glut else sys.stderr).write(msg + "\n")

    if args.json:
        json.dump(to_json(report), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        say(f"mcpbench: leaderboard | {len(report.results)} driver runs | best grade {report.best_grade}")
        for r in sorted(report.results, key=lambda r: (-_overall(r))):
            say(f"  {r.driver:<12} {r.grade}  conformance {r.scores.get('conformance',0):4.0f}  "
                f"policy {r.scores.get('policy',0):4.0f}  validity {r.scores.get('validity',0):4.0f}  "
                f"economy {r.scores.get('economy',0):4.0f}  drift {r.scores.get('drift',0):4.0f}  "
                f"tokens/outcome {r.tokens_per_outcome:.1f}")

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(render_html(report))
        say(f"mcpbench: wrote {args.output}")

    if args.share:
        from mcpbench.share import emit_bench_fingerprint
        path = emit_bench_fingerprint(report, args.share)
        say(f"mcpbench: census fingerprint -> {path}")
    return 0


def _overall(r) -> float:
    w = {"conformance": 0.25, "policy": 0.25, "validity": 0.30, "economy": 0.10, "drift": 0.10}
    return sum(r.scores.get(k, 0.0) * w[k] for k in w)


def cmd_list(args) -> int:
    print("mcpbench: reference drivers (each is a deterministic client behaviour profile):")
    for name in list_drivers():
        print(f"  {name}")
    print("mcpbench: use --drivers naive,canonical to benchmark a subset")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mcpbench",
        description="Benchmark the clients, not the servers. Drives reference MCP client "
                    "behaviour profiles against a standard fleet + workload in a sandbox and "
                    "scores conformance, policy, validity, economy, and drift into an A-F leaderboard.",
    )
    p.add_argument("--version", action="version", version=f"mcpbench {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="benchmark the reference drivers against the fleet")
    run.add_argument("--drivers", nargs="+", metavar="NAME", help="subset of drivers to run")
    run.add_argument("--timeout", type=float, default=8.0)
    run.add_argument("-o", "--output", default="mcpbench-report.html", help="leaderboard HTML path ('' disables)")
    run.add_argument("--json", action="store_true", help="emit machine-readable results to stdout")
    run.add_argument("--share", metavar="PATH", help="emit an mcpcensus bench fingerprint")
    run.set_defaults(func=cmd_run)

    _ls = sub.add_parser("list", help="list reference drivers")
    _ls.set_defaults(func=cmd_list)

    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("mcpbench: interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())