"""Sandboxing for the battery runner: a throwaway, deterministic environment.

Each battery run gets a fresh temp workdir and a scrubbed environment, exactly
like the sibling tools. The battery only ever talks to the stdio server command
the user names (default: the bundled reference fleet) over its own stdin/stdout;
the sandbox keeps timing and state comparable across runs.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Sandbox:
    cwd: str = field(default_factory=lambda: tempfile.mkdtemp(prefix="mcpbatt-"))
    _env: Dict[str, str] = field(default_factory=dict)

    def env(self, base: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        clean: Dict[str, str] = {}
        for k, v in (base or dict(os.environ)).items():
            kl = k.lower()
            if any(tok in kl for tok in ("token", "secret", "password", "api_key", "apikey", "authorization")):
                continue
            clean[k] = v
        clean["MCPBATT_SANDBOX"] = "1"
        return clean

    def spawn(self, argv: List[str], env: Optional[Dict[str, str]] = None) -> subprocess.Popen:
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