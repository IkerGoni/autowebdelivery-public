"""VNEXT-05 — Stitch Compiler: creative_spec → existing Stitch prompt path.

The compiler is a TRANSLATOR, not a replacement. It converts a creative_spec
dict (output of VNEXT-04) into a StitchPromptInput, then delegates to the
existing build_premium_stitch_prompt() — producing the same PremiumStitchPrompt
and contract with additional compiler provenance fields.

Feature flag: ``use_stitch_compiler`` (default OFF).

Key design:
  1. Extract business_identity → StitchPromptInput.facts + public_safe_fields
  2. Extract brand_strategy → design_style / feeling derivation
  3. Extract sellability → business_intelligence for BI guidance
  4. Extract content_policy → forbidden_claims
  5. Extract generation_directives → required_sections
  6. Call the EXISTING build_premium_stitch_prompt() with the constructed input
  7. Augment the contract with compiler provenance
  8. Return PremiumStitchPrompt + enriched contract
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from packages.generation.stitch_prompt_builder import (
    DEFAULT_REQUIRED_SECTIONS,
    PremiumStitchPrompt,
    StitchPromptInput,
    build_premium_stitch_prompt,
)

logger = logging.getLogger(__name__)

COMPILER_VERSION = "stitch_compiler_v1"
FEATURE_FLAG = "use_stitch_compiler"

# Map creative_spec section names → existing stitch_prompt_builder section IDs
_SECTION_MAP: dict[str, str] = {
    "hero": "hero_with_above_fold_cta",
    "services": "service_or_package_cards",
    "about": "verified_local_service_summary",
    "contact": "service_area_or_location",
    "cta": "final_cta",
}

# Known business_identity keys that map to facts
_FACT_KEYS = ("business_name", "category", "phone", "address", "hours")


def _envelope_value(entry: Any) -> str:
    """Extract the value string from a creative_spec envelope {value, source, confidence}.

    Returns the value field as a string, or empty string if absent.
    """
    if isinstance(entry, dict):
        v = entry.get("value")
        return str(v) if v is not None else ""
    return str(entry) if entry is not None else ""


def _envelope_confidence(entry: Any) -> str:
    """Extract the confidence field from a creative_spec envelope."""
    if isinstance(entry, dict):
        return str(entry.get("confidence", "unknown"))
    return "unknown"


def _extract_facts_from_spec(creative_spec: dict[str, Any]) -> dict[str, Any]:
    """Extract verified facts from creative_spec.business_identity.

    Returns a flat dict suitable for StitchPromptInput.facts, containing only
    keys with non-empty values and 'verified' confidence.
    """
    identity = creative_spec.get("business_identity", {})
    if not isinstance(identity, dict):
        return {}

    facts: dict[str, Any] = {}
    for key in _FACT_KEYS:
        entry = identity.get(key)
        if entry is None:
            continue
        value = _envelope_value(entry)
        confidence = _envelope_confidence(entry)
        if value and confidence == "verified":
            facts[key] = value
    return facts


def _extract_brand_feeling(creative_spec: dict[str, Any]) -> str:
    """Derive a design_style feeling string from brand_strategy.tone and color_direction."""
    brand = creative_spec.get("brand_strategy", {})
    if not isinstance(brand, dict):
        return "premium local-business website"

    tone_entry = brand.get("tone", {})
    tone = _envelope_value(tone_entry) if isinstance(tone_entry, dict) else str(tone_entry)

    color_dir = brand.get("color_direction", {})
    if isinstance(color_dir, dict):
        mood = str(color_dir.get("mood", ""))
        primary_hint = str(color_dir.get("primary_hint", ""))
    else:
        mood = ""
        primary_hint = ""

    # Build a feeling phrase from available brand data
    parts: list[str] = []
    if tone and tone not in ("professional", ""):
        parts.append(tone)
    if mood:
        parts.append(mood)
    if primary_hint:
        parts.append(primary_hint)

    if parts:
        return ", ".join(parts)
    return "premium local-business website"


def _extract_forbidden_claims(creative_spec: dict[str, Any]) -> list[str]:
    """Extract forbidden claims from content_policy."""
    policy = creative_spec.get("content_policy", {})
    if not isinstance(policy, dict):
        return []

    claims = policy.get("forbidden_claims", [])
    if isinstance(claims, list):
        return [str(c) for c in claims if str(c).strip()]
    return []


def _extract_sections(creative_spec: dict[str, Any]) -> tuple[str, ...]:
    """Extract required sections from generation_directives, mapping to builder IDs."""
    directives = creative_spec.get("generation_directives", {})
    if not isinstance(directives, dict):
        return DEFAULT_REQUIRED_SECTIONS

    sections = directives.get("sections", [])
    if not isinstance(sections, list) or not sections:
        return DEFAULT_REQUIRED_SECTIONS

    mapped: list[str] = []
    for section in sections:
        section_str = str(section)
        builder_id = _SECTION_MAP.get(section_str)
        if builder_id:
            mapped.append(builder_id)
        else:
            # Keep as-is for unknown sections (builder handles gracefully)
            mapped.append(section_str)

    return tuple(mapped) if mapped else DEFAULT_REQUIRED_SECTIONS


def _extract_bi_from_spec(creative_spec: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct business_intelligence from sellability for BI guidance.

    Maps sellability signals to prompt_hints that the existing
    build_public_safe_bi_context() can translate.
    """
    sellability = creative_spec.get("sellability", {})
    if not isinstance(sellability, dict):
        return {}

    hints: list[str] = []

    # Map website_status → positioning hints
    website_status = str(sellability.get("website_status", ""))
    if website_status == "no_website":
        hints.append("position_as_missing_website_upgrade")
    elif website_status in ("social_only", "poor_quality"):
        hints.append("position_as_social_to_owned_site_upgrade")

    # Map demand_signal
    demand = str(sellability.get("demand_signal", ""))
    if demand in ("high", "very_high"):
        hints.append("high_value_service_category")

    # Map positioning hints directly
    positioning = sellability.get("positioning", [])
    if isinstance(positioning, list):
        for pos in positioning:
            pos_str = str(pos)
            if pos_str in (
                "strong_rating_signal",
                "strong_review_volume_signal",
                "use_enriched_services_in_prompt",
                "use_visual_business_context",
                "use_enriched_business_summary",
            ):
                if pos_str not in hints:
                    hints.append(pos_str)

    return {"prompt_hints": hints}


