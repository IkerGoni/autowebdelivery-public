"""Unit tests for VNEXT-04 — Creative Specification Models."""

from __future__ import annotations

from packages.creative.creative_spec_models import (
    CANONICAL_SECTION_ORDER,
    FEATURE_FLAG,
    FORBIDDEN_PUBLIC_CLAIMS,
    REQUIRED_BRAND_STRATEGY_KEYS,
    REQUIRED_BUSINESS_IDENTITY_KEYS,
    REQUIRED_CONTENT_POLICY_KEYS,
    REQUIRED_EVALUATION_TARGETS_KEYS,
    REQUIRED_GENERATION_DIRECTIVES_KEYS,
    REQUIRED_INTERNAL_KEYS,
    REQUIRED_TOP_LEVEL_KEYS,
    SCHEMA_VERSION,
    UPSTREAM_ARTIFACTS,
)


class TestSchemaVersion:
    def test_schema_version_is_string(self):
        assert isinstance(SCHEMA_VERSION, str)
        assert SCHEMA_VERSION == "1.0.0"

    def test_schema_version_format(self):
        parts = SCHEMA_VERSION.split(".")
        assert len(parts) == 3
        for part in parts:
            assert part.isdigit()


class TestFeatureFlag:
    def test_feature_flag_name(self):
        assert FEATURE_FLAG == "use_creative_spec"


class TestRequiredTopLevelKeys:
    def test_all_required_keys_defined(self):
        expected = {
            "schema_version",
            "run_id",
            "business_slug",
            "generated_at",
            "business_identity",
            "brand_strategy",
            "sellability",
            "content_policy",
            "generation_directives",
            "evaluation_targets",
            "missing_data",
            "internal",
        }
        assert set(REQUIRED_TOP_LEVEL_KEYS) == expected

    def test_required_keys_are_tuple(self):
        assert isinstance(REQUIRED_TOP_LEVEL_KEYS, tuple)


class TestRequiredBusinessIdentityKeys:
    def test_business_identity_keys(self):
        expected = {"business_name", "category", "phone", "address", "hours"}
        assert set(REQUIRED_BUSINESS_IDENTITY_KEYS) == expected


class TestRequiredBrandStrategyKeys:
    def test_brand_strategy_keys(self):
        expected = {"tone", "trust_posture", "emotional_goals", "color_direction", "differentiation"}
        assert set(REQUIRED_BRAND_STRATEGY_KEYS) == expected


class TestRequiredContentPolicyKeys:
    def test_content_policy_keys(self):
        expected = {"forbidden_claims", "missing_data_handling", "claim_policy"}
        assert set(REQUIRED_CONTENT_POLICY_KEYS) == expected


class TestRequiredGenerationDirectivesKeys:
    def test_generation_directives_keys(self):
        expected = {"template_family", "sections", "required_cta", "mobile_first"}
        assert set(REQUIRED_GENERATION_DIRECTIVES_KEYS) == expected


class TestRequiredEvaluationTargetsKeys:
    def test_evaluation_targets_keys(self):
        expected = {"min_overall_score", "hard_block_on"}
        assert set(REQUIRED_EVALUATION_TARGETS_KEYS) == expected


class TestRequiredInternalKeys:
    def test_internal_keys(self):
        expected = {"flag", "schema_origin", "upstream_artifacts"}
        assert set(REQUIRED_INTERNAL_KEYS) == expected


class TestForbiddenPublicClaims:
    def test_forbidden_claims_count(self):
        assert len(FORBIDDEN_PUBLIC_CLAIMS) == 9

    def test_forbidden_claims_content(self):
        expected = {
            "years_in_business",
            "awards",
            "licenses",
            "insurance",
            "certifications",
            "staff_credentials",
            "testimonials",
            "guarantees",
            "superlatives",
        }
        assert set(FORBIDDEN_PUBLIC_CLAIMS) == expected

    def test_forbidden_claims_are_tuple(self):
        assert isinstance(FORBIDDEN_PUBLIC_CLAIMS, tuple)


class TestCanonicalSectionOrder:
    def test_section_order(self):
        assert CANONICAL_SECTION_ORDER == ("hero", "services", "about", "contact", "cta")

    def test_section_order_is_tuple(self):
        assert isinstance(CANONICAL_SECTION_ORDER, tuple)

    def test_five_sections(self):
        assert len(CANONICAL_SECTION_ORDER) == 5


class TestUpstreamArtifacts:
    def test_upstream_artifacts(self):
        expected = {
            "business_profile.json",
            "market_profile.json",
            "brand_profile.json",
            "competitor_profile.json",
        }
        assert set(UPSTREAM_ARTIFACTS) == expected

    def test_upstream_artifacts_are_tuple(self):
        assert isinstance(UPSTREAM_ARTIFACTS, tuple)
