"""Threat intel bundle: seed data + matchers, designed to be crowd-updated.

The durable moat of mcpguard is this database. A CLI can be rewritten by anyone;
a curated, versioned list of real-world package reports and exfil sinks cannot.
Entries marked "example" in the seed are structural illustrations for the demo;
production data ships as `intel.json` decoupled from code, updated via
`mcpguard intel update`.

All matches are heuristics — a hit is a *review trigger*, never a conviction.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

_SEG_RE = re.compile(r"[a-z0-9]+")


def _segs(text: str) -> List[str]:
    return _SEG_RE.findall(text.lower())


def _is_subsequence(needle: List[str], haystack: List[str]) -> bool:
    pos = 0
    for seg in haystack:
        if pos < len(needle) and seg == needle[pos]:
            pos += 1
    return pos == len(needle)

CANONICAL_PACKAGES = [
    "@modelcontextprotocol/server-github",
    "@modelcontextprotocol/server-filesystem",
    "@modelcontextprotocol/server-puppeteer",
    "@modelcontextprotocol/server-slack",
    "@modelcontextprotocol/server-everything",
    "@vercel/mcp-postgres",
    "@anthropic-ai/mcp-server-fetch",
    "mcp-server-atlassian",
]

TOOL_CATEGORIES: Dict[str, List[str]] = {
    "critical": [
        "run_command", "exec", "shell", "terminal", "open_terminal", "bash",
        "command", "execute_code", "eval", "system", "sudo", "shell_exec",
        "run_shell", "kill_process", "process", "kill",
    ],
    "high": [
        "write_file", "create_file", "overwrite", "db_write", "sql_execute",
        "insert", "update_row", "delete", "drop_table", "drop", "migrate",
        "rm", "remove_file", "delete_file", "privesc", "sudo_write", "append",
        "set_env", "export", "patch",
    ],
    "medium": [
        "read_file", "read_directory", "list_directory", "get_file", "fetch",
        "http", "download", "upload", "send_message", "post", "request",
        "read_all", "dump", "read_db", "query",
    ],
}

ENV_DANGEROUS = [
    "AWS_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
    "GITHUB_TOKEN", "GH_TOKEN", "GITLAB_TOKEN",
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "AZURE_OPENAI_KEY", "GOOGLE_API_KEY",
    "GEMINI_API_KEY", "HUGGINGFACE_TOKEN", "REPLICATE_API_TOKEN",
    "SLACK_TOKEN", "DISCORD_TOKEN", "TELEGRAM_BOT_TOKEN", "MESSAGEBIRD_API_KEY",
    "DATABASE_URL", "POSTGRES", "MYSQL", "REDIS_URL", "MONGODB",
    "STRIPE", "SUPA BASE", "SUPABASE", "SECRET_KEY", "PRIVATE_KEY",
    "CLIENT_SECRET", "PASSWORD", "PASSWD", "API_KEY", "TOKEN", "CREDENTIALS",
]

EXFIL_DOMAINS = [
    "ngrok.io", "ngrok-free.app", "ngrok.app", "webhook.site", "pipedream.net",
    "requestbin.net", "beeceptor.com", "interact.sh", "oast.fun", "canarytokens.org",
    "pastebin.com", "paste.ee", "dpaste.org", "transfer.sh", "tunnel",
    "exfil", "telemetry-gate", "collector.example",
]

SEED_INTEL = {
    "_note": "Seed bundle, structural/examples only. Replace via `mcpguard intel update`.",
    "version": "2026.08.15",
    "updated_at": "2026-08-15",
}


@dataclass
class IntelBundle:
    canonical_packages: List[str] = field(default_factory=lambda: list(CANONICAL_PACKAGES))
    tool_categories: Dict[str, List[str]] = field(default_factory=lambda: {k: list(v) for k, v in TOOL_CATEGORIES.items()})
    env_dangerous: List[str] = field(default_factory=lambda: list(ENV_DANGEROUS))
    exfil_domains: List[str] = field(default_factory=lambda: list(EXFIL_DOMAINS))
    package_warnings: Dict[str, str] = field(default_factory=dict)  # name_substring -> note
    version: str = SEED_INTEL["version"]
    updated_at: str = SEED_INTEL["updated_at"]

    @staticmethod
    def load(path: Optional[str] = None) -> "IntelBundle":
        if not path:
            env = os.environ.get("MCPGUARD_INTEL")
            if env:
                path = env
        if path:
            p = Path(path).expanduser()
            if p.exists():
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    return IntelBundle(**{k: data[k] for k in (
                        "canonical_packages", "tool_categories", "env_dangerous",
                        "exfil_domains", "package_warnings", "version", "updated_at",
                    ) if k in data})
                except (ValueError, TypeError):
                    pass
        return IntelBundle()

    # -- matchers -----------------------------------------------------------
    def classify_name(self, name: str) -> Optional[str]:
        """Tool-name matching: keyword token-set must be a subset of the name's
        tokens. Handles snake_case (`run_command`) without matching substrings
        of unrelated words (`filesystem` ≠ `system`)."""
        ns = set(_segs(name))
        if not ns:
            return None
        for risk in ("critical", "high", "medium"):
            for kw in self.tool_categories[risk]:
                ks = _segs(kw)
                if ks and all(k in ns for k in ks):
                    return risk
        return None

    def classify_description(self, desc: str) -> Optional[str]:
        """Description matching: only multi-token keywords, as an in-order
        subsequence, to avoid single generic words (`system`, `process`,
        `command`) tripping on ordinary prose."""
        ds = _segs(desc)
        if not ds:
            return None
        for risk in ("critical", "high", "medium"):
            for kw in self.tool_categories[risk]:
                ks = _segs(kw)
                if len(ks) >= 2 and _is_subsequence(ks, ds):
                    return risk
        return None

    def classify_tool(self, name: str) -> Optional[str]:
        """Back-compat: name + description combined (best-effort superset)."""
        return self.classify_name(name) or self.classify_description(name)

    def match_env(self, key: str) -> bool:
        up = key.upper()
        for pat in self.env_dangerous:
            if pat in up:  # case-insensitive substring
                return True
        return False

    def match_exfil_domain(self, text: str) -> Optional[str]:
        low = text.lower()
        for dom in self.exfil_domains:
            if dom in low:
                return dom
        return None

    def match_package_warning(self, target: Optional[str]) -> Optional[str]:
        if not target:
            return None
        low = target.lower()
        for key, note in self.package_warnings.items():
            if key.lower() in low:
                return note
        return None

    def typo_squat(self, target: Optional[str]) -> Optional[str]:
        """Return closest canonical package if `target` is within edit distance 2
        of a well-known one (high-signal homoglyph/typosquat heuristic)."""
        if not target:
            return None
        low = target.lower()
        best_d, best = 9, None
        for canon in self.canonical_packages:
            d = _edit_distance(low, canon.lower())
            if d < best_d:
                best_d, best = d, canon
        if best_d <= 2 and best_d > 0:
            return best
        return None


def _edit_distance(a: str, b: str) -> int:
    if len(a) > len(b):
        a, b = b, a
    prev = list(range(len(a) + 1))
    for j, cb in enumerate(b, 1):
        cur = [j]
        for i, ca in enumerate(a, 1):
            cur.append(min(prev[i] + 1, cur[i - 1] + 1, prev[i - 1] + (ca != cb)))
        prev = cur
    return prev[-1]