def _compute_creative_spec_hash(creative_spec: dict[str, Any]) -> str:
    """Compute SHA-256 of the creative_spec for contract provenance."""
    # Deterministic serialization: sort keys, compact JSON
    canonical = json.dumps(creative_spec, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_compiler_contract(
    creative_spec: dict[str, Any],
    included_facts: list[str],
    omitted_facts: dict[str, str],
    forbidden_claims: list[str],
    feeling_derived_from: str,
    sections_from: str,
) -> dict[str, Any]:
    """Build compiler-specific contract additions for provenance tracking."""
    return {
        "compiler_version": COMPILER_VERSION,
        "creative_spec_hash": _compute_creative_spec_hash(creative_spec),
        "included_facts": included_facts,
        "omitted_facts": omitted_facts,
        "compiler_decisions": {
            "feeling_derived_from": feeling_derived_from,
            "sections_from": sections_from,
        },
        "forbidden_claims": forbidden_claims,
    }


def compile_creative_spec_to_prompt(
    creative_spec: dict[str, Any],
    config: dict[str, Any],
) -> PremiumStitchPrompt:
    """Compile a creative_spec into a Stitch prompt via the existing builder.

    Parameters
    ----------
    creative_spec:
        Output of ``build_creative_spec()`` (VNEXT-04).
    config:
        Run-level config with potential overrides for niche, area, etc.

    Returns
    -------
    PremiumStitchPrompt with augmented contract containing compiler provenance.

    Raises
    ------
    ValueError
        If business_name or category cannot be extracted from the spec.
    """
    # --- 1. Extract fields from creative_spec ---
    facts = _extract_facts_from_spec(creative_spec)
    forbidden_claims = _extract_forbidden_claims(creative_spec)
    sections = _extract_sections(creative_spec)
    bi = _extract_bi_from_spec(creative_spec)
    feeling = _extract_brand_feeling(creative_spec)

    # --- 2. Get core identity ---
    identity = creative_spec.get("business_identity", {})
    business_name = _envelope_value(identity.get("business_name", {}))
    category = _envelope_value(identity.get("category", {}))
    business_slug = str(creative_spec.get("business_slug", ""))

    # Also check facts as fallback
    if not business_name:
        business_name = str(facts.get("business_name", ""))
    if not category:
        category = str(facts.get("category", ""))

    if not business_name.strip():
        raise ValueError("creative_spec must contain business_name in business_identity")
    if not business_slug.strip():
        raise ValueError("creative_spec must contain business_slug")
    if not category.strip():
        raise ValueError("creative_spec must contain category in business_identity")

    # --- 3. Determine compiler decision sources ---
    brand = creative_spec.get("brand_strategy", {})
    tone_entry = brand.get("tone", {})
    has_tone = isinstance(tone_entry, dict) and _envelope_value(tone_entry)
    feeling_source = "brand_strategy.tone" if has_tone else "default"

    directives = creative_spec.get("generation_directives", {})
    has_sections = isinstance(directives, dict) and directives.get("sections")
    sections_source = "generation_directives.sections" if has_sections else "default"

    # --- 4. Track included/omitted facts ---
    included_facts: list[str] = [k for k, v in facts.items() if v]
    omitted_facts: dict[str, str] = {}
    for key in _FACT_KEYS:
        if key in ("business_name", "category"):
            continue  # These are required, not omitted
        entry = identity.get(key)
        if entry is None:
            omitted_facts[key] = "not in business_identity"
        elif not _envelope_value(entry):
            omitted_facts[key] = "empty value"
        elif _envelope_confidence(entry) != "verified":
            omitted_facts[key] = f"confidence={_envelope_confidence(entry)}"

    # --- 5. Build StitchPromptInput ---
    niche = str(config.get("niche", "local business"))
    area = str(config.get("area", facts.get("area", "")))
    deploy_mode = str(config.get("deploy_mode", "production_deploy_mode"))

    # Merge area into facts if not present
    if area and "area" not in facts:
        facts["area"] = area

    prompt_input = StitchPromptInput(
        business_name=business_name,
        business_slug=business_slug,
        category=category,
        facts=facts,
        public_safe_fields={},  # Claim verification handled via explicit forbidden_claims
        forbidden_claims=forbidden_claims,
        design_style=feeling,
        niche=niche,
        deploy_mode=deploy_mode,
        required_sections=sections,
        business_intelligence=bi,
    )

    # --- 6. Call the EXISTING builder ---
    result = build_premium_stitch_prompt(prompt_input)

    # --- 7. Augment contract with compiler provenance ---
    compiler_contract = _build_compiler_contract(
        creative_spec=creative_spec,
        included_facts=included_facts,
        omitted_facts=omitted_facts,
        forbidden_claims=forbidden_claims,
        feeling_derived_from=feeling_source,
        sections_from=sections_source,
    )

    # Merge compiler fields into the existing contract
    augmented_contract = {**result.prompt_contract, "compiler": compiler_contract}

    # Build new metadata
    augmented_metadata = {
        **result.metadata,
        "compiler_version": COMPILER_VERSION,
        "creative_spec_hash": compiler_contract["creative_spec_hash"],
    }

    logger.info(
        "Stitch compiler: business=%s slug=%s spec_hash=%s included=%d omitted=%d",
        business_name,
        business_slug,
        compiler_contract["creative_spec_hash"][:12],
        len(included_facts),
        len(omitted_facts),
    )

    # Return new PremiumStitchPrompt with augmented contract/metadata
    return PremiumStitchPrompt(
        prompt=result.prompt,
        prompt_version=result.prompt_version,
        prompt_sha256=result.prompt_sha256,
        prompt_contract=augmented_contract,
        metadata=augmented_metadata,
    )
