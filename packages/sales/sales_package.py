"""
VNEXT-08 — Sales Package Contract.

Build a structured ``sales_package.json`` artifact for each preview-ready lead,
aggregating data from upstream artifacts (business_profile, market_profile,
creative_spec, evaluation_report) into an owner-facing sales package.

This module is pure-Python and deterministic: it takes structured dicts and
produces a deterministic dict with a fixed schema.  No LLM calls are involved.

Feature-flagged behind ``use_sales_package_contract`` (default OFF).
This module is **additive** — it does not modify existing Phase 08/09 output.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from packages.shared.forbidden_claims import FORBIDDEN_PUBLIC_CLAIMS as _FORBIDDEN_PUBLIC_CLAIMS
from packages.shared.provenance import (
    _has_value,
)

try:  # pragma: no cover - import-shim for tests and CLI
    from pipeline.json_io import write_json
except ModuleNotFoundError:  # pragma: no cover
    from packages.pipeline.json_io import write_json

SCHEMA_VERSION = "1.0.0"

# Provenance / confidence constants
CONFIDENCE_VERIFIED = "verified"
CONFIDENCE_INFERRED = "inferred"
CONFIDENCE_UNKNOWN = "unknown"

# Source labels
_SOURCE_BUSINESS_PROFILE = "business_profile.json"
_SOURCE_MARKET_PROFILE = "market_profile.json"
_SOURCE_CREATIVE_SPEC = "creative_spec.json"
_SOURCE_EVALUATION_REPORT = "evaluation_report.json"
_SOURCE_INPUT_CONFIG = "input_config.json"
_SOURCE_DEPLOYMENT = "deployment"
_SOURCE_PHASE_05_5 = "phase_05_5"
_SOURCE_GOOGLE_MAPS = "google_maps_listing"

# Explicit blocklist of claim categories that MUST NEVER appear in public copy.
# (Imported from packages.shared.forbidden_claims as _FORBIDDEN_PUBLIC_CLAIMS)

# Business summary fields that carry provenance envelopes.
_BUSINESS_SUMMARY_FIELDS: tuple[str, ...] = (
    "business_name",
    "category",
    "rating",
    "review_count",
    "address",
    "phone",
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _provenance(
    field_name: str,
    value: Any,
    *,
    source: str,
    confidence: str,
) -> dict[str, Any]:
    """Return a provenance envelope for a value."""
    return {"value": value, "source": source, "confidence": confidence}


def _deterministic_generated_at(run_id: str, business_slug: str) -> str:
    """Return a deterministic ISO8601 timestamp derived from (run_id, business_slug).

    Uses the same algorithm as business_profile: SHA-256 → day offset → epoch + offset.
    """
    digest = hashlib.sha256(
        f"sales_pkg|{run_id}|{business_slug}".encode()
    ).hexdigest()
    day_offset = int(digest[:8], 16) % 3650
    epoch = datetime(2026, 1, 1, tzinfo=timezone.utc)
    moment = epoch + timedelta(days=day_offset)
    return moment.isoformat().replace("+00:00", "Z")


def _extract_verified_fact(business_profile: dict, field: str) -> Any | None:
    """Extract a value from business_profile verified_facts, or fall back to top-level."""
    # Try verified_facts first
    vf = business_profile.get("verified_facts", {})
    if field in vf:
        entry = vf[field]
        if isinstance(entry, dict) and "value" in entry:
            return entry["value"]
    # Fall back to top-level for backward compat
    val = business_profile.get(field)
    if _has_value(val):
        return val
    return None


def _build_business_summary(
    business_profile: dict,
) -> dict[str, dict[str, Any]]:
    """Build the business_summary section with provenance envelopes."""
    summary: dict[str, dict[str, Any]] = {}
    for field in _BUSINESS_SUMMARY_FIELDS:
        value = _extract_verified_fact(business_profile, field)
        if _has_value(value):
            summary[field] = _provenance(
                field,
                value,
                source=_SOURCE_BUSINESS_PROFILE,
                confidence=CONFIDENCE_VERIFIED,
            )
    return summary


def _build_offer(config: dict | None) -> dict[str, dict[str, Any]]:
    """Build the offer section from config."""
    if config is None:
        return {}

    offer: dict[str, dict[str, Any]] = {}

    price = config.get("price_offer") or config.get("offer_price", "")
    if _has_value(price):
        offer["price"] = _provenance(
            "price",
            str(price),
            source=_SOURCE_INPUT_CONFIG,
            confidence=CONFIDENCE_VERIFIED,
        )

    offer_type = config.get("offer_type", "")
    if _has_value(offer_type):
        desc = "One-time setup" if offer_type == "setup_only" else str(offer_type)
    else:
        desc = "One-time setup"

    offer["description"] = _provenance(
        "description",
        desc,
        source=_SOURCE_INPUT_CONFIG,
        confidence=CONFIDENCE_VERIFIED,
    )

    return offer


def _build_owner_facing_summary(
    business_profile: dict,
    evaluation_report: dict | None,
) -> str:
    """Generate a safe, factual 1-2 sentence summary for the owner.

    Template-based, deterministic, no LLM.
    Template: "A professional website for {business_name} showcasing their
    {category} services{rating_phrase}{contact_phrase}."
    """
    business_name = _extract_verified_fact(business_profile, "business_name") or "your business"
    category = _extract_verified_fact(business_profile, "category") or ""

    # Category phrase
    category_phrase = f" {category}" if category else ""
    services_phrase = f"showcasing their{category_phrase} services" if category else "showcasing their services"

    # Rating phrase
    rating = _extract_verified_fact(business_profile, "rating")
    review_count = _extract_verified_fact(business_profile, "review_count")
    rating_phrase = ""
    if _has_value(rating) and _has_value(review_count):
        rating_phrase = f" with a {rating} rating from {review_count} reviews"
    elif _has_value(rating):
        rating_phrase = f" with a {rating} rating"

    # Contact phrase
    phone = _extract_verified_fact(business_profile, "phone")
    contact_phrase = " and easy booking" if _has_value(phone) else ""

    return f"A professional website for {business_name} {services_phrase}{rating_phrase}{contact_phrase}."


def _build_evaluation_summary(evaluation_report: dict | None) -> dict[str, Any]:
    """Extract top-level evaluation metrics."""
    if evaluation_report is None:
        return {
            "overall_score": None,
            "verdict": "not_evaluated",
            "top_dimensions": {},
        }

    overall_score = evaluation_report.get("overall_score")
    verdict = evaluation_report.get("verdict", "not_evaluated")

    # Extract dimension scores (top 3 by score)
    dimensions = evaluation_report.get("dimensions", {})
    top_dims: dict[str, Any] = {}
    if isinstance(dimensions, dict):
        sorted_dims = sorted(
            dimensions.items(),
            key=lambda item: item[1].get("score", 0) if isinstance(item[1], dict) else 0,
            reverse=True,
        )
        for name, data in sorted_dims[:3]:
            score = data.get("score") if isinstance(data, dict) else data
            if _has_value(score):
                top_dims[name] = score

    return {
        "overall_score": overall_score,
        "verdict": verdict,
        "top_dimensions": top_dims,
    }


def _build_compliance_notes(
    business_profile: dict,
    evaluation_report: dict | None,
) -> dict[str, Any]:
    """Build compliance verification notes."""
    # Check forbidden claims
    forbidden_check_passed = True
    unsupported_claims: list[str] = []

    if evaluation_report is not None:
        claims_check = evaluation_report.get("forbidden_claims_check", {})
        if isinstance(claims_check, dict):
            forbidden_check_passed = claims_check.get("passed", True)
            unsupported_claims = claims_check.get("violations", [])

    # Missing data from business profile
    missing_data = business_profile.get("missing_data", [])
    if not isinstance(missing_data, list):
        missing_data = []

    return {
        "forbidden_claims_checked": True,
        "no_unsupported_claims": forbidden_check_passed and len(unsupported_claims) == 0,
        "missing_data_noted": sorted(missing_data),
    }


def _build_recipient_channel(business_profile: dict) -> dict[str, Any]:
    """Extract recipient channel from business_profile."""
    # Try business_profile's own recipient_channel first
    rc = business_profile.get("recipient_channel")
    if isinstance(rc, dict) and _has_value(rc.get("value")):
        return rc

    # Fall back to phone from verified_facts
    phone = _extract_verified_fact(business_profile, "phone")
    if _has_value(phone):
        return {
            "channel": "phone",
            "value": str(phone),
            "source": _SOURCE_GOOGLE_MAPS,
            "confidence": CONFIDENCE_VERIFIED,
        }

    return {
        "channel": "unknown",
        "value": "",
        "source": "unknown",
        "confidence": CONFIDENCE_UNKNOWN,
    }


def _build_preview_url(
    preview_url: str,
    config: dict | None,
) -> dict[str, Any]:
    """Build preview_url section."""
    if _has_value(preview_url):
        return _provenance(
            "preview_url",
            preview_url,
            source=_SOURCE_DEPLOYMENT,
            confidence=CONFIDENCE_VERIFIED,
        )
    return _provenance(
        "preview_url",
        "",
        source=_SOURCE_DEPLOYMENT,
        confidence=CONFIDENCE_UNKNOWN,
    )


def _build_screenshots(screenshots: dict | None) -> dict[str, Any]:
    """Build screenshots section."""
    if screenshots is None:
        return {}

    result: dict[str, Any] = {}
    for key in ("desktop", "mobile"):
        val = screenshots.get(key)
        if _has_value(val):
            result[key] = _provenance(
                key,
                val,
                source=_SOURCE_PHASE_05_5,
                confidence=CONFIDENCE_VERIFIED,
            )
    return result


def _collect_missing_data(
    business_profile: dict,
    preview_url: str,
    screenshots: dict | None,
    evaluation_report: dict | None,
) -> list[str]:
    """Collect all missing data signals across sources."""
    missing: list[str] = []

    # From business_profile
    bp_missing = business_profile.get("missing_data", [])
    if isinstance(bp_missing, list):
        missing.extend(bp_missing)

    # No preview URL
    if not _has_value(preview_url):
        missing.append("preview_url")

    # Screenshots
    if screenshots is None:
        missing.append("screenshots")
    else:
        if not _has_value(screenshots.get("desktop")):
            missing.append("screenshot_desktop")
        if not _has_value(screenshots.get("mobile")):
            missing.append("screenshot_mobile")

    # No evaluation
    if evaluation_report is None:
        missing.append("evaluation_report")

    return sorted(set(missing))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_sales_package(
    business_profile: dict,
    market_profile: dict | None = None,
    creative_spec: dict | None = None,
    evaluation_report: dict | None = None,
    config: dict | None = None,
    *,
    run_id: str,
    preview_url: str = "",
    screenshots: dict | None = None,
) -> dict[str, Any]:
    """Build the canonical sales_package dict.

    Aggregates data from upstream artifacts into an owner-facing sales package.
    All inputs are structured dicts; no LLM calls. Fully deterministic given
    identical inputs.

    Parameters
    ----------
    business_profile:
        The canonical business_profile.json dict.
    market_profile:
        Optional market_profile.json dict (currently unused, reserved).
    creative_spec:
        Optional creative_spec.json dict (currently unused, reserved).
    evaluation_report:
        Optional evaluation_report.json dict.
    config:
        Optional run config dict (price_offer, offer_type, etc.).
    run_id:
        Pipeline run identifier.
    preview_url:
        Live URL of the deployed site (empty if not yet deployed).
    screenshots:
        Optional dict with "desktop" and/or "mobile" keys (paths or URLs).

    Returns
    -------
    dict
        A ``sales_package.json``-shaped dict.
    """
    business_slug = (business_profile.get("business_slug") or "").strip()
    if not business_slug:
        raise ValueError("business_profile.business_slug is required")

    package: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "business_slug": business_slug,
        "generated_at": _deterministic_generated_at(run_id, business_slug),
        "preview_url": _build_preview_url(preview_url, config),
        "screenshots": _build_screenshots(screenshots),
        "business_summary": _build_business_summary(business_profile),
        "offer": _build_offer(config),
        "evaluation_summary": _build_evaluation_summary(evaluation_report),
        "recipient_channel": _build_recipient_channel(business_profile),
        "compliance_notes": _build_compliance_notes(business_profile, evaluation_report),
        "owner_facing_summary": _build_owner_facing_summary(
            business_profile, evaluation_report
        ),
        "missing_data": _collect_missing_data(
            business_profile, preview_url, screenshots, evaluation_report
        ),
        "forbidden_public_claims": list(_FORBIDDEN_PUBLIC_CLAIMS),
        "internal": {
            "flag": "use_sales_package_contract",
            "schema_origin": "VNEXT-08",
        },
    }
    return package


def write_sales_package(
    package: dict, output_dir: str | Path, business_slug: str
) -> str:
    """Write the sales package to {output_dir}/{business_slug}/sales_package.json.

    Returns the absolute path of the written file.
    """
    output_path = Path(output_dir) / business_slug / "sales_package.json"
    return write_json(str(output_path), package)
