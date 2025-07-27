"""Sandboxing for the benchmark: a throwaway, deterministic environment.

Each driver run against the fleet gets a fresh temp workdir and a scrubbed
environment, exactly like mcphazard. Benchmarking only touches the bundled
reference fleet server — never a real host — so the sandbox is belt-and-
braces: it also makes timing and token counts comparable across runs by
giving every spawn the same empty cwd and sanitized env.
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
    cwd: str = field(default_factory=lambda: tempfile.mkdtemp(prefix="mcpbench-"))
    _env: Dict[str, str] = field(default_factory=dict)

    def env(self, base: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """A sanitized env for spawning the fleet: PATH/TEMP survive, the
        benchmark's own markers are set, credential-ish vars are scrubbed."""
        clean: Dict[str, str] = {}
        for k, v in (base or dict(os.environ)).items():
            kl = k.lower()
            if any(tok in kl for tok in ("token", "secret", "password", "api_key", "apikey", "authorization")):
                continue
            clean[k] = v
        clean["MCPBENCH_SANDBOX"] = "1"
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


def make_sandbox() -> Sandbox:
    return Sandbox()