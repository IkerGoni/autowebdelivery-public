"""
VNEXT-02 — Market Profile Contract.

Build a canonical `market_profile.json` artifact for each scored lead. The
market profile sits alongside `business_profile.json` (VNEXT-01) and serves a
complementary purpose:

  - `business_profile.json` is the **verified-facts** view (per the lead).
  - `market_profile.json` is the **sellability / strategy** view (per the
    scorecard's structured output) — a normalised summary of the scorecard
    signals that downstream copy and outreach generators consume.

The module is pure-Python: it takes a scored lead, the run-level config, and a
run_id, and produces a deterministic dict with five public sections
(`sellability`, `strategy_hints`, `missing_data`, `forbidden_public_claims`),
plus an `internal` block labelled as never-to-be-passed-to-public-copy.

Determinism: `generated_at` is derived from a SHA-256 of (run_id, business_slug)
mapped to a fixed epoch plus a day offset, so identical inputs produce byte-
identical output across processes and machines (no wall-clock dependence).
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

SCHEMA_VERSION = "1.1.0"

# Provenance / confidence enums. Re-exported for downstream tests.
CONFIDENCE_VERIFIED = "verified"
CONFIDENCE_INFERRED = "inferred"
CONFIDENCE_UNKNOWN = "unknown"

# Demand signal classification thresholds, in score units (0-100). These are
# the only thresholds where a derived label is allowed in public copy; they
# match the scorecard's component scale.
_DEMAND_SIGNAL_STRONG_THRESHOLD = 70.0
_DEMAND_SIGNAL_MODERATE_THRESHOLD = 50.0

# Lead-derived verified fields. The market profile treats the *scored lead* as
# the source of truth for these — they are present in the
# `selected_for_preview.json` artifact that downstream phases consume.
_LEAD_VERIFIED_FIELDS: tuple[str, ...] = (
    "category",
    "website_status",
)

# Fields that the market profile considers when reporting missing_data. This
# is a strict subset of the lead-derived fields — the market profile is a
# *strategy* artifact, so we only surface gaps that matter for sellability.
_MARKET_PROFILE_MISSING_FIELDS: tuple[str, ...] = (
    "category",
    "website_status",
    "phone",
    "address",
    "rating",
    "review_count",
)

# Explicit blocklist of claim categories that MUST NEVER appear in public
# copy derived from a market profile. Mirrors business_profile.py.
# (Imported from packages.shared.forbidden_claims as _FORBIDDEN_PUBLIC_CLAIMS)

# Prefix used by the scorecard to flag a value_driver as a positioning hint
# (e.g. "position_as_missing_website_upgrade").
_POSITIONING_HINT_PREFIX = "position_as_"


# -----------------------------------------------------------------------------
# Public helpers
# -----------------------------------------------------------------------------
def _forbidden_public_claims() -> list[str]:
    """Return the explicit blocklist of claim categories that must never appear
    in public marketing copy generated from this profile."""
    return list(_FORBIDDEN_PUBLIC_CLAIMS)


def _classify_demand_signal(component_score: float) -> str:
    """Map a numeric demand_signal component score to a public-safe label."""
    if component_score >= _DEMAND_SIGNAL_STRONG_THRESHOLD:
        return "strong"
    if component_score >= _DEMAND_SIGNAL_MODERATE_THRESHOLD:
        return "moderate"
    return "weak"


def _split_strategy_hints(value_drivers: list[str], risk_flags: list[str]) -> dict[str, list[str]]:
    """Split scorecard value_drivers into positioning vs. plain value_drivers,
    and pass through risk_flags unchanged.

    Positioning hints are identified by the `position_as_` prefix in their name.
    Any hint without that prefix is a generic value driver. The two lists are
    independent — a value driver that starts with `position_as_` is *only*
    surfaced in `positioning`, never duplicated in `value_drivers`.
    """
    positioning: list[str] = []
    drivers: list[str] = []
    for hint in value_drivers:
        name = str(hint or "").strip()
        if not name:
            continue
        if name.startswith(_POSITIONING_HINT_PREFIX):
            positioning.append(name)
        else:
            drivers.append(name)
    return {
        "positioning": positioning,
        "value_drivers": drivers,
        "risk_flags": [str(r).strip() for r in risk_flags if str(r or "").strip()],
    }


def _missing_data(lead: dict[str, Any]) -> list[str]:
    """Return the list of market-profile-relevant fields that are missing from
    the lead. Explicit and deterministic."""
    return [field for field in _MARKET_PROFILE_MISSING_FIELDS if not _has_value(lead.get(field))]


def _safe_component_score(bi_score: dict[str, Any]) -> float:
    """Extract the demand_signal component score from a scorecard payload,
    defaulting to 0.0 if missing or malformed."""
    component_scores = bi_score.get("component_scores") or {}
    raw = component_scores.get("demand_signal", 0.0)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _safe_overall_score(bi_score: dict[str, Any]) -> float:
    """Extract the overall score from a scorecard payload, defaulting to 0.0."""
    raw = bi_score.get("overall_score", 0.0)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _sellability_envelope(
    lead: dict[str, Any],
    bi_score: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Construct the public-safe `sellability` block.

    Each entry follows the same `{value, source, confidence}` shape used by `business_profile.py`, so downstream consumers can rely on a single envelope contract across the two artifacts.
    """
    envelope: dict[str, dict[str, Any]] = {
        "score": {
            "value": round(_safe_overall_score(bi_score), 2),
            "source": "scorecard",
            "confidence": CONFIDENCE_VERIFIED,
        },
    }

    # category — lead-derived, verified by selected_for_preview.json
    if _has_value(lead.get("category")):
        envelope["category"] = {
            "value": str(lead.get("category")),
            "source": "selected_for_preview.json",
            "confidence": CONFIDENCE_VERIFIED,
        }

    # website_status — lead-derived, verified by selected_for_preview.json
    if _has_value(lead.get("website_status")):
        envelope["website_status"] = {
            "value": str(lead.get("website_status")),
            "source": "selected_for_preview.json",
            "confidence": CONFIDENCE_VERIFIED,
        }

    # demand_signal — inferred classification from scorecard component score
    envelope["demand_signal"] = {
        "value": _classify_demand_signal(_safe_component_score(bi_score)),
        "source": "scorecard.component_scores",
        "confidence": CONFIDENCE_INFERRED,
    }

    return envelope


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------
def build_market_profile(
    lead: dict[str, Any],
    config: dict[str, Any],
    *,
    run_id: str,
    bi_score: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the canonical market_profile dict for a single scored lead.

    Parameters
    ----------
    lead:
        The scored lead dict. Phase 03 emits the canonical shape; the
        market_profile only consumes the public-safe fields.
    config:
        Run-level config (kept for symmetry with business_profile.build_business_profile
        and for future per-config overrides; not consumed today).
    run_id:
        Run identifier; used both as a top-level field and to derive a
        deterministic `generated_at`.
    bi_score:
        Output of `score_business_intelligence()`. If None, an empty dict is
        assumed and the score/demand_signal fields fall back to safe defaults.

    Returns
    -------
    A JSON-serializable dict with the structure::

        {
            "schema_version": "1.0.0",
            "run_id": ...,
            "business_slug": ...,
            "generated_at": ...,
            "sellability": { ... },
            "strategy_hints": {"positioning": [...], "value_drivers": [...], "risk_flags": [...]},
            "missing_data": [...],
            "forbidden_public_claims": [...],
            "internal": {
                "flag": "use_market_profile_contract",
                "schema_origin": "VNEXT-02",
                "migration_phase": "prompt_hints_alias_active",
            },
        }
    """
    del config  # reserved for future per-config overrides
    business_slug = _safe_str(lead.get("business_slug"))
    if not business_slug:
        raise ValueError("lead.business_slug is required to build a market_profile")

    bi = bi_score if isinstance(bi_score, dict) else {}
    value_drivers = [str(v) for v in (bi.get("value_drivers") or [])]
    risk_flags = [str(r) for r in (bi.get("risk_flags") or [])]

    profile: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "business_slug": business_slug,
        "generated_at": _deterministic_generated_at(run_id, business_slug),
        "sellability": _sellability_envelope(lead, bi),
        "strategy_hints": _split_strategy_hints(value_drivers, risk_flags),
        "missing_data": _missing_data(lead),
        "forbidden_public_claims": _forbidden_public_claims(),
        "internal": {
            "flag": "use_market_profile_contract",
            "schema_origin": "VNEXT-02",
            "migration_phase": "prompt_hints_alias_active",
        },
    }
    return profile


def write_market_profile(
    profile: dict[str, Any],
    output_dir: str | Path,
    business_slug: str,
) -> str:
    """Write the profile to {output_dir}/{business_slug}/market_profile.json.

    Returns the absolute path of the written file.
    """
    output_path = Path(output_dir) / business_slug / "market_profile.json"
    return write_json(str(output_path), profile)
