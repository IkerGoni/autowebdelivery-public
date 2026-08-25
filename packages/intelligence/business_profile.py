"""
VNEXT-01 — Business Profile Contract.

Build a canonical `business_profile.json` artifact for each preview-ready lead.

This module is pure-Python: it takes a selected lead, the run-level config, and a
run_id, and produces a deterministic dict with three public sections
(`verified_facts`, `inferred_strategy`, `missing_data`), an explicit
`forbidden_public_claims` blocklist, a mirrored `recipient_channel` envelope, and
an `internal` block labelled as never-to-be-passed-to-public-copy.

Determinism: `generated_at` is derived from a SHA-256 of (run_id, business_slug)
mapped to a fixed epoch plus a day offset, so identical inputs produce byte-
identical output across processes and machines (no wall-clock dependence).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from packages.shared.forbidden_claims import FORBIDDEN_PUBLIC_CLAIMS as _FORBIDDEN_PUBLIC_CLAIMS
from packages.shared.provenance import (
    _deterministic_generated_at,
    _has_value,
    _safe_str,
)

try:  # pragma: no cover - import-shim for tests and CLI
    from pipeline.json_io import write_json
except ModuleNotFoundError:  # pragma: no cover
    from packages.pipeline.json_io import write_json

SCHEMA_VERSION = "1.1.0"  # VNEXT-16 added enrichment section

# Source labels for enrichment modules
_SOURCE_OVERPASS = "overpass_enrichment"
_SOURCE_GMAPS = "gmaps_enrichment"
_SOURCE_SOCIAL = "social_enrichment"

# Sentinel used for all fields that the lead provides (i.e. selected_for_preview.json
# is the source of truth for verified facts). The recipient_channel may be derived
# from the lead's website_reason_codes — but that is still recorded under the
# "selected_for_preview.json" source label because it is part of the lead record.
_LEAD_SOURCE = "selected_for_preview.json"
_CONFIG_SOURCE = "input_config.json"

# Provenance / confidence enums.
CONFIDENCE_VERIFIED = "verified"
CONFIDENCE_INFERRED = "inferred"
CONFIDENCE_ENRICHED = "enriched"
CONFIDENCE_UNKNOWN = "unknown"

# Public-safe verified_facts field set, in the order they appear in the artifact.
# These are the only fields that may be considered "verified" from a lead.
_VERIFIED_FIELDS: tuple[str, ...] = (
    "business_name",
    "category",
    "rating",
    "review_count",
    "address",
    "phone",
    "hours",
    "maps_url",
)

# Inferred strategy fields. These are derived from the run config and the lead's
# website_status signal — not "verified" by an authoritative source, but stable
# hints for downstream copy generators.
_INFERRED_FIELDS: tuple[str, ...] = (
    "website_status",
    "niche",
    "area",
    "country",
    "template_family",
)

# Explicit blocklist of claim categories that MUST NEVER appear in public copy.
# These are categories where invented data would create legal or reputational
# risk (e.g. fake licenses, fake insurance, fake years_in_business).
# (Imported from packages.shared.forbidden_claims as _FORBIDDEN_PUBLIC_CLAIMS)


# -----------------------------------------------------------------------------
# Internal-only field registry
# -----------------------------------------------------------------------------
# Fields that are deliberately NEVER exposed through _public_safe, _verified_facts,
# or _inferred_strategy. They are internal scoring/routing signals.
_INTERNAL_ONLY_FIELDS: frozenset[str] = frozenset({
    "lead_score",
    "lead_score_components",
    "lead_score_reasons",
    "lead_score_band",
    "recipient_confidence",
    "recipient_confidence_detail",
    "manual_override_reason",  # internal process detail, not a public-safe claim
    "scoring_internal",
    "scoring_breakdown",
})


# -----------------------------------------------------------------------------
# Public helpers
# -----------------------------------------------------------------------------
def _provenance(field_name: str, source: str, confidence: str) -> dict[str, str]:
    """Return a provenance envelope for a public-safe value.

    The envelope shape is fixed: {"source": ..., "confidence": ...}. Any consumer
    of the business_profile contract can rely on these two keys being present
    whenever a public-safe value is exposed.
    """
    return {"source": source, "confidence": confidence}


def _forbidden_public_claims() -> list[str]:
    """Return the explicit blocklist of claim categories that must never appear
    in public marketing copy generated from this profile."""
    return list(_FORBIDDEN_PUBLIC_CLAIMS)


def _public_safe(field: str, value: Any, *, source: str, confidence: str) -> dict[str, Any]:
    """Wrap a public-safe value with its provenance envelope.

    This is the single chokepoint for exposing a value to downstream copy
    generators. Internal-only fields MUST NOT be passed through this function;
    callers that try to do so will get a ValueError.
    """
    if field in _INTERNAL_ONLY_FIELDS:
        raise ValueError(
            f"Refusing to expose internal-only field {field!r} via _public_safe"
        )
    return {
        "value": value,
        "source": source,
        "confidence": confidence,
    }


def _verified_facts(
    lead: dict[str, Any],
    config: dict[str, Any],
    *,
    overpass_enrichment: dict[str, Any] | None = None,
    gmaps_enrichment: dict[str, Any] | None = None,
    social_enrichment: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return only the verified, public-safe facts that are present on the lead.

    Each entry is a _public_safe envelope. Empty/missing values are simply
    omitted here and surfaced through _missing_data(lead) instead.

    When enrichment data is available (via overpass/gmaps/social_enrichment),
    it may fill in or augment verified facts with ``confidence=enriched``.
    """
    facts: dict[str, dict[str, Any]] = {}
    for field in _VERIFIED_FIELDS:
        raw = lead.get(field)
        # Prefer lead data (source of truth), fall back to enrichment
        if _has_value(raw):
            facts[field] = _public_safe(
                field,
                raw,
                source=_LEAD_SOURCE,
                confidence=CONFIDENCE_VERIFIED,
            )
        else:
            # Try enrichment modules for missing fields
            enriched = _resolve_enriched_fact(field, gmaps_enrichment, overpass_enrichment)
            if enriched is not None:
                facts[field] = _public_safe(
                    field,
                    enriched,
                    source=_SOURCE_GMAPS if gmaps_enrichment else _SOURCE_OVERPASS,
                    confidence=CONFIDENCE_ENRICHED,
                )
    return facts


