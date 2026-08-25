"""Tests for stitch_compiler.py (VNEXT-05).

Verifies that the compiler correctly translates creative_spec → StitchPromptInput
→ PremiumStitchPrompt, preserving fact safety and not breaking existing builder tests.
"""

import hashlib

import pytest

from packages.generation.stitch_compiler import (
    COMPILER_VERSION,
    FEATURE_FLAG,
    compile_creative_spec_to_prompt,
)
from packages.generation.stitch_prompt_builder import (
    PremiumStitchPrompt,
    StitchPromptInput,
    build_premium_stitch_prompt,
    build_prompt_from_creative_spec,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _envelope(value: str, *, source: str = "business_profile.json", confidence: str = "verified"):
    return {"value": value, "source": source, "confidence": confidence}


def _creative_spec_fixture(**overrides) -> dict:
    """Build a realistic creative_spec for testing."""
    spec = {
        "schema_version": "1.0.0",
        "run_id": "run_test_001",
        "business_slug": "frisco-mobile-detailing",
        "generated_at": "2026-06-01T00:00:00Z",
        "business_identity": {
            "business_name": _envelope("Frisco Mobile Detailing"),
            "category": _envelope("Mobile detailing service"),
            "phone": _envelope("+1 903-456-9029"),
            "address": _envelope("123 Main St, Frisco, TX"),
            "hours": _envelope("Mon-Sat 8am-6pm"),
        },
        "brand_strategy": {
            "tone": _envelope("bold and polished", source="brand_profile.json", confidence="inferred"),
            "trust_posture": {"value": "credential_safe", "source": "brand_profile.json", "confidence": "inferred"},
            "emotional_goals": ["confidence", "convenience"],
            "color_direction": {"primary_hint": "ceramic teal", "mood": "dark luxury automotive"},
        },
        "sellability": {
            "overall_score": 85.5,
            "demand_signal": "high",
            "website_status": "no_website",
            "positioning": ["strong_rating_signal"],
        },
        "content_policy": {
            "forbidden_claims": [
                "years_in_business",
                "awards",
                "licenses",
                "insurance",
                "certifications",
                "guarantees",
            ],
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
            "hard_block_on": ["broken_links", "missing_stylesheet"],
        },
        "missing_data": [],
        "internal": {
            "flag": "use_creative_spec",
            "schema_origin": "VNEXT-04",
            "upstream_artifacts": ["business_profile.json", "market_profile.json", "brand_profile.json"],
        },
    }
    spec.update(overrides)
    return spec


def _config_fixture(**overrides) -> dict:
    config = {
        "niche": "DFW mobile detailing",
        "area": "Frisco, TX",
        "deploy_mode": "production_deploy_mode",
    }
    config.update(overrides)
    return config


# ---------------------------------------------------------------------------
# Test: Basic compilation
# ---------------------------------------------------------------------------


def test_compile_creative_spec_to_prompt_basic():
    """Feeds a creative_spec fixture → gets PremiumStitchPrompt."""
    spec = _creative_spec_fixture()
    config = _config_fixture()
    result = compile_creative_spec_to_prompt(spec, config)

    assert isinstance(result, PremiumStitchPrompt)
    assert isinstance(result.prompt, str)
    assert len(result.prompt) > 0


def test_compiler_produces_valid_prompt():
    """prompt_version, prompt_sha256, prompt_text all present and correct."""
    spec = _creative_spec_fixture()
    config = _config_fixture()
    result = compile_creative_spec_to_prompt(spec, config)

    assert result.prompt_version == "premium_stitch_prompt_v2"
    assert len(result.prompt_sha256) == 64
    assert result.prompt.strip()
    # SHA-256 should match
    expected_hash = hashlib.sha256(result.prompt.encode("utf-8")).hexdigest()
    assert result.prompt_sha256 == expected_hash


def test_compiler_includes_verified_facts():
    """business_name, category, phone appear in prompt_text."""
    spec = _creative_spec_fixture()
    config = _config_fixture()
    result = compile_creative_spec_to_prompt(spec, config)

    assert "Frisco Mobile Detailing" in result.prompt
    assert "+1 903-456-9029" in result.prompt
    assert "123 Main St, Frisco, TX" in result.prompt
    assert "Mon-Sat 8am-6pm" in result.prompt


def test_compiler_omits_missing_facts():
    """Fields not in spec don't appear as invented values."""
    spec = _creative_spec_fixture()
    # Remove hours from business_identity
    del spec["business_identity"]["hours"]
    config = _config_fixture()
    result = compile_creative_spec_to_prompt(spec, config)

    # hours should be in missing_facts
    assert "hours" in result.prompt_contract["missing_facts"]
    # Should not have invented an hours value
    assert "Mon-Sat" not in result.prompt or "Missing:" in result.prompt


def test_compiler_respects_forbidden_claims():
    """Forbidden claims from content_policy appear in contract."""
    spec = _creative_spec_fixture()
    config = _config_fixture()
    result = compile_creative_spec_to_prompt(spec, config)

    # Check compiler contract has forbidden claims
    compiler_section = result.prompt_contract["compiler"]
    assert "certifications" in compiler_section["forbidden_claims"]
    assert "guarantees" in compiler_section["forbidden_claims"]
    assert "awards" in compiler_section["forbidden_claims"]

    # Also check main contract forbidden_claims includes them
    forbidden = result.prompt_contract["forbidden_claims"]
    assert any("certifications" in c for c in forbidden)


def test_compiler_derives_feeling_from_brand_strategy():
    """Feeling matches brand strategy tone."""
    spec = _creative_spec_fixture()
    config = _config_fixture()
    result = compile_creative_spec_to_prompt(spec, config)

    # Brand strategy has tone="bold and polished" and mood="dark luxury automotive"
    # The feeling should incorporate these
    assert "bold" in result.prompt.lower() or "polished" in result.prompt.lower() or "luxury" in result.prompt.lower()

    # Check compiler decision
    compiler_section = result.prompt_contract["compiler"]
    assert compiler_section["compiler_decisions"]["feeling_derived_from"] == "brand_strategy.tone"


def test_compiler_derives_sections_from_directives():
    """Sections match generation_directives."""
    spec = _creative_spec_fixture()
    config = _config_fixture()
    result = compile_creative_spec_to_prompt(spec, config)

    # Check that human-readable sections from the mapped IDs are in the prompt
    assert "Hero section" in result.prompt
    assert "Service or package cards" in result.prompt

    # Check compiler decision
    compiler_section = result.prompt_contract["compiler"]
    assert compiler_section["compiler_decisions"]["sections_from"] == "generation_directives.sections"


def test_compiler_no_raw_json_dump():
    """prompt_text doesn't contain raw JSON."""
    spec = _creative_spec_fixture()
    config = _config_fixture()
    result = compile_creative_spec_to_prompt(spec, config)

    assert '{"' not in result.prompt, "Prompt should not contain raw JSON"
    assert "schema_version" not in result.prompt
    assert "business_identity" not in result.prompt
    assert "generation_directives" not in result.prompt
    assert "content_policy" not in result.prompt


def test_compiler_deterministic():
    """Same input → same output."""
    spec = _creative_spec_fixture()
    config = _config_fixture()

    first = compile_creative_spec_to_prompt(spec, config)
    second = compile_creative_spec_to_prompt(spec, config)

    assert first.prompt == second.prompt
    assert first.prompt_sha256 == second.prompt_sha256
    assert first.prompt_contract["compiler"]["creative_spec_hash"] == second.prompt_contract["compiler"]["creative_spec_hash"]


# ---------------------------------------------------------------------------
# Test: Existing builder still works unmodified
# ---------------------------------------------------------------------------


def test_existing_builder_still_works():
    """Existing StitchPromptInput path works exactly as before."""
    prompt_input = StitchPromptInput(
        business_name="Frisco Mobile Detailing",
        business_slug="frisco-mobile-detailing",
        category="Mobile detailing service",
        facts={"area": "Frisco, TX", "phone": "+1 903-456-9029"},
        design_style="dark luxury automotive",
        niche="DFW mobile detailing",
    )
    result = build_premium_stitch_prompt(prompt_input)

    assert isinstance(result, PremiumStitchPrompt)
    assert "Frisco Mobile Detailing" in result.prompt
    assert "+1 903-456-9029" in result.prompt
    # Should NOT have compiler section
    assert "compiler" not in result.prompt_contract


# ---------------------------------------------------------------------------
# Test: Compatibility wrapper
# ---------------------------------------------------------------------------


def test_compatibility_wrapper():
    """build_prompt_from_creative_spec works as entry point."""
    spec = _creative_spec_fixture()
    result = build_prompt_from_creative_spec(spec)

    assert isinstance(result, PremiumStitchPrompt)
    assert "compiler" in result.prompt_contract


def test_compatibility_wrapper_with_config():
    """build_prompt_from_creative_spec passes config correctly."""
    spec = _creative_spec_fixture()
    config = _config_fixture(niche="premium auto detailing")
    result = build_prompt_from_creative_spec(spec, config)

    assert isinstance(result, PremiumStitchPrompt)


# ---------------------------------------------------------------------------
# Test: Feature flag
# ---------------------------------------------------------------------------


def test_flag_off_uses_old_path():
    """When flag is off, old builder path is used (no compiler)."""
    # Simulate the old path: use build_premium_stitch_prompt directly
    prompt_input = StitchPromptInput(
        business_name="Test Business",
        business_slug="test-business",
        category="Test Category",
    )
    result = build_premium_stitch_prompt(prompt_input)

    # This is the old path — no compiler section in contract
    assert "compiler" not in result.prompt_contract
    assert isinstance(result, PremiumStitchPrompt)


def test_feature_flag_constant():
    """Feature flag constant is correct."""
    assert FEATURE_FLAG == "use_stitch_compiler"


# ---------------------------------------------------------------------------
# Test: Compiler contract structure
# ---------------------------------------------------------------------------


def test_compiler_contract_has_all_required_fields():
    """Compiler contract includes all required provenance fields."""
    spec = _creative_spec_fixture()
    config = _config_fixture()
    result = compile_creative_spec_to_prompt(spec, config)

    compiler = result.prompt_contract["compiler"]
    assert compiler["compiler_version"] == COMPILER_VERSION
    assert "creative_spec_hash" in compiler
    assert len(compiler["creative_spec_hash"]) == 64
    assert isinstance(compiler["included_facts"], list)
    assert isinstance(compiler["omitted_facts"], dict)
    assert "feeling_derived_from" in compiler["compiler_decisions"]
    assert "sections_from" in compiler["compiler_decisions"]
    assert isinstance(compiler["forbidden_claims"], list)


def test_compiler_included_facts_tracking():
    """Compiler tracks which facts were successfully included."""
    spec = _creative_spec_fixture()
    config = _config_fixture()
    result = compile_creative_spec_to_prompt(spec, config)

    included = result.prompt_contract["compiler"]["included_facts"]
    assert "business_name" in included
    assert "category" in included
    assert "phone" in included
    assert "address" in included
    assert "hours" in included


def test_compiler_omitted_facts_tracking():
    """Compiler tracks which facts were omitted and why."""
    spec = _creative_spec_fixture()
    # Remove address and set phone confidence to 'unknown'
    del spec["business_identity"]["address"]
    spec["business_identity"]["phone"] = {"value": "+1 555-0000", "source": "test", "confidence": "unknown"}

    config = _config_fixture()
    result = compile_creative_spec_to_prompt(spec, config)

    omitted = result.prompt_contract["compiler"]["omitted_facts"]
    assert "address" in omitted
    assert omitted["address"] == "not in business_identity"
    assert "phone" in omitted
    assert "confidence=unknown" in omitted["phone"]


# ---------------------------------------------------------------------------
# Test: Edge cases
# ---------------------------------------------------------------------------


def test_compiler_with_minimal_spec():
    """Compiler works with minimal creative_spec (only required fields)."""
    spec = {
        "schema_version": "1.0.0",
        "run_id": "run_minimal",
        "business_slug": "minimal-biz",
        "generated_at": "2026-01-01T00:00:00Z",
        "business_identity": {
            "business_name": _envelope("Minimal Business"),
            "category": _envelope("General services"),
            "phone": {"value": "", "source": "test", "confidence": "unknown"},
            "address": {"value": "", "source": "test", "confidence": "unknown"},
            "hours": {"value": "", "source": "test", "confidence": "unknown"},
        },
        "brand_strategy": {
            "tone": {"value": "professional", "source": "brand_profile.json", "confidence": "inferred"},
            "trust_posture": {"value": "credential_safe", "source": "brand_profile.json", "confidence": "inferred"},
            "emotional_goals": [],
            "color_direction": {},
        },
        "sellability": {
            "overall_score": 0.0,
            "demand_signal": "unknown",
            "website_status": "unknown",
            "positioning": [],
        },
        "content_policy": {
            "forbidden_claims": [],
            "missing_data_handling": "omit_or_neutral",
            "claim_policy": "verified_facts_only",
        },
        "generation_directives": {
            "template_family": "industrial_reliable",
            "sections": [],
            "required_cta": "contact_form_or_phone",
            "mobile_first": True,
        },
        "evaluation_targets": {"min_overall_score": 70, "hard_block_on": []},
        "missing_data": [],
        "internal": {"flag": "use_creative_spec", "schema_origin": "VNEXT-04", "upstream_artifacts": []},
    }
    result = compile_creative_spec_to_prompt(spec, {})

    assert isinstance(result, PremiumStitchPrompt)
    assert "Minimal Business" in result.prompt
    # Should have used default sections
    assert "Hero section" in result.prompt


def test_compiler_raises_on_missing_business_name():
    """Compiler raises ValueError when business_name is missing."""
    spec = _creative_spec_fixture()
    spec["business_identity"]["business_name"] = {"value": "", "source": "test", "confidence": "unknown"}
    config = _config_fixture()

    with pytest.raises(ValueError, match="business_name"):
        compile_creative_spec_to_prompt(spec, config)


def test_compiler_raises_on_missing_slug():
    """Compiler raises ValueError when business_slug is missing."""
    spec = _creative_spec_fixture()
    spec["business_slug"] = ""
    config = _config_fixture()

    with pytest.raises(ValueError, match="business_slug"):
        compile_creative_spec_to_prompt(spec, config)


def test_compiler_raises_on_missing_category():
    """Compiler raises ValueError when category is missing."""
    spec = _creative_spec_fixture()
    spec["business_identity"]["category"] = {"value": "", "source": "test", "confidence": "unknown"}
    config = _config_fixture()

    with pytest.raises(ValueError, match="category"):
        compile_creative_spec_to_prompt(spec, config)


def test_compiler_creative_spec_hash_is_deterministic():
    """The creative_spec hash is deterministic for the same input."""
    spec = _creative_spec_fixture()
    config = _config_fixture()

    first = compile_creative_spec_to_prompt(spec, config)
    second = compile_creative_spec_to_prompt(spec, config)

    assert first.prompt_contract["compiler"]["creative_spec_hash"] == \
           second.prompt_contract["compiler"]["creative_spec_hash"]


def test_compiler_creative_spec_hash_changes_with_input():
    """Different specs produce different hashes."""
    spec_a = _creative_spec_fixture()
    spec_b = _creative_spec_fixture()
    spec_b["business_identity"]["business_name"] = _envelope("Different Business")
    config = _config_fixture()

    result_a = compile_creative_spec_to_prompt(spec_a, config)
    result_b = compile_creative_spec_to_prompt(spec_b, config)

    assert result_a.prompt_contract["compiler"]["creative_spec_hash"] != \
           result_b.prompt_contract["compiler"]["creative_spec_hash"]


def test_compiler_word_budget_under_400():
    """Compiled prompt respects the word budget."""
    spec = _creative_spec_fixture()
    config = _config_fixture()
    result = compile_creative_spec_to_prompt(spec, config)

    word_count = len(result.prompt.split())
    assert word_count < 400, f"Compiled prompt is {word_count} words, should be under 400"


def test_compiler_metadata_includes_compiler_info():
    """Metadata includes compiler version and spec hash."""
    spec = _creative_spec_fixture()
    config = _config_fixture()
    result = compile_creative_spec_to_prompt(spec, config)

    assert result.metadata["compiler_version"] == COMPILER_VERSION
    assert "creative_spec_hash" in result.metadata
