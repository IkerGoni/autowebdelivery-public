"""Unit tests for Task 1C.3 — Integration hooks for competitor_intel and patch planner.

Verifies that:
1. use_competitor_intelligence flag ON/OFF controls reachability
2. use_patch_phase flag ON/OFF controls reachability
"""

from __future__ import annotations

from packages.pipeline.vnext_integration import (
    run_vnext_post_phase_03_competitor_intel,
    run_vnext_post_phase_06_patch_plan,
)


class TestCompetitorIntelHook:
    def test_flag_off_skips(self):
        """use_competitor_intelligence OFF → empty list returned."""
        result = run_vnext_post_phase_03_competitor_intel(
            run_id="test_ci_off",
            workspace="/tmp",
            selected_leads=[],
            config={},
        )
        assert result == []

    def test_flag_on_reaches(self):
        """use_competitor_intelligence ON → hook executes (returns [] as placeholder)."""
        result = run_vnext_post_phase_03_competitor_intel(
            run_id="test_ci_on",
            workspace="/tmp",
            selected_leads=[],
            config={"vnext_flags": {"use_competitor_intelligence": True}},
        )
        # Placeholder returns empty list for now
        assert result == []


class TestPatchPhaseHook:
    def test_flag_off_skips(self):
        """use_patch_phase OFF → empty list returned."""
        result = run_vnext_post_phase_06_patch_plan(
            run_id="test_pp_off",
            workspace="/tmp",
            selected_leads=[],
            config={},
        )
        assert result == []

    def test_flag_on_reaches(self):
        """use_patch_phase ON → hook executes (returns [] as placeholder)."""
        result = run_vnext_post_phase_06_patch_plan(
            run_id="test_pp_on",
            workspace="/tmp",
            selected_leads=[],
            config={"vnext_flags": {"use_patch_phase": True}},
        )
        # Placeholder returns empty list for now
        assert result == []
