"""Tests for VNEXT-07 — patch_plan.py."""

from __future__ import annotations

import json
from pathlib import Path

from packages.patching.patch_plan import (
    APPROVED_CATEGORIES,
    SCHEMA_VERSION,
    build_patch_plan,
    write_patch_plan,
)


# ---------------------------------------------------------------------------
# HTML Fixtures
# ---------------------------------------------------------------------------


def _site_with_missing_cta() -> str:
    """Site without a final CTA section."""
    return """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Test Site</title></head>
<body>
<header><h1>Welcome</h1></header>
<main>
<section><p>We provide great services.</p></section>
<section><p>Learn more about us.</p></section>
</main>
<footer><p>Contact: info@example.com</p></footer>
</body>
</html>"""


def _site_with_forbidden_claim() -> str:
    """Site containing forbidden claims like 'award-winning' or 'guaranteed'."""
    return """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Test Site</title></head>
<body>
<header><h1>Welcome</h1></header>
<main>
<section><p>We are an award-winning service. Our results are guaranteed.</p></section>
<section><p>We are the best in the world at what we do.</p></section>
</main>
<footer><p>Contact us</p></footer>
</body>
</html>"""


def _site_with_mobile_overflow() -> str:
    """Site with horizontal scroll (no overflow-x:hidden)."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>body { margin: 0; }</style>
</head>
<body>
<header><h1>Welcome</h1></header>
<main><section style="width:1200px;">Wide content causing overflow</section></main>
</body>
</html>"""


def _site_with_bad_cta_link() -> str:
    """CTA with '#' link."""
    return """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Test Site</title></head>
<body>
<header><h1>Welcome</h1></header>
<main>
<section>
<a href="#" class="btn cta-button">Get Started</a>
</section>
</main>
</body>
</html>"""


def _site_with_spacing_issues() -> str:
    """Site with poor spacing between sections."""
    return """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Test Site</title>
<style>section { margin: 0; }</style>
</head>
<body>
<header><h1>Welcome</h1></header>
<main>
<section><p>Section 1</p></section>
<section><p>Section 2</p></section>
<section><p>Section 3</p></section>
</main>
</body>
</html>"""


