"""
VNEXT-04 — Creative Specification Builder.

Builds the canonical `creative_spec.json` artifact from upstream artifacts:
  - business_profile.json (VNEXT-01) — verified facts
  - market_profile.json (VNEXT-02) — sellability + strategy hints
  - brand_profile.json (VNEXT-03) — brand tone, trust, color

The creative_spec is the single source of truth before website generation.
It merges the three upstream views into a unified generation directive with
explicit content policy, section ordering, and evaluation targets.

The module is pure-Python: no LLM, no I/O (except write_creative_spec).

Determinism: `generated_at` is derived from a SHA-256 of (run_id, business_slug)
mapped to a fixed epoch plus a day offset, so identical inputs produce byte-
identical output across processes and machines (no wall-clock dependence).

Feature flag: `use_creative_spec` (default OFF).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:  # pragma: no cover - import-shim for tests and CLI
    from pipeline.json_io import write_json
except ModuleNotFoundError:  # pragma: no cover
    from packages.pipeline.json_io import write_json

from packages.creative.creative_spec_models import (
    CANONICAL_SECTION_ORDER,
    FEATURE_FLAG,
    FORBIDDEN_PUBLIC_CLAIMS,
    NICHE_SECTIONS,
    SCHEMA_VERSION,
    UPSTREAM_ARTIFACTS,
)

# Provenance / confidence enums.
CONFIDENCE_VERIFIED = "verified"
CONFIDENCE_INFERRED = "inferred"
CONFIDENCE_UNKNOWN = "unknown"

# Source labels.
_SOURCE_BUSINESS_PROFILE = "business_profile.json"
_SOURCE_BRAND_PROFILE = "brand_profile.json"


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------
def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _has_value(value: Any) -> bool:
    """A value is "present" only if it is not None, not empty, and not NaN-like."""
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    if isinstance(value, (list, dict, tuple)) and len(value) == 0:
        return False
    return True


def _envelope(value: Any, *, source: str, confidence: str) -> dict[str, Any]:
    """Return a provenance envelope {value, source, confidence}."""
    return {"value": value, "source": source, "confidence": confidence}


def _deterministic_generated_at(run_id: str, business_slug: str) -> str:
    """Return a deterministic ISO8601 timestamp derived from (run_id, business_slug).

    The reference epoch is 2026-01-01T00:00:00Z. The day offset is the first 8
    hex chars of the SHA-256 of (run_id|business_slug), interpreted as an
    unsigned 32-bit integer, modulo 3650 (10 years). This guarantees:
      - identical inputs → identical output (test determinism)
      - no wall-clock dependence
      - no process-id or import-order dependence
    """
    digest = hashlib.sha256(f"{run_id}|{business_slug}".encode()).hexdigest()
    day_offset = int(digest[:8], 16) % 3650
    epoch = datetime(2026, 1, 1, tzinfo=timezone.utc)
    moment = epoch + timedelta(days=day_offset)
    return moment.isoformat().replace("+00:00", "Z")


def _extract_verified_fact(business_profile: dict[str, Any], key: str) -> Any:
    """Extract a value from business_profile verified_facts."""
    vf = business_profile.get("verified_facts", {})
    if isinstance(vf, dict) and key in vf:
        entry = vf[key]
        if isinstance(entry, dict):
            return entry.get("value")
    return None


def _extract_brand_tone(brand_profile: dict[str, Any]) -> str:
    """Extract primary brand tone from brand_profile."""
    bt = brand_profile.get("brand_tone", {})
    if isinstance(bt, dict):
        primary = bt.get("primary", {})
        if isinstance(primary, dict):
            return str(primary.get("value", "professional"))
    return "professional"


def _extract_trust_posture(brand_profile: dict[str, Any]) -> str:
    """Extract trust posture from brand_profile."""
    tp = brand_profile.get("trust_posture", {})
    if isinstance(tp, dict):
        return str(tp.get("value", "credential_safe"))
    return "credential_safe"


def _extract_emotional_goals(brand_profile: dict[str, Any]) -> list[str]:
    """Extract emotional goals from brand_profile."""
    eg = brand_profile.get("emotional_goals", [])
    if isinstance(eg, list):
        return [str(g) for g in eg if str(g).strip()]
    return []


def _extract_color_direction(brand_profile: dict[str, Any]) -> dict[str, str]:
    """Extract color direction from brand_profile."""
    cd = brand_profile.get("color_direction", {})
    result: dict[str, str] = {}
    if isinstance(cd, dict):
        for key in ("primary_hint", "mood"):
            entry = cd.get(key, {})
            if isinstance(entry, dict) and _has_value(entry.get("value")):
                result[key] = str(entry["value"])
    return result


def _extract_overall_score(market_profile: dict[str, Any]) -> float:
    """Extract overall score from market_profile sellability."""
    sellability = market_profile.get("sellability", {})
    if isinstance(sellability, dict):
        score_entry = sellability.get("score", {})
        if isinstance(score_entry, dict):
            try:
                return float(score_entry.get("value", 0.0))
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def _extract_demand_signal(market_profile: dict[str, Any]) -> str:
    """Extract demand signal label from market_profile."""
    sellability = market_profile.get("sellability", {})
    if isinstance(sellability, dict):
        ds = sellability.get("demand_signal", {})
        if isinstance(ds, dict):
            return str(ds.get("value", "unknown"))
    return "unknown"


def _extract_website_status(market_profile: dict[str, Any]) -> str:
    """Extract website_status from market_profile sellability."""
    sellability = market_profile.get("sellability", {})
    if isinstance(sellability, dict):
        ws = sellability.get("website_status", {})
        if isinstance(ws, dict):
            return str(ws.get("value", "unknown"))
    return "unknown"


def _extract_positioning(market_profile: dict[str, Any]) -> list[str]:
    """Extract positioning hints from market_profile strategy_hints."""
    sh = market_profile.get("strategy_hints", {})
    if isinstance(sh, dict):
        pos = sh.get("positioning", [])
        if isinstance(pos, list):
            return [str(p) for p in pos if str(p).strip()]
    return []


def _build_business_identity(
    business_profile: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Build the business_identity section from business_profile verified_facts."""
    identity: dict[str, dict[str, Any]] = {}
    for key in ("business_name", "category", "phone", "address", "hours"):
        value = _extract_verified_fact(business_profile, key)
        identity[key] = _envelope(
            value if _has_value(value) else "",
            source=_SOURCE_BUSINESS_PROFILE,
            confidence=CONFIDENCE_VERIFIED if _has_value(value) else CONFIDENCE_UNKNOWN,
        )
    return identity



