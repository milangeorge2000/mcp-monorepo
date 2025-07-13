"""mcphazard command-line interface."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional, Sequence

from mcphazard import __version__
from mcphazard.harness import scan_server
from mcphazard.payloads import bundled_payloads
from mcphazard.report import render_html, to_json


def cmd_scan(args) -> int:
    live = bool(args.live)
    command = _resolve_command(args)
    if command is None:
        return 2
    glut = bool(args.json)

    def say(msg: str) -> None:
        (sys.stdout if not glut else sys.stderr).write(msg + "\n")

    config = getattr(args, "config", None)

    say(f"mcphazard: red-team scan | target={args.name} | mode={'LIVE-FIRE' if live else 'SANDBOX'}")
    say(f"mcphazard: payload bundle = {len(bundled_payloads(live=live))} "
        f"({len(bundled_payloads(live=True))} available with --live)")

    report = scan_server(command, server_name=args.name, live=live,
                         timeout=args.timeout, config=config)

    grade = report.overall_grade
    say(f"mcphazard: {report.tool_count} tools x {report.payload_count} payloads -> "
        f"{report.finding_count} findings ({report.risk_counts['critical']} crit / "
        f"{report.risk_counts['high']} high) . posture {grade}")

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(render_html(report))
        say(f"mcphazard: wrote {args.output}")

    if args.json:
        json.dump(to_json(report), sys.stdout, indent=2)
        sys.stdout.write("\n")

    if args.share:
        from mcphazard.share import emit_hazard_fingerprint
        path = emit_hazard_fingerprint(report, args.share)
        say(f"mcphazard: census fingerprint -> {path}")

    return 0


def cmd_payloads(args) -> int:
    items = bundled_payloads(live=args.live)
    if args.json:
        json.dump([{k: getattr(p, k) for k in ("klass", "name", "risk", "target_key", "bespoke")}
                   for p in items], sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    print(f"mcphazard: {len(items)} payloads "
          f"({'incl. --live weaponized' if args.live else 'non-bespoke only - add --live for the rest'})")
    for p in items:
        flag = " **LIVE**" if p.bespoke else ""
        print(f"  [{p.klass:<22}] {p.name:<22} risk={p.risk.value}{flag}")
    return 0


def _resolve_command(args) -> Optional[List[str]]:
    if getattr(args, "command", None):
        return args.command
    if getattr(args, "config", None):
        entry = _server_from_config(args.config, args.name)
        if entry is None:
            sys.exit(2)
        return entry
    # no target supplied (arg group is not required): reject loudly
    print("mcphazard: a target is required: --command <cmd...> or --config <mcp.json>", file=sys.stderr)
    return None


def _server_from_config(config: str, name: str) -> Optional[List[str]]:
    try:
        with open(config, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"mcphazard: cannot read config {config}: {exc}", file=sys.stderr)
        return None
    servers = data.get("mcpServers", data) if isinstance(data, dict) else {}
    entry = servers.get(name) if isinstance(servers, dict) else None
    if not entry or not isinstance(entry, dict):
        print(f"mcphazard: server '{name}' not found in {config}", file=sys.stderr)
        return None
    command = entry.get("command")
    if not command:
        print(f"mcphazard: server '{name}' has no stdio command (URL transport not yet supported)",
              file=sys.stderr)
        return None
    args = list(entry.get("args", []))
    base = os.path.dirname(os.path.abspath(config))
    if not os.path.isabs(command) and os.path.exists(os.path.join(base, command)):
        command = os.path.abspath(os.path.join(base, command))

    def _abs(a: str) -> str:
        if os.path.isabs(a):
            return a
        for root in (base, os.getcwd()):
            cand = os.path.join(root, a)
            if os.path.exists(cand):
                return os.path.abspath(cand)
        return a

    args = [_abs(a) for a in args]
    return [command] + args


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mcphazard",
                                description="Red-team harness for MCP servers: fuzz every tool with adversarial payloads in a sandbox, report what lands.")
    p.add_argument("--version", action="version", version=f"mcphazard {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="run the adversarial battery against a server")
    scan.add_argument("name", nargs="?", default="demo", help="server name (config key) or target label")
    target = scan.add_mutually_exclusive_group()
    target.add_argument("--command", nargs="+", metavar="ARG", help="stdio command+args of the server under test")
    target.add_argument("--config", metavar="mcp.json", help="server config containing the named server")
    scan.add_argument("--live", action="store_true", default=False,
                      help="LIVE-FIRE: allow weaponized payloads (URL sinks, shell punctuation). Sandbox-capped but explicit.")
    scan.add_argument("--timeout", type=float, default=10.0)
    scan.add_argument("-o", "--output", default="mcphazard-report.html", help="pentest HTML report path ('' disables)")
    scan.add_argument("--json", action="store_true", help="emit machine-readable results to stdout")
    scan.add_argument("--share", metavar="PATH", help="emit an mcpcensus hazard fingerprint")
    scan.set_defaults(func=cmd_scan)

    pl = sub.add_parser("payloads", help="inspect the adversarial payload bundle")
    pl.add_argument("--live", action="store_true", help="include weaponized (--live-only) payloads")
    pl.add_argument("--json", action="store_true")
    pl.set_defaults(func=cmd_payloads)

    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("mcphazard: interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())