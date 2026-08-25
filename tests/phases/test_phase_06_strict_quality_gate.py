"""Tests for Phase 06 Strict Quality Gate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packages.phases.phase_06_strict_quality_gate import (
    MAX_BROKEN_IMAGES,
    MIN_SECTION_COUNT,
    run_strict_phase_06,
    run_strict_quality_check,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _make_passing_site(
    site_dir: Path,
    brief_dir: Path,
    *,
    business_name: str = "Test Business",
) -> None:
    """Create a fully passing site with all Phase 05.5 artifacts."""
    # Legacy Phase 06 artifacts
    brief_dir.mkdir(parents=True, exist_ok=True)
    site_dir.mkdir(parents=True, exist_ok=True)

    facts = f"# FACTS\n\n- business_name: {business_name}\n- category: Restaurant\n"
    (brief_dir / "FACTS.md").write_text(facts, encoding="utf-8")

    _write_json(site_dir / "build_status.json", {"status": "done"})
    (site_dir / "site").mkdir(parents=True, exist_ok=True)
    (site_dir / "site" / "index.html").write_text(
        f"<html><h1>{business_name}</h1><p>Welcome</p></html>", encoding="utf-8"
    )
    (site_dir / "screenshot_desktop.png").write_bytes(b"fake_png")
    (site_dir / "screenshot_mobile.png").write_bytes(b"fake_png")

    # Phase 05.5 artifacts — all passing values
    _write_json(site_dir / "render_capture.json", {
        "capture_status": "done",
        "capture_mode": "browser",
    })
    _write_json(site_dir / "dom_metrics.json", {
        "horizontal_overflow": False,
        "missing_stylesheet": False,
        "stylesheet_count": 1,
        "broken_image_count": 0,
        "broken_link_count": 0,
        "visible_text_density_estimate": 0.01,
        "section_count": 5,
        "cta_count": 2,
    })
    _write_json(site_dir / "console_log.json", {
        "errors": ["minor warning"],
    })
    _write_json(site_dir / "asset_load_log.json", {
        "failed_requests": [],
        "stylesheet_count": 1,
    })
    _write_json(site_dir / "sanitizer_report.json", {
        "hard_block": False,
        "findings": [],
    })


class TestStrictQualityCheckAllPass:
    def test_all_checks_pass(self, tmp_path: Path) -> None:
        site_dir = tmp_path / "site"
        brief_dir = tmp_path / "brief"
        _make_passing_site(site_dir, brief_dir)

        result = run_strict_quality_check(site_dir, brief_dir, strict=True)
        assert result["status"] == "approved_for_deploy", result


class TestRenderCapture:
    def test_render_capture_missing_rejected(self, tmp_path: Path) -> None:
        site_dir = tmp_path / "site"
        brief_dir = tmp_path / "brief"
        _make_passing_site(site_dir, brief_dir)
        # Remove render_capture.json
        (site_dir / "render_capture.json").unlink()

        result = run_strict_quality_check(site_dir, brief_dir, strict=True)
        assert result["status"] == "rejected"
        assert any("render_capture.json missing" in r for r in result["rejection_reasons"])

    def test_capture_status_not_done_rejected(self, tmp_path: Path) -> None:
        site_dir = tmp_path / "site"
        brief_dir = tmp_path / "brief"
        _make_passing_site(site_dir, brief_dir)
        _write_json(site_dir / "render_capture.json", {
            "capture_status": "pending",
            "capture_mode": "browser",
        })

        result = run_strict_quality_check(site_dir, brief_dir, strict=True)
        assert result["status"] == "rejected"
        assert any("capture_status" in r for r in result["rejection_reasons"])

    def test_capture_mode_not_browser_rejected(self, tmp_path: Path) -> None:
        site_dir = tmp_path / "site"
        brief_dir = tmp_path / "brief"
        _make_passing_site(site_dir, brief_dir)
        _write_json(site_dir / "render_capture.json", {
            "capture_status": "done",
            "capture_mode": "deterministic_fallback",
        })

        result = run_strict_quality_check(site_dir, brief_dir, strict=True)
        assert result["status"] == "rejected"
        assert any("capture_mode" in r for r in result["rejection_reasons"])


class TestDomMetrics:
    def test_horizontal_overflow_rejected(self, tmp_path: Path) -> None:
        site_dir = tmp_path / "site"
        brief_dir = tmp_path / "brief"
        _make_passing_site(site_dir, brief_dir)
        metrics = json.loads((site_dir / "dom_metrics.json").read_text())
        metrics["horizontal_overflow"] = True
        _write_json(site_dir / "dom_metrics.json", metrics)

        result = run_strict_quality_check(site_dir, brief_dir, strict=True)
        assert result["status"] == "rejected"
        assert any("Horizontal overflow" in r for r in result["rejection_reasons"])

    def test_missing_stylesheet_rejected(self, tmp_path: Path) -> None:
        site_dir = tmp_path / "site"
        brief_dir = tmp_path / "brief"
        _make_passing_site(site_dir, brief_dir)
        metrics = json.loads((site_dir / "dom_metrics.json").read_text())
        metrics["missing_stylesheet"] = True
        metrics["stylesheet_count"] = 0
        _write_json(site_dir / "dom_metrics.json", metrics)

        result = run_strict_quality_check(site_dir, brief_dir, strict=True)
        assert result["status"] == "rejected"
        assert any("Missing stylesheet" in r for r in result["rejection_reasons"])

    def test_broken_images_rejected(self, tmp_path: Path) -> None:
        site_dir = tmp_path / "site"
        brief_dir = tmp_path / "brief"
        _make_passing_site(site_dir, brief_dir)
        metrics = json.loads((site_dir / "dom_metrics.json").read_text())
        metrics["broken_image_count"] = MAX_BROKEN_IMAGES + 1
        _write_json(site_dir / "dom_metrics.json", metrics)

        result = run_strict_quality_check(site_dir, brief_dir, strict=True)
        assert result["status"] == "rejected"
        assert any("broken images" in r.lower() for r in result["rejection_reasons"])

    def test_low_text_density_rejected(self, tmp_path: Path) -> None:
        site_dir = tmp_path / "site"
        brief_dir = tmp_path / "brief"
        _make_passing_site(site_dir, brief_dir)
        metrics = json.loads((site_dir / "dom_metrics.json").read_text())
        metrics["visible_text_density_estimate"] = 0.0
        _write_json(site_dir / "dom_metrics.json", metrics)

        result = run_strict_quality_check(site_dir, brief_dir, strict=True)
        assert result["status"] == "rejected"
        assert any("Text density" in r for r in result["rejection_reasons"])

    def test_insufficient_sections_rejected(self, tmp_path: Path) -> None:
        site_dir = tmp_path / "site"
        brief_dir = tmp_path / "brief"
        _make_passing_site(site_dir, brief_dir)
        metrics = json.loads((site_dir / "dom_metrics.json").read_text())
        metrics["section_count"] = MIN_SECTION_COUNT - 1
        _write_json(site_dir / "dom_metrics.json", metrics)

        result = run_strict_quality_check(site_dir, brief_dir, strict=True)
        assert result["status"] == "rejected"
        assert any("sections" in r.lower() for r in result["rejection_reasons"])

    def test_no_cta_rejected(self, tmp_path: Path) -> None:
        site_dir = tmp_path / "site"
        brief_dir = tmp_path / "brief"
        _make_passing_site(site_dir, brief_dir)
        metrics = json.loads((site_dir / "dom_metrics.json").read_text())
        metrics["cta_count"] = 0
        _write_json(site_dir / "dom_metrics.json", metrics)

        result = run_strict_quality_check(site_dir, brief_dir, strict=True)
        assert result["status"] == "rejected"
        assert any("CTA" in r for r in result["rejection_reasons"])

    def test_dom_metrics_missing_rejected(self, tmp_path: Path) -> None:
        site_dir = tmp_path / "site"
        brief_dir = tmp_path / "brief"
        _make_passing_site(site_dir, brief_dir)
        (site_dir / "dom_metrics.json").unlink()

        result = run_strict_quality_check(site_dir, brief_dir, strict=True)
        assert result["status"] == "rejected"
        assert any("dom_metrics.json missing" in r for r in result["rejection_reasons"])


class TestConsoleLog:
    def test_too_many_console_errors_needs_edit(self, tmp_path: Path) -> None:
        site_dir = tmp_path / "site"
        brief_dir = tmp_path / "brief"
        _make_passing_site(site_dir, brief_dir)
        _write_json(site_dir / "console_log.json", {
            "errors": ["err1", "err2", "err3", "err4"],  # 4 > MAX_CONSOLE_ERRORS=3
        })

        result = run_strict_quality_check(site_dir, brief_dir, strict=True)
        assert result["status"] == "needs_edit"
        assert any("console errors" in r.lower() for r in result["needs_edit_reasons"])


class TestAssetLoad:
    def test_critical_asset_failure_rejected(self, tmp_path: Path) -> None:
        site_dir = tmp_path / "site"
        brief_dir = tmp_path / "brief"
        _make_passing_site(site_dir, brief_dir)
        _write_json(site_dir / "asset_load_log.json", {
            "failed_requests": [
                {"url": "https://example.com/styles.css", "status": 404},
            ],
        })

        result = run_strict_quality_check(site_dir, brief_dir, strict=True)
        assert result["status"] == "rejected"
        assert any("Critical asset" in r for r in result["rejection_reasons"])

    def test_non_critical_asset_failure_needs_edit(self, tmp_path: Path) -> None:
        site_dir = tmp_path / "site"
        brief_dir = tmp_path / "brief"
        _make_passing_site(site_dir, brief_dir)
        _write_json(site_dir / "asset_load_log.json", {
            "failed_requests": [
                {"url": "https://example.com/hero.webp", "status": 404},
            ],
        })

        result = run_strict_quality_check(site_dir, brief_dir, strict=True)
        assert result["status"] == "needs_edit"
        assert any("Non-critical asset" in r for r in result["needs_edit_reasons"])


class TestSanitizer:
    def test_sanitizer_hard_block_rejected(self, tmp_path: Path) -> None:
        site_dir = tmp_path / "site"
        brief_dir = tmp_path / "brief"
        _make_passing_site(site_dir, brief_dir)
        _write_json(site_dir / "sanitizer_report.json", {
            "hard_block": True,
            "findings": ["dangerous content"],
        })

        result = run_strict_quality_check(site_dir, brief_dir, strict=True)
        assert result["status"] == "rejected"
        assert any("hard_block" in r for r in result["rejection_reasons"])


class TestLegacyPropagation:
    def test_legacy_rejection_propagates(self, tmp_path: Path) -> None:
        """Legacy Phase 06 rejection propagates to strict immediately."""
        site_dir = tmp_path / "site"
        brief_dir = tmp_path / "brief"

        # Create site that fails legacy (bad build status)
        site_dir.mkdir(parents=True, exist_ok=True)
        brief_dir.mkdir(parents=True, exist_ok=True)
        (brief_dir / "FACTS.md").write_text("# FACTS\n\n- business_name: Test\n", encoding="utf-8")
        _write_json(site_dir / "build_status.json", {"status": "failed"})

        result = run_strict_quality_check(site_dir, brief_dir, strict=True)
        assert result["status"] == "rejected"
        assert any("failed" in r for r in result["rejection_reasons"])

    def test_legacy_needs_edit_continues_strict_checks(self, tmp_path: Path) -> None:
        """Legacy needs_edit continues, but strict failure overrides."""
        site_dir = tmp_path / "site"
        brief_dir = tmp_path / "brief"
        _make_passing_site(site_dir, brief_dir)

        # Remove mobile screenshot to trigger legacy needs_edit
        (site_dir / "screenshot_mobile.png").unlink()
        # But also make strict fail (hard block)
        _write_json(site_dir / "sanitizer_report.json", {"hard_block": True, "findings": []})

        result = run_strict_quality_check(site_dir, brief_dir, strict=True)
        assert result["status"] == "rejected"


class TestStrictFalse:
    def test_strict_false_returns_legacy_result(self, tmp_path: Path) -> None:
        """strict=False falls back to legacy-only checks."""
        site_dir = tmp_path / "site"
        brief_dir = tmp_path / "brief"
        _make_passing_site(site_dir, brief_dir)

        # Remove Phase 05.5 artifacts — would fail strict
        (site_dir / "render_capture.json").unlink()
        (site_dir / "dom_metrics.json").unlink()
        (site_dir / "sanitizer_report.json").unlink()

        result = run_strict_quality_check(site_dir, brief_dir, strict=False)
        # Legacy Phase 06 should still approve
        assert result["status"] == "approved_for_deploy"


class TestRunStrictPhase06:
    def test_processes_multiple_sites(self, tmp_path: Path) -> None:
        root = tmp_path
        run_id = "test_run"
        sites_dir = root / "runs" / run_id / "05_sites"

        # Site 1: passes all checks
        site1 = sites_dir / "alpha-cafe"
        brief1 = root / "runs" / run_id / "04_briefs" / "alpha-cafe"
        _make_passing_site(site1, brief1, business_name="Alpha Cafe")

        # Site 2: fails legacy (bad build)
        site2 = sites_dir / "beta-fail"
        brief2 = root / "runs" / run_id / "04_briefs" / "beta-fail"
        site2.mkdir(parents=True, exist_ok=True)
        brief2.mkdir(parents=True, exist_ok=True)
        (brief2 / "FACTS.md").write_text("# FACTS\n\n- business_name: Beta\n", encoding="utf-8")
        _write_json(site2 / "build_status.json", {"status": "failed"})

        result = run_strict_phase_06(run_id, str(root), strict=True)
        assert result["status"] == "done"
        assert result["records_processed"] == 2
        assert result["records_created"] == 1  # only alpha-cafe approved

    def test_blocked_when_sites_missing(self, tmp_path: Path) -> None:
        result = run_strict_phase_06("nonexistent_run", str(tmp_path), strict=True)
        assert result["status"] == "blocked"
