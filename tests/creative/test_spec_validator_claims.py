"""Tests for creative_spec_validator word-boundary matching + all-violations collection.

Verifies:
1. Forbidden claims match only at word boundaries (well≠wellness, best≠best)
2. All violations are reported, not just the first one
"""
from __future__ import annotations


from packages.creative.creative_spec_validator import validate_creative_spec
from packages.creative.creative_spec_models import FORBIDDEN_PUBLIC_CLAIMS


def _minimal_spec() -> dict:
    """Return a minimally valid creative_spec that will pass all structural checks."""
    return {
        "schema_version": "1.0.0",
        "run_id": "r-test",
        "business_slug": "test-biz",
        "generated_at": "2026-06-01T00:00:00Z",
        "business_identity": {
            "business_name": {"value": "Test Biz", "source": "bp", "confidence": "verified"},
            "category": {"value": "Testing", "source": "bp", "confidence": "verified"},
            "phone": {"value": "+1-555-0000", "source": "bp", "confidence": "verified"},
            "address": {"value": "123 Main St", "source": "bp", "confidence": "verified"},
            "hours": {"value": "9-5", "source": "bp", "confidence": "verified"},
        },
        "brand_strategy": {
            "tone": {"value": "professional", "source": "brp", "confidence": "inferred"},
            "trust_posture": {"value": "credential_safe", "source": "brp", "confidence": "inferred"},
            "emotional_goals": ["confidence"],
            "color_direction": {"primary_hint": {"value": "blue"}, "mood": {"value": "clean"}},
        },
        "sellability": {
            "overall_score": 78.4,
            "demand_signal": "strong",
            "website_status": "no_website",
            "positioning": ["position_as_missing_website_upgrade"],
        },
        "content_policy": {
            "forbidden_claims": list(FORBIDDEN_PUBLIC_CLAIMS),
            "missing_data_handling": "omit_or_neutral",
            "claim_policy": "verified_facts_only",
        },
        "generation_directives": {
            "template_family": "industrial_reliable",
            "sections": ["hero", "services", "about", "contact", "cta"],
            "required_cta": "contact_form_or_phone",
            "mobile_first": True,
        },
        "evaluation_targets": {
            "min_overall_score": 70,
            "hard_block_on": ["broken_links"],
        },
        "missing_data": [],
        "internal": {
            "flag": "use_creative_spec",
            "schema_origin": "VNEXT-04",
            "upstream_artifacts": ["business_profile.json"],
        },
    }


class TestWordBoundaryMatching:
    """Forbidden claims must only match at word boundaries."""

    def test_wellness_does_not_match_well(self):
        """Word 'wellness' should NOT trigger a forbidden claim of 'well'.

        If any forbidden claim could be a substring of 'wellness', word-boundary
        matching ensures it does not match.
        """
        spec = _minimal_spec()
        # Inject 'wellness' into a public section — safe, no forbidden claim is a word boundary match
        spec["brand_strategy"]["extra_note"] = "wellness services available"
        errors = validate_creative_spec(spec)
        forbidden_errors = [e for e in errors if "forbidden claim" in e]
        # 'well' is not in FORBIDDEN_PUBLIC_CLAIMS, but neither should any claim
        # with '-well-' substring trigger on 'wellness'
        assert forbidden_errors == [], f"Unexpected forbidden claim matches: {forbidden_errors}"

    def test_best_does_not_match_substring_within_longer_word(self):
        """Word 'best' should not match when it appears inside a longer word like 'bestinclass'.

        Actually 'best' IS a forbidden claim word boundary, so 'best' as a standalone word
        WOULD match.  This test verifies that 'bestinclass' (no boundary) does NOT match 'best'.
        """
        spec = _minimal_spec()
        # Insert 'bestinclass' which contains 'best' but without a trailing word boundary
        spec["brand_strategy"]["extra_tagline"] = "we are bestinclass provider"
        errors = validate_creative_spec(spec)
        forbidden_errors = [e for e in errors if "forbidden claim" in e]
        # None of the FORBIDDEN_PUBLIC_CLAIMS is a substring of 'bestinclass' that
        # matches with word boundaries, so no forbidden claim should be triggered
        assert forbidden_errors == [], f"Unexpected forbidden claim matches: {forbidden_errors}"


class TestCollectAllViolations:
    """All forbidden claim violations must be reported, not just the first."""

    def test_multiple_forbidden_claims_reported(self):
        """When multiple forbidden claims appear in public sections, report all."""
        spec = _minimal_spec()
        # Inject multiple forbidden claim keywords into a public section
        # Use specific words that are in FORBIDDEN_PUBLIC_CLAIMS
        # Pick ones that are distinct and unlikely to collide
        fake_extra = (
            "We have many awards and licenses. "
            "Our certifications and insurance are top-notch. "
            "We offer guarantees on all services."
        )
        spec["brand_strategy"]["fake_marketing_copy"] = fake_extra

        errors = validate_creative_spec(spec)
        forbidden_errors = [e for e in errors if "forbidden claim" in e]

        # Should have at least 3 violations (awards, licenses, certifications, insurance, guarantees)
        assert len(forbidden_errors) >= 3, (
            f"Expected multiple forbidden claim violations, got {len(forbidden_errors)}: "
            f"{forbidden_errors}"
        )
        # Each error should mention a specific claim
        for err in forbidden_errors:
            assert "found in public sections" in err

    def test_single_forbidden_claim_single_error(self):
        """A single forbidden claim produces exactly one error."""
        spec = _minimal_spec()
        spec["brand_strategy"]["testimonials_note"] = "See our testimonials"

        errors = validate_creative_spec(spec)
        forbidden_errors = [e for e in errors if "forbidden claim" in e]

        # 'testimonials' is in FORBIDDEN_PUBLIC_CLAIMS
        assert len(forbidden_errors) == 1, (
            f"Expected exactly 1 forbidden claim error, got {len(forbidden_errors)}"
        )

    def test_no_forbidden_claims_no_errors(self):
        """Spec with no forbidden claims in public sections produces no errors."""
        spec = _minimal_spec()
        errors = validate_creative_spec(spec)
        forbidden_errors = [e for e in errors if "forbidden claim" in e]
        assert forbidden_errors == []
