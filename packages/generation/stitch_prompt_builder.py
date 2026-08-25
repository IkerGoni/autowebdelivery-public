"""Prompt contract builder for premium Stitch/Gemini website generation.

Design principle: Stitch generates best-quality HTML from concise, structured
prompts that read like a creative brief — not a legal contract. The prompt
follows the Obsidian guide pattern:

  1. Business objective + feeling
  2. Platform
  3. Numbered page sections (human-readable)
  4. Verified facts only
  5. Brief constraints

Target: under 350 words. No JSON dumps. No internal code identifiers.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROMPT_VERSION = "premium_stitch_prompt_v2"

DEFAULT_REQUIRED_SECTIONS = (
    "hero_with_above_fold_cta",
    "verified_local_service_summary",
    "service_or_package_cards",
    "process_or_booking_steps",
    "service_area_or_location",
    "final_cta",
    "footer_with_verified_contact_only",
)

DEFAULT_FORBIDDEN_CLAIMS = (
    "fake phone numbers",
    "fake emails",
    "fake addresses",
    "certifications",
    "guarantees",
    "awards",
)

FORBIDDEN_ABSTRACT_CLAIMS = (
    "best",
    "top-rated",
    "premier",
    "award-winning",
    "family-owned",
    "trusted by thousands",
)

NEUTRAL_FALLBACKS = (
    "Request a quote",
    "Serving the local area",
    "Mobile detailing services",
    "Designed for convenient booking",
)

_SAFE_BI_HINTS = {
    "position_as_missing_website_upgrade": "Focus on making booking and service discovery easy.",
    "position_as_social_to_owned_site_upgrade": "Emphasize clear site structure, service pages, and direct conversion paths.",
    "high_value_service_category": "Use premium visual hierarchy and confident but factual tone.",
    "strong_rating_signal": "Present verified ratings cleanly for trust.",
    "strong_review_volume_signal": "Present verified review counts plainly without embellishment.",
    "use_enriched_services_in_prompt": "Prioritize concrete service cards and package structure.",
    "use_visual_business_context": "Use visual context for imagery and atmosphere.",
    "use_enriched_business_summary": "Use summary context for page structure and tone.",
}

# Map internal section identifiers to human-readable descriptions for Stitch
_SECTION_LABELS: dict[str, str] = {
    "hero_with_above_fold_cta": "Hero section with headline, value proposition, and primary CTA above the fold",
    "verified_local_service_summary": "Brief business summary establishing local relevance",
    "service_or_package_cards": "Service or package cards with clear pricing tiers or descriptions",
    "process_or_booking_steps": "How it works or booking process steps (3-4 steps)",
    "service_area_or_location": "Service area or location section with map placeholder if address available",
    "final_cta": "Strong final call-to-action section",
    "footer_with_verified_contact_only": "Footer with verified contact info only, no unverified claims",
}


@dataclass(frozen=True)
class StitchPromptInput:
    """Inputs required to build a fact-safe premium Stitch prompt."""

    business_name: str
    business_slug: str
    category: str
    facts: dict[str, Any] = field(default_factory=dict)
    public_safe_fields: dict[str, Any] = field(default_factory=dict)
    copy_inputs: dict[str, Any] = field(default_factory=dict)
    visual_profile: dict[str, Any] = field(default_factory=dict)
    business_intelligence: dict[str, Any] = field(default_factory=dict)
    allowed_claims: list[str] = field(default_factory=list)
    forbidden_claims: list[str] = field(default_factory=list)
    design_style: str = "premium local-business website"
    niche: str = "local business"
    target_customer: str = "local customers ready to request service"
    deploy_mode: str = "production_deploy_mode"
    language: str = "English"
    required_sections: tuple[str, ...] = DEFAULT_REQUIRED_SECTIONS
    neutral_fallbacks: tuple[str, ...] = NEUTRAL_FALLBACKS


@dataclass(frozen=True)
class PremiumStitchPrompt:
    """Rendered prompt plus machine-readable guardrails."""

    prompt: str
    prompt_version: str
    prompt_sha256: str
    prompt_contract: dict[str, Any]
    metadata: dict[str, Any]


def build_public_safe_bi_context(business_intelligence: dict[str, Any] | None) -> list[str]:
    """Translate internal BI prompt hints into public-safe planning guidance only."""

    if not isinstance(business_intelligence, dict):
        return []
    guidance: list[str] = []
    for hint in business_intelligence.get("prompt_hints", []):
        if not isinstance(hint, str):
            continue
        safe = _SAFE_BI_HINTS.get(hint)
        if safe and safe not in guidance:
            guidance.append(safe)
    return guidance


def _clean_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return ", ".join(_clean_value(item) for item in value if _clean_value(item))
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return str(value).strip()


def _merge_facts(prompt_input: StitchPromptInput) -> dict[str, str]:
    merged: dict[str, str] = {}
    for source in (prompt_input.facts, prompt_input.public_safe_fields):
        for key, value in source.items():
            cleaned = _clean_value(value)
            if cleaned:
                merged[str(key)] = cleaned
    merged.setdefault("business_name", prompt_input.business_name)
    merged.setdefault("category", prompt_input.category)
    return dict(sorted(merged.items()))


def _missing_fact_names(facts: dict[str, str]) -> list[str]:
    important = ("phone", "email", "address", "hours", "rating", "review_count", "certifications")
    return [name for name in important if not facts.get(name)]


def _forbidden_claims(prompt_input: StitchPromptInput) -> list[str]:
    """Context-aware forbidden claims based on public_safe_fields verification.

    Claims like 'insured', 'licensed' are only forbidden if NOT verified
    in public_safe_fields. Abstract claims are always forbidden.
    """
    forbidden = list(FORBIDDEN_ABSTRACT_CLAIMS)
    forbidden.extend(prompt_input.forbidden_claims)

    # Get verified field names from public_safe_fields
    verified_fields: set[str] = set()
    for fld in prompt_input.public_safe_fields.get("fields", []):
        if isinstance(fld, dict):
            field_name = fld.get("field_name", "")
            if fld.get("safe_for_public_copy", False):
                verified_fields.add(field_name.lower())

    facts = _merge_facts(prompt_input)

    # Allow 'certified', 'insured', 'licensed', 'accredited' if verified
    for claim in ["certified", "insured", "licensed", "accredited", "certifications", "guarantees"]:
        is_verified = (
            claim in verified_fields
            or claim in {f.lower() for f in verified_fields}
            or any(claim in str(v).lower() for v in facts.values())
        )
        if not is_verified and claim not in forbidden:
            forbidden.append(claim)

    return sorted({claim.strip() for claim in forbidden if claim.strip()}, key=str.lower)


def _allowed_claims(prompt_input: StitchPromptInput, facts: dict[str, str]) -> list[str]:
    allowed = [claim.strip() for claim in prompt_input.allowed_claims if claim.strip()]
    if facts.get("rating") and facts.get("review_count"):
        allowed.append(f"Exact rating/review count only: {facts['rating']} from {facts['review_count']} reviews")
    if facts.get("phone"):
        allowed.append(f"Exact verified phone only: {facts['phone']}")
    if facts.get("address"):
        allowed.append(f"Exact verified address only: {facts['address']}")
    return sorted(set(allowed), key=str.lower)


def _photo_policy(deploy_mode: str) -> str:
    if deploy_mode == "production_deploy_mode":
        return (
            "Do not use Google-derived photos, scraped images, or unlicensed external business photos. "
            "Use safe visual treatments, gradients, icons, abstract automotive/detailing imagery, and CSS effects."
        )
    return "Use only clearly safe preview/demo visuals; do not imply unverified ownership of photos."


def _build_feeling(style: str, category: str) -> str:
    """Derive a concise feeling/vibe phrase from design_style and category."""
    style_lower = style.lower()
    # If the user set a specific, non-generic feeling, use it directly
    if style_lower not in ("premium local-business website", "local business", "") and any(
        word in style_lower for word in ("luxury", "clean", "warm", "clinical", "modern", "bold", "dark")
    ):
        return style.split(",")[0].strip()
    # Derive feeling from category
    cat_lower = category.lower()
    if any(word in cat_lower for word in ("dental", "medical", "clinic", "health")):
        return "Trustworthy, clean, professional"
    if any(word in cat_lower for word in ("auto", "detailing", "car")):
        return "Bold, polished, automotive"
    if any(word in cat_lower for word in ("restaurant", "cafe", "food")):
        return "Warm, inviting, appetizing"
    return "Professional, trustworthy, modern"


def _human_readable_sections(required_sections: tuple[str, ...]) -> list[str]:
    """Convert internal section IDs to numbered human-readable descriptions."""
    lines: list[str] = []
    for i, section_id in enumerate(required_sections, 1):
        label = _SECTION_LABELS.get(section_id)
        if label:
            lines.append(f"{i}. {label}")
        else:
            # Fallback: convert snake_case to Title Case
            readable = section_id.replace("_", " ").title()
            lines.append(f"{i}. {readable}")
    return lines


def _prompt_lines(prompt_input: StitchPromptInput, facts: dict[str, str], missing: list[str]) -> list[str]:
    """Build concise, structured Stitch prompt lines.

    Follows the validated pattern: objective → feeling → platform → sections → facts → constraints.
    Target: under 350 words.
    """
    business_name = prompt_input.business_name
    category = prompt_input.category
    location = facts.get("area", facts.get("address", facts.get("city", "")))
    feeling = _build_feeling(prompt_input.design_style, category)
    niche = prompt_input.niche

    # --- Line 1: Objective + feeling ---
    location_phrase = f" in {location}" if location else ""
    # Avoid doubling "Premium" if niche already starts with it
    niche_lower = niche.lower()
    if niche_lower.startswith("premium"):
        objective = f"{niche.title()} website for {business_name}{location_phrase}. {feeling}."
    else:
        objective = f"Premium {niche} website for {business_name}{location_phrase}. {feeling}."

    # --- Line 2: Platform ---
    platform = "Web, desktop-first with responsive mobile layout. Single-page landing site."

    # --- Line 3: Sections ---
    section_lines = _human_readable_sections(prompt_input.required_sections)

    # --- Verified facts (concise bullet list, no raw JSON) ---
    fact_lines: list[str] = []
    for key, value in facts.items():
        if key in ("business_name", "category"):
            continue  # already in objective
        fact_lines.append(f"- {key}: {value}")

    # --- Missing data guidance (brief) ---
    missing_line = ""
    if missing:
        missing_line = f"Missing: {', '.join(missing)}. Use neutral placeholders (e.g., 'Request a quote', 'Contact for availability'). Do not invent contact details."

    # --- BI guidance (if any, keep brief) ---
    bi_guidance = build_public_safe_bi_context(prompt_input.business_intelligence)
    bi_line = ""
    if bi_guidance:
        bi_line = " ".join(bi_guidance)

    # --- Photo policy (brief) ---
    photo_note = ""
    if prompt_input.deploy_mode == "production_deploy_mode":
        photo_note = "Use CSS effects, gradients, and icons for visuals — no external photos."

    # --- Build the final prompt ---
    lines: list[str] = []
    lines.append(objective)
    lines.append("")
    lines.append(platform)
    lines.append("")

    # Page sections
    lines.append("Page structure:")
    lines.extend(section_lines)
    lines.append("")

    # Verified facts
    if fact_lines:
        lines.append("Use these verified details:")
        lines.extend(fact_lines)
        lines.append("")

    # Missing data
    if missing_line:
        lines.append(missing_line)
        lines.append("")

    # BI guidance
    if bi_line:
        lines.append(bi_line)
        lines.append("")

    # Photo policy
    if photo_note:
        lines.append(photo_note)
        lines.append("")

    # Brief output instruction
    lines.append(
        "Output a complete, production-ready HTML page with inline CSS. "
        "Rich visual hierarchy, mobile spacing, concise copy, no placeholder text, no demo labels."
    )

    return lines


def build_premium_stitch_prompt(prompt_input: StitchPromptInput) -> PremiumStitchPrompt:
    """Build a deterministic, fact-safe Stitch prompt contract."""

    if not prompt_input.business_name.strip():
        raise ValueError("business_name is required")
    if not prompt_input.business_slug.strip():
        raise ValueError("business_slug is required")
    if not prompt_input.category.strip():
        raise ValueError("category is required")

    facts = _merge_facts(prompt_input)
    missing = _missing_fact_names(facts)
    forbidden = _forbidden_claims(prompt_input)
    allowed = _allowed_claims(prompt_input, facts)
    business_guidance = build_public_safe_bi_context(prompt_input.business_intelligence)
    prompt_text = "\n".join(_prompt_lines(prompt_input, facts, missing)).strip() + "\n"
    prompt_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()

    # Log the prompt for debugging
    word_count = len(prompt_text.split())
    logger.info(
        "Stitch prompt built: business=%s slug=%s sha256=%s words=%d",
        prompt_input.business_name,
        prompt_input.business_slug,
        prompt_hash[:12],
        word_count,
    )
    logger.debug("Full prompt:\n%s", prompt_text)

    contract = {
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": prompt_hash,
        "business_slug": prompt_input.business_slug,
        "business_name": prompt_input.business_name,
        "category": prompt_input.category,
        "verified_facts": facts,
        "missing_facts": missing,
        "allowed_claims": allowed,
        "forbidden_claims": forbidden,
        "required_sections": list(prompt_input.required_sections),
        "neutral_fallbacks": list(prompt_input.neutral_fallbacks),
        "deploy_mode": prompt_input.deploy_mode,
        "photo_policy": _photo_policy(prompt_input.deploy_mode),
        "visual_profile": prompt_input.visual_profile,
        "copy_inputs": prompt_input.copy_inputs,
        "business_guidance": business_guidance,
    }
    metadata = {
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": prompt_hash,
        "business_slug": prompt_input.business_slug,
        "facts_included": sorted(facts),
        "facts_missing": missing,
        "deploy_mode": prompt_input.deploy_mode,
        "word_count": word_count,
    }
    return PremiumStitchPrompt(
        prompt=prompt_text,
        prompt_version=PROMPT_VERSION,
        prompt_sha256=prompt_hash,
        prompt_contract=contract,
        metadata=metadata,
    )


def build_prompt_from_creative_spec(
    creative_spec: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> PremiumStitchPrompt:
    """Compatibility wrapper: compile creative_spec → StitchPromptInput → prompt.

    This is the entry point for VNEXT-05 code paths. It delegates to
    stitch_compiler.compile_creative_spec_to_prompt() which translates
    the creative_spec into the existing builder's input format.

    Parameters
    ----------
    creative_spec:
        Output of ``build_creative_spec()`` (VNEXT-04).
    config:
        Run-level config. Defaults to empty dict if not provided.

    Returns
    -------
    PremiumStitchPrompt with compiler provenance in the contract.
    """
    from packages.generation.stitch_compiler import compile_creative_spec_to_prompt

    return compile_creative_spec_to_prompt(creative_spec, config or {})


def write_prompt_contract(prompt: PremiumStitchPrompt, output_path: Path) -> Path:
    """Write a prompt contract JSON artifact."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(prompt.prompt_contract, indent=2, sort_keys=True), encoding="utf-8")
    return output_path
