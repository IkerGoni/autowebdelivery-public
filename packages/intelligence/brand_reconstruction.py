"""
VNEXT-03 — Brand Reconstruction Contract.

Build a canonical `brand_profile.json` artifact for each scored lead. The
brand profile sits alongside `business_profile.json` (VNEXT-01) and
`market_profile.json` (VNEXT-02), and serves a complementary purpose:

  - `business_profile.json` is the **verified-facts** view (per the lead).
  - `market_profile.json` is the **sellability / strategy** view (per the
    scorecard).
  - `brand_profile.json` is the **brand tone / trust / emotional** view —
    a lightweight, *inferred* strategy artifact that maps category keywords
    to deterministic brand tone, trust posture, emotional goals, and colour
    direction.  No LLM is involved; all mapping is static and deterministic.

The module is pure-Python: it takes a business_profile, a market_profile,
the run-level config, and a run_id, and produces a deterministic dict with
four public sections (`brand_tone`, `trust_posture`, `emotional_goals`,
`color_direction`), plus `missing_data`, `forbidden_public_claims`, and an
`internal` block labelled as never-to-be-passed-to-public-copy.

Determinism: `generated_at` is derived from a SHA-256 of (run_id, business_slug)
mapped to a fixed epoch plus a day offset, so identical inputs produce byte-
identical output across processes and machines (no wall-clock dependence).

Feature flag: `use_brand_reconstruction_contract` (default OFF). Downstream
consumers must check this flag before relying on brand_profile.json.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from packages.shared.provenance import (
    _deterministic_generated_at,
    _has_value,
    _safe_str,
)
from packages.shared.forbidden_claims import FORBIDDEN_PUBLIC_CLAIMS as _FORBIDDEN_PUBLIC_CLAIMS

try:  # pragma: no cover - import-shim for tests and CLI
    from pipeline.json_io import write_json
except ModuleNotFoundError:  # pragma: no cover
    from packages.pipeline.json_io import write_json

SCHEMA_VERSION = "1.1.0"  # VNEXT-16 supports enrichment-driven brand signals

# Provenance / confidence enums.
CONFIDENCE_INFERRED = "inferred"
CONFIDENCE_UNKNOWN = "unknown"

# Explicit blocklist of claim categories that MUST NEVER appear in public copy.
# Mirrors business_profile.py and market_profile.py.
# (Imported from packages.shared.forbidden_claims as _FORBIDDEN_PUBLIC_CLAIMS)

# Source labels for the inferred values.
_SOURCE_CATEGORY = "inferred_from_category"
_SOURCE_MARKET = "inferred_from_market_profile"
_SOURCE_DEFAULTS = "category_defaults"
_SOURCE_ENRICHMENT = "inferred_from_enrichment"


# ---------------------------------------------------------------------------
# Enrichment signal extractors
# ---------------------------------------------------------------------------
def _extract_gmaps_signals(gmaps: dict[str, Any] | None) -> dict[str, Any]:
    """Extract brand-relevant signals from Google Maps enrichment data.

    Returns a dict with:
      - has_reviews: bool
      - avg_rating: float
      - review_count: int
      - has_differentiators: bool
      - has_owner_signals: bool
      - sentiment_hint: str ("positive", "neutral", "none")
    """
    if not gmaps:
        return {"has_reviews": False, "avg_rating": 0.0, "review_count": 0,
                "has_differentiators": False, "has_owner_signals": False,
                "sentiment_hint": "none"}

    rating = float(gmaps.get("rating", 0))
    rcount = int(gmaps.get("review_count", 0))
    snippets = gmaps.get("review_snippets", [])
    differentiators = gmaps.get("differentiators", [])
    owner_signals = gmaps.get("owner_signals", [])

    sentiment_hint = "none"
    if rcount > 0:
        sentiment_hint = "positive" if rating >= 4.0 else "neutral"

    return {
        "has_reviews": rcount > 0,
        "avg_rating": rating,
        "review_count": rcount,
        "review_snippet_count": len(snippets) if isinstance(snippets, list) else 0,
        "has_differentiators": bool(differentiators),
        "has_owner_signals": bool(owner_signals),
        "sentiment_hint": sentiment_hint,
    }


def _extract_social_signals(social: dict[str, Any] | None) -> dict[str, Any]:
    """Extract brand-relevant signals from Social scraper enrichment data.

    Returns a dict with:
      - has_social_presence: bool
      - follower_count: int
      - post_count: int
      - is_verified: bool
      - social_category: str
      - brand_maturity: str ("emerging", "established", "unknown")
    """
    if not social:
        return {"has_social_presence": False, "follower_count": 0, "post_count": 0,
                "is_verified": False, "social_category": "", "brand_maturity": "unknown"}

    followers = int(social.get("follower_count", 0))
    posts = int(social.get("post_count", 0))
    verified = bool(social.get("is_verified", False))

    brand_maturity = "unknown"
    if followers > 0 or posts > 0:
        brand_maturity = "established" if followers > 100 or posts > 50 else "emerging"

    return {
        "has_social_presence": True,
        "follower_count": followers,
        "post_count": posts,
        "is_verified": verified,
        "social_category": str(social.get("business_category", "")),
        "platform": str(social.get("platform", "")),
        "brand_maturity": brand_maturity,
    }


def _extract_overpass_signals(overpass: dict[str, Any] | None) -> dict[str, Any]:
    """Extract brand-relevant signals from Overpass enrichment data."""
    if not overpass:
        return {"has_osm_data": False, "osm_category": ""}
    osm_tags = overpass.get("osm_tags", {})
    return {
        "has_osm_data": True,
        "osm_category": str(osm_tags.get("category", "")) if isinstance(osm_tags, dict) else "",
    }


# ---------------------------------------------------------------------------
# Static category → brand mapping (deterministic, no LLM)
# ---------------------------------------------------------------------------
# Each entry: (keywords_tuple, tone_dict)
# Keywords are matched case-insensitively against the category string.

_CategoryMapping = dict[str, Any]

_AUTO_DETAILING_MAP: _CategoryMapping = {
    "primary": "professional",
    "secondary": "warm",
    "voice": "authoritative_approachable",
    "trust_posture": "credential_safe",
    "emotional_goals": ["confidence", "reliability"],
    "primary_hint": "blue",
    "mood": "clean_professional",
}

_DENTAL_MEDICAL_MAP: _CategoryMapping = {
    "primary": "clinical",
    "secondary": "warm_professional",
    "voice": "reassuring_authoritative",
    "trust_posture": "credential_safe",
    "emotional_goals": ["trust", "safety"],
    "primary_hint": "white",
    "mood": "calming_clean",
}

_LEGAL_MAP: _CategoryMapping = {
    "primary": "authoritative",
    "secondary": "formal",
    "voice": "authoritative_formal",
    "trust_posture": "credential_safe",
    "emotional_goals": ["trust", "confidence"],
    "primary_hint": "navy",
    "mood": "professional_gravity",
}

_HOME_SERVICES_MAP: _CategoryMapping = {
    "primary": "reliable",
    "secondary": "friendly_professional",
    "voice": "friendly_reliable",
    "trust_posture": "credential_safe",
    "emotional_goals": ["safety", "competence"],
    "primary_hint": "orange",
    "mood": "warm_reliable",
}

_RESTAURANT_CAFE_MAP: _CategoryMapping = {
    "primary": "warm",
    "secondary": "casual_inviting",
    "voice": "casual_inviting",
    "trust_posture": "experience_safe",
    "emotional_goals": ["comfort", "celebration"],
    "primary_hint": "warm_red",
    "mood": "cozy_vibrant",
}

_DEFAULT_MAP: _CategoryMapping = {
    "primary": "professional",
    "secondary": "neutral_approachable",
    "voice": "neutral_approachable",
    "trust_posture": "credential_safe",
    "emotional_goals": ["confidence", "clarity"],
    "primary_hint": "gray",
    "mood": "clean_neutral",
}

# Ordered list of (keyword_set, mapping) — first match wins.
_CATEGORY_RULES: list[tuple[tuple[str, ...], _CategoryMapping]] = [
    (("auto detail", "detailing", "ceramic coating", "paint protection", "ppf", "mobile detail"), _AUTO_DETAILING_MAP),
    (("dentist", "dental", "med spa", "medical", "clinic", "orthodontist"), _DENTAL_MEDICAL_MAP),
    (("law", "attorney", "legal", "lawyer", "solicitor"), _LEGAL_MAP),
    (("hvac", "plumb", "roof", "electrician", "landscap", "pest control", "home service", "handyman"), _HOME_SERVICES_MAP),
    (("restaurant", "cafe", "coffee", "bakery", "bar ", "food truck", "fast food", "pizzeria", "bistro"), _RESTAURANT_CAFE_MAP),
]

# Trust posture overrides by category keyword.
# When a category matches one of these keyword groups, the returned trust posture
# replaces the generic one inferred from the market_profile heuristic.
_TRUST_POSTURE_RULES: list[tuple[tuple[str, ...], str]] = [
    (("healthcare", "medical", "dental", "clinic", "med spa", "orthodontist"), "conservative"),
    (("law", "legal", "attorney", "lawyer", "solicitor"), "authoritative"),
    (("auto detail", "detailing", "ceramic coating", "paint protection", "ppf", "mobile detail"), "credential_safe"),
    (("hvac", "plumb", "roof", "electrician", "landscap", "pest control", "home service", "handyman"), "credential_safe"),
    (("restaurant", "cafe", "coffee", "bakery", "bar ", "food truck", "fast food", "pizzeria", "bistro"), "experience_safe"),
]


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------
def _forbidden_public_claims() -> list[str]:
    """Return the explicit blocklist of claim categories that must never appear
    in public marketing copy generated from this profile."""
    return list(_FORBIDDEN_PUBLIC_CLAIMS)


def _match_category(category: str) -> _CategoryMapping:
    """Return the first matching category mapping, or the default."""
    cat_lower = (category or "").lower()
    for keywords, mapping in _CATEGORY_RULES:
        if any(kw in cat_lower for kw in keywords):
            return mapping
    return _DEFAULT_MAP


def _infer_brand_tone(category: str) -> dict[str, dict[str, str]]:
    """Infer brand tone from category using deterministic static mapping.

    Returns dict with keys: primary, secondary, voice.
    Each value is {value, source, confidence}.
    """
    mapping = _match_category(category)
    return {
        "primary": {
            "value": mapping["primary"],
            "source": _SOURCE_CATEGORY,
            "confidence": CONFIDENCE_INFERRED,
        },
        "secondary": {
            "value": mapping["secondary"],
            "source": _SOURCE_CATEGORY,
            "confidence": CONFIDENCE_INFERRED,
        },
        "voice": {
            "value": mapping["voice"],
            "source": _SOURCE_CATEGORY,
            "confidence": CONFIDENCE_INFERRED,
        },
    }


def _infer_trust_posture(
    market_profile: dict[str, Any] | None = None,
    category: str | None = None,
) -> dict[str, str]:
    """Infer trust posture from market_profile or explicit category.

    When *category* is provided it takes precedence: keyword matching against
    ``_TRUST_POSTURE_RULES`` returns niche-specific postures (e.g. healthcare→
    conservative, legal→authoritative).  When *category* is None the function
    falls back to extracting the category from *market_profile* and using the
    static ``_match_category`` mapping, which is more generic.
    """
    # Category-aware path — explicit category overrides everything
    if category is not None:
        cat_lower = category.lower()
        for keywords, posture in _TRUST_POSTURE_RULES:
            if any(kw in cat_lower for kw in keywords):
                return {
                    "value": posture,
                    "source": "inferred_from_category",
                    "confidence": CONFIDENCE_INFERRED,
                }

    # Fallback: extract category from market_profile
    extracted_category = ""
    if market_profile and isinstance(market_profile, dict):
        sellability = market_profile.get("sellability", {})
        if isinstance(sellability, dict):
            cat_entry = sellability.get("category", {})
            if isinstance(cat_entry, dict):
                extracted_category = str(cat_entry.get("value", ""))

    # If we have a category from market_profile, try posture rules too
    if extracted_category:
        cat_lower = extracted_category.lower()
        for keywords, posture in _TRUST_POSTURE_RULES:
            if any(kw in cat_lower for kw in keywords):
                return {
                    "value": posture,
                    "source": "inferred_from_category",
                    "confidence": CONFIDENCE_INFERRED,
                }

    mapping = _match_category(extracted_category)
    return {
        "value": mapping["trust_posture"],
        "source": _SOURCE_MARKET,
        "confidence": CONFIDENCE_INFERRED,
    }


def _infer_emotional_goals(category: str) -> list[str]:
    """Infer emotional goals from category.

    Returns a list of emotional goal strings.
    """
    mapping = _match_category(category)
    return list(mapping["emotional_goals"])


def _infer_color_direction(category: str) -> dict[str, dict[str, str]]:
    """Infer colour direction from category using deterministic static mapping.

    Returns dict with keys: primary_hint, mood.
    Each value is {value, source, confidence}.
    """
    mapping = _match_category(category)
    return {
        "primary_hint": {
            "value": mapping["primary_hint"],
            "source": _SOURCE_DEFAULTS,
            "confidence": CONFIDENCE_INFERRED,
        },
        "mood": {
            "value": mapping["mood"],
            "source": _SOURCE_DEFAULTS,
            "confidence": CONFIDENCE_INFERRED,
        },
    }


def _missing_data(
    business_profile: dict[str, Any],
    market_profile: dict[str, Any] | None = None,
) -> list[str]:
    """Return a list of fields that the brand profile considers missing.

    The brand profile depends on category (from business_profile verified_facts
    or inferred_strategy) and strategy_hints (from market_profile). If these
    are absent, the brand reconstruction operates with lower confidence.
    """
    missing: list[str] = []

    # Category is the primary driver for brand inference
    category = ""
    if isinstance(business_profile, dict):
        # Check verified_facts first, then inferred_strategy
        vf = business_profile.get("verified_facts", {})
        if isinstance(vf, dict) and _has_value(vf.get("category")):
            category = str(vf["category"].get("value", "")) if isinstance(vf["category"], dict) else ""
        if not category:
            ist = business_profile.get("inferred_strategy", {})
            if isinstance(ist, dict):
                niche_entry = ist.get("niche", {})
                if isinstance(niche_entry, dict):
                    category = str(niche_entry.get("value", ""))
    if not category.strip():
        missing.append("category")

    # strategy_hints from market_profile
    if market_profile and isinstance(market_profile, dict):
        sh = market_profile.get("strategy_hints")
        if not sh or not isinstance(sh, dict):
            missing.append("strategy_hints")
    else:
        missing.append("market_profile")

    return missing


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def build_brand_profile(
    business_profile: dict[str, Any],
    market_profile: dict[str, Any],
    config: dict[str, Any],
    *,
    run_id: str,
) -> dict[str, Any]:
    """Build the canonical brand_profile dict for a single lead.

    Parameters
    ----------
    business_profile:
        Output of ``build_business_profile()`` (VNEXT-01). The category
        is extracted from ``verified_facts.category.value`` or
        ``inferred_strategy.niche.value``. If enrichment data is present
        (via the ``enrichment`` section), it is used to refine brand signals.
    market_profile:
        Output of ``build_market_profile()`` (VNEXT-02). Strategy hints
        inform the trust posture.
    config:
        Run-level config (kept for symmetry with VNEXT-01/02; the feature
        flag ``use_brand_reconstruction_contract`` would live here).
    run_id:
        Run identifier; used both as a top-level field and to derive a
        deterministic ``generated_at``.

    Returns
    -------
    A JSON-serializable dict with the structure documented in the contract.

    Raises
    ------
    ValueError
        If ``business_slug`` is missing from the business_profile.
    """
    del config  # reserved for future per-config overrides

    business_slug = _safe_str(business_profile.get("business_slug"))
    if not business_slug:
        raise ValueError("business_profile.business_slug is required to build a brand_profile")

    # Extract category from business_profile
    category = ""
    vf = business_profile.get("verified_facts", {})
    if isinstance(vf, dict) and _has_value(vf.get("category")):
        cat_entry = vf["category"]
        category = str(cat_entry.get("value", "")) if isinstance(cat_entry, dict) else str(cat_entry)
    if not category:
        ist = business_profile.get("inferred_strategy", {})
        if isinstance(ist, dict):
            niche_entry = ist.get("niche", {})
            if isinstance(niche_entry, dict):
                category = str(niche_entry.get("value", ""))

    # Read enrichment data from business_profile (VNEXT-16)
    enrichment = business_profile.get("enrichment", {}) or {}
    gmaps_enrichment = enrichment.get("google_maps") if isinstance(enrichment, dict) else None
    social_enrichment = enrichment.get("social") if isinstance(enrichment, dict) else None
    overpass_enrichment = enrichment.get("overpass") if isinstance(enrichment, dict) else None

    gmaps_signals = _extract_gmaps_signals(gmaps_enrichment)
    social_signals = _extract_social_signals(social_enrichment)
    overpass_signals = _extract_overpass_signals(overpass_enrichment)

    brand_tone = _infer_brand_tone(category)
    trust_posture = _infer_trust_posture(market_profile, category=category)
    emotional_goals = _infer_emotional_goals(category)
    color_direction = _infer_color_direction(category)
    missing = _missing_data(business_profile, market_profile)

    # Build enrichment-derived signals section
    enrichment_signals: dict[str, Any] = {}
    if gmaps_signals.get("has_reviews") or social_signals.get("has_social_presence") or overpass_signals.get("has_osm_data"):
        enrichment_signals = {
            "gmaps_review_signals": gmaps_signals,
            "social_presence_signals": social_signals,
            "overpass_osm_signals": overpass_signals,
        }

    profile: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "business_slug": business_slug,
        "generated_at": _deterministic_generated_at(run_id, business_slug),
        "brand_tone": brand_tone,
        "trust_posture": trust_posture,
        "emotional_goals": emotional_goals,
        "color_direction": color_direction,
        "missing_data": missing,
        "forbidden_public_claims": _forbidden_public_claims(),
        "internal": {
            "flag": "use_brand_reconstruction_contract",
            "schema_origin": "VNEXT-03",
            "enrichment_consumed": bool(enrichment),
        },
    }

    # Include enrichment-derived signals when available
    if enrichment_signals:
        profile["enrichment_signals"] = enrichment_signals

    return profile


def write_brand_profile(
    profile: dict[str, Any],
    output_dir: str | Path,
    business_slug: str,
) -> str:
    """Write the profile to ``{output_dir}/{business_slug}/brand_profile.json``.

    Returns the absolute path of the written file.
    """
    output_path = Path(output_dir) / business_slug / "brand_profile.json"
    return write_json(str(output_path), profile)
