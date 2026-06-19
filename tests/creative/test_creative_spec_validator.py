"""Unit tests for VNEXT-04 — Creative Specification Validator."""

from __future__ import annotations

from packages.creative.creative_spec_builder import build_creative_spec
from packages.creative.creative_spec_validator import validate_creative_spec


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------
def _business_profile(**overrides):
    bp = {
        "schema_version": "1.0.0",
        "run_id": "r1",
        "business_slug": "north-dallas-mobile-detailing",
        "generated_at": "2027-03-15T00:00:00Z",
        "verified_facts": {
            "business_name": {
                "value": "North Dallas Mobile Detailing",
                "source": "selected_for_preview.json",
                "confidence": "verified",
            },
            "category": {
                "value": "Auto Detailing Service",
                "source": "selected_for_preview.json",
                "confidence": "verified",
            },
            "phone": {
                "value": "+1-555-123-4567",
                "source": "selected_for_preview.json",
                "confidence": "verified",
            },
            "address": {
                "value": "123 Main St, Dallas, TX",
                "source": "selected_for_preview.json",
                "confidence": "verified",
            },
            "hours": {
                "value": "Mon-Sat 9-5",
                "source": "selected_for_preview.json",
                "confidence": "verified",
            },
        },
        "inferred_strategy": {},
        "missing_data": [],
        "forbidden_public_claims": [],
        "internal": {
            "flag": "use_business_profile_contract",
            "schema_origin": "VNEXT-01",
        },
    }
    bp.update(overrides)
    return bp


def _market_profile(**overrides):
    mp = {
        "schema_version": "1.0.0",
        "run_id": "r1",
        "business_slug": "north-dallas-mobile-detailing",
        "generated_at": "2027-03-15T00:00:00Z",
        "sellability": {
            "score": {"value": 78.4, "source": "scorecard", "confidence": "verified"},
            "category": {
                "value": "Auto Detailing Service",
                "source": "selected_for_preview.json",
                "confidence": "verified",
            },
            "website_status": {
                "value": "no_website",
                "source": "selected_for_preview.json",
                "confidence": "verified",
            },
            "demand_signal": {
                "value": "strong",
                "source": "scorecard.component_scores",
                "confidence": "inferred",
            },
        },
        "strategy_hints": {
            "positioning": ["position_as_missing_website_upgrade"],
            "value_drivers": ["high_value_service_category"],
            "risk_flags": [],
        },
        "missing_data": [],
        "forbidden_public_claims": [],
        "internal": {
            "flag": "use_market_profile_contract",
            "schema_origin": "VNEXT-02",
        },
    }
    mp.update(overrides)
    return mp


def _brand_profile(**overrides):
    brp = {
        "schema_version": "1.0.0",
        "run_id": "r1",
        "business_slug": "north-dallas-mobile-detailing",
        "generated_at": "2027-03-15T00:00:00Z",
        "brand_tone": {
            "primary": {"value": "professional", "source": "inferred_from_category", "confidence": "inferred"},
            "secondary": {"value": "warm", "source": "inferred_from_category", "confidence": "inferred"},
            "voice": {"value": "authoritative_approachable", "source": "inferred_from_category", "confidence": "inferred"},
        },
        "trust_posture": {
            "value": "credential_safe",
            "source": "inferred_from_market_profile",
            "confidence": "inferred",
        },
        "emotional_goals": ["confidence", "reliability"],
        "color_direction": {
            "primary_hint": {"value": "blue", "source": "category_defaults", "confidence": "inferred"},
            "mood": {"value": "clean_professional", "source": "category_defaults", "confidence": "inferred"},
        },
        "missing_data": [],
        "forbidden_public_claims": [],
        "internal": {
            "flag": "use_brand_reconstruction_contract",
            "schema_origin": "VNEXT-03",
        },
    }
    brp.update(overrides)
    return brp


_BASE_CONFIG = {
    "niche": "auto-detailing",
    "area": "Dallas",
    "country": "US",
    "style_preset": "industrial_reliable",
}


