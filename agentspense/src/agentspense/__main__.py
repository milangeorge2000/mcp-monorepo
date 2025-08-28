"""agentspense.

Usage:
    agentspense normalize FILE... -l ledger.json [--rates RATES.json]
    agentspense ledger [ledger.json] [--month YYYY-MM] -o agent-pnl.html [--budget BUDGET.json]
    agentspense alerts [ledger.json] [--json]
    agentspense rates [--json]
    agentspense inspect FILE...
"""

from agentspense.cli import main

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())