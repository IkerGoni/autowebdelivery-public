"""
Phase 04.5 — Deterministic enrichment visual profile generation.

Generate per-business enrichment artifacts from Phase 04 briefs and
RunConfig using deterministic preset mapping and safe fallbacks only.

Inputs:
  - runs/{run_id}/config/input_config.json
  - runs/{run_id}/04_briefs/preview_ready_briefs.json

Outputs (per contract):
  - runs/{run_id}/04_5_enrichment/{business_slug}/enriched_facts.json
  - runs/{run_id}/04_5_enrichment/{business_slug}/enrichment_sources.json
  - runs/{run_id}/04_5_enrichment/{business_slug}/public_safe_fields.json
  - runs/{run_id}/04_5_enrichment/{business_slug}/internal_only_fields.json
  - runs/{run_id}/04_5_enrichment/{business_slug}/category_mapping.json
  - runs/{run_id}/04_5_enrichment/{business_slug}/design_preset_candidate.json
  - runs/{run_id}/04_5_enrichment/{business_slug}/visual_profile.json
  - runs/{run_id}/04_5_enrichment/{business_slug}/copy_inputs.json
  - runs/{run_id}/04_5_enrichment/{business_slug}/result.json
  - runs/{run_id}/04_5_enrichment/result.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from enrichment.hours_extractor import merge_hours, parse_hours_text
    from enrichment.pricing_extractor import (
        create_internal_pricing_fields,  # noqa: F401
        extract_pricing_from_html,  # noqa: F401
        format_pricing_hint,  # noqa: F401
    )
    from enrichment.services_extractor import (
        extract_services_from_html,
        merge_services_with_existing,  # noqa: F401
    )

    from pipeline.json_io import read_json, write_json
    from pipeline.result_envelope import ResultEnvelope
except ModuleNotFoundError:  # pragma: no cover - CLI fallback
    from packages.enrichment.hours_extractor import merge_hours, parse_hours_text
    from packages.enrichment.services_extractor import (
        extract_services_from_html,
    )
    from packages.pipeline.json_io import read_json, write_json
    from packages.pipeline.result_envelope import ResultEnvelope

try:
    from generation.niche_copy import copy_slots_to_dict, generate_copy_from_facts
except ModuleNotFoundError:  # pragma: no cover
    from packages.generation.niche_copy import copy_slots_to_dict, generate_copy_from_facts

from packages.shared.provenance import _safe_str

PHASE_SLUG = "04_5_enrichment"
PHASE_NAME = "04_5_enrichment"
SCHEMA_VERSION = "1.0"
CANONICAL_PRESETS = {
    "clinical_trust",
    "warm_editorial",
    "industrial_reliable",
    "fresh_utility",
}
PRESET_LABELS = {
    "clinical_trust": "Clinical Trust",
    "warm_editorial": "Warm Editorial",
    "industrial_reliable": "Industrial Reliable",
    "fresh_utility": "Fresh Utility",
}
PRESET_TONE_AXES = {
    "clinical_trust": {"formality": 0.8, "warmth": 0.3, "luxury": 0.2, "energy": 0.3},
    "warm_editorial": {"formality": 0.4, "warmth": 0.8, "luxury": 0.5, "energy": 0.5},
    "industrial_reliable": {"formality": 0.6, "warmth": 0.3, "luxury": 0.2, "energy": 0.5},
    "fresh_utility": {"formality": 0.3, "warmth": 0.5, "luxury": 0.2, "energy": 0.6},
}
PRESET_KEYWORDS = (
    ("clinical_trust", ("dentists", "dental", "clinic", "medical", "wellness", "legal")),
    ("warm_editorial", ("salon", "beauty", "spa", "massage", "tour", "hotel")),
    (
        "industrial_reliable",
        ("mechanic", "repair", "home service", "auto", "real estate", "electrician", "plumbing"),
    ),
    ("fresh_utility", ("cleaning", "eco", "pet")),
)

CATEGORY_PRESET_MAP = {
    "dental": "clinical_trust",
    "clinic": "clinical_trust",
    "restaurant": "warm_editorial",
    "cafe": "warm_editorial",
    "spa": "warm_editorial",
    "salon": "warm_editorial",
    "repair": "industrial_reliable",
    "mechanic": "industrial_reliable",
    "auto": "industrial_reliable",
    "cleaning": "fresh_utility",
    "laundry": "fresh_utility",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_business_facts(brief_path: Path) -> dict[str, Any]:
    facts_path = brief_path / "FACTS.md"
    if not facts_path.exists():
        return {}

    facts: dict[str, Any] = {}
    for raw_line in facts_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("- ") or ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        facts[key.strip()] = value.strip()
    return facts


def _select_preset(config: dict[str, Any]) -> tuple[str, float, str]:
    style_preset = _safe_str(config.get("style_preset"))
    if style_preset in CANONICAL_PRESETS:
        return style_preset, 1.0, "style_preset_override"

    niche = _safe_str(config.get("niche")).lower()
    for preset_id, keywords in PRESET_KEYWORDS:
        if any(keyword in niche for keyword in keywords):
            return preset_id, 0.8, f"niche_keyword_match:{niche}"

    return "clinical_trust", 0.5, "safe_fallback"


def _parse_facts_md(path: Path) -> dict[str, str]:
    facts: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("- ") or ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        facts[key.strip()] = value.strip()
    return facts


def _pick_preset(category: str) -> tuple[str, float, str]:
    lowered = category.lower()
    for token, preset_id in CATEGORY_PRESET_MAP.items():
        if token in lowered:
            return preset_id, 0.9, f"Category contains '{token}', mapped to {preset_id}."
    return "fresh_utility", 0.55, "Fallback preset used because category had no explicit mapping."


def _tone_axes(preset_id: str) -> dict[str, float]:
    presets = {
        "clinical_trust": {"formality": 0.85, "warmth": 0.45, "luxury": 0.35, "energy": 0.4},
        "warm_editorial": {"formality": 0.45, "warmth": 0.8, "luxury": 0.55, "energy": 0.55},
        "industrial_reliable": {"formality": 0.7, "warmth": 0.35, "luxury": 0.2, "energy": 0.45},
        "fresh_utility": {"formality": 0.5, "warmth": 0.55, "luxury": 0.15, "energy": 0.7},
    }
    return presets[preset_id]


def _hero_mode(facts: dict[str, Any]) -> str:
    return "map_context" if _safe_str(facts.get("maps_url")) else "text_first"


def _trust_chip_candidates(facts: dict[str, Any]) -> list[dict[str, Any]]:
    chips: list[dict[str, Any]] = []

    rating = _safe_float(facts.get("rating"))
    if rating is not None:
        chips.append(
            {
                "label": f"Rated {rating:g}",
                "source_type": "rating",
                "source_ref": None,
                "confidence": 0.9,
                "attribution_required": False,
            }
        )

    review_count = _safe_int(facts.get("review_count"))
    if review_count is not None:
        chips.append(
            {
                "label": f"{review_count} reviews",
                "source_type": "review_count",
                "source_ref": None,
                "confidence": 0.9,
                "attribution_required": False,
            }
        )

    if _safe_str(facts.get("phone")):
        chips.append(
            {
                "label": "Phone available",
                "source_type": "place_attribute",
                "source_ref": None,
                "confidence": 0.7,
                "attribution_required": False,
            }
        )

    return chips


def _local_visual_cues(facts: dict[str, Any]) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    address = _safe_str(facts.get("address"))
    maps_url = _safe_str(facts.get("maps_url"))

    if address:
        cues.append(
            {
                "cue_type": "geo_context",
                "label": address,
                "source_ref": "address",
                "confidence": 0.7,
            }
        )
    elif maps_url:
        cues.append(
            {
                "cue_type": "map_area",
                "label": "Google Maps listing available",
                "source_ref": maps_url,
                "confidence": 0.6,
            }
        )

    return cues


def _coverage_score(
    trust_chip_count: int,
    local_visual_cue_count: int,
    accent_color_confidence: float,
    preset_confidence: float,
    has_review_summary_candidate: bool,
    has_editorial_summary_candidate: bool,
) -> float:
    score = 0.0
    score += min(trust_chip_count, 3) / 3 * 0.35
    score += min(local_visual_cue_count, 1) * 0.15
    score += accent_color_confidence * 0.1
    score += preset_confidence * 0.25
    score += 0.1 if has_review_summary_candidate else 0.0
    score += 0.05 if has_editorial_summary_candidate else 0.0
    return round(min(score, 1.0), 2)


def _record_id(run_id: str, business_slug: str) -> str:
    return f"{run_id}:{PHASE_SLUG}:{business_slug}"


def _build_visual_profile(run_id: str, business_slug: str, config: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    now = _utc_now_iso()
    preset_id, preset_confidence, _preset_reason = _select_preset(config)
    trust_chips = _trust_chip_candidates(facts)
    local_visual_cues = _local_visual_cues(facts)
    hero_mode = _hero_mode(facts)
    accent_color_confidence = 0.0
    has_review_summary_candidate = False
    has_editorial_summary_candidate = False

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "business_slug": business_slug,
        "record_id": _record_id(run_id, business_slug),
        "phase": PHASE_SLUG,
        "created_at": now,
        "updated_at": now,
        "preset_id": preset_id,
        "preset_variant": None,
        "hero_mode": hero_mode,
        "photo_policy": "none",
        "accent_color_candidate": None,
        "accent_color_confidence": accent_color_confidence,
        "accent_source": "preset_default",
        "tone_axes": PRESET_TONE_AXES[preset_id],
        "trust_chip_candidates": trust_chips,
        "review_summary_candidate": {
            "text": None,
            "attribution_uri": None,
            "attribution_required": False,
        },
        "editorial_summary_candidate": {
            "text": None,
            "source_uri": None,
            "attribution_required": False,
        },
        "photo_candidates": [],
        "local_visual_cues": local_visual_cues,
        "attribution_requirements": [],
        "brand_risk_flags": [
            "no_safe_photos",
            "generic_color_fallback",
        ],
        "visual_personalization_score_inputs": {
            "has_photo_candidates": False,
            "photo_candidate_count": 0,
            "has_review_summary_candidate": has_review_summary_candidate,
            "has_editorial_summary_candidate": has_editorial_summary_candidate,
            "has_local_visual_cues": bool(local_visual_cues),
            "local_visual_cue_count": len(local_visual_cues),
            "accent_color_confidence": accent_color_confidence,
            "trust_chip_count": len(trust_chips),
            "preset_confidence": preset_confidence,
            "public_signal_coverage_score": _coverage_score(
                trust_chip_count=len(trust_chips),
                local_visual_cue_count=len(local_visual_cues),
                accent_color_confidence=accent_color_confidence,
                preset_confidence=preset_confidence,
                has_review_summary_candidate=has_review_summary_candidate,
                has_editorial_summary_candidate=has_editorial_summary_candidate,
            ),
        },
    }


def _build_enriched_facts(run_id: str, business_slug: str, record_id: str, facts: dict[str, Any], now: str) -> dict[str, Any]:
    rating = _safe_str(facts.get("rating"))
    review_count = _safe_str(facts.get("review_count"))
    enriched_value = None
    if rating and review_count:
        enriched_value = f"Google rating {rating} from {review_count} reviews"
    
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "business_slug": business_slug,
        "generated_at": now,
        "facts": [
            {
                "fact_id": f"{business_slug}:rating_summary",
                "run_id": run_id,
                "record_id": record_id,
                "phase": PHASE_SLUG,
                "category": "trust",
                "original_fact": f"rating={rating}; review_count={review_count}",
                "enriched_value": enriched_value,
                "enrichment_source": "FACTS.md",
                "source_verified": True,
                "confidence": 1.0,
                "contradicts_phase04": False,
                "provenance": {
                    "source_type": "manual",
                    "source_url": None,
                    "retrieval_timestamp": now,
                    "field_provenance": "Phase 04 FACTS.md verified fields",
                },
                "status": "enriched",
                "notes": None,
                "created_at": now,
                "updated_at": now,
            }
        ],
    }


def _build_enrichment_sources(run_id: str, business_slug: str, now: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "business_slug": business_slug,
        "sources": [
            {
                "source_id": f"{business_slug}:phase04_facts",
                "name": "Phase 04 FACTS.md",
                "type": "manual",
                "url": None,
                "accessed_at": now,
                "reliability_score": 1.0,
                "facts_sourced": [f"{business_slug}:rating_summary"],
            }
        ],
        "created_at": now,
        "updated_at": now,
    }


def _trusted_field(field_name: str) -> dict[str, Any]:
    """Create a standard trusted field structure for public_safe_fields."""
    return {
        "source_type": "extracted",
        "source_url": None,
        "retrieval_timestamp": _utc_now_iso(),
        "field_provenance": "Phase 04.5 enrichment extraction",
    }


def _extract_enriched_services(brief_dir: Path, facts: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract services from website HTML if present in brief dir.

    Looks for homepage.html in enrichment_cache subdirectory.
    Returns services with confidence >= 0.7 only.
    """
    html_path = brief_dir / "enrichment_cache" / "homepage.html"
    if not html_path.exists():
        return []

    html_text = html_path.read_text(encoding="utf-8")
    services = extract_services_from_html(html_text, facts.get("category", ""))
    return [s for s in services if s.get("confidence", 0) >= 0.7]


