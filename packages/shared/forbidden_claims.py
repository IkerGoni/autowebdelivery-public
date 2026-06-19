"""
Shared forbidden claims registry.

Consolidates `FORBIDDEN_PUBLIC_CLAIMS` tuple and `forbidden_public_claims()`
validator from 3+ separate copies across the codebase.

The tuple is frozen (immutable) — the canonical single source of truth.
"""

from __future__ import annotations

#: Explicit blocklist of claim categories that MUST NEVER appear in public copy.
#: These are categories where invented data would create legal or reputational
#: risk (e.g. fake licenses, fake insurance, fake years_in_business).
FORBIDDEN_PUBLIC_CLAIMS: tuple[str, ...] = (
    "years_in_business",
    "awards",
    "licenses",
    "insurance",
    "certifications",
    "staff_credentials",
    "testimonials",
    "guarantees",
    "superlatives",
)


def forbidden_public_claims() -> list[str]:
    """Return the explicit blocklist of claim categories that must never appear
    in public marketing copy.

    Returns a fresh list each call (callers may mutate without affecting the
    frozen canonical tuple).
    """
    return list(FORBIDDEN_PUBLIC_CLAIMS)
