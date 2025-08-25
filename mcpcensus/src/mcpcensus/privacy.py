"""Privacy engineering core: stable device ids, cohort bucketing, k-anonymity
suppression, and optional Laplace (LDP-style) noise so that no published
aggregate can be traced back to a single machine."""

from __future__ import annotations

import hashlib
import hmac
import os
import random
import json
from typing import Any, Dict, Optional

from mcpcensus import FORMAT, MIN_COHORT, SALT_BYTES

# --------------------------------------------------------------------------
# Stable device id (salted), so a user's monthly uploads chain together into an
# honest trendline while the id itself is unlinkable across installs.
# --------------------------------------------------------------------------


class DeviceSalt:
    """A persisted 128-bit install salt, kept off the wire."""

    def __init__(self, salt: bytes):
        self.salt = salt

    @classmethod
    def load_or_create(cls, path: str) -> "DeviceSalt":
        import errno

        try:
            with open(path, "rb") as fh:
                raw = fh.read().strip()
            if len(raw) != SALT_BYTES:
                raise ValueError("unexpected salt length")
            return cls(raw)
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                dry = cls(os.urandom(SALT_BYTES))
                dirpath = os.path.dirname(os.path.abspath(path))
                os.makedirs(dirpath, exist_ok=True)
                tmp = path + ".tmp"
                with open(tmp, "wb") as fh:
                    fh.write(dry.salt)
                os.replace(tmp, path)
                return dry
            raise
        except ValueError:
            dry = cls(os.urandom(SALT_BYTES))
            with open(path, "wb") as fh:
                fh.write(dry.salt)
            return dry

    @property
    def device_id(self) -> str:
        """sha256(salt + "mcpcensus/device")[:16], hex; the only identifier on the wire."""
        return stable_hash(self.salt, "device-salt-install", tag="device")[:16]


def stable_hash(salt: bytes, value: str, tag: str = "name") -> str:
    """HMAC-salted hash of a sensitive value under a per-field tag so two fields
    sharing a value (e.g. a server name in context vs security) never collide."""
    return hmac.new(salt, (tag + "\x00" + value).encode("utf-8"), hashlib.sha256).hexdigest()[:24]


# --------------------------------------------------------------------------
# Cohort bucketing
# --------------------------------------------------------------------------


def cohort_bucket(axes: Dict[str, Any], sensor: str) -> str:
    """A coarse anonymous descriptor of a submission for grouping before any
    counting. Intentionally lossy: buckets hide individual signatures."""
    if sensor == "context":
        servers = axes.get("server_models", [])
        total_tools = sum(s.get("tool_count", 0) for s in servers)
        return f"ctx|servers={bucket_ceil(len(servers), 2)}|tools={bucket_ceil(total_tools, 5)}|waste={bucket_ceil(axes.get('waste_percent', 0), 10)}"
    if sensor == "security":
        risk = axes.get("risk_totals", {})
        total = sum(risk.values())
        return f"sec|servers={bucket_ceil(axes.get('server_count', 0), 2)}|risk={bucket_ceil(total, 1)}"
    return "unknown"


def bucket_ceil(value: int, size: int) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        v = 0
    return ((v + size - 1) // size) * size if v > 0 else 0


def k_anonymize(rows: list, min_cohort: int = MIN_COHORT) -> list:
    """Suppress any row whose cohort has fewer than ``min_cohort`` members;
    return the surviving rows (with cohort exposed) and the suppressed count."""
    if not rows:
        return [], 0
    counts: Dict[str, int] = {}
    for r in rows:
        counts[r["cohort"]] = counts.get(r["cohort"], 0) + 1
    kept, suppressed = [], 0
    for r in rows:
        if counts.get(r["cohort"], 0) >= min_cohort:
            kept.append(r)
        else:
            suppressed += 1
    return kept, suppressed


def laplace_noise(scale: float, rng: Optional[random.Random] = None) -> float:
    """Laplace(0, scale) via inverse-CDF: symmetric noise for LDP-style counts."""
    from math import log

    rng = rng or random.SystemRandom()
    u = rng.random() - 0.5  # in [-0.5, 0.5)
    p = 2 * u               # in [-1, 1)
    return -scale * _sign(p) * log(1.0 - abs(p)) if p != 0 else 0.0


def _sign(x: float) -> float:
    return 1.0 if x >= 0 else -1.0


def clamp_noisy_count(base: int, scale: float, rng: Optional[random.Random] = None) -> int:
    """base + Laplace(scale), clamped to >= 0. The published count."""
    return max(0, int(round(base + laplace_noise(scale, rng))))


# --------------------------------------------------------------------------
# Fingerprint validation / roundtripping (pure, shared by registry + CLI)
# --------------------------------------------------------------------------


def is_valid_fingerprint(obj: Any) -> bool:
    return (
        isinstance(obj, dict)
        and obj.get("format") == FORMAT
        and isinstance(obj.get("device"), str)
        and isinstance(obj.get("submitted_at"), str)
        and isinstance(obj.get("sensor"), str)
        and isinstance(obj.get("axes"), dict)
    )


def load_fingerprints_json(lines_text: str) -> list:
    """Parse a JSONL registry file into a list of validated fingerprints."""
    out = []
    for line in lines_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if is_valid_fingerprint(obj):
            out.append(obj)
    return out