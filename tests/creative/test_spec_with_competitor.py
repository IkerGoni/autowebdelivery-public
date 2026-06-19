"""Unit tests for competitor_profile integration into creative_spec (VNEXT-10)."""

from __future__ import annotations

import tempfile

from packages.creative.creative_spec_builder import build_creative_spec


def test_creative_spec_without_competitor_profile():
    """Build spec without competitor profile should have empty differentiation list."""
    with tempfile.TemporaryDirectory() as _tmp:
        run_id = "test"
        slug = "test-business"

        business_profile = {
            "schema_version": "1.0.0",
            "run_id": run_id,
            "business_slug": slug,
            "facts": {"business_name": "Test Business"},
            "overview": {"industry": "Testing"},
            "location": {"region": "Local"},
        }

        market_profile = {
            "schema_version": "1.0.0",
            "run_id": run_id,
            "market_slug": f"{slug}-market",
            "demographics": {"median_income": 50000},
            "sentiment": {"overall": 0.7},
            "competitive_landscape": {},
        }

        brand_profile = {
            "schema_version": "1.0.0",
            "run_id": run_id,
            "brand_slug": slug,
            "identity": {"tone": "professional"},
        }

        config = {"vnext_flags": {"use_creative_spec": True}}

        spec = build_creative_spec(
            business_profile, market_profile, brand_profile, config, run_id=run_id,
            competitor_profile=None,
        )

        brand_strategy = spec.get("brand_strategy", {})
        assert "differentiation" in brand_strategy
        assert brand_strategy["differentiation"] == []


def test_creative_spec_with_competitor_profile():
    """Build spec with competitor profile should include differentiation content."""
    with tempfile.TemporaryDirectory() as _tmp:
        run_id = "test"
        slug = "test-business"

        business_profile = {
            "schema_version": "1.0.0",
            "run_id": run_id,
            "business_slug": slug,
            "facts": {"business_name": "Test Business"},
            "overview": {"industry": "Testing"},
            "location": {"region": "Local"},
        }

        market_profile = {
            "schema_version": "1.0.0",
            "run_id": run_id,
            "market_slug": f"{slug}-market",
            "demographics": {"median_income": 50000},
            "sentiment": {"overall": 0.7},
            "competitive_landscape": {},
        }

        brand_profile = {
            "schema_version": "1.0.0",
            "run_id": run_id,
            "brand_slug": slug,
            "identity": {"tone": "professional"},
        }

        competitor_profile = {
            "schema_version": "1.0.0",
            "run_id": run_id,
            "business_slug": slug,
            "strategic_differentiation": {
                "opportunities": [
                    "Unique local expertise",
                    "Personalized service",
                    "24/7 availability",
                ],
            },
        }

        config = {"vnext_flags": {"use_creative_spec": True}}

        spec = build_creative_spec(
            business_profile, market_profile, brand_profile, config, run_id=run_id,
            competitor_profile=competitor_profile,
        )

        brand_strategy = spec.get("brand_strategy", {})
        assert "differentiation" in brand_strategy
        diff = brand_strategy["differentiation"]
        assert isinstance(diff, list)
        assert len(diff) == 3
        assert "Unique local expertise" in diff


def test_creative_spec_with_empty_competitor_profile():
    """Build spec with empty competitor profile should have empty differentiation list."""
    with tempfile.TemporaryDirectory() as _tmp:
        run_id = "test"
        slug = "test-business"

        business_profile = {
            "schema_version": "1.0.0",
            "run_id": run_id,
            "business_slug": slug,
            "facts": {"business_name": "Test Business"},
        }

        market_profile = {
            "schema_version": "1.0.0",
            "run_id": run_id,
            "market_slug": f"{slug}-market",
            }

        brand_profile = {
            "schema_version": "1.0.0",
            "run_id": run_id,
            "brand_slug": slug,
        }

        # competitor_profile with empty strategic_differentiation
        competitor_profile = {
            "schema_version": "1.0.0",
            "run_id": run_id,
            "business_slug": slug,
            "strategic_differentiation": {},
        }

        config = {"vnext_flags": {"use_creative_spec": True}}

        spec = build_creative_spec(
            business_profile, market_profile, brand_profile, config, run_id=run_id,
            competitor_profile=competitor_profile,
        )

        brand_strategy = spec.get("brand_strategy", {})
        assert brand_strategy["differentiation"] == []