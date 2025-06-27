"""mcpbatt CLI: expand, run, list templates, share fingerprints."""
from __future__ import annotations

import argparse
import importlib.resources as resources
import json
import os
import sys
from typing import Any, Dict, List, Optional

from mcpbatt import __version__
from mcpbatt.expand import expand_template
from mcpbatt.models import BattReport, Template, grade_for
from mcpbatt.report import render_html, to_json
from mcpbatt.runner import run_battery
from mcpbatt.schema import load_template, validate_template


def _template_path() -> str:
    return str(resources.files("mcpbatt").joinpath("templates"))


def _load_named(name: str) -> Template:
    """Load a bundled template by name, or a template from an explicit path."""
    if os.path.exists(name):
        with open(name, encoding="utf-8") as fh:
            return load_template(json.load(fh))
    path = os.path.join(_template_path(), f"{name}.json")
    if not os.path.exists(path):
        raise ValueError(f"unknown template: {name} (use 'list')")
    with open(path, encoding="utf-8") as fh:
        return load_template(json.load(fh))


def list_templates() -> List[Dict[str, Any]]:
    tdir = _template_path()
    out: List[Dict[str, Any]] = []
    if not os.path.isdir(tdir):
        return out
    for fn in sorted(os.listdir(tdir)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(tdir, fn), encoding="utf-8") as fh:
            raw = json.load(fh)
        out.append({"name": raw.get("name", fn[:-5]), "description": raw.get("description", "")})
    return out


def cmd_list(_args) -> int:
    templates = list_templates()
    if not templates:
        print("mcpbatt: no bundled templates found")
        return 1
    print("mcpbatt: scenario templates (engine expands these into concrete batteries):")
    for t in templates:
        print(f"  {t['name']:<18} {t['description']}")
    print("mcpbatt: use --template <name> to expand or run a battery")
    return 0


def cmd_expand(args) -> int:
    try:
        template = _load_named(args.template)
        argv = _server_argv(args.server)
        tools = _list_server_tools(argv, args.timeout)
        battery = expand_template(template, tools)
    except ValueError as exc:
        print(f"mcpbatt: {exc}", file=sys.stderr)
        return 2

    out = {
        "format": "mcpbatt-battery/v1",
        "template": template.name,
        "select": template.select,
        "mode": template.mode,
        "tools_seen": len(tools),
        "calls": [
            {"seq": c.seq, "tool": c.tool, "expect": c.expect,
             "phase": c.phase, "arguments": c.arguments, "source": c.source}
            for c in battery
        ],
    }
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2)
        print(f"mcpbatt: expanded {template.name} -> {len(battery)} calls in {args.output}")
    else:
        json.dump(out, sys.stdout, indent=2)
        sys.stdout.write("\n")
    return 0


def cmd_run(args) -> int:
    try:
        template = _load_named(args.template)
    except ValueError as exc:
        print(f"mcpbatt: {exc}", file=sys.stderr)
        return 2

    argv = _server_argv(args.server)
    try:
        result = run_battery(template, server_argv=argv, timeout=args.timeout)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"mcpbatt: run failed: {exc}", file=sys.stderr)
        return 3

    report = BattReport(results=[result], template=template.name)

    glut = bool(args.json)

    def say(msg: str) -> None:
        (sys.stdout if not glut else sys.stderr).write(msg + "\n")

    if args.json:
        json.dump(to_json(report), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        say(f"mcpbatt: {template.name} | {result.server} | grade {result.grade}")
        for axis in ("fidelity", "discipline", "stability", "drift", "overall"):
            say(f"  {axis:<10} {result.scores.get(axis, 0):5.1f}")
        say(f"  calls {result.calls_total} | ok {result.ok_calls} | rejected {result.invalid_calls}"
            f" | drift-honored {result.drift_seen}")

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(render_html(report))
        say(f"mcpbatt: wrote {args.output}")

    if args.share:
        from mcpbatt.share import emit_batt_fingerprint
        path = emit_batt_fingerprint(report, args.share)
        say(f"mcpbatt: census fingerprint -> {path}")
    return 0


def _server_argv(server: Optional[str]) -> List[str]:
    if server:
        return server.split()
    return [sys.executable, "-m", "mcpbatt.fleet"]


def _list_server_tools(argv: List[str], timeout: float) -> List[Dict[str, Any]]:
    """Spawn the server briefly just to read its tools/list (used by expand)."""
    from mcpbatt.client import Client, Recorder
    from mcpbatt.sandbox import Sandbox
    sb = Sandbox()
    try:
        proc = sb.spawn(argv)
        rec = Recorder()
        client = Client(proc, rec, timeout=timeout)
        client.initialize()
        return client.list_tools()
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        sb.cleanup()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mcpbatt",
        description="A benchmark that writes its own benchmark. Author scenario "
                    "templates; the engine expands them into concrete batteries "
                    "tailored to a live server's schemas and grades the server.",
    )
    parser.add_argument("--version", action="version", version=f"mcpbatt {__version__}")
    sub = parser.add_subparsers(dest="command")

    p_run = sub.add_parser("run", help="expand + execute a battery against a server")
    p_run.add_argument("--template", required=True)
    p_run.add_argument("--server", default=None, help="stdio command (default: bundled reference fleet)")
    p_run.add_argument("--timeout", type=float, default=8.0)
    p_run.add_argument("-o", "--output", default=None, help="write an HTML report")
    p_run.add_argument("--json", action="store_true")
    p_run.add_argument("--share", default=None, metavar="PATH")

    p_exp = sub.add_parser("expand", help="print the generated battery without running it")
    p_exp.add_argument("--template", required=True)
    p_exp.add_argument("--server", default=None, help="stdio command (default: bundled reference fleet)")
    p_exp.add_argument("--timeout", type=float, default=8.0)
    p_exp.add_argument("-o", "--output", default=None)

    sub.add_parser("list", help="list bundled scenario templates")

    args = parser.parse_args(argv)
    if args.command == "run":
        return cmd_run(args)
    if args.command == "expand":
        return cmd_expand(args)
    if args.command == "list":
        return cmd_list(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())