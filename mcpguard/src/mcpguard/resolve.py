"""Classify how an MCP server is launched and derive static risk signals."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from mcpguard.models import ServerConfiguration

_PKG_SPEC_RE = re.compile(r"^[@A-Za-z0-9._\-/]+@([0-9][0-9A-Za-z._\-]*|[vV][0-9].*)$")
_PIP_SPEC_RE = re.compile(r"^[@A-Za-z0-9._\-/]+==[0-9][0-9A-Za-z._\-]*$")
_SHA_REF_RE = re.compile(r"@sha256:")
_REGISTRY_FROM_RE = re.compile(r"(?i)(--registry|--registry-uri|--index-url|i)\s*[:=]?\s*(\S+)")


@dataclass
class Invocation:
    mode: str = "binary"                     # npx|pipx|uvx|docker|python|shell-pipe|http|binary|other
    remote_code: bool = False
    auto_install: bool = False
    pinned: bool = False
    target: Optional[str] = None             # package arg / image / url
    flags: List[str] = field(default_factory=list)


def _base(exe: str) -> str:
    return exe.replace("\\", "/").rsplit("/", 1)[-1].lower()


def _looks_like_registry_url(token: str) -> bool:
    return token.lower().startswith(("http://", "https://")) and any(
        frag in token.lower() for frag in ("registry", "mirror", "proxy", "artifactory", "nexus")
    )


def _first_pkg_token(tokens: List[str]) -> Optional[str]:
    for t in tokens:
        if t.startswith("-"):
            continue
        if t in ("run",):  # pipx run / uvx run subcommand
            continue
        return t
    return None


def classify(config: ServerConfiguration) -> Invocation:
    if config.url:
        return Invocation(mode="http", remote_code=True, pinned=False, target=config.url,
                          flags=["network transport; server code is remote and out of your custody"])
    argv = config.command
    if not argv:
        return Invocation(mode="other", remote_code=False)

    base = _base(argv[0])
    tokens = [t for t in argv[1:]]

    if base in ("npx", "npx.cmd", "npx.exe"):
        auto = any(t in ("-y", "--yes", "--force") or t.startswith("--yes") for t in tokens)
        pinned = any(_PKG_SPEC_RE.match(t) for t in tokens)
        target = _first_pkg_token(tokens)
        flags = []
        if auto:
            flags.append("auto-installs requested package from registry")
        if not pinned:
            flags.append("target version not pinned (registry latest may change shape)")
        reg = _find_registry(tokens)
        if reg is not None:
            flags.append(f"custom registry override: {reg}")
        return Invocation("npx", remote_code=True, auto_install=auto, pinned=pinned,
                          target=target, flags=flags)

    if base in ("pipx", "pipx.exe"):
        sub = tokens[0] if tokens else ""
        auto = sub == "run"
        pinned = any(_PIP_SPEC_RE.match(t) or _PKG_SPEC_RE.match(t) for t in tokens)
        target = _first_pkg_token(tokens[1:] if sub == "run" else tokens)
        flags = []
        if auto:
            flags.append("pipx run fetches package from PyPI at execution time")
        if not pinned:
            flags.append("package version not pinned")
        return Invocation("pipx", remote_code=True, auto_install=auto, pinned=pinned,
                          target=target, flags=flags)

    if base in ("uvx", "uvx.exe"):
        pinned = any(_PIP_SPEC_RE.match(t) or _PKG_SPEC_RE.match(t) for t in tokens)
        target = _first_pkg_token(tokens)
        return Invocation("uvx", remote_code=True, auto_install=True, pinned=pinned,
                          target=target, flags=["uvx fetches package from registry"])

    if base in ("docker", "docker.exe"):
        if tokens and tokens[0] == "run":
            idx = tokens.index("run")
            rest = tokens[idx + 1:]
            image = next((t for t in rest if not t.startswith("-")), None)
            pinned = bool(image and _SHA_REF_RE.search(image))
            flags = []
            if not pinned:
                flags.append("image tag not pinned to a content hash")
            return Invocation("docker", remote_code=True, auto_install=False,
                              pinned=pinned, target=image, flags=flags)
        return Invocation("docker", remote_code=False, pinned=False, target=None,
                          flags=["docker invocations other than 'docker run' are not launch points"])

    if base in ("python", "python3", "py", "python.exe", "node", "node.exe", "deno", "bun", "ruby"):
        lang = "python" if base.startswith(("python", "py")) else base
        return Invocation(lang, remote_code=False, pinned=True, target=_first_pkg_token(tokens),
                          flags=["executes a local interpreter; supply chain risk is upstream of this command"])

    if base in ("curl", "wget", "iwr", "curl.exe", "wget.exe"):
        joined = " ".join(tokens).lower()
        if "|" in joined and any(b in joined for b in ("bash", "sh", "python", "powershell", "pwsh")):
            return Invocation("shell-pipe", remote_code=True, auto_install=True, pinned=False,
                              target=None, flags=["downloads and executes remote script via pipe"])
        return Invocation("binary", remote_code=False, pinned=True, flags=["curl/wget without pipe"])

    if base in ("bash", "sh", "zsh", "cmd", "cmd.exe", "powershell", "pwsh"):
        joined = " ".join(tokens)
        if "http" in joined.lower() and any(c in joined for c in ("|", "curl", "wget")):
            return Invocation("shell-pipe", remote_code=True, pinned=False,
                              flags=["shell command that fetches remote content"])
        return Invocation("other", remote_code=False, pinned=True, flags=["raw shell launch"])

    return Invocation("binary", remote_code=False, pinned=True, flags=["plain binary/local command"])


def _find_registry(tokens: List[str]) -> Optional[str]:
    for t in tokens:
        idx = t.find("=")
        if idx > 0:
            key, val = t[:idx], t[idx + 1:]
            if key.lower() in ("--registry", "--registry-uri", "--index-url") or key == "-i":
                return val
        if _looks_like_registry_url(t):
            return t
    for i, t in enumerate(tokens):
        if t.lower() == "--registry" and i + 1 < len(tokens):
            return tokens[i + 1]
    return None