def _valid_spec():
    """Build a valid creative_spec for testing."""
    return build_creative_spec(
        _business_profile(),
        _market_profile(),
        _brand_profile(),
        _BASE_CONFIG,
        run_id="r1",
    )


# ---------------------------------------------------------------------------
# Validation — valid spec
# ---------------------------------------------------------------------------
class TestValidSpec:
    def test_valid_spec_no_errors(self):
        spec = _valid_spec()
        errors = validate_creative_spec(spec)
        assert errors == [], f"unexpected errors: {errors}"

    def test_valid_spec_is_list(self):
        spec = _valid_spec()
        errors = validate_creative_spec(spec)
        assert isinstance(errors, list)


# ---------------------------------------------------------------------------
# Validation — missing top-level keys
# ---------------------------------------------------------------------------
class TestMissingTopLevelKeys:
    def test_empty_dict_errors(self):
        errors = validate_creative_spec({})
        assert len(errors) > 0
        assert any("schema_version" in e for e in errors)

    def test_missing_single_key(self):
        spec = _valid_spec()
        del spec["business_identity"]
        errors = validate_creative_spec(spec)
        assert any("business_identity" in e for e in errors)

    def test_missing_multiple_keys(self):
        spec = {"schema_version": "1.0.0"}
        errors = validate_creative_spec(spec)
        assert len(errors) >= 5  # many missing keys

    def test_non_dict_input(self):
        errors = validate_creative_spec("not a dict")
        assert len(errors) == 1
        assert "must be a dict" in errors[0]


# ---------------------------------------------------------------------------
# Validation — nested section keys
# ---------------------------------------------------------------------------
class TestMissingNestedKeys:
    def test_missing_business_identity_key(self):
        spec = _valid_spec()
        del spec["business_identity"]["business_name"]
        errors = validate_creative_spec(spec)
        assert any("business_identity" in e and "business_name" in e for e in errors)

    def test_missing_brand_strategy_key(self):
        spec = _valid_spec()
        del spec["brand_strategy"]["tone"]
        errors = validate_creative_spec(spec)
        assert any("brand_strategy" in e and "tone" in e for e in errors)

    def test_missing_content_policy_key(self):
        spec = _valid_spec()
        del spec["content_policy"]["claim_policy"]
        errors = validate_creative_spec(spec)
        assert any("content_policy" in e and "claim_policy" in e for e in errors)

    def test_missing_generation_directives_key(self):
        spec = _valid_spec()
        del spec["generation_directives"]["sections"]
        errors = validate_creative_spec(spec)
        assert any("generation_directives" in e and "sections" in e for e in errors)

    def test_missing_evaluation_targets_key(self):
        spec = _valid_spec()
        del spec["evaluation_targets"]["min_overall_score"]
        errors = validate_creative_spec(spec)
        assert any("evaluation_targets" in e and "min_overall_score" in e for e in errors)

    def test_missing_internal_key(self):
        spec = _valid_spec()
        del spec["internal"]["schema_origin"]
        errors = validate_creative_spec(spec)
        assert any("internal" in e and "schema_origin" in e for e in errors)

    def test_non_dict_section(self):
        spec = _valid_spec()
        spec["business_identity"] = "not a dict"
        errors = validate_creative_spec(spec)
        assert any("business_identity" in e and "must be a dict" in e for e in errors)


# ---------------------------------------------------------------------------
# Validation — section ordering
# ---------------------------------------------------------------------------
class TestSectionOrdering:
    def test_correct_ordering_valid(self):
        spec = _valid_spec()
        errors = validate_creative_spec(spec)
        # Should not have any section ordering errors
        section_errors = [e for e in errors if "sections" in e]
        assert section_errors == []

    def test_wrong_ordering_detected(self):
        spec = _valid_spec()
        spec["generation_directives"]["sections"] = ["about", "hero", "services", "contact", "cta"]
        errors = validate_creative_spec(spec)
        section_errors = [e for e in errors if "sections" in e]
        assert len(section_errors) > 0

    def test_missing_canonical_section(self):
        spec = _valid_spec()
        spec["generation_directives"]["sections"] = ["hero", "services", "about", "contact"]
        errors = validate_creative_spec(spec)
        assert any("cta" in e for e in errors)

    def test_sections_not_list(self):
        spec = _valid_spec()
        spec["generation_directives"]["sections"] = "hero,services"
        errors = validate_creative_spec(spec)
        assert any("sections" in e and "must be a list" in e for e in errors)


