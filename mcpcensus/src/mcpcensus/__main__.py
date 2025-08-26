"""mcpcensus.

Usage:
    mcpcensus serve --db registry.jsonl [--port 8787]
    mcpcensus ingest FINGERPRINT.json... [--db registry.jsonl]
    mcpcensus aggregate [--db registry.jsonl] [--min-cohort N] [--min-devices N] -o aggregates.json
    mcpcensus report aggregates.json -o report.html [--title "..."]
    mcpcensus suggest aggregates.json FINGERPRINT.json
    mcpcensus badge aggregates.json [--grade F] -o badge.svg
"""

from mcpcensus.cli import main

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())