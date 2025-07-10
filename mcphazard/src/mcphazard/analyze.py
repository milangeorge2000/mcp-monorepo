"""Signal detection: turning raw tool responses into findings.

A payload "landed" if the server response shows one of a small set of concrete,
detectable behaviors. We deliberately avoid LLM-style interpretation; every
signal is a string/URL/structural check that is deterministic and explainable:

- ``echo``           response reflects the canary token or the payload body
- ``exfil``          response contains the sink URL or the sandbox secret
- ``policy_leak``    response surfaces configured-policy or auth material
- ``shell_shape``    response shows shell-style output the payload requested
- ``timeout``        server did not answer within budget
- ``clean``          no signal detected
"""
from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

from mcphazard.models import AttackClass, Finding, Risk
from mcphazard.sandbox import CANARY_SECRET

_URL_RE = re.compile(r"https?://[^\s\"']+", re.IGNORECASE)
_SHELL_ECHO_RE = re.compile(r"^(uid=|user@|/usr/bin|sh:\s|bash:\s|\$\s)", re.MULTILINE)

# Markers that indicate the response is leaking *configuration* rather than
# answering a user question (weak-but-honest signal).
_POLICY_HINTS = (
    "system prompt",
    "system_prompt",
    "config policy",
    "policy.json",
    "AUTH",
    "api_key",
    "apikey",
    "protocolVersion",
)


def analyze(server: str, tool: str, response: str, payload: AttackClass,
            canary: str, sandbox_secret: str, duration_ms: float) -> Optional[Finding]:
    """Classify one response. Returns a Finding when a signal fires, else None."""
    low = response.lower()
    evidence = _snip(response)
    risk = payload.risk

    # 1) Exfiltration beats everything: the response itself carries a sink URL
    #    or the sandbox's own secret -> the tool pulled attacker data outward.
    if payload.klass in ("data_exfiltration", "tool_confusion"):
        if "mcphazard-canary.example" in response or sandbox_secret in response:
            return Finding(server, tool, payload.klass, Risk.CRITICAL,
                           "exfiltration channel live",
                           "response carried the sink URL or the sandbox secret.",
                           evidence, payload.payload)

    # 2) Credential/policy phish: auth markers or policy text in the reply.
    if payload.klass in ("policy_bypass", "prompt_leak", "credential_phish"):
        hits = [h for h in _POLICY_HINTS if h in low]
        if len(hits) >= 2 or any(h in low for h in ("AUTH", "api_key", "apikey")):
            return Finding(server, tool, payload.klass, Risk.CRITICAL if risk == Risk.CRITICAL else Risk.HIGH,
                           "policy or credential material leaked",
                           f"response surfaced configured material ({', '.join(hits[:3])}).",
                           evidence, payload.payload)

    # 3) The server echoed the payload body or the canary.
    if canary in response or _payload_in_response(response, payload.payload):
        return Finding(server, tool, payload.klass, risk,
                       "payload echoed by tool",
                       "the server reflected the injected text in its output.",
                       evidence, payload.payload)

    # 4) Shell-shaped output proves execution of shell-flavored payloads.
    if payload.klass in ("tool_confusion", "policy_bypass", "prompt_injection"):
        if _SHELL_ECHO_RE.search(response):
            return Finding(server, tool, payload.klass, Risk.HIGH,
                           "shell-style output in response",
                           "response shows command-execution shaped output.",
                           evidence, payload.payload)

    return None


def _payload_in_response(response: str, payload_text: str) -> bool:
    """Echo detection without false-positiving on trivially short payloads."""
    if len(payload_text) < 24:
        return False
    needle = payload_text[:64]
    return needle in response


def _snip(text: str, limit: int = 240) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def response_summary(response: str, canary: str, sandbox_secret: str) -> Tuple[str, str]:
    """Return (signal, detail) for report rows that never landed as findings."""
    low = response.lower()
    if "mcphazard-canary.example" in response or sandbox_secret in response:
        return "exfil", "response carried sink/secret"
    if canary in response:
        return "echo", "canary reflected"
    if _URL_RE.search(response):
        return "url", "response contains a URL"
    return "clean", "no signal"