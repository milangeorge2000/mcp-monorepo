"""agentspense command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, List, Optional, Sequence

from agentspense import __version__, PROVIDERS
from agentspense.anomaly import detect, session_spikes
from agentspense.models import AgentLedger, read_ledger, write_ledger
from agentspense.normalize import normalize_files, rate_card_report
from agentspense.providers import read_export
from agentspense.rates import load_rates
from agentspense.report import console_summary, month_totals, write_month


def cmd_normalize(args) -> int:
    rates = load_rates(args.rates)
    ledger = normalize_files(args.files, rates)
    write_ledger(ledger, args.ledger)
    skipped = sum(1 for l in ledger.lines if not l.listed_cost and not l.rated_cost)
    print(f"agentspense: {len(ledger.lines)} lines normalized -> {args.ledger}")
    if skipped:
        print(f"agentspense: {skipped} lines had no price and no rate-card match "
              "(model unknown); fix --rates", file=sys.stderr)
    return 0


def cmd_ledger(args) -> int:
    ledger = read_ledger(args.ledger)
    anomalies = detect(ledger, k=args.z, window=args.window)
    spikes = session_spikes(ledger, args.session_threshold)
    month = month_totals(ledger, args.month or "")
    print(f"agentspense: {args.ledger} · {args.month or 'all time'}")
    print(console_summary(month))
    if anomalies:
        print("\n  anomalies (z > {:.0f}):".format(args.z))
        for a in anomalies:
            print(f"    {a['day']} {a['team']:<18} ${a['cost']:>8.2f}  z={a['z']:.1f}")
    if spikes:
        print("\n  session overruns:")
        for s in spikes:
            print(f"    {s['session'][:46]:<48} ${s['cost']:>7.2f}")
    write_month(ledger, args.output, args.month or "", args.title or "Agent P&L",
                budgets=_load_budget(args.budget), anomalies=anomalies, session_spikes=spikes)
    print(f"agentspense: wrote {args.output}")
    return 0


def _load_budget(path: str):
    if not path:
        return None
    import os
    if not os.path.exists(path):
        print(f"agentspense: budget file not found: {path}", file=sys.stderr)
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        print(f"agentspense: budget file invalid JSON: {exc}", file=sys.stderr)
        return None


def cmd_rates(args) -> int:
    payload = rate_card_report(load_rates(args.rates))
    if args.json:
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        for prov, models in payload.items():
            print(prov)
            for m, r in models.items():
                print(f"  {m:<26} in ${r['in']:.2f}/M  out ${r['out']:.2f}/M")
    return 0


def cmd_inspect(args) -> int:
    for p in args.files:
        for rr in read_export(p):
            print(f"{rr.provider:<9} {rr.model:<28} ${rr.cost:>8.2f}  "
                  f"{rr.tokens_in:>8,}->{rr.tokens_out:<8,}  tags={','.join(rr.tags) or '-'}")
    return 0


def cmd_alerts(args) -> int:
    ledger = read_ledger(args.ledger)
    anomalies = detect(ledger, k=args.z, window=args.window)
    spikes = session_spikes(ledger, args.session_threshold)
    payload = {"ok": not anomalies and not spikes, "anomalies": anomalies, "session_spikes": spikes}
    if args.json:
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0 if payload["ok"] else 1
    for a in anomalies:
        print(f"ALERT {a['day']} {a['team']:<18} ${a['cost']:>8.2f} z={a['z']:.1f}")
    for s in spikes:
        print(f"ALERT session {s['session'][:40]:<42} ${s['cost']:>7.2f}")
    print("agentspense: clean" if payload["ok"] else f"agentspense: {len(anomalies) + len(spikes)} alert(s)")
    return 0 if payload["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agentspense",
                                description="Agent cost intelligence: one ledger, many providers.")
    p.add_argument("--version", action="version", version=f"agentspense {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    norm = sub.add_parser("normalize", help="fold provider spend exports into a ledger")
    norm.add_argument("files", nargs="+", help="provider export files (json/jsonl/csv/tsv)")
    norm.add_argument("-l", "--ledger", default="agent-ledger.json")
    norm.add_argument("--rates", metavar="RATES.json", help="rate-card overrides")
    norm.set_defaults(func=cmd_normalize)

    led = sub.add_parser("ledger", help="render the agent P&L month report")
    led.add_argument("ledger", nargs="?", default="agent-ledger.json")
    led.add_argument("-o", "--output", default="agent-pnl.html")
    led.add_argument("--month", default="", help="YYYY-MM, default all")
    led.add_argument("--title", default="Agent P&L")
    led.add_argument("-z", type=float, default=4.0, help="z-score spike threshold")
    led.add_argument("-w", "--window", type=int, default=7)
    led.add_argument("--session-threshold", type=float, default=10.0)
    led.add_argument("--budget", metavar="BUDGET.json")
    led.set_defaults(func=cmd_ledger)

    rates_p = sub.add_parser("rates", help="show the bundled rate card")
    rates_p.add_argument("--rates", metavar="RATES.json")
    rates_p.add_argument("--json", action="store_true")
    rates_p.set_defaults(func=cmd_rates)

    insp = sub.add_parser("inspect", help="peek at raw provider rows")
    insp.add_argument("files", nargs="+")
    insp.set_defaults(func=cmd_inspect)

    al = sub.add_parser("alerts", help="check for spend anomalies; nonzero exit on findings")
    al.add_argument("ledger", nargs="?", default="agent-ledger.json")
    al.add_argument("-z", type=float, default=4.0)
    al.add_argument("-w", "--window", type=int, default=7)
    al.add_argument("--session-threshold", type=float, default=10.0)
    al.add_argument("--json", action="store_true")
    al.set_defaults(func=cmd_alerts)

    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())