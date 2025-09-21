"""Thin browser-open indirection so tests can stub it without importing webbrowser."""
from __future__ import annotations

from pathlib import Path


def open_html(path: str) -> None:
    import webbrowser

    webbrowser.open(Path(path).resolve().as_uri())