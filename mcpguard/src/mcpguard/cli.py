"""Command-line entrypoint for mcpguard.

Usage:
  mcpguard scan   [--config PATH] [--timeout SEC] [--report PATH] [--json] [--no-live]
  mcpguard watch  [--config PATH] [--json]          # baseline against ~/.mcpguard/state.json, alert on new criticals
  mcpguard intel  show | update [--from URL]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

from mcpguard import __version__
from mcpguard.audit import audit_servers
from mcpguard.config import discover_configs, load_servers
from mcpguard.intel import IntelBundle
from mcpguard.models import GuardReport, Risk
from mcpguard.report import render_html, write_hardened_config

STATE_DIR = Path.home() / ".mcpguard"


def _print_json(obj, stream=None) -> None:
    json.dump(obj, stream or sys.stdout, indent=2)
    sys.stdout.write("\n")


def _cwd_report_path(prefix: str = "mcpguard-report") -> str:
    return f"{prefix}.html"


def scan(args) -> GuardReport:
    servers = load_servers(args.config)
    if not servers:
        sys.stderr.write(
            f"mcpguard: no MCP servers found. Tried {len(discover_configs(args.config))} config file(s). "
            "Pass --config <path> or place .mcp.json in this directory.\n"
        )
        sys.exit(2)
    intel = IntelBundle.load(args.intel)
    results = audit_servers(servers, intel, timeout=args.timeout, live=not args.no_live)
    return GuardReport(
        results=results,
        generated_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        source_configs=[str(p) for p in discover_configs(args.config)],
        intel_bundle_version=intel.version,
        intel_updated_at=intel.updated_at,
    )


def _summary_dict(report: GuardReport) -> dict:
    return {
        "overall_grade": report.overall_grade,
        "risk_counts": report.risk_counts,
        "servers": [
            {
                "server": r.server,
                "grade": r.grade,
                "mode": r.mode,
                "remote_code": r.remote_code,
                "pinned": r.pinned,
                "tools_scanned": r.tools_scanned,
                "probe_error": r.probe_error,
                "findings": [
                    {"risk": f.risk.value, "kind": f.kind, "detail": f.detail, "tool": f.tool}
                    for f in r.findings
                ],
            }
            for r in report.results
        ],
        "hardened_config": write_hardened_config(report),
        "source_configs": report.source_configs,
        "generated_at": report.generated_at,
        "intel_version": report.intel_bundle_version,
    }


def cmd_scan(args) -> int:
    report = scan(args)
    if args.json:
        _print_json(_summary_dict(report))
        return 0
    if args.share:
        try:
            from mcpguard.share import emit_security_fingerprint
        except ImportError:  # pragma: no cover
            print("mcpguard: --share needs mcpguard.share; reinstall the package", file=sys.stderr)
            return 2
        path = emit_security_fingerprint(_summary_dict(report), args.share)
        print(f"Wrote census fingerprint {path} · nothing sensitive leaves this file — only salted hashes")
        return 0

    html = render_html(report, report.source_configs)
    path = args.report or _cwd_report_path()
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"Wrote {path} · overall grade {report.overall_grade} · "
          f"{report.risk_counts['critical']} critical, {report.risk_counts['high']} high")
    try:
        from mcpguard._webbrowser_open import open_html
        open_html(path)
    except Exception:  # pragma: no cover
        pass
    return 0


def cmd_watch(args) -> int:
    report = scan(args)
    state = _load_state()
    new_crit = []
    for r in report.results:
        crit_findings = [f for f in r.findings if f.risk == Risk.CRITICAL]
        if crit_findings:
            prev = state.get("critical", {}).get(r.server, [])
            if prev != [f.kind for f in crit_findings]:
                new_crit.append({"server": r.server, "findings": [f.detail for f in crit_findings]})
    state["critical"] = {
        r.server: [f.kind for f in r.findings if f.risk == Risk.CRITICAL] for r in report.results
    }
    state["last_scan"] = report.generated_at
    _save_state(state)
    if args.json:
        _print_json({"new_critical": new_crit, **{k: v for k, v in _summary_dict(report).items() if k != "servers"}})
    if new_crit:
        print("mcpguard: NEW critical findings introduced since last watch:")
        for n in new_crit:
            print(f"  - {n['server']}: {'; '.join(n['findings'])}")
        return 3
    print(f"mcpguard: no new critical findings (overall {report.overall_grade})")
    return 0


def cmd_intel(args) -> int:
    if args.intel_action == "show":
        intel = IntelBundle.load(args.intel)
        _print_json({
            "version": intel.version,
            "updated_at": intel.updated_at,
            "canonical_packages": intel.canonical_packages,
            "exfil_domains": intel.exfil_domains,
            "env_dangerous": len(intel.env_dangerous),
            "tool_categories": {k: len(v) for k, v in intel.tool_categories.items()},
            "package_warnings": intel.package_warnings,
        })
        return 0
    if args.intel_action == "update":
        from_prompt = args.from_url
        if not from_prompt:
            sys.stderr.write("intel update requires --from <url> (or set MCPGUARD_INTEL_UPDATE_URL)\n")
            return 2
        _print_json({
            "status": "not_implemented",
            "hint": "curl a signed bundle from your intel URL and save with MCPGUARD_INTEL=<path>.",
        })
        return 1
    return 2


def _state_path() -> Path:
    base = os.environ.get("MCPGUARD_STATE_DIR")
    d = Path(base) if base else STATE_DIR
    return d / "state.json"


def _load_state() -> dict:
    try:
        return json.loads(_state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(state: dict) -> None:
    try:
        _state_path().parent.mkdir(parents=True, exist_ok=True)
        _state_path().write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError:  # pragma: no cover
        pass


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mcpguard",
        description="Security scorecard for your MCP servers: risky launchers, dangerous tool "
        "capabilities, credential env exposure, and known-bad package intel.",
    )
    parser.add_argument("--version", action="version", version=f"mcpguard {__version__}")
    parser.add_argument("--intel", metavar="PATH", help="Custom intel bundle (default: bundled seed; MCPGUARD_INTEL overrides)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="grade every server and write a report")
    p_scan.set_defaults(func=cmd_scan)
    p_scan.add_argument("--config", metavar="PATH")
    p_scan.add_argument("--timeout", type=float, default=10.0)
    p_scan.add_argument("--report", metavar="PATH")
    p_scan.add_argument("--no-live", action="store_true", help="skip the live tools/list handshake")
    p_scan.add_argument("--json", action="store_true")
    p_scan.add_argument("--share", metavar="PATH", help="write an anonymized mcpcensus fingerprint to PATH instead of html/json")

    p_watch = sub.add_parser("watch", help="scan and alert on newly-introduced critical findings")
    p_watch.set_defaults(func=cmd_watch)
    p_watch.add_argument("--config", metavar="PATH")
    p_watch.add_argument("--timeout", type=float, default=10.0)
    p_watch.add_argument("--no-live", action="store_true")
    p_watch.add_argument("--json", action="store_true")

    p_intel = sub.add_parser("intel", help="inspect or refresh the threat-intel bundle")
    p_intel.add_argument("intel_action", choices=["show", "update"])
    p_intel.add_argument("--from", dest="from_url", metavar="URL")
    p_intel.set_defaults(func=cmd_intel)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())