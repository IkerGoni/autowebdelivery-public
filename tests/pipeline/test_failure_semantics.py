"""Tests for the failure-semantics taxonomy module (Sprint S2, T1)."""

from __future__ import annotations

import pytest

from packages.pipeline.failure_semantics import (
    FailureClass,
    Phase06Counts,
    Phase06DecisionError,
    classify_phase_status,
    classify_scorecard_verdict,
    parse_phase_06_decisions,
)


class TestFailureClassEnum:
    def test_six_taxonomy_values(self) -> None:
        expected = {
            "retryable",
            "optional",
            "degraded_success",
            "hard_failure",
            "blocked",
            "not_verified",
        }
        assert {c.value for c in FailureClass} == expected


class TestClassifyPhaseStatus:
    def test_done_is_clean_success(self) -> None:
        assert classify_phase_status("done") is None

    def test_done_with_hard_block_is_hard_failure(self) -> None:
        sem = classify_phase_status("done", hard_block=True)
        assert sem is not None
        assert sem.failure_class == FailureClass.HARD_FAILURE
        assert sem.blocks_deployment

    def test_blocked_maps_to_blocked(self) -> None:
        sem = classify_phase_status("blocked")
        assert sem is not None
        assert sem.failure_class == FailureClass.BLOCKED
        assert sem.blocks_deployment

    def test_failed_maps_to_hard_failure(self) -> None:
        sem = classify_phase_status("failed")
        assert sem is not None
        assert sem.failure_class == FailureClass.HARD_FAILURE
        assert sem.blocks_deployment

    def test_needs_review_blocks(self) -> None:
        sem = classify_phase_status("needs_review")
        assert sem is not None
        assert sem.failure_class == FailureClass.BLOCKED
        assert sem.blocks_deployment

    def test_skipped_is_optional(self) -> None:
        sem = classify_phase_status("skipped")
        assert sem is not None
        assert sem.failure_class == FailureClass.OPTIONAL
        assert not sem.blocks_deployment

    def test_missing_status_blocks(self) -> None:
        sem = classify_phase_status("")
        assert sem is not None
        assert sem.failure_class == FailureClass.BLOCKED

    def test_unknown_status_is_hard_failure(self) -> None:
        sem = classify_phase_status("weird")
        assert sem is not None
        assert sem.failure_class == FailureClass.HARD_FAILURE


class TestClassifyScorecardVerdict:
    def test_pass_is_clean_success(self) -> None:
        assert classify_scorecard_verdict("PASS") is None

    def test_not_verified_never_passes_and_blocks_in_production(self) -> None:
        sem = classify_scorecard_verdict("NOT_VERIFIED", production=True)
        assert sem is not None
        assert sem.failure_class == FailureClass.NOT_VERIFIED
        assert sem.blocks_deployment

    def test_not_verified_does_not_block_in_preview(self) -> None:
        sem = classify_scorecard_verdict("NOT_VERIFIED", production=False)
        assert sem is not None
        assert sem.failure_class == FailureClass.NOT_VERIFIED
        assert not sem.blocks_deployment

    def test_needs_edit_is_degraded_success(self) -> None:
        sem = classify_scorecard_verdict("NEEDS_EDIT")
        assert sem is not None
        assert sem.failure_class == FailureClass.DEGRADED_SUCCESS
        assert sem.retryable

    def test_reject_is_hard_failure(self) -> None:
        sem = classify_scorecard_verdict("REJECT")
        assert sem is not None
        assert sem.failure_class == FailureClass.HARD_FAILURE
        assert sem.blocks_deployment


class TestParsePhase06Decisions:
    def test_parses_canonical_line(self) -> None:
        counts = parse_phase_06_decisions(
            [
                "Strict quality checked 3 sites",
                "Approved: 1, Needs edit: 2, Rejected: 0",
            ]
        )
        assert counts == Phase06Counts(approved=1, needs_edit=2, rejected=0)
        assert counts.total == 3
        assert counts.to_tuple() == (1, 2, 0)

    def test_tolerates_spacing_variations(self) -> None:
        counts = parse_phase_06_decisions(["Approved:1,Needs edit: 0,Rejected: 2"])
        assert counts == Phase06Counts(approved=1, needs_edit=0, rejected=2)

    def test_missing_line_raises(self) -> None:
        with pytest.raises(Phase06DecisionError):
            parse_phase_06_decisions(["Quality gate completed without breakdown"])

    def test_non_integer_count_raises(self) -> None:
        with pytest.raises(Phase06DecisionError):
            parse_phase_06_decisions(["Approved: 1, Needs edit: x, Rejected: 0"])

    def test_empty_decisions_raise(self) -> None:
        with pytest.raises(Phase06DecisionError):
            parse_phase_06_decisions([])