def _build_public_safe_fields(run_id: str, business_slug: str, facts: dict[str, Any], gate_status: str, now: str, enriched_services: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Build public-safe fields including extracted services and pricing hints.

    Args:
        enriched_services: Optional list of extracted services to include
    """
    fields: list[dict[str, Any]] = [
        {
            "field_name": "business_name",
            "field_value": _safe_str(facts.get("business_name")),
            "source_fact_id": f"{business_slug}:business_name",
            "provenance": {
                "source_type": "manual",
                "source_url": None,
                "retrieval_timestamp": now,
                "field_provenance": "Phase 04 FACTS.md verified field",
            },
            "safe_for_public_copy": True,
            "copy_slot_eligible": True,
            "gate_status": gate_status,
            "notes": None,
        },
        {
            "field_name": "category",
            "field_value": _safe_str(facts.get("category")),
            "source_fact_id": f"{business_slug}:category",
            "provenance": {
                "source_type": "manual",
                "source_url": None,
                "retrieval_timestamp": now,
                "field_provenance": "Phase 04 FACTS.md verified field",
            },
            "safe_for_public_copy": True,
            "copy_slot_eligible": True,
            "gate_status": gate_status,
            "notes": None,
        },
    ]

    # Add extracted services if available
    if enriched_services:
        services_list = [s.get("service_name", "") for s in enriched_services if s.get("service_name")]
        if services_list:
            fields.append({
                "field_name": "primary_services",
                "field_value": services_list,
                "source_fact_id": f"{business_slug}:services",
                "provenance": _trusted_field("primary_services"),
                "safe_for_public_copy": True,
                "copy_slot_eligible": True,
                "gate_status": gate_status,
                "notes": f"Extracted with confidence {[s.get('confidence', 0) for s in enriched_services]}",
            })

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "business_slug": business_slug,
        "fields": fields,
        "created_at": now,
        "updated_at": now,
    }


def _build_internal_only_fields(run_id: str, business_slug: str, gate_notes: list[str], now: str, enriched_services: list[dict[str, Any]] | None = None, facts: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build internal-only fields including pricing and extracted services."""
    fields: list[dict[str, Any]] = [
        {
            "field_name": "gate_notes",
            "field_value": " | ".join(gate_notes),
            "reason_internal_only": "Internal gating metadata",
            "source_fact_id": f"{business_slug}:gate_notes",
            "provenance": {
                "source_type": "manual",
                "source_url": None,
                "retrieval_timestamp": now,
                "field_provenance": "Phase 04.5 deterministic gate analysis",
            },
            "notes": None,
        }
    ]

    # Add extracted services for internal reference
    if enriched_services:
        for svc in enriched_services:
            fields.append({
                "field_name": f"service_{svc.get('service_name', 'unknown').lower().replace(' ', '_')}",
                "field_value": svc,
                "reason_internal_only": "Extracted service for verification before public use",
                "source_fact_id": f"{business_slug}:services",
                "provenance": _trusted_field("service"),
                "notes": None,
            })

    # Add hours parsing if available
    enriched_hours: dict[str, Any] = {}
    if facts and facts.get("hours"):
        enriched_hours = merge_hours(facts.get("hours"), parse_hours_text(facts.get("hours", "")))
        if enriched_hours.get("parsed_structured"):
            fields.append({
                "field_name": "hours_parsed",
                "field_value": enriched_hours,
                "reason_internal_only": "Structured hours for validation",
                "source_fact_id": f"{business_slug}:hours",
                "provenance": _trusted_field("hours"),
                "notes": None,
            })

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "business_slug": business_slug,
        "fields": fields,
        "created_at": now,
        "updated_at": now,
    }


