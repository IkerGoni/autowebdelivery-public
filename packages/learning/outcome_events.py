"""VNEXT-09 — Outcome Events.

Append-only outcome tracking for learning records.  Events are appended
sequentially and the record's ``outcome.status`` is updated to the latest
event type.

Feature-flagged behind ``use_learning_record_contract`` (default OFF).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

VALID_EVENT_TYPES: tuple[str, ...] = (
    "created",
    "preview_sent",
    "owner_viewed",
    "owner_responded",
    "sale_completed",
    "sale_declined",
    "follow_up_scheduled",
    "expired",
)


def append_outcome_event(
    record: dict,
    event_type: str,
    details: dict | None = None,
) -> dict:
    """Append an outcome event to the learning record.

    Events are **append-only** — the events list only ever grows.
    The record is mutated in-place and returned.

    Parameters
    ----------
    record:
        The learning record dict (mutated and returned).
    event_type:
        One of :data:`VALID_EVENT_TYPES`.
    details:
        Optional dict of event-specific details.

    Returns
    -------
    dict
        The mutated record (same object).

    Raises
    ------
    ValueError
        If *event_type* is not in :data:`VALID_EVENT_TYPES`.
    """
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(
            f"Invalid event_type {event_type!r}. "
            f"Must be one of {VALID_EVENT_TYPES}"
        )

    now = datetime.now(timezone.utc).isoformat()

    event: dict[str, Any] = {
        "event_type": event_type,
        "timestamp": now,
    }
    if details is not None:
        event["details"] = details

    # Get the existing events list (or empty) and append
    old_outcome = record.get("outcome", {})
    old_events = old_outcome.get("events", [])
    record["outcome"] = {
        "status": event_type,
        "events": [*old_events, event],
        "last_updated": now,
    }

    # Update analytics_keys.outcome_category
    record["analytics_keys"] = {
        **record.get("analytics_keys", {}),
        "outcome_category": get_outcome_category(record),
    }

    return record


def get_outcome_category(record: dict) -> str:
    """Derive ``outcome_category`` from the latest event.

    Returns
    -------
    str
        - ``"pending"`` if no events
        - ``"converted"`` if latest event is ``sale_completed``
        - ``"lost"`` if latest event is ``sale_declined`` or ``"expired"``
        - ``"in_progress"`` otherwise
    """
    events = _safe_get(record, "outcome", "events")
    if not events:
        return "pending"

    latest = events[-1].get("event_type", "")

    if latest == "sale_completed":
        return "converted"
    if latest in ("sale_declined", "expired"):
        return "lost"
    return "in_progress"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _safe_get(mapping: dict | None, *keys: str, default: Any = None) -> Any:
    """Nested dict getter that tolerates None at any level."""
    obj = mapping
    for key in keys:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(key, default)
    return obj