"""Tests for the Stitch prompt builder (v2 — concise, structured prompts)."""

import pytest

from packages.generation.stitch_prompt_builder import (
    PROMPT_VERSION,
    StitchPromptInput,
    build_premium_stitch_prompt,
    build_public_safe_bi_context,
)


def _input(**overrides):
    values = {
        "business_name": "Frisco Mobile Detailing",
        "business_slug": "frisco-mobile-detailing",
        "category": "Mobile detailing service",
        "facts": {"area": "Frisco, TX", "rating": "4.8", "review_count": "108"},
        "public_safe_fields": {},
        "copy_inputs": {"cta": "Request a quote"},
        "visual_profile": {"preset_id": "industrial_reliable", "accent": "ceramic teal"},
        "design_style": "dark luxury automotive detailing, obsidian and ceramic teal",
        "niche": "DFW mobile detailing",
        "target_customer": "vehicle owners who want convenient mobile detailing",
    }
    values.update(overrides)
    return StitchPromptInput(**values)


# ---------------------------------------------------------------------------
# Core prompt structure tests
# ---------------------------------------------------------------------------


def test_prompt_includes_business_name_and_verified_facts():
    built = build_premium_stitch_prompt(_input(facts={"phone": "+1 903-456-9029", "area": "Frisco, TX"}))
    assert "Frisco Mobile Detailing" in built.prompt
    assert "+1 903-456-9029" in built.prompt
    assert "Frisco, TX" in built.prompt
    assert built.prompt_contract["verified_facts"]["phone"] == "+1 903-456-9029"
    assert built.prompt_contract["business_slug"] == "frisco-mobile-detailing"


def test_prompt_is_concise_under_400_words():
    built = build_premium_stitch_prompt(_input())
    word_count = len(built.prompt.split())
    assert word_count < 400, f"Prompt is {word_count} words, should be under 400"


def test_prompt_has_numbered_sections():
    built = build_premium_stitch_prompt(_input())
    assert "1." in built.prompt
    assert "2." in built.prompt
    assert "Hero section" in built.prompt
    assert "Service or package cards" in built.prompt


def test_prompt_includes_platform_direction():
    built = build_premium_stitch_prompt(_input())
    assert "desktop-first" in built.prompt
    assert "responsive" in built.prompt.lower()


def test_prompt_has_premium_output_instruction():
    built = build_premium_stitch_prompt(_input())
    assert "production-ready HTML" in built.prompt
    assert "inline CSS" in built.prompt


def test_prompt_no_raw_json_dumps():
    """The prompt should never contain raw JSON objects."""
    built = build_premium_stitch_prompt(_input(
        visual_profile={"preset_id": "industrial_reliable", "accent": "ceramic teal"},
        copy_inputs={"cta": "Request a quote", "slots": {"hero": "Book Now"}},
    ))
    assert '{"' not in built.prompt, "Prompt should not contain raw JSON"
    assert "preset_id" not in built.prompt, "Internal keys should not appear in prompt"


def test_prompt_no_internal_section_identifiers():
    """Section names in prompt should be human-readable, not snake_case code IDs."""
    built = build_premium_stitch_prompt(_input())
    # These internal IDs should NOT appear in the prompt text
    assert "hero_with_above_fold_cta" not in built.prompt
    assert "footer_with_verified_contact_only" not in built.prompt
    assert "service_or_package_cards" not in built.prompt


# ---------------------------------------------------------------------------
# Fact safety tests
# ---------------------------------------------------------------------------


def test_missing_phone_and_hours_use_neutral_language():
    built = build_premium_stitch_prompt(_input(facts={"area": "Plano, TX"}))
    assert "Missing:" in built.prompt
    assert "phone" in built.prompt_contract["missing_facts"]
    assert "hours" in built.prompt_contract["missing_facts"]
    assert "Request a quote" in built.prompt
    assert "555" not in built.prompt
    # Should NOT have fake contact details
    assert "fake" not in built.prompt.lower() or "do not invent" in built.prompt.lower()