def _build_category_mapping(run_id: str, business_slug: str, category: str, now: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "business_slug": business_slug,
        "mappings": [
            {
                "fact_id": f"{business_slug}:category",
                "phase04_category": category,
                "enrichment_category": "primary_business_category",
                "design_preset_relevant": True,
                "copy_slot_target": "hero_tagline",
            }
        ],
        "created_at": now,
        "updated_at": now,
    }


def _build_design_preset_candidate(run_id: str, business_slug: str, preset_id: str, preset_confidence: float, mapping_reason: str, now: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "business_slug": business_slug,
        "candidates": [
            {
                "preset_id": preset_id,
                "preset_label": PRESET_LABELS[preset_id],
                "palette": {"accent": "#1f6feb", "surface": "#f8fafc"},
                "layout_variant": "text_first",
                "tone_words": [PRESET_LABELS[preset_id].lower().replace(" ", "_"), "local", "clear"],
                "mapping_reason": mapping_reason,
                "confidence": preset_confidence,
            }
        ],
        "created_at": now,
        "updated_at": now,
    }


def _build_copy_inputs(run_id: str, business_slug: str, facts: dict[str, Any], gate_status: str, now: str, enriched_services: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    business_name = _safe_str(facts.get("business_name"))
    category = _safe_str(facts.get("category"))
    address = _safe_str(facts.get("address"))
    rating = _safe_str(facts.get("rating"))
    review_count = _safe_str(facts.get("review_count"))

    # Use niche copy generator for persuasive, human-sounding copy
    niche_slots = generate_copy_from_facts(facts)
    niche_dict = copy_slots_to_dict(niche_slots)

    # Build services string for copy
    services_str = ""
    if enriched_services:
        services_str = ", ".join(s.get("service_name", "") for s in enriched_services if s.get("service_name"))

    slots = {
        "hero_tagline": niche_dict["hero_tagline"] if niche_dict["hero_tagline"] else (f"{business_name} — {category}" if business_name and category else None),
        "hero_supporting_line": niche_dict["hero_supporting_line"] if niche_dict["hero_supporting_line"] else (services_str if services_str else None),
        "overview_intro": niche_dict["overview_intro"] if niche_dict["overview_intro"] else (f"{business_name} — {category} services in {address.split(',')[0] if address else 'your area'}." if business_name and category else None),
        "overview_support_block_1": niche_dict["overview_support_block_1"] if niche_dict["overview_support_block_1"] else (f"Category focus: {category}." if category else None),
        "overview_support_block_2": niche_dict["overview_support_block_2"] if niche_dict["overview_support_block_2"] else (f"Listed address: {address}." if address else None),
        "trust_intro": niche_dict["trust_intro"] if niche_dict["trust_intro"] else (f"Google rating {rating} from {review_count} reviews." if rating and review_count else None),
        "location_intro": niche_dict["location_intro"] if niche_dict["location_intro"] else (f"Located at {address}." if address else None),
        "cta_body": niche_dict["cta_body"] if niche_dict["cta_body"] else "Request a quote and check service availability.",
        "footer_note": niche_dict["footer_note"] if niche_dict["footer_note"] else (f"Information for {business_name}." if business_name else None),
    }
    slot_provenance = {
        key: {"source_fact_id": key if value is not None else None, "enrichment_used": bool(enriched_services)}
        for key, value in slots.items()
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "business_slug": business_slug,
        "slots": slots,
        "slot_provenance": slot_provenance,
        "gate_status": gate_status,
        "created_at": now,
        "updated_at": now,
    }


def _gate_status(facts: dict[str, str]) -> tuple[str, list[str]]:
    missing_core = [field for field in ("business_name", "category", "address", "maps_url") if not _safe_str(facts.get(field))]
    notes: list[str] = []
    if not _safe_str(facts.get("hours")):
        notes.append("Hours missing; render fallback required.")
    if missing_core:
        notes.append("Missing core fields: " + ", ".join(missing_core))
    if missing_core:
        return "render_allowed_but_not_deploy_eligible", notes
    return "render_allowed", notes


def _build_business_result(
    run_id: str,
    business_slug: str,
    started_at: str,
    completed_at: str,
    outputs_created: list[str],
    visual_profile: dict[str, Any],
    facts: dict[str, Any],
) -> dict[str, Any]:
    gate_status, gate_notes = _gate_status(facts)
    rating = _safe_str(facts.get("rating"))
    review_count = _safe_str(facts.get("review_count"))
    address = _safe_str(facts.get("address"))

    result = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_SLUG,
        "status": "done",
        "run_id": run_id,
        "business_slug": business_slug,
        "started_at": started_at,
        "completed_at": completed_at,
        "created_at": started_at,
        "updated_at": completed_at,
        "inputs_used": [
            f"runs/{run_id}/config/input_config.json",
            f"runs/{run_id}/04_briefs/preview_ready_briefs.json",
            f"runs/{run_id}/04_briefs/{business_slug}/FACTS.md",
        ],
        "outputs_created": outputs_created,
        "records_processed": 1,
        "records_created": 1,
        "records_skipped": 0,
        "scores": {
            "data_depth_score": 100 if gate_status == "render_allowed" else 75,
            "public_copy_ready_score": 100 if gate_status == "render_allowed" else 80,
            "trust_signal_score": 80 if rating and review_count else 45,
            "local_context_score": 75 if address else 30,
            "missing_core_fields_count": sum(1 for field in ("business_name", "category", "address", "maps_url") if not _safe_str(facts.get(field))),
        },
        "gates": {
            "render_allowed": gate_status == "render_allowed",
            "render_allowed_but_not_deploy_eligible": gate_status == "render_allowed_but_not_deploy_eligible",
            "needs_review": False,
        },
        "missing_fields": [field for field in ("hours", "phone") if not _safe_str(facts.get(field))],
        "decisions": [
            f"Selected preset {visual_profile['preset_id']} deterministically",
            f"Set hero_mode to {visual_profile['hero_mode']}",
            "Set photo_policy to none pending safe photo extraction",
            f"Gate set to {gate_status}.",
        ],
        "risks": gate_notes,
        "errors": [],
        "flags": [] if gate_status == "render_allowed" else [gate_status],
        "summary": "Deterministic visual profile generated from verified brief facts and RunConfig.",
        "next_tasks": ["Phase 05 — Preview Site Generation"],
    }
    return result


