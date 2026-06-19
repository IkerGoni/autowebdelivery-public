"""Pricing extractor for business enrichment - extracts pricing hints from public sources."""

from __future__ import annotations

import re
from typing import Any


def extract_pricing_from_html(html_text: str, source_url: str | None = None) -> list[dict[str, Any]]:
    """Extract 'from' pricing from product pages, mark internal_only."""
    # Match patterns like: $199, from $160, starting at $499
    prices = re.findall(
        r"(?:from\s*|starting\s*at\s*?|starts\s*at\s*?)?\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
        html_text,
        re.IGNORECASE
    )

    extracted: list[dict[str, Any]] = []
    seen_values: set[str] = set()

    for price in prices[:10]:  # Limit to top 10 unique prices
        clean_price = price.replace(",", "")
        if clean_price in seen_values:
            continue
        seen_values.add(clean_price)

        extracted.append(
            {
                "price": clean_price,
                "raw_text": f"from ${clean_price}",
                "source_url": source_url,
                "confidence": 0.85,
            }
        )

    return extracted


def format_pricing_hint(pricing_list: list[dict[str, Any]]) -> str:
    """Create safe pricing hint for copy (NOT exact prices)."""
    if not pricing_list:
        return "Multiple service packages available"

    prices = [p["price"] for p in pricing_list]
    min_price = min(prices)

    return f"Services starting from ${min_price}"


def pricing_to_safe_field(pricing_list: list[dict[str, Any]], source_url: str | None = None) -> dict[str, Any]:
    """Convert pricing to public-safe hint field format."""
    if not pricing_list:
        return {}

    hint = format_pricing_hint(pricing_list)
    return {
        "field_name": "pricing_hint",
        "field_value": hint,
        "safe_for_public_copy": True,
        "copy_slot_eligible": True,
        "source_url": source_url,
    }


def pricing_to_internal_field(pricing_list: list[dict[str, Any]], source_url: str | None = None) -> dict[str, Any]:
    """Convert exact pricing to internal-only field format."""
    if not pricing_list:
        return {}

    return {
        "field_name": "verified_pricing",
        "field_value": pricing_list,
        "safe_for_public_copy": False,
        "reason_internal_only": "Exact pricing must not be quoted verbatim on preview sites",
        "source_url": source_url,
    }


def create_internal_pricing_fields(
    prices: list[dict[str, Any]],
    business_slug: str,
    now: str,
) -> list[dict[str, Any]]:
    """Create internal-only pricing fields with provenance.

    Args:
        prices: List of extracted price dicts
        business_slug: Business slug for fact_id
        now: ISO timestamp

    Returns:
        List of field dicts ready for internal_only_fields
    """
    if not prices:
        return []

    return [
        {
            "field_name": "verified_pricing",
            "field_value": prices,
            "reason_internal_only": "Exact pricing for internal reference before public-safe hint",
            "source_fact_id": f"{business_slug}:pricing",
            "provenance": {
                "source_type": "extracted",
                "source_url": prices[0].get("source_url"),
                "retrieval_timestamp": now,
                "field_provenance": "Phase 04.5 pricing extraction",
            },
        }
    ]