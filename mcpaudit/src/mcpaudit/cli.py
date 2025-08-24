"""Command-line entrypoint for mcpaudit.

Usage:
  mcpaudit [--config PATH] [--context N] [--window N] [--report PATH] [--json]
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from typing import List, Optional

from mcpaudit import __version__
from mcpaudit.config import discover_configs, load_servers
from mcpaudit.measure import measure_servers
from mcpaudit.models import AuditReport
from mcpaudit.probe import scan_usage
from mcpaudit.report import render_html, write_slim_config


def _print_json(obj) -> None:
    json.dump(obj, sys.stdout, indent=2)
    sys.stdout.write("\n")


def run(
    config_path: Optional[str] = None,
    context_limit: int = 200_000,
    window_days: int = 30,
    timeout: float = 10.0,
) -> AuditReport:
    servers = load_servers(config_path)
    if not servers:
        sources = discover_configs(config_path)
        sys.stderr.write(
            f"mcpaudit: no MCP servers found. Tried {len(sources)} config file(s); "
            "pass --config <path> or place .mcp.json in this directory.\n"
        )
        sys.exit(2)

    usage = scan_usage(window_days=window_days)
    measurements = measure_servers(servers, timeout=timeout)

    return AuditReport(
        servers=measurements,
        usage=usage,
        context_limit=context_limit,
        generated_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        source_configs=[str(p) for p in discover_configs(config_path)],
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mcpaudit",
        description="Report card for your MCP context diet: measure per-server schema waste, "
        "find dead tools, export a slimmed mcp.json.",
    )
    parser.add_argument("--version", action="version", version=f"mcpaudit {__version__}")
    parser.add_argument(
        "--config",
        metavar="PATH",
        help="Explicit MCP config file to audit (default: auto-discover .mcp.json, "
        "~/.claude.json, ~/.cursor/mcp.json, ~/.config/opencode/opencode.json, "
        "opencode.json[c])",
    )
    parser.add_argument("--context", type=int, default=200_000, help="Context window in tokens (default 200000)")
    parser.add_argument("--window", type=int, default=30, help="Session-log usage window in days (default 30)")
    parser.add_argument("--timeout", type=float, default=10.0, help="Per-server MCP timeout in seconds (default 10)")
    parser.add_argument("--report", metavar="PATH", help="Write report.html to PATH (default: mcpaudit-report.html in current dir)")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary to stdout instead of opening HTML")
    parser.add_argument("--share", metavar="PATH", help="Write an anonymized mcpcensus fingerprint to PATH (e.g. ~/.mcpcensus/mcpaudit-census.json) instead of html/json")
    args = parser.parse_args(argv)

    report = run(
        config_path=args.config,
        context_limit=args.context,
        window_days=args.window,
        timeout=args.timeout,
    )

    result = {
        "grade": report.grade,
        "waste_percent": round(report.waste_percent, 1),
        "baseline_tokens": report.baseline_tokens,
        "context_footprint_percent": round(report.context_footprint_percent, 1),
        "dead_tools": report.dead_tools,
        "dead_schema_tokens": report.dead_schema_tokens,
        "servers": [
            {
                "server": s.server,
                "ok": s.ok,
                "tools": len(s.tools),
                "schema_tokens": s.schema_tokens,
                "baseline_tokens": s.baseline_tokens,
                "error": s.error,
            }
            for s in report.servers
        ],
        "slim_config": write_slim_config(report),
        "source_configs": report.source_configs,
    }

    if args.json:
        _print_json(result)
        return 0

    if args.share:
        try:
            from mcpaudit.share import emit_context_fingerprint
        except ImportError:  # pragma: no cover
            print("mcpaudit: --share needs mcpaudit.share; reinstall the package", file=sys.stderr)
            return 2
        path = emit_context_fingerprint(result, args.share)
        print(f"Wrote census fingerprint {path} · nothing sensitive leaves this file — only salted hashes")
        return 0

    try:
        from mcpaudit._webbrowser_open import open_html  # thin indirection for tests
    except ImportError:  # pragma: no cover
        import webbrowser

        def open_html(path):  # pragma: no cover
            webbrowser.open(f"file://{path}")

    html = render_html(report)
    path = args.report or "mcpaudit-report.html"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"Wrote {path} · grade {report.grade} · {report.dead_schema_tokens:,} dead-tool tokens "
          f"({report.waste_percent:.1f}% of schema baseline)")
    open_html(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())