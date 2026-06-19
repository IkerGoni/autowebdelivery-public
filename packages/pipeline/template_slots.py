"""Shared helpers for unresolved template slot detection."""

from __future__ import annotations

import re

UNRESOLVED_SLOT_PATTERN = re.compile(r"\{\{\s*[a-zA-Z0-9_\.]+\s*\}\}")


def find_unresolved_slots(text: str) -> list[str]:
    """Return unique unresolved {{slot}} placeholders from rendered text."""
    seen: list[str] = []
    for match in UNRESOLVED_SLOT_PATTERN.findall(text or ""):
        if match not in seen:
            seen.append(match)
    return seen
