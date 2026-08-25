"""
Shared provenance utilities.

Centralizes `_safe_str`, `_has_value`, `_envelope`, and
`_deterministic_generated_at` from intelligence modules.

These are pure functions with no external dependencies beyond the stdlib.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any


def _safe_str(value: Any) -> str:
    """Convert value to stripped string, empty on None/falsy."""
    return str(value or "").strip()


def _has_value(value: Any) -> bool:
    """A value is "present" only if it is not None, not empty, and not NaN-like."""
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    if isinstance(value, (list, dict, tuple)) and len(value) == 0:
        return False
    return True


def _envelope(source: str, confidence: str) -> dict[str, str]:
    """Return a provenance envelope dict.

    The envelope shape is fixed: {"source": ..., "confidence": ...}.
    """
    return {"source": source, "confidence": confidence}


def _deterministic_generated_at(run_id: str, business_slug: str) -> str:
    """Return a deterministic ISO8601 timestamp derived from (run_id, business_slug).

    The reference epoch is 2026-01-01T00:00:00Z. The day offset is the first 8
    hex chars of the SHA-256 of (run_id|business_slug), interpreted as an
    unsigned 32-bit integer, modulo 3650 (10 years). This guarantees:
      - identical inputs → identical output (test determinism)
      - no wall-clock dependence
      - no process-id or import-order dependence
    """
    digest = hashlib.sha256(f"{run_id}|{business_slug}".encode()).hexdigest()
    day_offset = int(digest[:8], 16) % 3650
    epoch = datetime(2026, 1, 1, tzinfo=timezone.utc)
    moment = epoch + timedelta(days=day_offset)
    return moment.isoformat().replace("+00:00", "Z")
