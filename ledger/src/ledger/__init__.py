"""ledger - agent action forensics.

Session transcripts are a running tape of what a model was *asked* to do. ledger
normalizes that tape into a structured, replayable **trail** of actions, then
answers the three questions a postmortem needs:

  * what happened, in what order?     -> ``ledger record``  (transcript->trail)
  * what story do the facts tell?     -> ``ledger dossier`` (incident report)
  * did it stay inside the rules?     -> ``ledger gate``    (policy check)
  * what changed between attempts?    -> ``ledger diff``    (behavior change)
"""

__version__ = "0.1.0"

EVENT_KINDS = ("tool_use", "tool_result", "think", "text", "edit", "bash", "approval", "state")
# Rough chat-token heuristic: ~4 chars/token for code-ish content.
CHARS_PER_TOKEN = 4.0

DEFAULT_RATES = {
    "in_per_mtok": 3.0,     # $ per million input tokens
    "out_per_mtok": 15.0,   # $ per million output tokens
    "tool_per_call": 0.002,  # flat marginal for tool round-trips
}