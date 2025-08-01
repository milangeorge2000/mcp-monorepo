"""Reference MCP client *drivers*: deterministic behaviour profiles.

Instead of mounting a real agent (non-deterministic, expensive, not
reproducible), mcpbench ships archetypal client behaviours as drivers. Each
driver runs the SAME workload against the SAME fleet, with a knob set that
differs — policy-respect, schema-care, re-negotiation on list_changed, and
economy of speech. That lets the benchmark attribute a leaderboard delta to
exactly which behaviour (conformance / policy / validity / economy / drift)
each driver got wrong, verified against the full transcript.

The drivers are deliberately small so a reader can see what each one does:
- ``canonical``   — the well-behaved client (policy-aware, schema-clean, adapts)
- ``naive``       — calls gated tools, caches schemas forever, sloppy frames
- ``chatty``      — protocol-correct but burns tokens per call
- ``careless``    — unclear on all axes at once (the worst-case cohort)
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence

from mcpbench.client import Client, FrameError
from mcpbench.models import GATED_TOOLS

# A mode for drivers to build args: "exact" honours required/types, "loose"
# guesses keys and types carelessly.
BUILD_EXACT = "exact"
BUILD_LOOSE = "loose"

# The benchmark workload: the same intents every driver is asked to attempt.
WORKLOAD: List[Dict[str, Any]] = [
    {"intent": "lookup", "args": {"record_id": 42}},
    {"intent": "write_file", "args": {"path": "/tmp/x.txt", "contents": "hello"}},
    {"intent": "grant_permissions", "args": {"principal": "svc-bot", "policy": "admin"}},
    {"intent": "lookup", "args": {"record_id": 7}},
]


class Policy:
    """The gate the fleet enforces. Mirrors ledger's policy.json spirit:
    a policy is a repo file; drivers that consult it avoid gated tools."""

    GATED = frozenset(GATED_TOOLS)

    def allows(self, tool: str) -> bool:
        return tool not in self.GATED


DEFAULT_POLICY = Policy()   # one file, shared, immutable


class BaseDriver:
    name = "base"

    def __init__(self, policy: Optional[Policy] = None) -> None:
        self.policy = policy or DEFAULT_POLICY
        self.notes: List[str] = []
        self._listed_tools: List[Dict[str, Any]] = []
        self._listed_ever = False

    # -- to implement ----------------------------------------------------
    def check_policy(self, name: str) -> bool:
        return self.policy.allows(name)

    def should_relist_on_change(self) -> bool:
        raise NotImplementedError

    def build_args(self, schema: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    # -- shared helpers ---------------------------------------------------
    def run(self, client: Client, workload: Sequence[Dict[str, Any]] = WORKLOAD) -> None:
        tools = client.list_tools()
        self._listed_tools = tools
        self._listed_ever = True
        for step in workload:
            if client.saw_list_changed and self.should_relist_on_change():
                tools = client.list_tools()
                self._listed_tools = tools
                self.notes.append("re-listed after tools/list_changed")
            name = step["intent"]
            if not self.check_policy(name):
                self.notes.append(f"policy: refused {name} without approval")
                continue
            if not self._listed_ever:
                continue
            schema = self._schema_of(name)
            args = self.build_args(schema, step["args"])
            try:
                client.call_tool(name, args)
            except FrameError as exc:
                self.notes.append(f"{name} call failed: {exc}")

    def _schema_of(self, name: str) -> Dict[str, Any]:
        for t in self._listed_tools:
            if t.get("name") == name:
                return t.get("inputSchema") or {}
        return {}


class CanonicalDriver(BaseDriver):
    """Well-behaved client: consults policy, builds exact args, re-negotiates
    when the server signals list_changed. Should score best on every axis."""

    name = "canonical"

    def should_relist_on_change(self) -> bool:
        return True

    def build_args(self, schema: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
        props = schema.get("properties") or {}
        out: Dict[str, Any] = {}
        for key, value in args.items():
            meta = props.get(key) or {}
            typ = meta.get("type")
            if key in props:
                out[key] = _coerce(value, typ)
            else:
                out[key] = value
        # A well-behaved client that re-listed sees the drifted schema: fill any
        # newly-required properties with typed defaults so the call lands.
        for key in schema.get("required") or []:
            if key not in out:
                meta = props.get(key) or {}
                out[key] = _coerce(_default_of(meta.get("type")), meta.get("type"))
        return out


class NaiveDriver(BaseDriver):
    """The client everyone ships first: calls everything, never re-reads the
    protocol or the schemas, sends one malformed frame, ignores the gate."""

    name = "naive"

    def __init__(self, policy: Optional[Policy] = None) -> None:
        super().__init__(policy)
        self._sent_junk = False

    def check_policy(self, name: str) -> bool:
        # naive clients do not consult policy files
        return True

    def should_relist_on_change(self) -> bool:
        return False

    def build_args(self, schema: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
        return args  # ships whatever the caller guessed; no schema discipline

    def run(self, client: Client, workload: Sequence[Dict[str, Any]] = WORKLOAD) -> None:
        tools = client.list_tools()
        self._listed_tools = tools
        self._listed_ever = True
        for step in workload:
            name = step["intent"]
            args = step["args"]
            if not self._sent_junk:
                self._sent_junk = True
                _send_raw(client, '{"jsonrpc":"2.0","method":"tools/call"}')  # malformed
            try:
                client.call_tool(name, args)
            except FrameError as exc:
                self.notes.append(f"{name} call failed: {exc}")


class ChattyDriver(CanonicalDriver):
    """Protocol- and policy-correct, but speaks far too much: each call
    re-sends tool context and pads arguments. Wins on conformance/policy,
    loses on economy."""

    name = "chatty"

    def build_args(self, schema: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
        base = super().build_args(schema, args)
        padded: Dict[str, Any] = {}
        for key, value in base.items():
            if isinstance(value, str):
                padded[key] = value + " " + "context " * 24
            else:
                padded[key] = value
        # include every schema property (dense framing) to inflate outbound cost
        for prop in dict(schema.get("properties") or {}):
            padded.setdefault(prop, "lore")
        return padded


class CarelessDriver(NaiveDriver):
    """Worst case: ignores policy, loose args, never adapts, and floods with
    junk frames. Exists to anchor the bottom of the leaderboard."""

    name = "careless"

    def build_args(self, schema: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
        return {"guess_" + k: v for k, v in args.items()}  # wrong keys entirely

    def run(self, client: Client, workload: Sequence[Dict[str, Any]] = WORKLOAD) -> None:
        client.list_tools()
        self._listed_ever = True
        for step in workload:
            name = step["intent"]
            if not self._sent_junk:
                self._sent_junk = True
                _send_raw(client, 'this is not json-rpc')
            for _ in range(3):  # redundant attempts
                try:
                    client.call_tool(name, self.build_args({}, step["args"]))
                except FrameError as exc:
                    self.notes.append(f"{name} call failed: {exc}")


DRIVER_REGISTRY: Dict[str, type] = {
    d.name: d for d in (CanonicalDriver, NaiveDriver, ChattyDriver, CarelessDriver)
}


def make_driver(name: str) -> BaseDriver:
    cls = DRIVER_REGISTRY.get(name)
    if cls is None:
        raise KeyError(f"unknown driver: {name}")
    return cls()


def _coerce(value: Any, typ: Optional[str]) -> Any:
    if typ == "integer":
        return int(value) if not isinstance(value, int) else value
    if typ == "string":
        return str(value)
    if typ == "boolean":
        return bool(value)
    return value


def _default_of(typ: Optional[str]) -> Any:
    return {"string": "", "integer": 0, "boolean": False}.get(typ, "")


def _send_raw(client: Client, text: str) -> None:
    """Inject a raw, possibly-malformed line onto the wire (for naive/careless
    drivers). Recorded in the transcript so the scorer sees the violation."""
    client.rec.record("out", text)
    assert client.proc.stdin is not None
    client.proc.stdin.write(text + "\n")
    client.proc.stdin.flush()