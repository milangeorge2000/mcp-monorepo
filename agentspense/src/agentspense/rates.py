"""The rate card: published model pricing, bundled so a spend file from one
provider can be compared against another's on equal footing.

Rates are per 1M tokens:

.. code-block:: json

    { "provider/model": {"in": 3.00, "out": 15.00} }

Overrides can be provided as a JSON file (``--rates rates.json``) with the same
shape; entries merge over the bundled defaults.
"""

from __future__ import annotations

import json
import os
from typing import Dict, Optional, Tuple

_BUNDLED = {
    "claude": {
        "claude-sonnet-4.5": {"in": 3.00, "out": 15.00},
        "claude-opus-4.5": {"in": 5.00, "out": 25.00},
        "claude-sonnet-4": {"in": 3.00, "out": 15.00},
        "claude-opus-4": {"in": 15.00, "out": 75.00},
        "claude-3-7-sonnet": {"in": 3.00, "out": 15.00},
        "claude-3-5-sonnet": {"in": 3.00, "out": 15.00},
        "claude-3-5-haiku": {"in": 0.80, "out": 4.00},
        "claude-3-haiku": {"in": 0.25, "out": 1.25},
    },
    "cursor": {
        "gpt-4.1": {"in": 2.00, "out": 8.00},
        "gpt-4.1-mini": {"in": 0.40, "out": 1.60},
        "gpt-5": {"in": 1.25, "out": 10.00},
        "claude-sonnet-4": {"in": 3.00, "out": 15.00},
        "cursor-small": {"in": 0.30, "out": 1.00},
    },
    "codex": {
        "gpt-5.2-codex": {"in": 1.00, "out": 8.00},
        "gpt-5-codex": {"in": 1.25, "out": 10.00},
        "gpt-4.1-codex": {"in": 2.00, "out": 8.00},
    },
    "opencode": {
        "deepseek-v4-flash": {"in": 0.07, "out": 0.27},
        "chatgpt-mini": {"in": 0.15, "out": 0.60},
        "gpt-5": {"in": 1.25, "out": 10.00},
        "claude-sonnet-4": {"in": 3.00, "out": 15.00},
    },
}


def load_rates(path: Optional[str] = None) -> Dict[str, Dict[str, Tuple[float, float]]]:
    """Bundled rates merged with an optional override file."""
    merged: Dict[str, Dict[str, Dict[str, float]]] = _deep_copy(_BUNDLED)
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            overrides = json.load(fh)
        for provider, models in overrides.items():
            bucket = merged.setdefault(str(provider), {})
            for model, r in models.items():
                bucket[str(model)] = r
    return _flatten(merged)


def _flatten(merged: Dict[str, Dict[str, Dict[str, float]]]) -> Dict[str, Dict[str, Tuple[float, float]]]:
    out: Dict[str, Dict[str, Tuple[float, float]]] = {}
    for provider, models in merged.items():
        out[provider] = {}
        for model, r in models.items():
            out[provider][model] = (float(r["in"]), float(r["out"]))
    return out


def _deep_copy(d: Dict) -> Dict:
    return {k: dict(v) for k, v in d.items()}


def lookup(provider: str, model: str, rates: Optional[Dict[str, Dict]] = None) -> Optional[Tuple[float, float]]:
    """Rates (in, out) for a provider+model, best-effort normalizing names."""
    rates = rates or load_rates()
    provider = (provider or "").lower().replace(" ", "-")
    if provider in rates:
        bucket = rates[provider]
        if model in bucket:
            return bucket[model]
        # a longer model name truncation match for vendor-suffixed exports
        lowered = model.lower()
        for known, r in bucket.items():
            if known.lower() in lowered or lowered in known.lower():
                return r
    else:
        for alias, target in (("claude-code", "claude"), ("claude-", "claude"),
                              ("anthropic", "claude"), ("openai", "codex")):
            if provider.startswith(alias) and target in rates:
                return lookup(target, model, rates)
    return None