# ---------------------------------------------------------------------------
# Validation — claim policy
# ---------------------------------------------------------------------------
class TestClaimPolicyValidation:
    def test_valid_claim_policy(self):
        spec = _valid_spec()
        errors = validate_creative_spec(spec)
        claim_errors = [e for e in errors if "claim_policy" in e]
        assert claim_errors == []

    def test_empty_claim_policy(self):
        spec = _valid_spec()
        spec["content_policy"]["claim_policy"] = ""
        errors = validate_creative_spec(spec)
        assert any("claim_policy" in e for e in errors)

    def test_non_string_claim_policy(self):
        spec = _valid_spec()
        spec["content_policy"]["claim_policy"] = 42
        errors = validate_creative_spec(spec)
        assert any("claim_policy" in e for e in errors)


# ---------------------------------------------------------------------------
# Validation — forbidden claims
# ---------------------------------------------------------------------------
class TestForbiddenClaimsValidation:
    def test_no_forbidden_claims_in_valid_spec(self):
        spec = _valid_spec()
        errors = validate_creative_spec(spec)
        forbidden_errors = [e for e in errors if "forbidden claim" in e]
        assert forbidden_errors == []


# ---------------------------------------------------------------------------
# Validation — missing_data
# ---------------------------------------------------------------------------
class TestMissingDataValidation:
    def test_missing_data_list_valid(self):
        spec = _valid_spec()
        errors = validate_creative_spec(spec)
        md_errors = [e for e in errors if "missing_data" in e]
        assert md_errors == []

    def test_missing_data_not_list(self):
        spec = _valid_spec()
        spec["missing_data"] = "not a list"
        errors = validate_creative_spec(spec)
        assert any("missing_data" in e for e in errors)


# ---------------------------------------------------------------------------
# Validation — evaluation targets
# ---------------------------------------------------------------------------
class TestEvaluationTargetsValidation:
    def test_numeric_min_overall_score_valid(self):
        spec = _valid_spec()
        errors = validate_creative_spec(spec)
        et_errors = [e for e in errors if "min_overall_score" in e and "numeric" in e]
        assert et_errors == []

    def test_string_min_overall_score_invalid(self):
        spec = _valid_spec()
        spec["evaluation_targets"]["min_overall_score"] = "not_a_number"
        errors = validate_creative_spec(spec)
        assert any("min_overall_score" in e and "numeric" in e for e in errors)


# ---------------------------------------------------------------------------
# Validation — internal block
# ---------------------------------------------------------------------------
class TestInternalBlockValidation:
    def test_correct_internal_block(self):
        spec = _valid_spec()
        errors = validate_creative_spec(spec)
        internal_errors = [e for e in errors if "internal" in e]
        assert internal_errors == []

    def test_wrong_flag(self):
        spec = _valid_spec()
        spec["internal"]["flag"] = "wrong_flag"
        errors = validate_creative_spec(spec)
        assert any("flag" in e and "use_creative_spec" in e for e in errors)

    def test_wrong_schema_origin(self):
        spec = _valid_spec()
        spec["internal"]["schema_origin"] = "WRONG"
        errors = validate_creative_spec(spec)
        assert any("schema_origin" in e and "VNEXT-04" in e for e in errors)

    def test_missing_upstream_artifacts(self):
        spec = _valid_spec()
        spec["internal"]["upstream_artifacts"] = []
        errors = validate_creative_spec(spec)
        assert any("upstream_artifacts" in e for e in errors)

    def test_upstream_artifacts_not_list(self):
        spec = _valid_spec()
        spec["internal"]["upstream_artifacts"] = "not a list"
        errors = validate_creative_spec(spec)
        assert any("upstream_artifacts" in e for e in errors)
