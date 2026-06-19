"""
Phase 04 — Business Brief and Recipient Routing

Generate fact-safe brief packs and route them by recipient availability.

Inputs:
  - runs/{run_id}/config/input_config.json
  - runs/{run_id}/03_scoring/selected_for_preview.json

Outputs:
  - runs/{run_id}/04_briefs/{business_slug}/FACTS.md
  - runs/{run_id}/04_briefs/{business_slug}/MISSING_DATA.md
  - runs/{run_id}/04_briefs/{business_slug}/BUSINESS_BRIEF.md
  - runs/{run_id}/04_briefs/{business_slug}/CONTENT_PLAN.md
  - runs/{run_id}/04_briefs/{business_slug}/DESIGN.md
  - runs/{run_id}/04_briefs/{business_slug}/GENERATION_PROMPT.md
  - runs/{run_id}/04_briefs/{business_slug}/recipient_channel.json
  - runs/{run_id}/04_briefs/briefs_index.json
  - runs/{run_id}/04_briefs/preview_ready_briefs.json
  - runs/{run_id}/04_briefs/blocked_no_recipient_channel.json
  - runs/{run_id}/04_briefs/result.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from pipeline.json_io import read_json, write_json
    from pipeline.result_envelope import ResultEnvelope
except ModuleNotFoundError:  # pragma: no cover - CLI fallback
    from packages.pipeline.json_io import read_json, write_json
    from packages.pipeline.result_envelope import ResultEnvelope

from packages.shared.provenance import _safe_str

try:
    from packages.intelligence.business_profile import (
        build_business_profile,
        write_business_profile,
    )
except ModuleNotFoundError:  # pragma: no cover - CLI fallback
    from pipeline.business_profile import (  # type: ignore[no-redef]
        build_business_profile,
        write_business_profile,
    )

try:
    from packages.intelligence.market_profile import (
        build_market_profile,
        write_market_profile,
    )
except ModuleNotFoundError:  # pragma: no cover - CLI fallback
    from pipeline.market_profile import (  # type: ignore[no-redef]
        build_market_profile,
        write_market_profile,
    )

PHASE_SLUG = "04_briefs"
PHASE_NAME = "phase_04_business_brief"
BLOCKED_REASON = "recipient_channel is unknown; manual recipient discovery or override required"

# VNEXT-01: feature flag (default OFF). When ON, Phase 04 also writes a
# canonical `business_profile.json` per business. The flag is intentionally
# NOT read from any default config; callers must opt in explicitly.
USE_BUSINESS_PROFILE_CONTRACT_FLAG = "use_business_profile_contract"

# VNEXT-02: feature flag
USE_MARKET_PROFILE_CONTRACT_FLAG = "use_market_profile_contract"


def _missing_fields(lead: dict[str, Any]) -> list[str]:
    checks = (
        ("address", _safe_str(lead.get("address"))),
        ("phone", _safe_str(lead.get("phone"))),
        ("hours", _safe_str(lead.get("hours"))),
        ("maps_url", _safe_str(lead.get("maps_url"))),
    )
    return [name for name, value in checks if not value]


def detect_recipient_channel(lead: dict[str, Any]) -> dict[str, Any]:
    business_slug = _safe_str(lead.get("business_slug"))
    reason_codes = [str(code) for code in lead.get("website_reason_codes", [])]
    manual_override = bool(lead.get("manual_override", False))
    manual_override_reason = _safe_str(lead.get("manual_override_reason"))

    for code in reason_codes:
        if code == "social_platform:facebook.com":
            return {
                "business_slug": business_slug,
                "recipient_channel": "facebook_message",
                "recipient_value": "facebook.com",
                "recipient_source": "social_profile",
                "recipient_confidence": "inferred",
                "discovery_notes": "Derived from Phase 02.1 social platform signal: facebook.com",
                "manual_override": manual_override,
                "manual_override_reason": manual_override_reason,
            }
        if code == "social_platform:instagram.com":
            return {
                "business_slug": business_slug,
                "recipient_channel": "instagram_dm",
                "recipient_value": "instagram.com",
                "recipient_source": "social_profile",
                "recipient_confidence": "inferred",
                "discovery_notes": "Derived from Phase 02.1 social platform signal: instagram.com",
                "manual_override": manual_override,
                "manual_override_reason": manual_override_reason,
            }
        if code == "social_platform:line.me":
            return {
                "business_slug": business_slug,
                "recipient_channel": "line",
                "recipient_value": "line.me",
                "recipient_source": "social_profile",
                "recipient_confidence": "inferred",
                "discovery_notes": "Derived from Phase 02.1 social platform signal: line.me",
                "manual_override": manual_override,
                "manual_override_reason": manual_override_reason,
            }

    phone = _safe_str(lead.get("phone"))
    if phone:
        return {
            "business_slug": business_slug,
            "recipient_channel": "phone",
            "recipient_value": phone,
            "recipient_source": "google_maps_listing",
            "recipient_confidence": "verified",
            "discovery_notes": "Phone present in selected_for_preview.json source record",
            "manual_override": manual_override,
            "manual_override_reason": manual_override_reason,
        }

    return {
        "business_slug": business_slug,
        "recipient_channel": "unknown",
        "recipient_value": "",
        "recipient_source": "unknown",
        "recipient_confidence": "unknown",
        "discovery_notes": "No verified outreach endpoint available from selected lead fields",
        "manual_override": manual_override,
        "manual_override_reason": manual_override_reason,
    }


def _facts_md(lead: dict[str, Any], recipient: dict[str, Any]) -> str:
    facts = [
        "# FACTS",
        "",
        f"- business_name: {lead.get('business_name', '')}",
        f"- category: {lead.get('category', '')}",
        f"- rating: {lead.get('rating', '')}",
        f"- review_count: {lead.get('review_count', '')}",
        f"- address: {lead.get('address', '')}",
        f"- phone: {lead.get('phone', '')}",
        f"- hours: {lead.get('hours', '')}",
        f"- maps_url: {lead.get('maps_url', '')}",
        f"- website_status: {lead.get('website_status', '')}",
        f"- niche: {lead.get('niche', '')}",
        f"- area: {lead.get('area', '')}",
        f"- country: {lead.get('country', '')}",
        f"- template_family: {lead.get('template_family', '')}",
        f"- template_variant: {lead.get('template_variant', '')}",
        f"- stitch_project_id: {lead.get('stitch_project_id', '')}",
        f"- recipient_channel: {recipient['recipient_channel']}",
        f"- recipient_value: {recipient['recipient_value']}",
        f"- price_offer: {lead.get('price_offer', '')}",
        f"- offer_type: {lead.get('offer_type', '')}",
        f"- offer_price: {lead.get('offer_price', '')}",
        f"- currency: {lead.get('currency', '')}",
        f"- pricing_market: {lead.get('pricing_market', '')}",
    ]
    return "\n".join(facts) + "\n"


def _missing_data_md(missing: list[str]) -> str:
    lines = ["# MISSING_DATA", ""]
    if not missing:
        lines.append("- none")
    else:
        lines.extend(f"- {field}" for field in missing)
    return "\n".join(lines) + "\n"


def _business_brief_md(lead: dict[str, Any], missing: list[str]) -> str:
    lines = [
        "# BUSINESS_BRIEF",
        "",
        f"Business: {lead.get('business_name', '')}",
        f"Category: {lead.get('category', '')}",
        f"Location: {lead.get('address', '') or 'Unknown'}",
        "",
        "## Verified positioning inputs",
        f"- Rating: {lead.get('rating', '')}",
        f"- Review count: {lead.get('review_count', '')}",
        f"- Website status: {lead.get('website_status', '')}",
        f"- Google Maps URL: {lead.get('maps_url', '')}",
        "",
        "## Constraints",
        "- Use verified facts only.",
        "- Do not invent services, offers, staff, years in business, or claims.",
        "- If field missing, omit from generated marketing copy.",
        "",
        "## Missing data",
    ]
    if missing:
        lines.extend(f"- {field}" for field in missing)
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def _content_plan_md(lead: dict[str, Any], missing: list[str]) -> str:
    lines = [
        "# CONTENT_PLAN",
        "",
        "## Sections",
        f"- Hero: business name and category for {lead.get('business_name', '')}",
        f"- Trust: rating {lead.get('rating', '')} and {lead.get('review_count', '')} reviews",
        "- Location: address and Google Maps CTA if available",
        "- Contact: phone and hours only if present",
        "",
        "## Omit if missing",
    ]
    if missing:
        lines.extend(f"- {field}" for field in missing)
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def _design_md(config: dict[str, Any], lead: dict[str, Any]) -> str:
    return "\n".join([
        "# DESIGN",
        "",
        f"- style_preset: {config.get('style_preset', '')}",
        f"- niche: {config.get('niche', '')}",
        f"- area: {config.get('area', '')}",
        f"- country: {config.get('country', '')}",
        f"- language: {config.get('language', '')}",
        f"- business_slug: {lead.get('business_slug', '')}",
        f"- template_family: {config.get('style_preset', '')}",
        "- template_variant: single_page_preview",
        f"- stitch_project_id: {config.get('stitch_project_id', '')}",
        "- visual_rule: clean, local, trustworthy, mobile-first",
    ]) + "\n"


def _generation_prompt_md(lead: dict[str, Any], recipient: dict[str, Any], missing: list[str], config: dict[str, Any]) -> str:
    lines = [
        "# GENERATION_PROMPT",
        "",
        "Build one-page preview site using verified facts only.",
        f"Business: {lead.get('business_name', '')}",
        f"Category: {lead.get('category', '')}",
        f"Area: {config.get('area', '')}, {config.get('country', '')}",
        f"Style preset: {config.get('style_preset', '')}",
        f"Offer: {config.get('price_offer', '')}",
        f"Recipient channel: {recipient.get('recipient_channel', '')}",
        "Do not invent unsupported claims.",
        "Use rating and review count exactly as given.",
        "Omit missing fields instead of guessing.",
        "",
        "Missing fields:",
    ]
    if missing:
        lines.extend(f"- {field}" for field in missing)
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def build_brief_pack(lead: dict[str, Any], config: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    enriched = dict(lead)
    enriched["price_offer"] = config.get("price_offer", "")
    enriched["offer_type"] = config.get("offer_type", "setup_only")
    enriched["offer_price"] = config.get("offer_price", "")
    enriched["currency"] = config.get("currency", "")
    enriched["pricing_market"] = config.get("pricing_market", f"{config.get('area', '')}, {config.get('country', '')}".strip(", "))
    enriched["niche"] = config.get("niche", "")
    enriched["area"] = config.get("area", "")
    enriched["country"] = config.get("country", "")
    enriched["template_family"] = config.get("style_preset", "")
    enriched["template_variant"] = config.get("template_variant", "single_page_preview")
    enriched["stitch_project_id"] = config.get("stitch_project_id", "")
    recipient = detect_recipient_channel(enriched)
    missing = _missing_fields(enriched)

    business_dir = output_dir / _safe_str(lead.get("business_slug"))
    business_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "FACTS.md": _facts_md(enriched, recipient),
        "MISSING_DATA.md": _missing_data_md(missing),
        "BUSINESS_BRIEF.md": _business_brief_md(enriched, missing),
        "CONTENT_PLAN.md": _content_plan_md(enriched, missing),
        "DESIGN.md": _design_md(config, enriched),
        "GENERATION_PROMPT.md": _generation_prompt_md(enriched, recipient, missing, config),
    }
    for name, content in files.items():
        (business_dir / name).write_text(content, encoding="utf-8")

    recipient_path = business_dir / "recipient_channel.json"
    write_json(str(recipient_path), recipient)

    # VNEXT-01: optional canonical business_profile.json (feature-flagged, default OFF).
    # This block must not alter any of the files written above.
    if bool(config.get(USE_BUSINESS_PROFILE_CONTRACT_FLAG, False)):
        run_id = _safe_str(lead.get("run_id")) or "unknown_run"
        profile = build_business_profile(enriched, config, run_id=run_id)
        write_business_profile(profile, output_dir, _safe_str(lead.get("business_slug")))

    # VNEXT-02: market_profile.json
    if bool(config.get(USE_MARKET_PROFILE_CONTRACT_FLAG, False)):
        run_id = _safe_str(lead.get("run_id")) or "unknown_run"
        bi_score = lead.get("business_intelligence") or {}
        m_profile = build_market_profile(enriched, config, run_id=run_id, bi_score=bi_score)
        write_market_profile(m_profile, output_dir, _safe_str(lead.get("business_slug")))

    return {
        "run_id": _safe_str(lead.get("run_id")),
        "business_slug": _safe_str(lead.get("business_slug")),
        "business_name": _safe_str(lead.get("business_name")),
        "brief_path": f"runs/{_safe_str(lead.get('run_id'))}/{PHASE_SLUG}/{_safe_str(lead.get('business_slug'))}",
        "recipient_channel": recipient["recipient_channel"],
        "manual_override": recipient.get("manual_override", False),
        "manual_override_reason": recipient.get("manual_override_reason", ""),
        "missing_fields": missing,
        "website_status": _safe_str(lead.get("website_status")),
    }


def route_briefs(briefs_index: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    preview_ready: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for row in briefs_index:
        manual_override = bool(row.get("manual_override", False))
        manual_override_reason = _safe_str(row.get("manual_override_reason"))
        if row.get("recipient_channel") != "unknown":
            preview_ready.append({
                "business_slug": row["business_slug"],
                "brief_path": row["brief_path"],
                "recipient_channel": row["recipient_channel"],
                "manual_override": manual_override,
                "manual_override_reason": manual_override_reason,
            })
            continue
        if manual_override and manual_override_reason:
            preview_ready.append({
                "business_slug": row["business_slug"],
                "brief_path": row["brief_path"],
                "recipient_channel": row["recipient_channel"],
                "manual_override": True,
                "manual_override_reason": manual_override_reason,
            })
            continue
        blocked.append({
            "business_slug": row["business_slug"],
            "brief_path": row["brief_path"],
            "recipient_channel": "unknown",
            "blocked_reason": BLOCKED_REASON,
        })

    return preview_ready, blocked


def run_phase_04(run_id: str, workspace: str) -> dict[str, Any]:
    root = Path(workspace)
    config_path = root / "runs" / run_id / "config" / "input_config.json"
    selected_path = root / "runs" / run_id / "03_scoring" / "selected_for_preview.json"

    missing_fields: list[str] = []
    for path, label in (
        (config_path, "RunConfig"),
        (selected_path, "selected_for_preview[]"),
    ):
        if not path.exists():
            missing_fields.append(label)

    if missing_fields:
        return ResultEnvelope.blocked(
            phase=PHASE_NAME,
            run_id=run_id,
            missing_fields=missing_fields,
            inputs_used=[],
            errors=["Phase 01 and Phase 03 outputs required before Phase 04"],
        ).to_dict()

    config = read_json(str(config_path))
    selected = read_json(str(selected_path))
    output_dir = root / "runs" / run_id / PHASE_SLUG
    output_dir.mkdir(parents=True, exist_ok=True)

    briefs_index = [build_brief_pack(lead, config, output_dir) for lead in selected]
    preview_ready, blocked = route_briefs(briefs_index)

    briefs_index_path = output_dir / "briefs_index.json"
    preview_ready_path = output_dir / "preview_ready_briefs.json"
    blocked_path = output_dir / "blocked_no_recipient_channel.json"
    result_path = output_dir / "result.json"

    write_json(str(briefs_index_path), briefs_index)
    write_json(str(preview_ready_path), preview_ready)
    write_json(str(blocked_path), blocked)

    # VNEXT-01: if the feature flag is on, surface the per-business
    # business_profile.json files in outputs_created for orchestrator visibility.
    extra_outputs: list[str] = []
    if bool(config.get(USE_BUSINESS_PROFILE_CONTRACT_FLAG, False)):
        extra_outputs = [
            f"runs/{run_id}/{PHASE_SLUG}/{row['business_slug']}/business_profile.json"
            for row in briefs_index
        ]

    if bool(config.get(USE_MARKET_PROFILE_CONTRACT_FLAG, False)):
        extra_outputs.extend([
            f"runs/{run_id}/{PHASE_SLUG}/{row['business_slug']}/market_profile.json"
            for row in briefs_index
        ])

    result = ResultEnvelope(
        phase=PHASE_NAME,
        status="done",
        run_id=run_id,
        inputs_used=[
            f"runs/{run_id}/config/input_config.json",
            f"runs/{run_id}/03_scoring/selected_for_preview.json",
        ],
        outputs_created=[
            *[f"runs/{run_id}/{PHASE_SLUG}/{row['business_slug']}/FACTS.md" for row in briefs_index],
            *[f"runs/{run_id}/{PHASE_SLUG}/{row['business_slug']}/MISSING_DATA.md" for row in briefs_index],
            *[f"runs/{run_id}/{PHASE_SLUG}/{row['business_slug']}/BUSINESS_BRIEF.md" for row in briefs_index],
            *[f"runs/{run_id}/{PHASE_SLUG}/{row['business_slug']}/CONTENT_PLAN.md" for row in briefs_index],
            *[f"runs/{run_id}/{PHASE_SLUG}/{row['business_slug']}/DESIGN.md" for row in briefs_index],
            *[f"runs/{run_id}/{PHASE_SLUG}/{row['business_slug']}/GENERATION_PROMPT.md" for row in briefs_index],
            *[f"runs/{run_id}/{PHASE_SLUG}/{row['business_slug']}/recipient_channel.json" for row in briefs_index],
            *extra_outputs,
            f"runs/{run_id}/{PHASE_SLUG}/briefs_index.json",
            f"runs/{run_id}/{PHASE_SLUG}/preview_ready_briefs.json",
            f"runs/{run_id}/{PHASE_SLUG}/blocked_no_recipient_channel.json",
            f"runs/{run_id}/{PHASE_SLUG}/result.json",
        ],
        records_processed=len(selected),
        records_created=len(briefs_index),
        records_skipped=len(blocked),
        missing_fields=[],
        decisions=[
            f"Generated {len(briefs_index)} business brief packs",
            f"Routed {len(preview_ready)} briefs to preview_ready_briefs.json",
            f"Routed {len(blocked)} briefs to blocked_no_recipient_channel.json",
        ],
        risks=[],
        errors=[],
        next_tasks=["Phase 05 — Preview Site Generation"],
    ).model_dump(exclude_none=True, by_alias=True)
    write_json(str(result_path), result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 04 — Business Brief and Recipient Routing")
    parser.add_argument("--run-id", default="fixture_001", help="Run ID (default: fixture_001)")
    parser.add_argument("--project-root", default=".", help="Project root (default: current directory)")
    args = parser.parse_args()

    result = run_phase_04(args.run_id, args.project_root)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
