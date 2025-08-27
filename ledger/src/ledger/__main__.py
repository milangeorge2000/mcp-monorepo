"""ledger.

Usage:
    ledger record     TRANSCRIPT.jsonl... [-o trail.jsonl] [--format claude-code|generic]
    ledger dossier    trail.jsonl [-o dossier.html] [--title "..."]
    ledger diff       trail-a.jsonl trail-b.jsonl [-o diff.txt]
    ledger gate       trail.jsonl --rules policy.json [--json]
"""

from ledger.cli import main

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())