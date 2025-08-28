"""agentspense - agent cost intelligence.

Every AI coding provider exports spend in its own dialect. agentspense
normalizes them into **one accountable ledger**:

  * parse provider exports (claude, cursor, codex, opencode, csv, generic)
  * fill missing costs from a rate card so every line is comparable
  * attribute spend to team/feature/project
  * render a monthly agent P&L
  * alert on spend spikes

The output is a folder-nd JSON ledger anyone can diff, search, or export.
"""

__version__ = "0.1.0"

PnlSchema = "agentspense/pnl/v1"
LedgerSchema = "agentspense/ledger/v1"

PROVIDERS = ("claude", "cursor", "codex", "opencode", "generic")

DEFAULT_BUDGET = {
    "team": 100.0,       # $/mo per team
    "feature": 50.0,     # $/mo per feature
    "session": 10.0,     # $/session alert threshold
}