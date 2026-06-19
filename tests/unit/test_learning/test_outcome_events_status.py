"""Unit tests for Task 1C.1 — outcome_events.py no-mutation status derivation.

Verifies that:
1. Calling append_outcome_event twice with the same input yields identical results
2. The original outcome metadata dict is never mutated
"""

from __future__ import annotations

from packages.learning.outcome_events import (
    append_outcome_event,
    get_outcome_category,
)


def _make_record() -> dict:
    """Minimal learning record dict."""
    return {
        "run_id": "test_no_mut_001",
        "business_slug": "no-mut-biz",
        "outcome": {
            "status": "pending",
            "events": [],
            "last_updated": None,
        },
        "analytics_keys": {
            "niche": "dentist",
            "outcome_category": "pending",
        },
    }


class TestNoMutation:
    def test_original_outcome_dict_not_mutated(self):
        """The nested outcome dict passed in is never mutated in-place."""
        rec = _make_record()
        original_outcome = rec["outcome"]
        original_events = rec["outcome"]["events"]

        result = append_outcome_event(rec, "created")

        # The original nested dict is replaced, not mutated
        # So rec["outcome"] is a NEW dict
        assert result["outcome"] is not original_outcome
        # The original events list is untouched
        assert original_events == []
        # The original outcome dict is untouched
        assert original_outcome == {"status": "pending", "events": [], "last_updated": None}

    def test_original_analytics_not_mutated(self):
        """The nested analytics_keys dict is replaced, not mutated."""
        rec = _make_record()
        original_analytics = rec["analytics_keys"]

        result = append_outcome_event(rec, "created")

        assert result["analytics_keys"] is not original_analytics
        assert original_analytics == {
            "niche": "dentist",
            "outcome_category": "pending",
        }

    def test_call_twice_same_input_identical_results(self):
        """Calling with same initial state gives semantically identical results.

        Timestamps will differ (generated at different times), but all
        non-temporal fields must match.
        """
        rec1 = _make_record()
        rec2 = _make_record()

        result1 = append_outcome_event(rec1, "preview_sent")
        result2 = append_outcome_event(rec2, "preview_sent")

        assert result1["outcome"]["status"] == result2["outcome"]["status"]
        assert result1["outcome"]["status"] == "preview_sent"

        # Events match except timestamp
        for e1, e2 in zip(result1["outcome"]["events"], result2["outcome"]["events"]):
            assert e1["event_type"] == e2["event_type"]
            assert "timestamp" in e1
            assert "timestamp" in e2

        assert result1["analytics_keys"]["outcome_category"] == result2["analytics_keys"]["outcome_category"]

    def test_status_derived_from_last_event(self):
        """Status is always derived from the event_type passed."""
        rec = _make_record()
        result = append_outcome_event(rec, "sale_completed")
        assert result["outcome"]["status"] == "sale_completed"

    def test_status_from_last_event_with_multiple(self):
        """After multiple events, status reflects the latest."""
        rec = _make_record()
        append_outcome_event(rec, "created")
        append_outcome_event(rec, "preview_sent")
        append_outcome_event(rec, "sale_completed")
        assert rec["outcome"]["status"] == "sale_completed"

    def test_get_outcome_category_works(self):
        """get_outcome_category still works correctly after refactor."""
        rec = _make_record()
        append_outcome_event(rec, "created")
        assert get_outcome_category(rec) == "in_progress"
        append_outcome_event(rec, "sale_completed")
        assert get_outcome_category(rec) == "converted"
