"""A recording MCP stdio *client-under-test* transport.

`mcpbench run` spawns the bundled reference fleet server and drives it through
this client. Every JSON-RPC frame the driver sends is recorded verbatim, so
the scorer can audit conformance (well-formed frames, proper initialize
handshake), measure outbound token cost, and verify `tools/list_changed`
handling — all from the same transcript the report quotes.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from mcpbench.sandbox import Sandbox


class FrameError(Exception):
    pass


class Recorder:
    """Appends every outbound/inbound line to a shared transcript."""

    def __init__(self) -> None:
        self.lines: List[Dict[str, Any]] = []      # {"dir", "text", "ts"}
        self.tokens: int = 0

    def record(self, direction: str, text: str) -> None:
        self.lines.append({"dir": direction, "text": text, "ts": time.monotonic()})
        # rough cost: characters as proxy for tokens (stdlib-only, no model)
        self.tokens += max(1, len(text) // 4)


class Client:
    """Minimal MCP over stdio that ALSO records everything for scoring.

    The driver talks to this object. It deliberately mirrors the protocol in a
    small, auditable way: initialize -> notifications/initialized ->
    tools/list -> tools/call, with JSON-RPC error frames surfaced not crashed on.
    """

    def __init__(self, proc, recorder: Recorder, timeout: float = 8.0):
        self.proc = proc
        self.rec = recorder
        self.timeout = timeout
        self._req = 0
        self._initialized = False

    # -- protocol surface used by drivers -------------------------------

    def initialize(self, protocol_version: str = "2024-11-05") -> Dict[str, Any]:
        result = self._request("initialize", {
            "protocolVersion": protocol_version,
            "capabilities": {},
            "clientInfo": {"name": "mcpbench-driver", "version": "0.1.0"},
        })
        self._initialized = True
        self._notify("notifications/initialized")
        return result

    def list_tools(self) -> List[Dict[str, Any]]:
        result = self._request("tools/list", {})
        return result.get("tools") or []

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("tools/call", {"name": name, "arguments": arguments or {}})

    @property
    def initialized(self) -> bool:
        return self._initialized

    @property
    def token_budget(self) -> int:
        return self.rec.tokens

    @property
    def saw_list_changed(self) -> bool:
        """True if the server notified tools/list_changed at some point."""
        return any("tools/list_changed" in ln.get("text", "") for ln in self.rec.lines)

    # -- transport internals --------------------------------------------

    def _next_id(self) -> int:
        self._req += 1
        if self._req > 1_000_000:
            self._req = 1
        return self._req

    def _request(self, method: str, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        msg: Dict[str, Any] = {"jsonrpc": "2.0", "id": self._next_id(), "method": method}
        if params is not None:
            msg["params"] = params
        self._send(msg, record=True)
        return self._receive()

    def _notify(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        msg: Dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self._send(msg, record=True)

    def _send(self, msg: Dict[str, Any], record: bool) -> None:
        text = json.dumps(msg, ensure_ascii=False)
        if record:
            self.rec.record("out", text)
        assert self.proc.stdin is not None
        self.proc.stdin.write(text + "\n")
        self.proc.stdin.flush()

    def _receive(self) -> Dict[str, Any]:
        """Read frames until the frame bearing our pending request id arrives.

        Server->client notifications (no id, has method) are recorded into the
        transcript and skipped — they are signals, not responses. This is what
        makes the benchmark able to test list_changed handling without breaking
        the strict request/response loop.
        """
        assert self.proc.stdout is not None
        while True:
            raw = self.proc.stdout.readline()
            if not raw:
                self.rec.record("in", "<eof>")
                raise FrameError("server closed stdout")
            self.rec.record("in", raw.rstrip("\n"))
            try:
                frame: Dict[str, Any] = json.loads(raw)
            except ValueError as exc:
                raise FrameError(f"non-JSON response: {raw[:200]!r}") from exc
            if frame.get("method"):
                continue  # server->client notification: record + keep waiting
            if frame.get("error"):
                raise FrameError(str(frame["error"]))
            return frame.get("result") or {}


def _kill(proc) -> None:
    try:
        proc.terminate()
        proc.wait(timeout=2)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass