"""Tests for Premium Quality Scorecard (Slice 5)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packages.phases.premium_quality_scorecard import (
    PASS_THRESHOLD,
    run_premium_scorecard,
    score_site,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _make_good_site(
    site_dir: Path,
    brief_dir: Path,
    *,
    business_name: str = "Test Business",
    phone: str = "555-123-4567",
) -> None:
    """Create a fully passing site with all good metrics."""
    site_dir.mkdir(parents=True, exist_ok=True)
    brief_dir.mkdir(parents=True, exist_ok=True)

    # Brief
    facts = f"# FACTS\n\n- business_name: {business_name}\n- category: Plumbing\n- phone: {phone}\n"
    (brief_dir / "FACTS.md").write_text(facts, encoding="utf-8")

    # HTML
    html = (
        f"<html><head><link rel='stylesheet' href='styles.css'></head>"
        f"<body>"
        f"<h1>{business_name}</h1>"
        f"<h2>Professional Plumbing Services</h2>"
        f"<h2>Contact Us</h2>"
        f"<p>Welcome to {business_name}, serving the local area. "
        f"Call us at <a href='tel:{phone}'>{phone}</a></p>"
        f"<p>Our service area includes the greater metro region. "
        f"Contact us to book your appointment today.</p>"
        f"<p>We provide quality service. Book now for best results. "
        f"Additional details about our services. More content here. "
        f"Even more content to reach 200 words. Quality guaranteed service.</p>"
        f"<a class='cta' href='tel:{phone}'>Call Now</a>"
        f"<a class='cta' href='#contact'>Contact Us</a>"
        f"</body></html>"
    )
    (site_dir / "site").mkdir(parents=True, exist_ok=True)
    (site_dir / "site" / "index.html").write_text(html, encoding="utf-8")

    # Screenshots
    (site_dir / "screenshot_desktop.png").write_bytes(b"fake_png")
    (site_dir / "screenshot_mobile.png").write_bytes(b"fake_png")

    # Build status
    _write_json(site_dir / "build_status.json", {"status": "done"})

    # DOM metrics
    _write_json(site_dir / "dom_metrics.json", {
        "section_count": 6,
        "heading_count": 4,
        "image_count": 2,
        "horizontal_overflow": False,
        "missing_stylesheet": False,
        "stylesheet_count": 1,
        "broken_image_count": 0,
        "broken_link_count": 0,
        "visible_text_density_estimate": 0.01,
        "body_word_count": 250,
        "cta_count": 2,
        "duplicate_text_signals": 0,
        "section_order": ["hero", "services", "about", "location", "contact", "footer"],
    })

    # Render capture
    _write_json(site_dir / "render_capture.json", {
        "capture_status": "done",
        "capture_mode": "browser",
    })

    # Console log
    _write_json(site_dir / "console_log.json", {"errors": []})

    # Sanitizer
    _write_json(site_dir / "sanitizer_report.json", {
        "hard_block": False,
        "findings": [],
    })

    # Fact usage
    _write_json(site_dir / "fact_usage_report.json", {
        "generic_copy_blocks": [],
    })


# ===========================================================================
# Full site tests
# ===========================================================================

class TestPassForWellFormedSite:
    def test_pass(self, tmp_path: Path) -> None:
        brief = tmp_path / "04_briefs" / "test-biz"
        site_parent = tmp_path / "05_sites" / "test-biz"
        _make_good_site(site_parent, brief)

        result = score_site(site_parent, brief)
        assert result.overall_verdict == "PASS"
        assert result.overall_score >= PASS_THRESHOLD


class TestRejectFromSanitizerHardBlock:
    def test_hard_block_reject(self, tmp_path: Path) -> None:
        site = tmp_path / "05_sites" / "test-biz"
        brief = tmp_path / "04_briefs" / "test-biz"
        _make_good_site(site, brief)
        _write_json(site / "sanitizer_report.json", {
            "hard_block": True,
            "findings": ["dangerous content"],
        })

        result = score_site(site, brief)
        assert result.overall_verdict == "REJECT"
        factual = [d for d in result.dimensions if d.name == "factual_safety"][0]
        assert factual.score == 0.0
        assert factual.verdict == "reject"


class TestRejectFromHorizontalOverflow:
    def test_overflow_reject(self, tmp_path: Path) -> None:
        site = tmp_path / "05_sites" / "test-biz"
        brief = tmp_path / "04_briefs" / "test-biz"
        _make_good_site(site, brief)
        metrics = json.loads((site / "dom_metrics.json").read_text())
        metrics["horizontal_overflow"] = True
        _write_json(site / "dom_metrics.json", metrics)

        result = score_site(site, brief)
        assert result.overall_verdict == "REJECT"
        mobile = [d for d in result.dimensions if d.name == "mobile_quality"][0]
        assert mobile.score == 0.0
        assert mobile.verdict == "reject"


class TestRejectFromZeroCTAs:
    def test_zero_cta_reject(self, tmp_path: Path) -> None:
        site = tmp_path / "05_sites" / "test-biz"
        brief = tmp_path / "04_briefs" / "test-biz"
        _make_good_site(site, brief)
        metrics = json.loads((site / "dom_metrics.json").read_text())
        metrics["cta_count"] = 0
        _write_json(site / "dom_metrics.json", metrics)

        result = score_site(site, brief)
        assert result.overall_verdict == "REJECT"
        cta = [d for d in result.dimensions if d.name == "cta_clarity"][0]
        assert cta.score == 0.0
        assert cta.verdict == "reject"


class TestNeedsEditFromMediocreScores:
    def test_needs_edit(self, tmp_path: Path) -> None:
        site = tmp_path / "05_sites" / "test-biz"
        brief = tmp_path / "04_briefs" / "test-biz"
        _make_good_site(site, brief)

        # Make everything mediocre — no reject triggers but below pass
        metrics = json.loads((site / "dom_metrics.json").read_text())
        metrics["section_count"] = 2
        metrics["heading_count"] = 1
        metrics["image_count"] = 0
        metrics["body_word_count"] = 40
        metrics["cta_count"] = 1
        metrics["duplicate_text_signals"] = 5
        _write_json(site / "dom_metrics.json", metrics)

        # Remove screenshots to further lower visual score
        (site / "screenshot_desktop.png").unlink()
        (site / "screenshot_mobile.png").unlink()

        result = score_site(site, brief)
        # Should be NEEDS_EDIT or worse (not PASS)
        assert result.overall_verdict in ("NEEDS_EDIT", "REJECT")
        assert result.overall_score < PASS_THRESHOLD


# ===========================================================================
# Individual dimension tests
# ===========================================================================

class TestFactualSafety:
    def test_no_findings_score_1(self, tmp_path: Path) -> None:
        site = tmp_path / "05_sites" / "test-biz"
        brief = tmp_path / "04_briefs" / "test-biz"
        _make_good_site(site, brief)

        result = score_site(site, brief)
        dim = [d for d in result.dimensions if d.name == "factual_safety"][0]
        assert dim.score == 1.0
        assert dim.verdict == "pass"

    def test_hard_block_score_0(self, tmp_path: Path) -> None:
        site = tmp_path / "site"
        brief = tmp_path / "brief"
        site.mkdir(parents=True, exist_ok=True)
        brief.mkdir(parents=True, exist_ok=True)
        _write_json(site / "sanitizer_report.json", {"hard_block": True, "findings": ["x"]})

        result = score_site(site, brief)
        dim = [d for d in result.dimensions if d.name == "factual_safety"][0]
        assert dim.score == 0.0
        assert dim.verdict == "reject"

    def test_findings_reduce_score(self, tmp_path: Path) -> None:
        site = tmp_path / "site"
        brief = tmp_path / "brief"
        site.mkdir(parents=True, exist_ok=True)
        brief.mkdir(parents=True, exist_ok=True)
        _write_json(site / "sanitizer_report.json", {
            "hard_block": False,
            "findings": ["issue1", "issue2", "issue3"],
        })

        result = score_site(site, brief)
        dim = [d for d in result.dimensions if d.name == "factual_safety"][0]
        assert dim.score == 0.7  # 1.0 - 3 * 0.1

    def test_no_sanitizer_report_defaults_safe(self, tmp_path: Path) -> None:
        site = tmp_path / "site"
        brief = tmp_path / "brief"
        site.mkdir(parents=True, exist_ok=True)
        brief.mkdir(parents=True, exist_ok=True)

        result = score_site(site, brief)
        dim = [d for d in result.dimensions if d.name == "factual_safety"][0]
        assert dim.score == 1.0


class TestVisualCompleteness:
    def test_good_sections_score_high(self, tmp_path: Path) -> None:
        site = tmp_path / "05_sites" / "test-biz"
        brief = tmp_path / "04_briefs" / "test-biz"
        _make_good_site(site, brief)

        result = score_site(site, brief)
        dim = [d for d in result.dimensions if d.name == "visual_completeness"][0]
        assert dim.score >= 0.8
        assert dim.verdict == "pass"

    def test_few_sections_low_score(self, tmp_path: Path) -> None:
        site = tmp_path / "site"
        brief = tmp_path / "brief"
        site.mkdir(parents=True, exist_ok=True)
        brief.mkdir(parents=True, exist_ok=True)
        _write_json(site / "dom_metrics.json", {
            "section_count": 1,
            "heading_count": 0,
            "image_count": 0,
        })

        result = score_site(site, brief)
        dim = [d for d in result.dimensions if d.name == "visual_completeness"][0]
        assert dim.score < 0.4
        assert dim.verdict == "reject"

    def test_missing_dom_metrics(self, tmp_path: Path) -> None:
        site = tmp_path / "site"
        brief = tmp_path / "brief"
        site.mkdir(parents=True, exist_ok=True)
        brief.mkdir(parents=True, exist_ok=True)

        result = score_site(site, brief)
        dim = [d for d in result.dimensions if d.name == "visual_completeness"][0]
        assert dim.score == 0.0
        assert dim.verdict == "reject"


class TestMobileQuality:
    def test_no_overflow_pass(self, tmp_path: Path) -> None:
        site = tmp_path / "05_sites" / "test-biz"
        brief = tmp_path / "04_briefs" / "test-biz"
        _make_good_site(site, brief)

        result = score_site(site, brief)
        dim = [d for d in result.dimensions if d.name == "mobile_quality"][0]
        assert dim.score == 1.0
        assert dim.verdict == "pass"

    def test_overflow_reject(self, tmp_path: Path) -> None:
        site = tmp_path / "site"
        brief = tmp_path / "brief"
        site.mkdir(parents=True, exist_ok=True)
        brief.mkdir(parents=True, exist_ok=True)
        _write_json(site / "dom_metrics.json", {"horizontal_overflow": True})

        result = score_site(site, brief)
        dim = [d for d in result.dimensions if d.name == "mobile_quality"][0]
        assert dim.score == 0.0
        assert dim.verdict == "reject"

    def test_layout_summary_mobile_overflow_reject(self, tmp_path: Path) -> None:
        site = tmp_path / "05_sites" / "test-biz"
        brief = tmp_path / "04_briefs" / "test-biz"
        _make_good_site(site, brief)
        _write_json(site / "layout_summary.json", {
            "mobile": {"horizontal_overflow": True},
        })

        result = score_site(site, brief)
        dim = [d for d in result.dimensions if d.name == "mobile_quality"][0]
        assert dim.score == 0.0
        assert dim.verdict == "reject"


class TestCtaClarity:
    def test_two_ctas_perfect(self, tmp_path: Path) -> None:
        site = tmp_path / "05_sites" / "test-biz"
        brief = tmp_path / "04_briefs" / "test-biz"
        _make_good_site(site, brief)

        result = score_site(site, brief)
        dim = [d for d in result.dimensions if d.name == "cta_clarity"][0]
        assert dim.score == 1.0

    def test_one_cta_scores_07(self, tmp_path: Path) -> None:
        site = tmp_path / "site"
        brief = tmp_path / "brief"
        site.mkdir(parents=True, exist_ok=True)
        brief.mkdir(parents=True, exist_ok=True)
        _write_json(site / "dom_metrics.json", {"cta_count": 1})
        (site / "site").mkdir(parents=True, exist_ok=True)
        (site / "site" / "index.html").write_text("<html><body><p>hello</p></body></html>")

        result = score_site(site, brief)
        dim = [d for d in result.dimensions if d.name == "cta_clarity"][0]
        assert dim.score == 0.7

    def test_zero_ctas_reject(self, tmp_path: Path) -> None:
        site = tmp_path / "site"
        brief = tmp_path / "brief"
        site.mkdir(parents=True, exist_ok=True)
        brief.mkdir(parents=True, exist_ok=True)
        _write_json(site / "dom_metrics.json", {"cta_count": 0})

        result = score_site(site, brief)
        dim = [d for d in result.dimensions if d.name == "cta_clarity"][0]
        assert dim.score == 0.0
        assert dim.verdict == "reject"

    def test_above_fold_cta_detected(self, tmp_path: Path) -> None:
        site = tmp_path / "site"
        brief = tmp_path / "brief"
        site.mkdir(parents=True, exist_ok=True)
        brief.mkdir(parents=True, exist_ok=True)
        _write_json(site / "dom_metrics.json", {"cta_count": 2})
        (site / "site").mkdir(parents=True, exist_ok=True)
        (site / "site" / "index.html").write_text(
            "<html><body><a href='tel:555-1234'>Call</a><p>rest of page</p></body></html>"
        )

        result = score_site(site, brief)
        dim = [d for d in result.dimensions if d.name == "cta_clarity"][0]
        assert any("above-fold" in f for f in dim.findings)


class TestLocalRelevance:
    def test_all_signals_present(self, tmp_path: Path) -> None:
        site = tmp_path / "05_sites" / "test-biz"
        brief = tmp_path / "04_briefs" / "test-biz"
        _make_good_site(site, brief)

        result = score_site(site, brief)
        dim = [d for d in result.dimensions if d.name == "local_relevance"][0]
        assert dim.score >= 0.75

    def test_no_signals_low_score(self, tmp_path: Path) -> None:
        site = tmp_path / "site"
        brief = tmp_path / "brief"
        site.mkdir(parents=True, exist_ok=True)
        brief.mkdir(parents=True, exist_ok=True)
        # No FACTS.md, no HTML, no dom_metrics
        (brief / "FACTS.md").write_text("# FACTS\n\n- category: Test\n", encoding="utf-8")
        (site / "site").mkdir(parents=True, exist_ok=True)
        (site / "site" / "index.html").write_text("<html><body><p>Generic</p></body></html>")

        result = score_site(site, brief)
        dim = [d for d in result.dimensions if d.name == "local_relevance"][0]
        assert dim.score <= 0.5


class TestCopySpecificity:
    def test_high_word_count_pass(self, tmp_path: Path) -> None:
        site = tmp_path / "05_sites" / "test-biz"
        brief = tmp_path / "04_briefs" / "test-biz"
        _make_good_site(site, brief)

        result = score_site(site, brief)
        dim = [d for d in result.dimensions if d.name == "copy_specificity"][0]
        assert dim.score >= 0.8

    def test_low_word_count_penalty(self, tmp_path: Path) -> None:
        site = tmp_path / "site"
        brief = tmp_path / "brief"
        site.mkdir(parents=True, exist_ok=True)
        brief.mkdir(parents=True, exist_ok=True)
        _write_json(site / "dom_metrics.json", {
            "body_word_count": 30,
            "visible_text_density_estimate": 0.0001,
            "duplicate_text_signals": 0,
        })
        (site / "site").mkdir(parents=True, exist_ok=True)
        (site / "site" / "index.html").write_text("<html><body><p>Hi</p></body></html>")

        result = score_site(site, brief)
        dim = [d for d in result.dimensions if d.name == "copy_specificity"][0]
        assert dim.score < 0.3

    def test_placeholder_text_penalty(self, tmp_path: Path) -> None:
        site = tmp_path / "site"
        brief = tmp_path / "brief"
        site.mkdir(parents=True, exist_ok=True)
        brief.mkdir(parents=True, exist_ok=True)
        _write_json(site / "dom_metrics.json", {
            "body_word_count": 200,
            "visible_text_density_estimate": 0.01,
            "duplicate_text_signals": 0,
        })
        (site / "site").mkdir(parents=True, exist_ok=True)
        (site / "site" / "index.html").write_text(
            "<html><body><p>Lorem ipsum dolor sit amet TODO fix this</p></body></html>"
        )

        result = score_site(site, brief)
        dim = [d for d in result.dimensions if d.name == "copy_specificity"][0]
        assert dim.score < 1.0


class TestTemplateSmellPenalty:
    def test_clean_site_no_penalty(self, tmp_path: Path) -> None:
        site = tmp_path / "05_sites" / "test-biz"
        brief = tmp_path / "04_briefs" / "test-biz"
        _make_good_site(site, brief)

        result = score_site(site, brief)
        dim = [d for d in result.dimensions if d.name == "template_smell_penalty"][0]
        assert dim.score >= 0.8

    def test_high_duplicates_penalty(self, tmp_path: Path) -> None:
        site = tmp_path / "site"
        brief = tmp_path / "brief"
        site.mkdir(parents=True, exist_ok=True)
        brief.mkdir(parents=True, exist_ok=True)
        _write_json(site / "dom_metrics.json", {
            "body_word_count": 200,
            "duplicate_text_signals": 5,
        })

        result = score_site(site, brief)
        dim = [d for d in result.dimensions if d.name == "template_smell_penalty"][0]
        assert dim.score <= 0.7

    def test_many_generic_blocks_penalty(self, tmp_path: Path) -> None:
        site = tmp_path / "site"
        brief = tmp_path / "brief"
        site.mkdir(parents=True, exist_ok=True)
        brief.mkdir(parents=True, exist_ok=True)
        _write_json(site / "dom_metrics.json", {
            "body_word_count": 200,
            "duplicate_text_signals": 0,
        })
        _write_json(site / "fact_usage_report.json", {
            "generic_copy_blocks": ["block1", "block2", "block3", "block4"],
        })

        result = score_site(site, brief)
        dim = [d for d in result.dimensions if d.name == "template_smell_penalty"][0]
        assert dim.score <= 0.6

    def test_very_low_word_count_penalty(self, tmp_path: Path) -> None:
        site = tmp_path / "site"
        brief = tmp_path / "brief"
        site.mkdir(parents=True, exist_ok=True)
        brief.mkdir(parents=True, exist_ok=True)
        _write_json(site / "dom_metrics.json", {
            "body_word_count": 20,
            "duplicate_text_signals": 0,
        })

        result = score_site(site, brief)
        dim = [d for d in result.dimensions if d.name == "template_smell_penalty"][0]
        assert dim.score <= 0.7


# ===========================================================================
# Batch runner
# ===========================================================================

class TestRunPremiumScorecard:
    def test_batch_processing(self, tmp_path: Path) -> None:
        root = tmp_path
        run_id = "test_run"

        # Site 1: passes
        site1 = root / "runs" / run_id / "05_sites" / "alpha-cafe"
        brief1 = root / "runs" / run_id / "04_briefs" / "alpha-cafe"
        _make_good_site(site1, brief1, business_name="Alpha Cafe")

        # Site 2: fails (hard block)
        site2 = root / "runs" / run_id / "05_sites" / "beta-fail"
        brief2 = root / "runs" / run_id / "04_briefs" / "beta-fail"
        _make_good_site(site2, brief2, business_name="Beta Fail")
        _write_json(site2 / "sanitizer_report.json", {"hard_block": True, "findings": ["x"]})

        result = run_premium_scorecard(run_id, str(root))

        assert result["status"] == "done"
        assert result["records_processed"] == 2
        assert result["records_created"] == 1
        assert result["records_skipped"] == 1
        assert len(result["outputs_created"]) == 2

        # Verify JSON files written
        score_path = root / "runs" / run_id / "06_quality" / "alpha-cafe" / "premium_quality_score.json"
        assert score_path.exists()
        score_data = json.loads(score_path.read_text())
        assert score_data["overall_verdict"] == "PASS"

    def test_blocked_when_sites_missing(self, tmp_path: Path) -> None:
        result = run_premium_scorecard("nonexistent", str(tmp_path))
        assert result["status"] == "blocked"


class TestMissingArtifactsGraceful:
    def test_missing_all_artifacts_gives_zero_dimensions(self, tmp_path: Path) -> None:
        site = tmp_path / "site"
        brief = tmp_path / "brief"
        site.mkdir(parents=True, exist_ok=True)
        brief.mkdir(parents=True, exist_ok=True)
        # No artifacts at all

        result = score_site(site, brief)
        assert result.overall_verdict == "REJECT"

        # factual_safety: no sanitizer report = 1.0 (assumes safe)
        factual = [d for d in result.dimensions if d.name == "factual_safety"][0]
        assert factual.score == 1.0

        # visual_completeness: no dom_metrics = 0.0
        visual = [d for d in result.dimensions if d.name == "visual_completeness"][0]
        assert visual.score == 0.0

        # mobile_quality: no dom_metrics = 0.0
        mobile = [d for d in result.dimensions if d.name == "mobile_quality"][0]
        assert mobile.score == 0.0

        # cta_clarity: no dom_metrics = 0.0
        cta = [d for d in result.dimensions if d.name == "cta_clarity"][0]
        assert cta.score == 0.0

    def test_missing_some_artifacts_degrades_gracefully(self, tmp_path: Path) -> None:
        site = tmp_path / "site"
        brief = tmp_path / "brief"
        site.mkdir(parents=True, exist_ok=True)
        brief.mkdir(parents=True, exist_ok=True)

        # Only provide sanitizer and dom_metrics, no screenshots
        _write_json(site / "sanitizer_report.json", {"hard_block": False, "findings": []})
        _write_json(site / "dom_metrics.json", {
            "section_count": 5,
            "heading_count": 4,
            "image_count": 1,
            "horizontal_overflow": False,
            "missing_stylesheet": False,
            "stylesheet_count": 1,
            "broken_image_count": 0,
            "body_word_count": 200,
            "cta_count": 2,
            "duplicate_text_signals": 0,
            "visible_text_density_estimate": 0.01,
        })

        result = score_site(site, brief)
        # Should not crash; visual_completeness will be slightly lower (no screenshots)
        visual = [d for d in result.dimensions if d.name == "visual_completeness"][0]
        assert visual.score >= 0.5  # sections+headings+images still score well


class TestPremiumQualityScoreSerialization:
    def test_dimensions_list_present(self, tmp_path: Path) -> None:
        site = tmp_path / "05_sites" / "test-biz"
        brief = tmp_path / "04_briefs" / "test-biz"
        _make_good_site(site, brief)

        result = score_site(site, brief)
        assert len(result.dimensions) == 8
        names = [d.name for d in result.dimensions]
        expected = [
            "factual_safety", "visual_completeness", "mobile_quality", "cta_clarity",
            "local_relevance", "copy_specificity", "premium_feel", "template_smell_penalty",
        ]
        assert names == expected

    def test_weights_sum_to_one(self, tmp_path: Path) -> None:
        site = tmp_path / "05_sites" / "test-biz"
        brief = tmp_path / "04_briefs" / "test-biz"
        _make_good_site(site, brief)

        result = score_site(site, brief)
        total_weight = sum(d.weight for d in result.dimensions)
        assert abs(total_weight - 1.0) < 0.001

    def test_metadata_present(self, tmp_path: Path) -> None:
        site = tmp_path / "05_sites" / "test-biz"
        brief = tmp_path / "04_briefs" / "test-biz"
        _make_good_site(site, brief)

        result = score_site(site, brief)
        assert result.metadata["scorer_version"] == "premium_v1"
        assert "timestamp" in result.metadata