def _extract_differentiation(competitor_profile: dict[str, Any] | None) -> list[str]:
    """Extract strategic differentiation from competitor_profile if available."""
    if not competitor_profile:
        return []
        
    diff = competitor_profile.get("strategic_differentiation", {})
    if isinstance(diff, dict):
        opportunities = diff.get("opportunities", [])
        if isinstance(opportunities, list):
            return [str(o) for o in opportunities if str(o).strip()]
    return []


def _build_brand_strategy(
    brand_profile: dict[str, Any],
    competitor_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the brand_strategy section from brand_profile and competitor_profile."""
    tone = _extract_brand_tone(brand_profile)
    trust_posture = _extract_trust_posture(brand_profile)
    emotional_goals = _extract_emotional_goals(brand_profile)
    color_direction = _extract_color_direction(brand_profile)
    differentiation = _extract_differentiation(competitor_profile)

    return {
        "tone": _envelope(tone, source=_SOURCE_BRAND_PROFILE, confidence=CONFIDENCE_INFERRED),
        "trust_posture": _envelope(trust_posture, source=_SOURCE_BRAND_PROFILE, confidence=CONFIDENCE_INFERRED),
        "emotional_goals": emotional_goals,
        "color_direction": color_direction,
        "differentiation": differentiation,
    }


def _build_sellability(
    market_profile: dict[str, Any],
) -> dict[str, Any]:
    """Build the sellability section from market_profile."""
    overall_score = _extract_overall_score(market_profile)
    demand_signal = _extract_demand_signal(market_profile)
    website_status = _extract_website_status(market_profile)
    positioning = _extract_positioning(market_profile)

    return {
        "overall_score": round(overall_score, 2),
        "demand_signal": demand_signal,
        "website_status": website_status,
        "positioning": positioning,
    }


def _build_content_policy() -> dict[str, Any]:
    """Build the content_policy section with explicit claim rules."""
    return {
        "forbidden_claims": list(FORBIDDEN_PUBLIC_CLAIMS),
        "missing_data_handling": "omit_or_neutral",
        "claim_policy": "verified_facts_only",
    }


def _build_generation_directives(
    config: dict[str, Any],
    market_profile: dict[str, Any],
    business_profile: dict[str, Any],
) -> dict[str, Any]:
    """Build the generation_directives section from config and strategy."""
    template_family = _safe_str(config.get("style_preset", "industrial_reliable"))

    # Sections are ordered by canonical strategy.
    sections = list(CANONICAL_SECTION_ORDER)

    # Append niche-specific sections based on business category.
    category = _extract_verified_fact(business_profile, "category")
    category_lower = str(category).strip().lower() if category else ""
    niche_additions = NICHE_SECTIONS.get(category_lower, ())
    if niche_additions:
        for ns in niche_additions:
            if ns not in sections:
                sections.append(ns)

    # CTA type is always contact_form_or_phone for current pipeline.
    required_cta = "contact_form_or_phone"

    return {
        "template_family": template_family,
        "sections": sections,
        "required_cta": required_cta,
        "mobile_first": True,
    }


def _build_evaluation_targets() -> dict[str, Any]:
    """Build the evaluation_targets section with explicit quality gates."""
    return {
        "min_overall_score": 70,
        "hard_block_on": ["broken_links", "missing_stylesheet", "horizontal_overflow"],
    }


def _build_missing_data(
    business_profile: dict[str, Any],
    market_profile: dict[str, Any],
    brand_profile: dict[str, Any],
) -> list[str]:
    """Build the missing_data list from all upstream profiles."""
    missing: list[str] = []

    # From business_profile
    bp_missing = business_profile.get("missing_data", [])
    if isinstance(bp_missing, list):
        missing.extend(str(m) for m in bp_missing)

    # From market_profile
    mp_missing = market_profile.get("missing_data", [])
    if isinstance(mp_missing, list):
        for m in mp_missing:
            m_str = str(m)
            if m_str not in missing:
                missing.append(m_str)

    # From brand_profile
    brp_missing = brand_profile.get("missing_data", [])
    if isinstance(brp_missing, list):
        for m in brp_missing:
            m_str = str(m)
            if m_str not in missing:
                missing.append(m_str)

    return missing


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def build_creative_spec(
    business_profile: dict[str, Any],
    market_profile: dict[str, Any],
    brand_profile: dict[str, Any],
    config: dict[str, Any],
    *,
    run_id: str,
    competitor_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the canonical creative_spec dict from upstream artifacts.

    Parameters
    ----------
    business_profile:
        Output of ``build_business_profile()`` (VNEXT-01).
    market_profile:
        Output of ``build_market_profile()`` (VNEXT-02).
    brand_profile:
        Output of ``build_brand_profile()`` (VNEXT-03).
    config:
        Run-level config with template_family, niche, area, etc.
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
    business_slug = _safe_str(business_profile.get("business_slug"))
    if not business_slug:
        raise ValueError("business_profile.business_slug is required to build a creative_spec")

    spec: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "business_slug": business_slug,
        "generated_at": _deterministic_generated_at(run_id, business_slug),
        "business_identity": _build_business_identity(business_profile),
        "brand_strategy": _build_brand_strategy(brand_profile, competitor_profile),
        "sellability": _build_sellability(market_profile),
        "content_policy": _build_content_policy(),
        "generation_directives": _build_generation_directives(config, market_profile, business_profile),
        "evaluation_targets": _build_evaluation_targets(),
        "missing_data": _build_missing_data(business_profile, market_profile, brand_profile),
        "internal": {
            "flag": FEATURE_FLAG,
            "schema_origin": "VNEXT-04",
            "upstream_artifacts": list(UPSTREAM_ARTIFACTS),
        },
    }
    return spec


def write_creative_spec(
    spec: dict[str, Any],
    output_dir: str | Path,
    business_slug: str,
) -> str:
    """Write the spec to ``{output_dir}/{business_slug}/creative_spec.json``.

    Returns the absolute path of the written file.
    """
    output_path = Path(output_dir) / business_slug / "creative_spec.json"
    return write_json(str(output_path), spec)
