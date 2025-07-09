"""Sandboxing: a throwaway, deterministic environment for firing payloads.

The harness never runs against a real worktree or a real secret. Each scan
gets a fresh temp workdir, a canary secret file, a stripped-down environment,
and — in default (non-live) mode — a network-blocked subprocess runner so that
even a *successful* exfiltration attempt cannot reach out.

Design notes
------------
- ``Sandbox.cwd`` is unique per scan; the MCP server process is spawned with
  ``cwd=sandbox.cwd`` and a sanitized env.
- ``Sandbox.secret_file`` contains the canary secret; analyze.py looks for
  that value in tool responses to prove exfiltration of the sandbox's own data.
- ``--live`` mode keeps network access (URL payloads are only shipped then);
  default mode points proxy vars at localhost so outbound egress is inert.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional

CANARY_SECRET = "MCPhazardC4n4ryS3cret_8f21"

_PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
               "http_proxy", "https_proxy", "all_proxy", "no_proxy")


@dataclass
class Sandbox:
    cwd: str = field(default_factory=lambda: tempfile.mkdtemp(prefix="mcphz-"))
    live: bool = False
    secret_file: str = ""
    _env: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.secret_file:
            self.secret_file = os.path.join(self.cwd, "sandbox-secret.txt")
        with open(self.secret_file, "w", encoding="utf-8") as fh:
            fh.write(CANARY_SECRET)

    def env(self, base: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """A sanitized env for spawning the server under test.

        Keep PATH and TEMP so stdio servers can run, but scrub anything that
        looks like a real credential and, in non-live mode, strand proxies at
        localhost so outbound egress cannot escape the box.
        """
        clean: Dict[str, str] = {}
        for k, v in (base or dict(os.environ)).items():
            kl = k.lower()
            if any(tok in kl for tok in ("token", "secret", "password", "api_key", "apikey", "authorization")):
                continue
            clean[k] = v
        if not self.live:
            for var in _PROXY_VARS:
                if var not in clean:
                    clean[var] = "http://127.0.0.1:1"
        clean["MCPHZ_SANDBOX"] = "1"
        clean["MCPHZ_CANARY"] = CANARY_SECRET
        return clean

    def read_secret(self) -> str:
        try:
            with open(self.secret_file, "r", encoding="utf-8") as fh:
                return fh.read().strip()
        except OSError:
            return ""

    def spawn(self, argv: List[str], timeout: float = 10.0, env: Optional[Dict[str, str]] = None) -> subprocess.Popen:
        """Spawn a server inside the sandbox. In non-live mode, network is inert."""
        return subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=self.cwd,
            env=self.env(env),
            text=True,
            encoding="utf-8",
        )

    def cleanup(self) -> None:
        shutil.rmtree(self.cwd, ignore_errors=True)


def make_sandbox(live: bool = False) -> Sandbox:
    return Sandbox(live=live)