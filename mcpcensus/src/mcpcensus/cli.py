"""mcpcensus command-line interface.

Commands mirror the observatory lifecycle:
  serve      run the stdlib HTTP registry
  ingest     add fingerprints to a local registry file
  aggregate  reduce the registry for one sensor into a published snapshot
  report     render a published snapshot to State-of-MCP HTML
  badge      render a shields-style SVG badge from a published snapshot
  suggest    show where a device sits in the current distribution
  fingerprint  build a fingerprint from an mcpaudit/mcpguard --json report
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Sequence

from mcpcensus import __version__
from mcpcensus.fingerprint import (
    build_context_fingerprint,
    build_security_fingerprint,
    write_fingerprint,
)
from mcpcensus.privacy import (
    DeviceSalt,
    cohort_bucket,
    is_valid_fingerprint,
    k_anonymize,
    stable_hash,
)
from mcpcensus.registry import (
    aggregate,
    append_registry,
    load_registry,
    suggest,
    written_form,
)
from mcpcensus.report import write_badge, write_report


def _out(obj: Any) -> None:
    json.dump(obj, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_fingerprints(paths: List[str]) -> List[Dict[str, Any]]:
    fps: List[Dict[str, Any]] = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as fh:
            obj = json.load(fh)
        if isinstance(obj, list):
            fps.extend(o for o in obj if is_valid_fingerprint(o))
        elif is_valid_fingerprint(obj):
            fps.append(obj)
        else:
            print(f"mcpcensus: skipping {p}: not a valid mcpcensus/v1 fingerprint", file=sys.stderr)
    return fps


def cmd_fingerprint(args) -> int:
    report = _read_json(args.report)
    salt_path = args.salt_file or os.path.join(os.path.expanduser("~"), ".mcpcensus", "salt")
    dev = DeviceSalt.load_or_create(salt_path)
    fp = (build_context_fingerprint if args.sensor == "context" else build_security_fingerprint)(
        report, dev.salt, dev.device_id)
    path = write_fingerprint(fp, args.out)
    print(f"mcpcensus: wrote {path} (sensor={args.sensor}, device={fp['device']})")
    return 0


def cmd_ingest(args) -> int:
    fps = _load_fingerprints(args.fingerprints)
    added = append_registry(args.db, fps)
    print(f"mcpcensus: {added}/{len(fps)} fingerprints appended to {args.db}")
    return 0


def cmd_aggregate(args) -> int:
    fps = load_registry(args.db)
    sensors = [args.sensor] if args.sensor else sorted({fp.get("sensor") for fp in fps if fp.get("sensor")})
    if not sensors:
        print("mcpcensus: registry is empty; nothing to aggregate", file=sys.stderr)
        return 1
    outputs: Dict[str, Any] = {}
    for sensor in sensors:
        outputs[sensor] = aggregate(fps, sensor, min_cohort=args.min_cohort, noise_scale=args.noise_scale)
    payload = outputs if len(sensors) > 1 else outputs[sensors[0]]
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(written_form(payload))
    print(f"mcpcensus: wrote {args.output} (sensors: {', '.join(sensors)})")
    return 0


def cmd_report(args) -> int:
    published = _read_json(args.aggregates)
    if args.sensor and published.get("sensor") != args.sensor:
        print(f"mcpcensus: {args.aggregates} is sensor '{published.get('sensor')}', wanted '{args.sensor}'", file=sys.stderr)
        return 2
    path = write_report(published, args.output, args.title)
    print(f"mcpcensus: wrote {path}")
    return 0


def cmd_badge(args) -> int:
    published = _read_json(args.aggregates)
    path = write_badge(published, args.output, args.grade)
    print(f"mcpcensus: wrote {path}")
    return 0


def cmd_suggest(args) -> int:
    published = _read_json(args.aggregates)
    fp = _load_fingerprints([args.fingerprint])
    if not fp:
        print("mcpcensus: not a valid fingerprint", file=sys.stderr)
        return 2
    hint = suggest(published, fp[0])
    _out(hint)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mcpcensus", description="The MCP Observatory: sensor registry, aggregation, State-of-MCP reports.")
    p.add_argument("--version", action="version", version=f"mcpcensus {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    fp = sub.add_parser("fingerprint", help="build a fingerprint from a tool --json report")
    fp.add_argument("--report", required=True, help="mcpaudit or mcpguard --json report file")
    fp.add_argument("--sensor", choices=("context", "security"), default="context")
    fp.add_argument("--out", default="census-fingerprint.json")
    fp.add_argument("--salt-file", default=None, help="device salt (default ~/.mcpcensus/salt)")
    fp.set_defaults(func=cmd_fingerprint)

    ing = sub.add_parser("ingest", help="append fingerprint(s) to a local registry")
    ing.add_argument("fingerprints", nargs="+", help="fingerprint JSON file(s)")
    ing.add_argument("--db", default="registry.jsonl")
    ing.set_defaults(func=cmd_ingest)

    agg = sub.add_parser("aggregate", help="reduce registry to published snapshots")
    agg.add_argument("--db", default="registry.jsonl")
    agg.add_argument("--sensor", choices=("context", "security"), default=None)
    agg.add_argument("--min-cohort", type=int, default=5, help="k for k-anonymity")
    agg.add_argument("--noise", dest="noise_scale", type=float, default=0.0, help="Laplace noise scale (LDP)")
    agg.add_argument("-o", "--output", default="published.json")
    agg.set_defaults(func=cmd_aggregate)

    rep = sub.add_parser("report", help="render published snapshot to HTML")
    rep.add_argument("aggregates")
    rep.add_argument("-o", "--output", default="state-of-mcp.html")
    rep.add_argument("--sensor", choices=("context", "security"), default=None)
    rep.add_argument("--title")
    rep.set_defaults(func=cmd_report)

    bad = sub.add_parser("badge", help="render an SVG badge from a published snapshot")
    bad.add_argument("aggregates")
    bad.add_argument("-o", "--output", default="mcpcensus-badge.svg")
    bad.add_argument("--grade")
    bad.set_defaults(func=cmd_badge)

    sug = sub.add_parser("suggest", help="percentile feedback for one fingerprint")
    sug.add_argument("aggregates")
    sug.add_argument("fingerprint")
    sug.set_defaults(func=cmd_suggest)

    def cmd_serve(args) -> int:
        from mcpcensus.server import run_server
        return run_server(args.db, port=args.port, min_cohort=args.min_cohort, noise_scale=args.noise_scale)

    ser = sub.add_parser("serve", help="run the reference observatory server")
    ser.add_argument("--db", default="registry.jsonl")
    ser.add_argument("--port", type=int, default=8787)
    ser.add_argument("--min-cohort", type=int, default=5)
    ser.add_argument("--noise", dest="noise_scale", type=float, default=0.0)
    ser.set_defaults(func=cmd_serve)

    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())