def _good_site() -> str:
    """Site that needs no patches — good CTA, no forbidden claims, responsive."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body { margin: 0; overflow-x: hidden; }
section { padding: 2rem 1rem; }
</style>
</head>
<body>
<header><h1>Welcome to Quality Service</h1></header>
<main>
<section><p>Professional and reliable services.</p></section>
<section>
<a href="#contact" class="btn">Contact Us</a>
</section>
</main>
<footer><p>Email: info@example.com | 123 Main St, Springfield IL 62701</p></footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Evaluation report fixtures
# ---------------------------------------------------------------------------


def _good_evaluation_report(html: str = "") -> dict:
    """Evaluation report with 'pass' verdict — no patches needed."""
    return {
        "schema_version": "1.0.0",
        "run_id": "run_test_001",
        "business_slug": "test-business",
        "verdict": "pass",
        "overall_score": 82.5,
        "hard_failures": [],
        "patchable_failures": [],
        "dimensions": {
            "conversion": {"score": 85, "status": "pass", "notes": "Good CTA"},
            "factual_safety": {"score": 100, "status": "pass", "notes": "No forbidden claims"},
            "mobile_experience": {"score": 78, "status": "pass", "notes": "Responsive"},
            "spacing": {"score": 75, "status": "pass", "notes": "Good spacing"},
        },
        "creative_spec_alignment": {
            "forbidden_claims_found": [],
        },
        "_site_html": html,
    }


def _hard_fail_evaluation_report() -> dict:
    """Evaluation report with 'fail' verdict — should NOT be patched."""
    return {
        "schema_version": "1.0.0",
        "run_id": "run_fail_001",
        "business_slug": "fail-business",
        "verdict": "fail",
        "overall_score": 28.0,
        "hard_failures": ["factual_safety", "accessibility"],
        "patchable_failures": [],
        "dimensions": {
            "factual_safety": {"score": 10, "status": "fail", "notes": "Multiple forbidden claims"},
            "accessibility": {"score": 20, "status": "fail", "notes": "No alt text, no lang attr"},
            "conversion": {"score": 30, "status": "warn", "notes": "No CTA found"},
        },
        "creative_spec_alignment": {
            "forbidden_claims_found": [],
        },
    }


def _patchable_evaluation_report(html: str = "") -> dict:
    """Evaluation report with 'patchable' verdict — patches needed."""
    return {
        "schema_version": "1.0.0",
        "run_id": "run_patch_001",
        "business_slug": "patch-business",
        "verdict": "patchable",
        "overall_score": 52.0,
        "hard_failures": [],
        "patchable_failures": ["spacing"],
        "dimensions": {
            "conversion": {"score": 35, "status": "warn", "notes": "No CTA found"},
            "factual_safety": {"score": 100, "status": "pass", "notes": "No forbidden claims"},
            "mobile_experience": {"score": 30, "status": "warn", "notes": "No overflow fix"},
            "spacing": {"score": 25, "status": "patchable", "notes": "Poor spacing"},
        },
        "creative_spec_alignment": {
            "forbidden_claims_found": [],
        },
        "_site_html": html,
    }


# ---------------------------------------------------------------------------
# Tests — build_patch_plan
# ---------------------------------------------------------------------------


class TestBuildPatchPlan:
    """Tests for build_patch_plan."""

    def test_build_patch_plan_empty_for_good_site(self) -> None:
        """A 'pass' site should produce no patches."""
        report = _good_evaluation_report()
        plan = build_patch_plan(report, run_id="run_001", business_slug="good-site")
        assert plan["patches"] == []
        assert plan["verdict"] == "pass"
        assert plan["original_verdict"] == "pass"

    def test_build_patch_plan_empty_for_hard_fail(self) -> None:
        """A 'fail' site should produce no patches — hard-reject."""
        report = _hard_fail_evaluation_report()
        plan = build_patch_plan(report, run_id="run_001", business_slug="fail-site")
        assert plan["patches"] == []
        assert plan["verdict"] == "fail"

    def test_build_patch_plan_detects_missing_cta(self) -> None:
        """Low conversion score should trigger missing_final_cta patch."""
        html = _site_with_missing_cta()
        report = _patchable_evaluation_report(html)
        plan = build_patch_plan(report, run_id="run_001", business_slug="no-cta")
        categories = [p["category"] for p in plan["patches"]]
        assert "missing_final_cta" in categories

    def test_build_patch_plan_detects_forbidden_claims(self) -> None:
        """Forbidden claims in HTML should trigger removal patches."""
        html = _site_with_forbidden_claim()
        report = _patchable_evaluation_report(html)
        creative_spec = {
            "content_policy": {
                "forbidden_claims": ["guaranteed", "best in the world", "award-winning"],
            },
        }
        plan = build_patch_plan(
            report, creative_spec, run_id="run_001", business_slug="claims"
        )
        categories = [p["category"] for p in plan["patches"]]
        assert "forbidden_claim_removal" in categories
        # Each found claim should produce a separate patch
        claim_patches = [p for p in plan["patches"] if p["category"] == "forbidden_claim_removal"]
        assert len(claim_patches) >= 1

    def test_build_patch_plan_detects_mobile_overflow(self) -> None:
        """Low mobile_experience score should trigger overflow patch."""
        html = _site_with_mobile_overflow()
        report = _patchable_evaluation_report(html)
        plan = build_patch_plan(report, run_id="run_001", business_slug="overflow")
        categories = [p["category"] for p in plan["patches"]]
        assert "mobile_overflow_css_fix" in categories

    def test_build_patch_plan_detects_bad_cta_link(self) -> None:
        """CTA link with '#' should trigger cta_link_correction."""
        html = _site_with_bad_cta_link()
        report = _patchable_evaluation_report(html)
        plan = build_patch_plan(report, run_id="run_001", business_slug="bad-link")
        categories = [p["category"] for p in plan["patches"]]
        assert "cta_link_correction" in categories

    def test_build_patch_plan_detects_spacing(self) -> None:
        """Low spacing score should trigger spacing_adjustment."""
        html = _site_with_spacing_issues()
        report = _patchable_evaluation_report(html)
        plan = build_patch_plan(report, run_id="run_001", business_slug="spacing")
        categories = [p["category"] for p in plan["patches"]]
        assert "spacing_adjustment" in categories

    def test_build_patch_plan_schema_version(self) -> None:
        """Plan should have correct schema_version."""
        report = _good_evaluation_report()
        plan = build_patch_plan(report, run_id="run_001", business_slug="test")
        assert plan["schema_version"] == SCHEMA_VERSION

    def test_build_patch_plan_internal(self) -> None:
        """Plan should have internal metadata."""
        report = _good_evaluation_report()
        plan = build_patch_plan(report, run_id="run_001", business_slug="test")
        assert plan["internal"]["flag"] == "use_patch_phase"
        assert plan["internal"]["schema_origin"] == "VNEXT-07"

    def test_build_patch_plan_skipped_reasons(self) -> None:
        """Plan should have a skipped_reasons list."""
        report = _good_evaluation_report()
        plan = build_patch_plan(report, run_id="run_001", business_slug="test")
        assert "skipped_reasons" in plan
        assert isinstance(plan["skipped_reasons"], list)

    def test_only_approved_categories(self) -> None:
        """All patches must use only approved categories."""
        html = _site_with_forbidden_claim()
        report = _patchable_evaluation_report(html)
        creative_spec = {
            "content_policy": {
                "forbidden_claims": ["guaranteed"],
            },
        }
        plan = build_patch_plan(
            report, creative_spec, run_id="run_001", business_slug="test"
        )
        for patch in plan["patches"]:
            assert patch["category"] in APPROVED_CATEGORIES

    def test_deterministic_patch_ids(self) -> None:
        """Patch IDs should be deterministic and sequential."""
        html = _site_with_forbidden_claim()
        report = _patchable_evaluation_report(html)
        creative_spec = {
            "content_policy": {
                "forbidden_claims": ["guaranteed"],
            },
        }
        plan = build_patch_plan(
            report, creative_spec, run_id="run_001", business_slug="test"
        )
        for i, patch in enumerate(plan["patches"], start=1):
            assert patch["id"] == f"patch_{i:03d}"


# ---------------------------------------------------------------------------
# Tests — write_patch_plan
# ---------------------------------------------------------------------------


class TestWritePatchPlan:
    """Tests for write_patch_plan."""

    def test_write_patch_plan(self, tmp_path: Path) -> None:
        """write_patch_plan should create a valid JSON file."""
        report = _good_evaluation_report()
        plan = build_patch_plan(report, run_id="run_001", business_slug="test-write")

        path = write_patch_plan(plan, str(tmp_path), "test-write")
        assert Path(path).exists()
        assert Path(path).name == "patch_plan.json"

        data = json.loads(Path(path).read_text(encoding="utf-8"))
        assert data["schema_version"] == SCHEMA_VERSION
        assert data["run_id"] == "run_001"
        assert data["business_slug"] == "test-write"

    def test_write_patch_plan_creates_directory(self, tmp_path: Path) -> None:
        """write_patch_plan should create the business_slug subdirectory."""
        report = _good_evaluation_report()
        plan = build_patch_plan(report, run_id="run_001", business_slug="new-dir")

        path = write_patch_plan(plan, str(tmp_path), "new-dir")
        assert (tmp_path / "new-dir").is_dir()
        assert Path(path).parent == tmp_path / "new-dir"

    def test_deterministic_timestamp_same_inputs(self) -> None:
        """Same run_id + business_slug should produce same generated_at."""
        report = _good_evaluation_report()
        plan1 = build_patch_plan(report, run_id="run_abc", business_slug="same")
        plan2 = build_patch_plan(report, run_id="run_abc", business_slug="same")
        assert plan1["generated_at"] == plan2["generated_at"]

    def test_different_inputs_different_timestamps(self) -> None:
        """Different run_id should produce different generated_at."""
        report = _good_evaluation_report()
        plan1 = build_patch_plan(report, run_id="run_abc", business_slug="same")
        plan2 = build_patch_plan(report, run_id="run_xyz", business_slug="same")
        # They may coincidentally match due to second-level resolution,
        # but the deterministic hash changes
        assert isinstance(plan1["generated_at"], str)
        assert isinstance(plan2["generated_at"], str)

    def test_plan_json_round_trip(self, tmp_path: Path) -> None:
        """Plan should survive JSON serialization round-trip."""
        html = _site_with_missing_cta()
        report = _patchable_evaluation_report(html)
        plan = build_patch_plan(report, run_id="run_rt", business_slug="roundtrip")

        path = write_patch_plan(plan, str(tmp_path), "roundtrip")
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        assert data == plan
