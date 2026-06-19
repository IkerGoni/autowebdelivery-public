"""Unit tests for Phase 04.6 — Competitor Intelligence phase runner."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from packages.phases.phase_04_6_competitor_intelligence import (
    USE_COMPETITOR_INTELLIGENCE_FLAG,
    run_phase_04_6,
)


def _make_workspace(tmp: str, leads: list[dict] | None = None) -> str:
    """Create a minimal workspace with briefs index for testing."""
    run_id = "run_test_phase"
    briefs_dir = Path(tmp) / "runs" / run_id / "04_briefs"
    briefs_dir.mkdir(parents=True, exist_ok=True)

    if leads is None:
        leads = [
            {
                "business_slug": "test-detailing",
                "business_name": "Test Detailing",
                "category": "Auto Detailing Service",
                "area": "Dallas, TX",
            }
        ]

    briefs_index = {"leads": leads}
    (briefs_dir / "preview_ready_briefs.json").write_text(
        json.dumps(briefs_index), encoding="utf-8"
    )
    return tmp


# ---------------------------------------------------------------------------
# Test: phase runs when flag is ON
# ---------------------------------------------------------------------------
class TestPhaseRunsWhenFlagOn:
    def test_runs_and_produces_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_workspace(tmp)
            result = run_phase_04_6(
                run_id="run_test_phase",
                workspace=tmp,
                config={USE_COMPETITOR_INTELLIGENCE_FLAG: True},
            )
            assert result["status"] == "done"
            assert result["records_processed"] == 1

            # Check file was created
            profile_path = (
                Path(tmp)
                / "runs"
                / "run_test_phase"
                / "04_6_competitor_intelligence"
                / "test-detailing"
                / "competitor_profile.json"
            )
            assert profile_path.exists()
            data = json.loads(profile_path.read_text(encoding="utf-8"))
            assert data["business_slug"] == "test-detailing"

    def test_runs_multiple_leads(self):
        leads = [
            {
                "business_slug": "detailing-1",
                "category": "Auto Detailing Service",
                "area": "Dallas, TX",
            },
            {
                "business_slug": "dental-1",
                "category": "Dental Clinic",
                "area": "Chicago, IL",
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            _make_workspace(tmp, leads=leads)
            result = run_phase_04_6(
                run_id="run_test_phase",
                workspace=tmp,
                config={USE_COMPETITOR_INTELLIGENCE_FLAG: True},
            )
            assert result["status"] == "done"
            assert result["records_processed"] == 2


# ---------------------------------------------------------------------------
# Test: phase skips when flag is OFF
# ---------------------------------------------------------------------------
class TestPhaseSkipsWhenFlagOff:
    def test_skips_with_no_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_workspace(tmp)
            result = run_phase_04_6(
                run_id="run_test_phase",
                workspace=tmp,
                config={},
            )
            assert result["status"] == "skipped"

    def test_skips_with_explicit_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_workspace(tmp)
            result = run_phase_04_6(
                run_id="run_test_phase",
                workspace=tmp,
                config={USE_COMPETITOR_INTELLIGENCE_FLAG: False},
            )
            assert result["status"] == "skipped"


# ---------------------------------------------------------------------------
# Test: phase skips when scope is none
# ---------------------------------------------------------------------------
class TestPhaseSkipsWhenScopeNone:
    def test_skips_when_scope_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_workspace(tmp)
            result = run_phase_04_6(
                run_id="run_test_phase",
                workspace=tmp,
                config={
                    USE_COMPETITOR_INTELLIGENCE_FLAG: True,
                    "competitor_scope": "none",
                },
            )
            assert result["status"] == "skipped"

    def test_blocked_when_no_briefs(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_phase_04_6(
                run_id="run_test_phase",
                workspace=tmp,
                config={USE_COMPETITOR_INTELLIGENCE_FLAG: True},
            )
            assert result["status"] == "blocked"


# ---------------------------------------------------------------------------
# Test: phase result file written
# ---------------------------------------------------------------------------
class TestPhaseResultFile:
    def test_result_json_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_workspace(tmp)
            run_phase_04_6(
                run_id="run_test_phase",
                workspace=tmp,
                config={USE_COMPETITOR_INTELLIGENCE_FLAG: True},
            )
            result_path = (
                Path(tmp)
                / "runs"
                / "run_test_phase"
                / "04_6_competitor_intelligence"
                / "result.json"
            )
            assert result_path.exists()
            data = json.loads(result_path.read_text(encoding="utf-8"))
            assert data["phase"] == "phase_04_6_competitor_intelligence"
            assert "test-detailing" in data["processed"]