def build_enrichment_record(root: Path, run_id: str, brief_row: dict[str, Any]) -> dict[str, Any]:
    """Build and write all 9 enrichment artifacts for a single business.

    Convenience function used by unit tests.  Returns a summary dict with
    gate_status so callers can assert on the result without re-reading files.
    """
    business_slug = _safe_str(brief_row.get("business_slug"))
    brief_dir = root / "runs" / run_id / "04_briefs" / business_slug
    facts_path = brief_dir / "FACTS.md"

    if not facts_path.exists():
        return {
            "business_slug": business_slug,
            "status": "blocked",
            "missing_fields": [f"runs/{run_id}/04_briefs/{business_slug}/FACTS.md"],
        }

    facts = _parse_facts_md(facts_path)
    facts["run_id"] = run_id
    facts["business_slug"] = business_slug

    out_dir = root / "runs" / run_id / PHASE_SLUG / business_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    started_at = _utc_now_iso()
    gate_status, gate_notes = _gate_status(facts)
    record_id = _safe_str(brief_row.get("record_id")) or _record_id(run_id, business_slug)
    preset_id, preset_confidence, preset_reason = _pick_preset(_safe_str(facts.get("category")))

    # Extract services from website HTML
    enriched_services = _extract_enriched_services(brief_dir, facts)

    enriched_facts = _build_enriched_facts(run_id, business_slug, record_id, facts, started_at)
    enrichment_sources = _build_enrichment_sources(run_id, business_slug, started_at)
    public_safe_fields = _build_public_safe_fields(run_id, business_slug, facts, gate_status, started_at, enriched_services)
    internal_only_fields = _build_internal_only_fields(run_id, business_slug, gate_notes, started_at, enriched_services, facts)
    category_mapping = _build_category_mapping(run_id, business_slug, _safe_str(facts.get("category")), started_at)
    design_preset_candidate = _build_design_preset_candidate(run_id, business_slug, preset_id, preset_confidence, preset_reason, started_at)
    config_for_vp = {"style_preset": preset_id, "niche": _safe_str(facts.get("category"))}
    visual_profile = _build_visual_profile(run_id, business_slug, config_for_vp, facts)
    copy_inputs = _build_copy_inputs(run_id, business_slug, facts, gate_status, started_at, enriched_services)

    write_json(str(out_dir / "enriched_facts.json"), enriched_facts)
    write_json(str(out_dir / "enrichment_sources.json"), enrichment_sources)
    write_json(str(out_dir / "public_safe_fields.json"), public_safe_fields)
    write_json(str(out_dir / "internal_only_fields.json"), internal_only_fields)
    write_json(str(out_dir / "category_mapping.json"), category_mapping)
    write_json(str(out_dir / "design_preset_candidate.json"), design_preset_candidate)
    write_json(str(out_dir / "visual_profile.json"), visual_profile)
    write_json(str(out_dir / "copy_inputs.json"), copy_inputs)

    business_outputs = [
        f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/enriched_facts.json",
        f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/enrichment_sources.json",
        f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/public_safe_fields.json",
        f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/internal_only_fields.json",
        f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/category_mapping.json",
        f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/design_preset_candidate.json",
        f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/visual_profile.json",
        f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/copy_inputs.json",
        f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/result.json",
    ]
    completed_at = _utc_now_iso()
    business_result = _build_business_result(
        run_id=run_id,
        business_slug=business_slug,
        started_at=started_at,
        completed_at=completed_at,
        outputs_created=business_outputs,
        visual_profile=visual_profile,
        facts=facts,
    )
    write_json(str(out_dir / "result.json"), business_result)

    return {
        "business_slug": business_slug,
        "status": "done",
        "gate_status": gate_status,
        "visual_profile_path": f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/visual_profile.json",
        "copy_inputs_path": f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/copy_inputs.json",
    }


