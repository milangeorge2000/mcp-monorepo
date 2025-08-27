"""ledger command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, List, Optional, Sequence

from ledger import __version__
from ledger.dossier import diff_trails, format_diff, write_diff, write_dossier
from ledger.models import read_trail, write_trail
from ledger.policy import gate, load_policy
from ledger.transcript import record_transcripts


def cmd_record(args) -> int:
    trail = record_transcripts(args.transcripts, fmt=args.format)
    write_trail(trail, args.out)
    s = trail.summary()
    print(f"ledger: recorded {s['events']} events ({s['tool_calls']} tool calls, "
          f"{s['files_touched']} files) -> {args.out}")
    return 0


def cmd_dossier(args) -> int:
    trail = read_trail(args.trail)
    violations = None
    gate_note = ""
    if args.rules:
        try:
            result = gate(trail, load_policy(args.rules))
            violations = result.violations
            gate_note = _gate_note(result)
        except (FileNotFoundError, ValueError) as exc:
            print(f"ledger: {exc}", file=sys.stderr)
            return 2
    write_dossier(trail, args.output, args.title or "Incident dossier", violations, gate_note)
    print(f"ledger: wrote {args.output}")
    return 0


def _gate_note(result) -> str:
    if not result.violations:
        return f'<p class="ok">policy gate passed — {result.scanned_events} tool calls scanned</p>'
    rows = "".join(
        f'<tr><td>{v.rule}</td><td>{v.reason}</td><td>{v.seq or "—"}</td></tr>'
        for v in result.violations
    )
    return f'<p class="warn">{len(result.violations)} violation(s)</p><table><tr><th>rule</th><th>reason</th><th>seq</th></tr>{rows}</table>'


def cmd_diff(args) -> int:
    a = read_trail(args.a)
    b = read_trail(args.b)
    write_diff(args.a, args.b, args.output)
    sys.stdout.write(format_diff(diff_trails(a, b)))
    return 0


def cmd_gate(args) -> int:
    try:
        policy = load_policy(args.rules)
        result = gate(read_trail(args.trail), policy)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ledger: {exc}", file=sys.stderr)
        return 2
    if args.json:
        json.dump(result.to_dict(), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        for v in result.violations:
            print(f"  [{'deny' if v.rule == 'deny' else v.rule}] (seq {v.seq}) {v.reason}")
        print(f"ledger: {'PASS' if result.ok else 'FAIL'} — {len(result.violations)} violation(s), "
              f"{result.scanned_events} tool calls scanned")
    return 0 if result.ok else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ledger",
                                description="Agent action forensics: transcript -> auditable trail.")
    p.add_argument("--version", action="version", version=f"ledger {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    rec = sub.add_parser("record", help="normalize transcripts into a trail")
    rec.add_argument("transcripts", nargs="+", help="transcript JSONL file(s)")
    rec.add_argument("--format", choices=("auto", "claude-code", "generic"), default="auto")
    rec.add_argument("-o", "--out", default="trail.json")
    rec.set_defaults(func=cmd_record)

    dos = sub.add_parser("dossier", help="render an incident dossier HTML from a trail")
    dos.add_argument("trail")
    dos.add_argument("-o", "--output", default="dossier.html")
    dos.add_argument("--title")
    dos.add_argument("--rules", metavar="POLICY.json", help="attach policy gate results")
    dos.set_defaults(func=cmd_dossier)

    df = sub.add_parser("diff", help="compare two trails and print a behavior diff")
    df.add_argument("a")
    df.add_argument("b")
    df.add_argument("-o", "--output", default="behavior-diff.txt")
    df.set_defaults(func=cmd_diff)

    gt = sub.add_parser("gate", help="check a trail against a policy file")
    gt.add_argument("trail")
    gt.add_argument("--rules", required=True, metavar="POLICY.json")
    gt.add_argument("--json", action="store_true")
    gt.set_defaults(func=cmd_gate)

    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())