def test_prompt_hash_is_stable_and_changes_with_input():
    first = build_premium_stitch_prompt(_input())
    second = build_premium_stitch_prompt(_input())
    changed = build_premium_stitch_prompt(_input(business_name="On Time Mobile Detailing"))

    assert first.prompt_sha256 == second.prompt_sha256
    assert first.prompt_sha256 != changed.prompt_sha256
    assert first.prompt_contract["prompt_sha256"] == first.prompt_sha256


def test_prompt_version_is_v2():
    assert PROMPT_VERSION == "premium_stitch_prompt_v2"


def test_metadata_includes_word_count():
    built = build_premium_stitch_prompt(_input())
    assert "word_count" in built.metadata
    assert built.metadata["word_count"] > 0
    assert built.metadata["word_count"] == len(built.prompt.split())


# ---------------------------------------------------------------------------
# BI context safety
# ---------------------------------------------------------------------------


def test_public_safe_bi_context_maps_hints_without_raw_keys():
    raw_bi = {
        "overall_score": 91.5,
        "component_scores": {"website_need": 95},
        "risk_flags": ["missing_phone"],
        "prompt_hints": [
            "position_as_missing_website_upgrade",
            "high_value_service_category",
            "unknown_internal_hint",
        ],
    }

    guidance = build_public_safe_bi_context(raw_bi)
    joined = "\n".join(guidance)

    assert "booking and service discovery easy" in joined
    assert "premium visual hierarchy" in joined
    for raw in [
        "overall_score",
        "component_scores",
        "risk_flags",
        "missing_phone",
        "position_as_missing_website_upgrade",
        "unknown_internal_hint",
    ]:
        assert raw not in joined


def test_prompt_and_contract_include_safe_bi_guidance_without_raw_bi():
    raw_bi = {
        "overall_score": 91.5,
        "component_scores": {"website_need": 95},
        "risk_flags": ["missing_phone"],
        "prompt_hints": ["position_as_missing_website_upgrade"],
    }

    built = build_premium_stitch_prompt(_input(business_intelligence=raw_bi))
    contract_text = str(built.prompt_contract)

    assert "booking and service discovery easy" in built.prompt
    assert "business_guidance" in built.prompt_contract
    assert "booking and service discovery easy" in "\n".join(built.prompt_contract["business_guidance"])
    for raw in [
        "overall_score",
        "component_scores",
        "risk_flags",
        "missing_phone",
        "position_as_missing_website_upgrade",
        "business_intelligence",
    ]:
        assert raw not in built.prompt
        assert raw not in contract_text


# ---------------------------------------------------------------------------
# Photo policy
# ---------------------------------------------------------------------------


def test_production_mode_uses_css_effects_not_photos():
    built = build_premium_stitch_prompt(_input(deploy_mode="production_deploy_mode"))
    assert "CSS effects" in built.prompt
    assert "no external photos" in built.prompt
    assert "scraped images" in built.prompt_contract["photo_policy"]


def test_preview_demo_mode_photo_policy_in_contract():
    built = build_premium_stitch_prompt(_input(deploy_mode="preview_demo_mode"))
    assert "safe preview/demo visuals" in built.prompt_contract["photo_policy"]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field,value", [("business_name", ""), ("business_slug", ""), ("category", "")])
def test_prompt_requires_core_identity_fields(field, value):
    kwargs = {field: value}
    with pytest.raises(ValueError):
        build_premium_stitch_prompt(_input(**kwargs))


# ---------------------------------------------------------------------------
# Feeling/vibe derivation
# ---------------------------------------------------------------------------


def test_feeling_derived_from_design_style():
    built = build_premium_stitch_prompt(_input(design_style="dark luxury automotive detailing"))
    # Should include the style-derived feeling
    assert "dark luxury automotive detailing" in built.prompt


def test_feeling_derived_from_category_for_medical():
    built = build_premium_stitch_prompt(_input(
        category="Dental clinic",
        design_style="premium local-business website",
        niche="dental care",
    ))
    assert "Trustworthy" in built.prompt or "Professional" in built.prompt