def run_phase_04_5(run_id: str, workspace: str) -> dict[str, Any]:
    root = Path(workspace)
    config_path = root / "runs" / run_id / "config" / "input_config.json"
    preview_ready_path = root / "runs" / run_id / "04_briefs" / "preview_ready_briefs.json"

    missing_fields: list[str] = []
    for path, label in (
        (config_path, "RunConfig"),
        (preview_ready_path, "preview_ready_briefs[]"),
    ):
        if not path.exists():
            missing_fields.append(label)

    if missing_fields:
        return ResultEnvelope.blocked(
            phase=PHASE_NAME,
            run_id=run_id,
            missing_fields=missing_fields,
            inputs_used=[],
            errors=["Phase 04 outputs required before Phase 04.5"],
        ).to_dict()

    config = read_json(str(config_path))
    preview_ready = read_json(str(preview_ready_path))
    output_dir = root / "runs" / run_id / PHASE_SLUG
    output_dir.mkdir(parents=True, exist_ok=True)

    outputs_created: list[str] = []
    decisions: list[str] = []
    errors: list[str] = []
    processed = 0
    created = 0
    skipped = 0

    for row in preview_ready:
        business_slug = _safe_str(row.get("business_slug"))
        brief_path_str = _safe_str(row.get("brief_path"))
        brief_path = root / brief_path_str if brief_path_str else root / "runs" / run_id / "04_briefs" / business_slug
        facts = _extract_business_facts(brief_path)

        if not business_slug:
            skipped += 1
            errors.append("Skipped preview_ready row with missing business_slug")
            continue

        started_at = _utc_now_iso()
        business_dir = output_dir / business_slug
        business_dir.mkdir(parents=True, exist_ok=True)

        record_id = _record_id(run_id, business_slug)
        preset_id, preset_confidence, preset_reason = _select_preset(config)
        gate_status, gate_notes = _gate_status(facts)

        # Extract services from website HTML
        enriched_services = _extract_enriched_services(brief_path, facts)

        visual_profile = _build_visual_profile(run_id, business_slug, config, facts)
        enriched_facts = _build_enriched_facts(run_id, business_slug, record_id, facts, started_at)
        enrichment_sources = _build_enrichment_sources(run_id, business_slug, started_at)
        public_safe_fields = _build_public_safe_fields(run_id, business_slug, facts, gate_status, started_at, enriched_services)
        internal_only_fields = _build_internal_only_fields(run_id, business_slug, gate_notes, started_at, enriched_services, facts)
        category_mapping = _build_category_mapping(run_id, business_slug, _safe_str(facts.get("category")), started_at)
        design_preset_candidate = _build_design_preset_candidate(run_id, business_slug, preset_id, preset_confidence, preset_reason, started_at)
        copy_inputs = _build_copy_inputs(run_id, business_slug, facts, gate_status, started_at, enriched_services)

        write_json(str(business_dir / "enriched_facts.json"), enriched_facts)
        write_json(str(business_dir / "enrichment_sources.json"), enrichment_sources)
        write_json(str(business_dir / "public_safe_fields.json"), public_safe_fields)
        write_json(str(business_dir / "internal_only_fields.json"), internal_only_fields)
        write_json(str(business_dir / "category_mapping.json"), category_mapping)
        write_json(str(business_dir / "design_preset_candidate.json"), design_preset_candidate)
        write_json(str(business_dir / "visual_profile.json"), visual_profile)
        write_json(str(business_dir / "copy_inputs.json"), copy_inputs)

        business_outputs = [
            f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/enriched_facts.json",
            f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/enrichment_sources.json",
            f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/public_safe_fields.json",
            f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/internal_only_fields.json",
            f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/category_mapping.json",
            f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/design_preset_candidate.json",
            f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/visual_profile.json",
            f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/copy_inputs.json",
            f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/result.json",
        ]
        completed_at = _utc_now_iso()
        business_result = _build_business_result(
            run_id=run_id,
            business_slug=business_slug,
            started_at=started_at,
            completed_at=completed_at,
            outputs_created=business_outputs,
            visual_profile=visual_profile,
            facts=facts,
        )
        business_result_path = business_dir / "result.json"
        write_json(str(business_result_path), business_result)

        outputs_created.extend(business_outputs)
        decisions.append(
            f"Generated visual_profile for {business_slug} with preset {visual_profile['preset_id']} and hero_mode {visual_profile['hero_mode']}"
        )
        processed += 1
        created += 1

    phase_result_path = output_dir / "result.json"
    outputs_created.append(f"runs/{run_id}/{PHASE_SLUG}/result.json")

    phase_result = ResultEnvelope(
        phase=PHASE_NAME,
        status="done",
        run_id=run_id,
        inputs_used=[
            f"runs/{run_id}/config/input_config.json",
            f"runs/{run_id}/04_briefs/preview_ready_briefs.json",
        ],
        outputs_created=outputs_created,
        records_processed=processed,
        records_created=created,
        records_skipped=skipped,
        missing_fields=[],
        decisions=decisions,
        risks=["No photo extraction in initial implementation", "Accent color falls back to generic preset default"],
        errors=errors,
        next_tasks=["Phase 05 — Preview Site Generation"],
    ).model_dump(exclude_none=True, by_alias=True)
    write_json(str(phase_result_path), phase_result)
    return phase_result


def run(run_id: str, workspace: str) -> dict[str, Any]:
    return run_phase_04_5(run_id, workspace)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 04.5 deterministic enrichment")
    parser.add_argument("run_id")
    parser.add_argument("workspace")
    args = parser.parse_args()
    result = run_phase_04_5(args.run_id, args.workspace)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
