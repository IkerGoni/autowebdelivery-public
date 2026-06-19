"""
VNEXT-04 — Creative Specification Models.

Defines the required-fields spec as constants/tuples for the creative_spec.json
artifact. This module is pure-constants: no builder logic, no I/O.

The creative_spec.json is the single source of truth before website generation,
merging verified facts (VNEXT-01), sellability/strategy (VNEXT-02), and
brand tone/trust/emotion (VNEXT-03) into a unified generation directive.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------
SCHEMA_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------
FEATURE_FLAG = "use_creative_spec"

# ---------------------------------------------------------------------------
# Required top-level keys in a valid creative_spec
# ---------------------------------------------------------------------------
REQUIRED_TOP_LEVEL_KEYS: tuple[str, ...] = (
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
)

# ---------------------------------------------------------------------------
# Required keys within business_identity
# ---------------------------------------------------------------------------
REQUIRED_BUSINESS_IDENTITY_KEYS: tuple[str, ...] = (
    "business_name",
    "category",
    "phone",
    "address",
    "hours",
)

# ---------------------------------------------------------------------------
# Required keys within brand_strategy
# ---------------------------------------------------------------------------
REQUIRED_BRAND_STRATEGY_KEYS: tuple[str, ...] = (
    "tone",
    "trust_posture",
    "emotional_goals",
    "color_direction",
    "differentiation",
)

# ---------------------------------------------------------------------------
# Required keys within content_policy
# ---------------------------------------------------------------------------
REQUIRED_CONTENT_POLICY_KEYS: tuple[str, ...] = (
    "forbidden_claims",
    "missing_data_handling",
    "claim_policy",
)

# ---------------------------------------------------------------------------
# Required keys within generation_directives
# ---------------------------------------------------------------------------
REQUIRED_GENERATION_DIRECTIVES_KEYS: tuple[str, ...] = (
    "template_family",
    "sections",
    "required_cta",
    "mobile_first",
)

# ---------------------------------------------------------------------------
# Required keys within evaluation_targets
# ---------------------------------------------------------------------------
REQUIRED_EVALUATION_TARGETS_KEYS: tuple[str, ...] = (
    "min_overall_score",
    "hard_block_on",
)

# ---------------------------------------------------------------------------
# Required keys within internal
# ---------------------------------------------------------------------------
REQUIRED_INTERNAL_KEYS: tuple[str, ...] = (
    "flag",
    "schema_origin",
    "upstream_artifacts",
)

# ---------------------------------------------------------------------------
# Explicit blocklist of claim categories that MUST NEVER appear in public copy.
# Mirrors business_profile.py, market_profile.py, brand_reconstruction.py.
# ---------------------------------------------------------------------------
FORBIDDEN_PUBLIC_CLAIMS: tuple[str, ...] = (
    "years_in_business",
    "awards",
    "licenses",
    "insurance",
    "certifications",
    "staff_credentials",
    "testimonials",
    "guarantees",
    "superlatives",
)

# ---------------------------------------------------------------------------
# Section ordering strategy for generation_directives.sections.
# Ordered by strategic priority: hero (first impression) → cta (final conversion).
# ---------------------------------------------------------------------------
CANONICAL_SECTION_ORDER: tuple[str, ...] = (
    "hero",
    "services",
    "about",
    "contact",
    "cta",
)

# ---------------------------------------------------------------------------
# Niche-specific additional sections appended after the canonical sections.
# Each key is a lowercase business category; the value is a tuple of extra
# section names that supplement the standard sections for that vertical.
# ---------------------------------------------------------------------------
NICHE_SECTIONS: dict[str, tuple[str, ...]] = {
    "healthcare": (
        "insurance_accepted",
        "telehealth",
        "compliance_notice",
    ),
    "legal": (
        "practice_areas",
        "case_results",
        "free_consultation",
    ),
    "restaurant": (
        "menu",
        "reservations",
        "hours_location",
    ),
    "trades": (
        "service_areas",
        "licenses_insurance",
        "free_estimates",
    ),
}

# ---------------------------------------------------------------------------
# Upstream artifacts that the creative_spec depends on
# ---------------------------------------------------------------------------
UPSTREAM_ARTIFACTS: tuple[str, ...] = (
    "business_profile.json",
    "market_profile.json",
    "brand_profile.json",
    "competitor_profile.json",
)
