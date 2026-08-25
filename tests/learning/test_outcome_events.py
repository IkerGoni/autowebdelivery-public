"""Unit tests for VNEXT-09 — Outcome Events (outcome_events.py)."""

from __future__ import annotations

from packages.learning.learning_record import build_learning_record
from packages.learning.outcome_events import (
    VALID_EVENT_TYPES,
    append_outcome_event,
    get_outcome_category,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_record() -> dict:
    return build_learning_record(run_id="run_oe", business_slug="outcome-biz")


# ---------------------------------------------------------------------------
# Tests — append_outcome_event
# ---------------------------------------------------------------------------


class TestAppendOutcomeEvent:
    def test_appends_event(self):
        rec = _make_record()
        result = append_outcome_event(rec, "created")
        assert len(result["outcome"]["events"]) == 1
        assert result["outcome"]["events"][0]["event_type"] == "created"

    def test_updates_status(self):
        rec = _make_record()
        append_outcome_event(rec, "created")
        assert rec["outcome"]["status"] == "created"

    def test_sets_last_updated(self):
        rec = _make_record()
        append_outcome_event(rec, "created")
        assert rec["outcome"]["last_updated"] is not None
        assert "T" in rec["outcome"]["last_updated"]

    def test_returns_same_object(self):
        rec = _make_record()
        result = append_outcome_event(rec, "created")
        assert result is rec

    def test_invalid_event_type_raises(self):
        rec = _make_record()
        import pytest
        with pytest.raises(ValueError, match="Invalid event_type"):
            append_outcome_event(rec, "invalid_type")

    def test_with_details(self):
        rec = _make_record()
        append_outcome_event(rec, "owner_responded", details={"response": "interested"})
        evt = rec["outcome"]["events"][0]
        assert evt["details"] == {"response": "interested"}

    def test_without_details(self):
        rec = _make_record()
        append_outcome_event(rec, "created")
        evt = rec["outcome"]["events"][0]
        assert "details" not in evt


# ---------------------------------------------------------------------------
# Tests — multiple events in sequence
# ---------------------------------------------------------------------------


class TestMultipleEvents:
    def test_append_preserves_order(self):
        rec = _make_record()
        append_outcome_event(rec, "created")
        append_outcome_event(rec, "preview_sent")
        append_outcome_event(rec, "owner_viewed")
        events = rec["outcome"]["events"]
        assert len(events) == 3
        assert events[0]["event_type"] == "created"
        assert events[1]["event_type"] == "preview_sent"
        assert events[2]["event_type"] == "owner_viewed"

    def test_status_is_latest(self):
        rec = _make_record()
        append_outcome_event(rec, "created")
        append_outcome_event(rec, "preview_sent")
        append_outcome_event(rec, "owner_viewed")
        assert rec["outcome"]["status"] == "owner_viewed"

    def test_events_are_append_only(self):
        """Events list grows and is never overwritten."""
        rec = _make_record()
        for et in ["created", "preview_sent", "owner_viewed", "owner_responded"]:
            append_outcome_event(rec, et)
        assert len(rec["outcome"]["events"]) == 4


# ---------------------------------------------------------------------------
# Tests — get_outcome_category
# ---------------------------------------------------------------------------


class TestGetOutcomeCategory:
    def test_pending_no_events(self):
        rec = _make_record()
        assert get_outcome_category(rec) == "pending"

    def test_converted(self):
        rec = _make_record()
        append_outcome_event(rec, "created")
        append_outcome_event(rec, "sale_completed")
        assert get_outcome_category(rec) == "converted"

    def test_lost_declined(self):
        rec = _make_record()
        append_outcome_event(rec, "created")
        append_outcome_event(rec, "sale_declined")
        assert get_outcome_category(rec) == "lost"

    def test_lost_expired(self):
        rec = _make_record()
        append_outcome_event(rec, "created")
        append_outcome_event(rec, "expired")
        assert get_outcome_category(rec) == "lost"

    def test_in_progress_created(self):
        rec = _make_record()
        append_outcome_event(rec, "created")
        assert get_outcome_category(rec) == "in_progress"

    def test_in_progress_preview_sent(self):
        rec = _make_record()
        append_outcome_event(rec, "preview_sent")
        assert get_outcome_category(rec) == "in_progress"

    def test_in_progress_owner_viewed(self):
        rec = _make_record()
        append_outcome_event(rec, "owner_viewed")
        assert get_outcome_category(rec) == "in_progress"

    def test_in_progress_follow_up(self):
        rec = _make_record()
        append_outcome_event(rec, "follow_up_scheduled")
        assert get_outcome_category(rec) == "in_progress"


# ---------------------------------------------------------------------------
# Tests — analytics_keys updated on event
# ---------------------------------------------------------------------------


class TestAnalyticsKeysUpdated:
    def test_outcome_category_updated_on_sale(self):
        rec = _make_record()
        append_outcome_event(rec, "sale_completed")
        assert rec["analytics_keys"]["outcome_category"] == "converted"

    def test_outcome_category_updated_on_declined(self):
        rec = _make_record()
        append_outcome_event(rec, "sale_declined")
        assert rec["analytics_keys"]["outcome_category"] == "lost"


# ---------------------------------------------------------------------------
# Tests — valid event types constant
# ---------------------------------------------------------------------------


class TestValidEventTypes:
    def test_all_expected_types(self):
        expected = {
            "created", "preview_sent", "owner_viewed", "owner_responded",
            "sale_completed", "sale_declined", "follow_up_scheduled", "expired",
        }
        assert set(VALID_EVENT_TYPES) == expected

    def test_is_tuple(self):
        assert isinstance(VALID_EVENT_TYPES, tuple)