def _resolve_enriched_fact(
    field: str,
    gmaps_enrichment: dict[str, Any] | None,
    overpass_enrichment: dict[str, Any] | None,
) -> Any:
    """Resolve a verified_fact field from enrichment data.

    Returns the enriched value, or None if not available.
    """
    # Google Maps enrichment provides rating, review_count, hours, description
    if gmaps_enrichment:
        if field == "rating":
            r = gmaps_enrichment.get("rating")
            if r and float(r) > 0:
                return r
        if field == "review_count":
            rc = gmaps_enrichment.get("review_count")
            if rc and int(rc) > 0:
                return rc
        if field == "hours":
            hrs = gmaps_enrichment.get("hours")
            if hrs and isinstance(hrs, dict) and len(hrs) > 0:
                return hrs
        if field == "maps_url":
            su = gmaps_enrichment.get("source_url")
            if su:
                return su

    # Overpass enrichment provides hours via OSM tags
    if overpass_enrichment and field == "hours":
        osm_tags = overpass_enrichment.get("osm_tags", {})
        if isinstance(osm_tags, dict):
            hrs = osm_tags.get("hours")
            if hrs:
                return hrs

    return None


def _inferred_strategy(lead: dict[str, Any], config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return inferred strategy signals, public-safe, with confidence=inferred.

    website_status is a lead signal; niche/area/country/template_family are
    run-level config values. None are sourced from an authoritative registry.
    """
    strategy: dict[str, dict[str, Any]] = {}
    # website_status — from lead
    website_status = lead.get("website_status")
    if _has_value(website_status):
        strategy["website_status"] = _public_safe(
            "website_status",
            website_status,
            source=_LEAD_SOURCE,
            confidence=CONFIDENCE_INFERRED,
        )
    # Run-level config values
    for field, config_key in (
        ("niche", "niche"),
        ("area", "area"),
        ("country", "country"),
        ("template_family", "style_preset"),
    ):
        value = config.get(config_key)
        if not _has_value(value):
            continue
        strategy[field] = _public_safe(
            field,
            value,
            source=_CONFIG_SOURCE,
            confidence=CONFIDENCE_INFERRED,
        )
    return strategy


def _missing_data(
    lead: dict[str, Any],
    *,
    overpass_enrichment: dict[str, Any] | None = None,
    gmaps_enrichment: dict[str, Any] | None = None,
    social_enrichment: dict[str, Any] | None = None,
) -> list[str]:
    """Return the list of expected public-safe verified_facts fields that are
    missing from the lead and not filled by enrichment."""
    missing: list[str] = []
    for field in _VERIFIED_FIELDS:
        if _has_value(lead.get(field)):
            continue
        # Check if enrichment fills it
        if _resolve_enriched_fact(field, gmaps_enrichment, overpass_enrichment) is not None:
            continue
        missing.append(field)
    return missing


def _recipient_channel_envelope(lead: dict[str, Any]) -> dict[str, Any] | None:
    """Mirror the recipient_channel.json shape (channel/value/source/confidence).

    Returns None if no recipient channel is known — the contract is explicit
    that an unknown channel is itself a signal that downstream generators must
    surface (e.g. as a "blocked" reason), not silently coerced into a value.
    """
    reason_codes = [str(code) for code in lead.get("website_reason_codes", [])]
    phone = _safe_str(lead.get("phone"))

    # Phone is verified if present
    if phone:
        return {
            "channel": "phone",
            "value": phone,
            "source": "google_maps_listing",
            "confidence": CONFIDENCE_VERIFIED,
        }

    # Social platforms are inferred from the lead's reason codes
    for code in reason_codes:
        if code == "social_platform:facebook.com":
            return {
                "channel": "facebook_message",
                "value": "facebook.com",
                "source": "social_profile",
                "confidence": CONFIDENCE_INFERRED,
            }
        if code == "social_platform:instagram.com":
            return {
                "channel": "instagram_dm",
                "value": "instagram.com",
                "source": "social_profile",
                "confidence": CONFIDENCE_INFERRED,
            }
        if code == "social_platform:line.me":
            return {
                "channel": "line",
                "value": "line.me",
                "source": "social_profile",
                "confidence": CONFIDENCE_INFERRED,
            }

    # No known channel — explicit null
    return {
        "channel": "unknown",
        "value": "",
        "source": "unknown",
        "confidence": CONFIDENCE_UNKNOWN,
    }


# -----------------------------------------------------------------------------
# Enrichment section builder
# -----------------------------------------------------------------------------
def _enrichment_data(
    overpass_enrichment: dict[str, Any] | None = None,
    gmaps_enrichment: dict[str, Any] | None = None,
    social_enrichment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the enrichment section of the business profile.

    Collects structured metadata from each enrichment module that was
    active during the run. Only non-empty sources are included.
    """
    section: dict[str, Any] = {}

    if overpass_enrichment:
        section["overpass"] = {
            "osm_type": overpass_enrichment.get("osm_type", ""),
            "osm_tags": overpass_enrichment.get("osm_tags", {}),
            "enrichment_source": "overpass",
        }

    if gmaps_enrichment:
        gmb = dict(gmaps_enrichment)  # shallow copy
        # Omit large payloads that aren't needed for brand/profile inference
        gmb.pop("photos", None)
        section["google_maps"] = gmb

    if social_enrichment:
        section["social"] = {
            "platform": social_enrichment.get("platform", ""),
            "username": social_enrichment.get("username", ""),
            "profile_url": social_enrichment.get("profile_url", ""),
            "about_text": social_enrichment.get("about_text", ""),
            "follower_count": social_enrichment.get("follower_count", 0),
            "following_count": social_enrichment.get("following_count", 0),
            "post_count": social_enrichment.get("post_count", 0),
            "is_verified": social_enrichment.get("is_verified", False),
            "business_category": social_enrichment.get("business_category", ""),
            "enrichment_source": "social_scraper",
        }

    return section


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------
def build_business_profile(
    lead: dict[str, Any],
    config: dict[str, Any],
    *,
    run_id: str,
    overpass_enrichment: dict[str, Any] | None = None,
    gmaps_enrichment: dict[str, Any] | None = None,
    social_enrichment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the canonical business_profile dict for a single lead.

    The returned dict is fully serializable to JSON and contains only:
      - verified_facts   (public-safe, confidence=verified, source=lead)
      - inferred_strategy (public-safe hints, confidence=inferred, source=config/lead)
      - enrichment       (structured data from Overpass/GMB/Social modules)
      - missing_data      (explicit list of expected fields not present)
      - forbidden_public_claims (blocklist, present in every profile)
      - recipient_channel (mirrors recipient_channel.json, never silently dropped)
      - internal          (labelled as not-for-public-copy; carries provenance only)
    """
    business_slug = _safe_str(lead.get("business_slug"))
    if not business_slug:
        raise ValueError("lead.business_slug is required to build a business_profile")

    # Build enrichment section only if any enrichment data is present
    enrichment = _enrichment_data(
        overpass_enrichment=overpass_enrichment,
        gmaps_enrichment=gmaps_enrichment,
        social_enrichment=social_enrichment,
    )

    profile: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "business_slug": business_slug,
        "generated_at": _deterministic_generated_at(run_id, business_slug),
        "verified_facts": _verified_facts(
            lead, config,
            overpass_enrichment=overpass_enrichment,
            gmaps_enrichment=gmaps_enrichment,
            social_enrichment=social_enrichment,
        ),
        "inferred_strategy": _inferred_strategy(lead, config),
        "missing_data": _missing_data(
            lead,
            overpass_enrichment=overpass_enrichment,
            gmaps_enrichment=gmaps_enrichment,
            social_enrichment=social_enrichment,
        ),
        "forbidden_public_claims": _forbidden_public_claims(),
        "recipient_channel": _recipient_channel_envelope(lead),
        "internal": {
            "flag": "use_business_profile_contract",
            "schema_origin": "VNEXT-01",
            "enrichment_sources": [
                src for src, val in [
                    ("overpass", overpass_enrichment),
                    ("gmaps", gmaps_enrichment),
                    ("social", social_enrichment),
                ] if val
            ],
        },
    }

    # Only include enrichment section when there's data
    if enrichment:
        profile["enrichment"] = enrichment

    return profile


def write_business_profile(profile: dict[str, Any], output_dir: str | Path, business_slug: str) -> str:
    """Write the profile to {output_dir}/{business_slug}/business_profile.json.

    Returns the absolute path of the written file.
    """
    output_path = Path(output_dir) / business_slug / "business_profile.json"
    return write_json(str(output_path), profile)
