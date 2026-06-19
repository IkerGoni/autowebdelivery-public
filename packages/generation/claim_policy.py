"""Claim policy module - context-aware validation for Stitch prompts."""

from __future__ import annotations

from typing import Any


DEFAULT_VERIFIED_CLAIMS = (
    "certified",
    "insured",
    "licensed",
    "accredited",
    "satisfaction guarantee",
)

FORBIDDEN_ALWAYS = (
    "best",
    "#1",
    "top-rated",
    "top rated",
    "premier",
    "award-winning",
    "award winning",
    "trusted by thousands",
    "world-class",
    "unparalleled",
    "guaranteed",
)

CLAIM_ALLOWANCE_MAP = {
    "insured": "insured",
    "licensed": "licensed",
    "certified": "certified",
    "accredited": "accredited",
    "satisfaction guarantee": "satisfaction guarantee",
}


def validate_claim_allowed(text: str, source_verified: bool = False, verified_fields: set[str] | None = None) -> bool:
    """Check if claim is verifiable and source is validated.

    Rules:
    - Abstract superlative claims are always forbidden
    - Verified credentials (insured, licensed, certified, accredited) are allowed
      ONLY if present in verified_fields
    - Re-stated facts are allowed (no invention)
    """
    if not text:
        return True

    lower = text.lower()
    verified_fields = verified_fields or set()

    # Check always-forbidden claims first
    for forbidden in FORBIDDEN_ALWAYS:
        if forbidden in lower:
            return False

    # Check verified claims - only allow if in verified fields
    for claim, field in CLAIM_ALLOWANCE_MAP.items():
        if claim in lower:
            if field not in verified_fields and source_verified is False:
                return False

    return True


def allowed_claims_for_business(facts: dict[str, Any]) -> list[str]:
    """Build list of allowed claims based on verified facts."""
    allowed = []
    verified_fields = set(facts.keys())

    # Rating + reviews - only if we have verified values
    if facts.get("rating") and facts.get("review_count"):
        allowed.append(f"Exact rating/review count only: {facts['rating']} from {facts['review_count']} reviews")

    if facts.get("phone"):
        allowed.append(f"Exact verified phone only: {facts['phone']}")

    if facts.get("address"):
        allowed.append(f"Exact verified address only: {facts['address']}")

    # Verified credentials
    for field in ["insured", "licensed", "certified", "accredited"]:
        if field in verified_fields:
            allowed.append(f"Claim '{field}' is verified in source facts")

    return allowed


def forbidden_claims_for_business(public_safe_fields: dict[str, Any] | None = None) -> list[str]:
    """Build list of actually-forbidden claims based on verified fields.

    This replaces the static DEFAULT_FORBIDDEN_CLAIMS with context-aware logic.
    """
    forbidden = list(FORBIDDEN_ALWAYS)

    if not public_safe_fields:
        return forbidden

    verified_field_names = {f.get("field_name") for f in public_safe_fields.get("fields", [])}

    # Only block cred claims if NOT verified
    if "insured" not in verified_field_names:
        forbidden.append("insured")

    if "licensed" not in verified_field_names:
        forbidden.append("licensed")

    if "certified" not in verified_field_names:
        forbidden.append("certified")

    if "accredited" not in verified_field_names:
        forbidden.append("accredited")

    # "reviews" and "ratings" - these are allowed when we have verified values
    # We add them as "allowed claims" instead of forbidden

    return sorted(set(forbidden), key=str.lower)