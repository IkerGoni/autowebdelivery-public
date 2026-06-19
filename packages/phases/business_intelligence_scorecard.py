"""Pure business-intelligence sellability scorecard for lead prioritization."""

from __future__ import annotations

import math
from typing import Any

WEIGHTS = {
    "category_value": 0.25,
    "website_need": 0.25,
    "demand_signal": 0.20,
    "contact_friction": 0.15,
    "enrichment_signal": 0.15,
}

HIGH_VALUE_CATEGORY_KEYWORDS = (
    "auto detail",
    "detailing",
    "ceramic coating",
    "paint protection",
    "ppf",
    "mobile detail",
    "dentist",
    "dental",
    "med spa",
    "law",
    "attorney",
    "roof",
    "hvac",
    "plumb",
)

LOW_VALUE_CATEGORY_KEYWORDS = (
    "restaurant",
    "coffee",
    "cafe",
    "bar",
    "food truck",
    "fast food",
)

SOCIAL_DOMAINS = ("facebook.", "instagram.", "linktr.ee", "tiktok.", "yelp.")


def safe_float(value: Any, default: float = 0.0) -> float:
    """Parse float-like input, returning default for malformed/missing values."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed):
        return default
    return max(parsed, 0.0)


def safe_int(value: Any, default: int = 0) -> int:
    """Parse int-like input, returning default for malformed/missing values."""
    try:
        parsed_float = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed_float):
        return default
    return max(int(parsed_float), 0)


def score_category_value(lead: dict[str, Any]) -> tuple[float, list[str]]:
    """Score likely project value from business category without public claims."""
    category = str(lead.get("category") or "").lower()
    name = str(lead.get("business_name") or "").lower()
    text = f"{category} {name}"
    if any(keyword in text for keyword in HIGH_VALUE_CATEGORY_KEYWORDS):
        return 90.0, ["high_value_service_category"]
    if any(keyword in text for keyword in LOW_VALUE_CATEGORY_KEYWORDS):
        return 45.0, ["lower_margin_or_saturated_category"]
    if not category.strip():
        return 50.0, ["unknown_category_neutral"]
    return 55.0, ["category_value_neutral"]


def score_website_need(lead: dict[str, Any]) -> tuple[float, list[str], list[str]]:
    """Score need for website upgrade from safe existing fields."""
    website_status = str(lead.get("website_status") or "").lower()
    website_raw = str(lead.get("website_raw") or "").lower()
    hints: list[str] = []
    risks: list[str] = []
    if website_status == "no_website" or not website_raw.strip():
        hints.append("position_as_missing_website_upgrade")
        return 95.0, hints, risks
    if website_status == "social_only" or any(domain in website_raw for domain in SOCIAL_DOMAINS):
        hints.append("position_as_social_to_owned_site_upgrade")
        return 70.0, hints, risks
    risks.append("existing_website_may_reduce_urgency")
    return 35.0, hints, risks


def score_demand_signal(lead: dict[str, Any]) -> tuple[float, list[str]]:
    """Score market demand from reviews/rating already present in lead."""
    rating = safe_float(lead.get("rating"), 0.0)
    reviews = safe_int(lead.get("review_count"), 0)
    score = 50.0
    hints: list[str] = []
    if rating >= 4.7:
        score += 20
        hints.append("strong_rating_signal")
    elif rating >= 4.3:
        score += 10
    if reviews >= 150:
        score += 25
        hints.append("strong_review_volume_signal")
    elif reviews >= 40:
        score += 15
    return min(score, 100.0), hints


def score_contact_friction(lead: dict[str, Any]) -> tuple[float, list[str]]:
    """Score ease of outreach; higher means lower friction."""
    score = 30.0
    risks: list[str] = []
    if str(lead.get("phone") or "").strip():
        score += 35
    else:
        risks.append("missing_phone")
    if str(lead.get("maps_url") or "").strip():
        score += 20
    else:
        risks.append("missing_maps_url")
    if str(lead.get("address") or "").strip():
        score += 15
    return min(score, 100.0), risks


def score_enrichment_signal(enrichment: dict[str, Any] | None) -> tuple[float, list[str], list[str]]:
    """Score optional enrichment without requiring it."""
    if not enrichment:
        return 35.0, [], ["missing_enrichment"]
    hints: list[str] = []
    risks: list[str] = []
    score = 50.0
    if enrichment.get("services") or enrichment.get("service_keywords"):
        score += 20
        hints.append("use_enriched_services_in_prompt")
    if enrichment.get("photos") or enrichment.get("photo_count"):
        score += 10
        hints.append("use_visual_business_context")
    if enrichment.get("business_summary") or enrichment.get("description"):
        score += 10
        hints.append("use_enriched_business_summary")
    if enrichment.get("verified_contact") or enrichment.get("hours"):
        score += 10
    if score == 50.0:
        risks.append("thin_enrichment")
    return min(score, 100.0), hints, risks


def score_business_intelligence(
    lead: dict[str, Any],
    config: dict[str, Any] | None = None,
    enrichment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return stable BI score dict for internal lead prioritization and prompt hints."""
    del config  # reserved for later weight/config overrides
    category_score, category_hints = score_category_value(lead)
    website_score, website_hints, website_risks = score_website_need(lead)
    demand_score, demand_hints = score_demand_signal(lead)
    friction_score, friction_risks = score_contact_friction(lead)
    enrichment_score, enrichment_hints, enrichment_risks = score_enrichment_signal(enrichment)

    component_scores = {
        "category_value": round(category_score, 2),
        "website_need": round(website_score, 2),
        "demand_signal": round(demand_score, 2),
        "contact_friction": round(friction_score, 2),
        "enrichment_signal": round(enrichment_score, 2),
    }
    overall = sum(component_scores[name] * weight for name, weight in WEIGHTS.items())
    value_drivers = category_hints + website_hints + demand_hints + enrichment_hints
    risk_flags = website_risks + friction_risks + enrichment_risks
    confidence = "medium" if enrichment else "low"
    if enrichment and not risk_flags:
        confidence = "high"

    return {
        "overall_score": round(overall, 2),
        "component_scores": component_scores,
        "value_drivers": value_drivers,
        "risk_flags": risk_flags,
        "prompt_hints": value_drivers.copy(),
        "strategy_hints": {
            "positioning": [
                hint for hint in value_drivers
                if str(hint).startswith("position_as_")
            ],
            "value_drivers": [
                hint for hint in value_drivers
                if not str(hint).startswith("position_as_")
            ],
            "risk_flags": list(risk_flags),
        },
        "confidence": confidence,
    }
