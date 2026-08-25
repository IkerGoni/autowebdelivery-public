"""Unit tests for VNEXT-10 — Competitor Intelligence module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from packages.intelligence.competitor_intelligence import (
    SCHEMA_VERSION,
    _load_benchmark,
    _match_category,
    _validate_no_copies,
    build_competitor_profile,
    write_competitor_profile,
)


# ---------------------------------------------------------------------------
# Test: build_competitor_profile — Auto Detailing
# ---------------------------------------------------------------------------
class TestBuildCompetitorProfileAutoDetailing:
    def test_auto_detailing_matches_fixture(self):
        profile = build_competitor_profile(
            category="Auto Detailing Service",
            area="Dallas, TX",
            run_id="run_test_001",
            business_slug="test-detailing",
        )
        assert profile["schema_version"] == SCHEMA_VERSION
        assert profile["run_id"] == "run_test_001"
        assert profile["business_slug"] == "test-detailing"
        assert profile["category"] == "Auto Detailing Service"
        assert profile["area"] == "Dallas, TX"
        # Should match the auto_detailing fixture
        assert len(profile["patterns"]["common_sections"]) > 0
        assert "hero" in profile["patterns"]["common_sections"]

    def test_auto_detailing_has_cta_types(self):
        profile = build_competitor_profile(
            category="Auto Detailing Service",
            area="Dallas, TX",
            run_id="run_test_001",
            business_slug="test-detailing",
        )
        assert "phone_call" in profile["patterns"]["common_cta_types"]

    def test_auto_detailing_color_patterns(self):
        profile = build_competitor_profile(
            category="Auto Detailing Service",
            area="Dallas, TX",
            run_id="run_test_001",
            business_slug="test-detailing",
        )
        colors = profile["patterns"]["color_patterns"]
        assert "dominant_colors" in colors
        assert "accent_colors" in colors
        assert len(colors["dominant_colors"]) > 0


# ---------------------------------------------------------------------------
# Test: build_competitor_profile — Dental
# ---------------------------------------------------------------------------
class TestBuildCompetitorProfileDental:
    def test_dental_matches_fixture(self):
        profile = build_competitor_profile(
            category="Dental Clinic",
            area="Chicago, IL",
            run_id="run_test_002",
            business_slug="test-dental",
        )
        assert profile["category"] == "Dental Clinic"
        assert profile["area"] == "Chicago, IL"
        assert len(profile["patterns"]["common_sections"]) > 0
        assert "services" in profile["patterns"]["common_sections"]

    def test_dental_has_insurance_based_pricing(self):
        profile = build_competitor_profile(
            category="Dental Clinic",
            area="Chicago, IL",
            run_id="run_test_002",
            business_slug="test-dental",
        )
        assert profile["patterns"]["pricing_visibility"] == "insurance_based"

    def test_dental_trust_signals(self):
        profile = build_competitor_profile(
            category="Dental Clinic",
            area="Chicago, IL",
            run_id="run_test_002",
            business_slug="test-dental",
        )
        assert "board_certification_badge" in profile["patterns"]["trust_signals"]


# ---------------------------------------------------------------------------
# Test: build_competitor_profile — HVAC
# ---------------------------------------------------------------------------
class TestBuildCompetitorProfileHVAC:
    def test_hvac_matches_fixture(self):
        profile = build_competitor_profile(
            category="HVAC Service",
            area="Phoenix, AZ",
            run_id="run_test_003",
            business_slug="test-hvac",
        )
        assert profile["category"] == "HVAC Service"
        assert profile["area"] == "Phoenix, AZ"
        assert len(profile["patterns"]["common_sections"]) > 0

    def test_hvac_has_emergency_cta(self):
        profile = build_competitor_profile(
            category="HVAC Service",
            area="Phoenix, AZ",
            run_id="run_test_003",
            business_slug="test-hvac",
        )
        assert "emergency_call" in profile["patterns"]["common_cta_types"]

    def test_hvac_has_emergency_layout(self):
        profile = build_competitor_profile(
            category="HVAC Service",
            area="Phoenix, AZ",
            run_id="run_test_003",
            business_slug="test-hvac",
        )
        assert "emergency_banner_top" in profile["patterns"]["layout_patterns"]


# ---------------------------------------------------------------------------
# Test: unknown category returns empty patterns
# ---------------------------------------------------------------------------
class TestBuildCompetitorProfileUnknownCategory:
    def test_unknown_category_empty_patterns(self):
        profile = build_competitor_profile(
            category="Underwater Basket Weaving",
            area="Atlantis",
            run_id="run_test_004",
            business_slug="test-unknown",
        )
        assert profile["patterns"]["common_sections"] == []
        assert profile["patterns"]["common_cta_types"] == []
        assert profile["benchmarks_used"] == []

    def test_unknown_category_has_missing_data(self):
        profile = build_competitor_profile(
            category="Underwater Basket Weaving",
            area="Atlantis",
            run_id="run_test_004",
            business_slug="test-unknown",
        )
        assert "benchmark_match" in profile["missing_data"]


# ---------------------------------------------------------------------------
# Test: patterns are structural, not copies
# ---------------------------------------------------------------------------
class TestPatternsNotCopies:
    def test_no_text_content_in_patterns(self):
        profile = build_competitor_profile(
            category="Auto Detailing Service",
            area="Dallas, TX",
            run_id="run_test_001",
            business_slug="test-detailing",
        )
        violations = _validate_no_copies(profile["patterns"])
        assert violations == []  # No forbidden content keys

    def test_validate_detects_forbidden_key(self):
        bad_patterns = {"text_content": "Hello world"}
        violations = _validate_no_copies(bad_patterns)
        assert "text_content" in violations

    def test_validate_detects_images_key(self):
        bad_patterns = {"images": ["logo.png"]}
        violations = _validate_no_copies(bad_patterns)
        assert "images" in violations

    def test_patterns_contain_no_brand_info(self):
        profile = build_competitor_profile(
            category="Dental Clinic",
            area="Chicago, IL",
            run_id="run_test_002",
            business_slug="test-dental",
        )
        profile_json = json.dumps(profile["patterns"]).lower()
        # Should not contain company names or slogans
        assert "dr." not in profile_json
        assert " inc" not in profile_json
        assert " llc" not in profile_json


# ---------------------------------------------------------------------------
# Test: disclaimer present
# ---------------------------------------------------------------------------
class TestDisclaimerPresent:
    def test_disclaimer_in_profile(self):
        profile = build_competitor_profile(
            category="Auto Detailing Service",
            area="Dallas, TX",
            run_id="run_test_001",
            business_slug="test-detailing",
        )
        assert "disclaimer" in profile
        assert "curated benchmarks" in profile["disclaimer"]
        assert "No competitor content" in profile["disclaimer"]
        assert "images" in profile["disclaimer"]
        assert "logos" in profile["disclaimer"]
        assert "brand marks" in profile["disclaimer"]


# ---------------------------------------------------------------------------
# Test: deterministic output
# ---------------------------------------------------------------------------
class TestDeterministicOutput:
    def test_same_inputs_produce_same_output(self):
        kwargs = {
            "category": "Auto Detailing Service",
            "area": "Dallas, TX",
            "run_id": "run_det_001",
            "business_slug": "det-test",
        }
        a = build_competitor_profile(**kwargs)
        b = build_competitor_profile(**kwargs)
        assert a == b
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
        assert a["generated_at"] == b["generated_at"]

    def test_different_run_id_changes_generated_at(self):
        a = build_competitor_profile(
            category="Auto Detailing Service",
            area="Dallas, TX",
            run_id="run_a",
            business_slug="test",
        )
        b = build_competitor_profile(
            category="Auto Detailing Service",
            area="Dallas, TX",
            run_id="run_b",
            business_slug="test",
        )
        assert a["generated_at"] != b["generated_at"]


# ---------------------------------------------------------------------------
# Test: write_competitor_profile
# ---------------------------------------------------------------------------
class TestWriteCompetitorProfile:
    def test_writes_to_correct_path(self):
        profile = build_competitor_profile(
            category="Auto Detailing Service",
            area="Dallas, TX",
            run_id="run_write_001",
            business_slug="write-test",
        )
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            ret = write_competitor_profile(profile, str(out_dir), "write-test")
            assert ret.endswith("competitor_profile.json")
            assert Path(ret).is_file()

            target = out_dir / "write-test" / "competitor_profile.json"
            assert target.exists()
            on_disk = json.loads(target.read_text(encoding="utf-8"))
            assert on_disk["schema_version"] == SCHEMA_VERSION
            assert on_disk["business_slug"] == "write-test"
            assert on_disk["run_id"] == "run_write_001"


# ---------------------------------------------------------------------------
# Test: internal block
# ---------------------------------------------------------------------------
class TestInternalBlock:
    def test_internal_has_flag_and_origin(self):
        profile = build_competitor_profile(
            category="Auto Detailing Service",
            area="Dallas, TX",
            run_id="run_int_001",
            business_slug="int-test",
        )
        assert profile["internal"]["flag"] == "use_competitor_intelligence"
        assert profile["internal"]["scope"] == "fixtures_only"
        assert profile["internal"]["schema_origin"] == "VNEXT-10"

    def test_internal_scope_from_config(self):
        profile = build_competitor_profile(
            category="Auto Detailing Service",
            area="Dallas, TX",
            config={"competitor_scope": "curated"},
            run_id="run_int_002",
            business_slug="int-test",
        )
        assert profile["internal"]["scope"] == "curated"


# ---------------------------------------------------------------------------
# Test: benchmark matching
# ---------------------------------------------------------------------------
class TestBenchmarkMatchingScore:
    def test_exact_match_scores_high(self):
        score = _match_category("Auto Detailing Service", "Auto Detailing Service")
        assert score == 1.0

    def test_partial_match_scores_partial(self):
        score = _match_category("Auto Repair Shop", "Auto Detailing Service")
        assert 0.0 < score < 1.0

    def test_no_match_scores_zero(self):
        score = _match_category("Plumbing", "Auto Detailing Service")
        assert score == 0.0

    def test_case_insensitive(self):
        score = _match_category("auto detailing service", "Auto Detailing Service")
        assert score == 1.0

    def test_load_benchmark_auto_detailing(self):
        bm = _load_benchmark("Auto Detailing Service", "Dallas, TX")
        assert bm is not None
        assert bm["category"] == "Auto Detailing Service"

    def test_load_benchmark_unknown_returns_none(self):
        bm = _load_benchmark("Totally Unknown Niche", "Nowhere")
        assert bm is None


# ---------------------------------------------------------------------------
# Test: benchmarks_used field
# ---------------------------------------------------------------------------
class TestBenchmarksUsed:
    def test_matched_fixture_name_in_benchmarks_used(self):
        profile = build_competitor_profile(
            category="Auto Detailing Service",
            area="Dallas, TX",
            run_id="run_bu_001",
            business_slug="bu-test",
        )
        assert len(profile["benchmarks_used"]) > 0
        assert "auto_detailing" in profile["benchmarks_used"][0]


# ---------------------------------------------------------------------------
# Test: forbidden_public_claims in output
# ---------------------------------------------------------------------------
class TestForbiddenPublicClaimsOutput:
    def test_forbidden_public_claims_in_profile(self):
        profile = build_competitor_profile(
            category="Auto Detailing Service",
            area="Dallas, TX",
            run_id="run_fpc_001",
            business_slug="fpc-test",
        )
        assert "forbidden_public_claims" in profile
        assert isinstance(profile["forbidden_public_claims"], list)
        assert "years_in_business" in profile["forbidden_public_claims"]
        assert "awards" in profile["forbidden_public_claims"]

    def test_warnings_field_present(self):
        profile = build_competitor_profile(
            category="Auto Detailing Service",
            area="Dallas, TX",
            run_id="run_warn_001",
            business_slug="warn-test",
        )
        assert "warnings" in profile
        assert isinstance(profile["warnings"], list)

    def test_warnings_empty_for_clean_patterns(self):
        profile = build_competitor_profile(
            category="Auto Detailing Service",
            area="Dallas, TX",
            run_id="run_warn_002",
            business_slug="warn-test",
        )
        # Clean patterns should have no warnings
        assert profile["warnings"] == []


# ---------------------------------------------------------------------------
# Test: recursive key inspection in _validate_no_copies
# ---------------------------------------------------------------------------
class TestValidateNoCopiesRecursive:
    def test_detects_nested_forbidden_key(self):
        patterns = {
            "color_patterns": {
                "images": ["something.png"]
            }
        }
        violations = _validate_no_copies(patterns)
        assert "color_patterns.images" in violations

    def test_detects_multiple_nested_keys(self):
        patterns = {
            "top_level": "value",
            "nested": {
                "images": ["img1.png"],
                "logos": ["logo1.png"],
            },
            "deep": {
                "level1": {
                    "level2": {
                        "text_content": "hello"
                    }
                }
            }
        }
        violations = _validate_no_copies(patterns)
        assert "nested.images" in violations
        assert "nested.logos" in violations
        assert "deep.level1.level2.text_content" in violations

    def test_detects_forbidden_key_in_list_item(self):
        patterns = {
            "trust_signals": [
                {"logos": ["logo.png"]},
                "ratings_display"
            ]
        }
        violations = _validate_no_copies(patterns)
        assert "trust_signals[0].logos" in violations

    def test_clean_patterns_returns_empty_list(self):
        patterns = {
            "common_sections": ["hero", "services"],
            "common_cta_types": ["phone_call"],
        }
        violations = _validate_no_copies(patterns)
        assert violations == []
