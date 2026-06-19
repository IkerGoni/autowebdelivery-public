"""Tests for niche-specific sections in creative_spec_models and builder.

Verifies that NICHE_SECTIONS dict is correctly defined and that the
creative_spec builder appends niche-specific sections based on business category.
"""
from __future__ import annotations

import pytest

from packages.creative.creative_spec_builder import build_creative_spec
from packages.creative.creative_spec_models import (
    CANONICAL_SECTION_ORDER,
    NICHE_SECTIONS,
)


class TestNicheSectionsDict:
    """NICHE_SECTIONS must be well-formed."""

    def test_is_dict(self):
        assert isinstance(NICHE_SECTIONS, dict)

    def test_contains_known_categories(self):
        assert "healthcare" in NICHE_SECTIONS
        assert "legal" in NICHE_SECTIONS
        assert "restaurant" in NICHE_SECTIONS
        assert "trades" in NICHE_SECTIONS

    def test_each_value_is_tuple(self):
        for key, val in NICHE_SECTIONS.items():
            assert isinstance(val, tuple), f"{key!r} value must be a tuple"

    def test_each_value_has_at_least_one_section(self):
        for key, val in NICHE_SECTIONS.items():
            assert len(val) > 0, f"{key!r} has empty sections tuple"

    def test_no_duplicate_sections_within_niche(self):
        for key, val in NICHE_SECTIONS.items():
            assert len(val) == len(set(val)), f"{key!r} has duplicate sections"


class TestNicheSectionsInSpec:
    """Niche-specific sections should appear in the built creative_spec."""

    @pytest.mark.parametrize(
        "category,expected_sections",
        [
            ("Healthcare", ["insurance_accepted", "telehealth", "compliance_notice"]),
            ("Legal", ["practice_areas", "case_results", "free_consultation"]),
            ("Restaurant", ["menu", "reservations", "hours_location"]),
            ("Trades", ["service_areas", "licenses_insurance", "free_estimates"]),
        ],
    )
    def test_category_includes_niche_sections(self, category, expected_sections):
        spec = build_creative_spec(
            _business_profile(business_name="Test Biz", category=category),
            _market_profile(),
            _brand_profile(),
            _BASE_CONFIG,
            run_id="r-test-niche",
        )
        sections = spec["generation_directives"]["sections"]
        for es in expected_sections:
            assert es in sections, (
                f"Expected section {es!r} for category {category!r}, "
                f"got sections: {sections}"
            )
        # Canonical sections must still be present
        for cs in CANONICAL_SECTION_ORDER:
            assert cs in sections, (
                f"Canonical section {cs!r} missing for category {category!r}, "
                f"got sections: {sections}"
            )

    def test_unknown_category_no_extra_sections(self):
        """An unknown/unlisted category should have only canonical sections."""
        spec = build_creative_spec(
            _business_profile(business_name="Unknown Co", category="Plumbing"),
            _market_profile(),
            _brand_profile(),
            _BASE_CONFIG,
            run_id="r-test-unknown",
        )
        sections = spec["generation_directives"]["sections"]
        assert list(sections) == list(CANONICAL_SECTION_ORDER), (
            f"Unknown category should have only canonical sections, "
            f"got: {sections}"
        )

    def test_empty_category_no_extra_sections(self):
        """An empty category should have only canonical sections."""
        spec = build_creative_spec(
            _business_profile(business_name="No Cat Co", category=""),
            _market_profile(),
            _brand_profile(),
            _BASE_CONFIG,
            run_id="r-test-empty-cat",
        )
        sections = spec["generation_directives"]["sections"]
        assert list(sections) == list(CANONICAL_SECTION_ORDER), (
            f"Empty category should have only canonical sections, "
            f"got: {sections}"
        )

    def test_missing_category_no_extra_sections(self):
        """A missing category field should result in only canonical sections."""

        bp = _business_profile()
        del bp["verified_facts"]["category"]
        spec = build_creative_spec(
            bp,
            _market_profile(),
            _brand_profile(),
            _BASE_CONFIG,
            run_id="r-test-no-cat",
        )
        sections = spec["generation_directives"]["sections"]
        assert list(sections) == list(CANONICAL_SECTION_ORDER), (
            f"Missing category should have only canonical sections, "
            f"got: {sections}"
        )

    def test_niche_order_after_canonical(self):
        """Niche-specific sections should appear after canonical sections."""
        spec = build_creative_spec(
            _business_profile(business_name="Health Co", category="Healthcare"),
            _market_profile(),
            _brand_profile(),
            _BASE_CONFIG,
            run_id="r-test-order",
        )
        sections = spec["generation_directives"]["sections"]
        canonical_list = list(CANONICAL_SECTION_ORDER)
        max_canonical_idx = max(sections.index(cs) for cs in canonical_list)
        for niche_section in NICHE_SECTIONS["healthcare"]:
            assert sections.index(niche_section) > max_canonical_idx, (
                f"Niche section {niche_section!r} should appear after all "
                f"canonical sections, got order: {sections}"
            )


# ---------------------------------------------------------------------------
# Test helpers (mirrored from test_creative_spec_validator.py)
# ---------------------------------------------------------------------------


def _business_profile(**overrides):
    category = overrides.pop("category", "Auto Detailing Service")
    business_name = overrides.pop("business_name", "North Dallas Mobile Detailing")
    bp = {
        "schema_version": "1.0.0",
        "run_id": "r1",
        "business_slug": "test-biz-slug",
        "generated_at": "2027-03-15T00:00:00Z",
        "verified_facts": {
            "business_name": {
                "value": business_name,
                "source": "selected_for_preview.json",
                "confidence": "verified",
            },
            "category": {
                "value": category,
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
        "business_slug": "test-biz-slug",
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
        "business_slug": "test-biz-slug",
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
