"""Validation for the scenario-template DSL.

Templates are plain JSON so they are easy to author, diff, and version. This
module rejects everything that would expand ambiguously or run dangerously
off-schema, so a template can never produce a battery the engine did not build.
"""
from __future__ import annotations

from typing import Any, Dict, List

from mcpbatt.models import DriftSpec, MODES, Template

_ALLOWED_EXPECT = {"ok", "invalid", "any"}


def load_template(raw: Dict[str, Any]) -> Template:
    """Parse + validate a template dict. Raises ValueError with a precise reason."""
    errors = validate_template(raw)
    if errors:
        raise ValueError("; ".join(errors))

    drift_raw = raw.get("drift")
    drift = None
    if isinstance(drift_raw, dict):
        drift = DriftSpec(
            tool=str(drift_raw.get("tool", "")),
            add_required=[str(x) for x in drift_raw.get("add_required", [])],
        )
    return Template(
        name=raw["name"],
        description=raw.get("description", ""),
        select=raw.get("select", "*"),
        mode=raw.get("mode", "required"),
        expect=raw.get("expect", "ok"),
        drift=drift,
    )


def validate_template(raw: Any) -> List[str]:
    """One message per problem found; empty list means the template is valid."""
    if not isinstance(raw, dict):
        return ["template must be a JSON object"]
    errors: List[str] = []

    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("name must be a non-empty string")

    mode = raw.get("mode", "required")
    if mode not in MODES:
        errors.append(f"mode must be one of {', '.join(MODES)}, got {mode!r}")

    expect = raw.get("expect", "ok")
    if expect not in _ALLOWED_EXPECT:
        errors.append(f"expect must be one of {', '.join(sorted(_ALLOWED_EXPECT))}, got {expect!r}")

    select = raw.get("select", "*")
    if not isinstance(select, str) or not select.strip():
        errors.append("select must be a non-empty string")

    drift = raw.get("drift")
    if drift is not None:
        if not isinstance(drift, dict):
            errors.append("drift must be an object")
        else:
            tool = drift.get("tool")
            if not isinstance(tool, str) or not tool.strip():
                errors.append("drift.tool must be a non-empty string")
            added = drift.get("add_required", [])
            if not isinstance(added, list) or not all(isinstance(x, str) and x for x in added):
                errors.append("drift.add_required must be a list of field names")

    return errors