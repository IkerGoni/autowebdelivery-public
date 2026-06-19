"""
VNEXT-09 — Learning Record Contract.

Build a structured ``learning_record.json`` artifact for each lead that connects
lead features, generation features, evaluation, sales package, and outcome.

This module is pure-Python and deterministic: it takes structured dicts and
produces a deterministic dict with a fixed schema.  No LLM calls are involved.

Feature-flagged behind ``use_learning_record_contract`` (default OFF).
This module is **additive** — it does not modify existing pipeline output.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
_SOURCE_SELECTED_FOR_PREVIEW = "selected_for_preview.json"
_SOURCE_CREATIVE_SPEC = "creative_spec.json"
_SOURCE_EVALUATION_REPORT = "evaluation_report.json"
_SOURCE_SALES_PACKAGE = "sales_package.json"
_SOURCE_STITCH_PROMPT = "stitch_prompt_contract.json"

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _safe_get(mapping: dict | None, *keys: str, default: Any = None) -> Any:
    """Nested dict getter that tolerates None at any level."""
    obj = mapping
    for key in keys:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(key, default)
    return obj


def _prov(value: Any, source: str, confidence: str) -> dict:
    """Wrap a value in a provenance envelope."""
    return {"value": value, "source": source, "confidence": confidence}


def _deterministic_generated_at(run_id: str, business_slug: str) -> str:
    """Produce a deterministic ISO-8601 timestamp from run_id + slug.

    The timestamp is derived from a SHA-256 of ``f"{run_id}/{business_slug}"``
    interpreted as a second offset from ``2025-01-01T00:00:00Z``.
    """
    raw = f"{run_id}/{business_slug}"
    digest = hashlib.sha256(raw.encode()).hexdigest()
    offset_seconds = int(digest[:8], 16) % (365 * 24 * 3600)
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return (base + __import__("datetime").timedelta(seconds=offset_seconds)).isoformat()


# ---------------------------------------------------------------------------
# Extractor helpers
# ---------------------------------------------------------------------------


def _extract_lead_features(
    business_profile: dict | None,
    market_profile: dict | None,
) -> dict:
    """Extract lead-level features from business/market profiles."""
    features: dict[str, dict] = {}

    bp = business_profile or {}
    mp = market_profile or {}

    # category — from business_profile verified_facts or market_profile
    category = _safe_get(bp, "verified_facts", "category", "value")
    if not _has_value(category):
        category = _safe_get(mp, "category", "value")
    if _has_value(category):
        features["category"] = _prov(category, _SOURCE_SELECTED_FOR_PREVIEW, CONFIDENCE_VERIFIED)

    # area — from business_profile or market_profile
    area = _safe_get(bp, "verified_facts", "area", "value")
    if not _has_value(area):
        area = _safe_get(bp, "verified_facts", "address", "value")
    if not _has_value(area):
        area = _safe_get(mp, "area", "value")
    if _has_value(area):
        features["area"] = _prov(area, _SOURCE_SELECTED_FOR_PREVIEW, CONFIDENCE_VERIFIED)

    # rating — from business_profile
    rating = _safe_get(bp, "verified_facts", "rating", "value")
    if _has_value(rating):
        features["rating"] = _prov(rating, _SOURCE_BUSINESS_PROFILE, CONFIDENCE_VERIFIED)

    # review_count — from business_profile
    review_count = _safe_get(bp, "verified_facts", "review_count", "value")
    if _has_value(review_count):
        features["review_count"] = _prov(review_count, _SOURCE_BUSINESS_PROFILE, CONFIDENCE_VERIFIED)

    # website_status — from market_profile
    ws = _safe_get(mp, "website_status", "value")
    if _has_value(ws):
        features["website_status"] = _prov(ws, _SOURCE_MARKET_PROFILE, CONFIDENCE_VERIFIED)

    return features


def _extract_generation_features(
    creative_spec: dict | None,
    prompt_contract: dict | None,
) -> dict:
    """Extract generation features from creative_spec and prompt_contract."""
    features: dict[str, dict] = {}

    cs = creative_spec or {}
    pc = prompt_contract or {}

    # template_family — from creative_spec
    tf = _safe_get(cs, "template_family", "value")
    if _has_value(tf):
        features["template_family"] = _prov(tf, _SOURCE_CREATIVE_SPEC, CONFIDENCE_INFERRED)

    # sections — from creative_spec
    sections = _safe_get(cs, "sections", "value")
    if _has_value(sections):
        features["sections"] = _prov(sections, _SOURCE_CREATIVE_SPEC, CONFIDENCE_INFERRED)

    # prompt_hash — from prompt_contract
    ph = _safe_get(pc, "prompt_hash", "value")
    if _has_value(ph):
        features["prompt_hash"] = _prov(ph, _SOURCE_STITCH_PROMPT, CONFIDENCE_VERIFIED)

    # compiler_version — from prompt_contract
    cv = _safe_get(pc, "compiler_version", "value")
    if _has_value(cv):
        features["compiler_version"] = _prov(cv, _SOURCE_STITCH_PROMPT, CONFIDENCE_VERIFIED)

    return features


def _extract_evaluation_summary(
    evaluation_report: dict | None,
) -> dict:
    """Extract evaluation summary from evaluation_report."""
    features: dict[str, dict] = {}

    er = evaluation_report or {}

    # overall_score
    score = _safe_get(er, "overall_score", "value")
    if _has_value(score):
        features["overall_score"] = _prov(score, _SOURCE_EVALUATION_REPORT, CONFIDENCE_VERIFIED)

    # verdict
    verdict = _safe_get(er, "verdict", "value")
    if _has_value(verdict):
        features["verdict"] = _prov(verdict, _SOURCE_EVALUATION_REPORT, CONFIDENCE_VERIFIED)

    # factual_safety
    fs = _safe_get(er, "factual_safety", "value")
    if _has_value(fs):
        features["factual_safety"] = _prov(fs, _SOURCE_EVALUATION_REPORT, CONFIDENCE_VERIFIED)

    # hard_failures
    hf = _safe_get(er, "hard_failures", "value")
    if _has_value(hf):
        features["hard_failures"] = _prov(hf, _SOURCE_EVALUATION_REPORT, CONFIDENCE_VERIFIED)

    return features


def _extract_sales_package_ref(
    sales_package: dict | None,
) -> dict:
    """Extract sales package reference."""
    sp = sales_package or {}
    ref: dict[str, Any] = {"has_sales_package": _has_value(sp)}

    offer_price = _safe_get(sp, "offer", "price", "value")
    if _has_value(offer_price):
        ref["offer_price"] = _prov(offer_price, _SOURCE_SALES_PACKAGE, CONFIDENCE_VERIFIED)

    return ref


def _compute_score_band(score: float | None) -> str:
    """Return score band: 'low' (<50), 'medium' (50-70), 'high' (70-85), 'premium' (85+)."""
    if score is None:
        return "unknown"
    if score < 50:
        return "low"
    if score < 70:
        return "medium"
    if score < 85:
        return "high"
    return "premium"


def _compute_analytics_keys(
    lead_features: dict,
    evaluation_summary: dict,
    sales_package_ref: dict,
) -> dict:
    """Compute analytics grouping keys from extracted features."""
    # niche — derive from category
    category = _safe_get(lead_features, "category", "value")
    niche = "unknown"
    if _has_value(category):
        niche = str(category).lower().replace(" ", "_")

    # score_band
    score = _safe_get(evaluation_summary, "overall_score", "value")
    score_band = _compute_score_band(score)

    # creative_strategy — derive from website_status
    ws = _safe_get(lead_features, "website_status", "value")
    if ws == "no_website":
        creative_strategy = "missing_website_upgrade"
    elif ws == "has_website":
        creative_strategy = "website_redesign"
    else:
        creative_strategy = "unknown"

    # channel — default to phone (from sales_package)
    channel = "phone"

    # outcome_category — pending by default
    outcome_category = "pending"

    return {
        "niche": niche,
        "score_band": score_band,
        "creative_strategy": creative_strategy,
        "channel": channel,
        "outcome_category": outcome_category,
    }


def _collect_missing_data(record: dict) -> list[str]:
    """Collect names of top-level sections with no meaningful data."""
    missing: list[str] = []
    for key in ("lead_features", "generation_features", "evaluation_summary"):
        section = record.get(key, {})
        if not section or not any(_has_value(v.get("value")) for v in section.values() if isinstance(v, dict)):
            missing.append(key)
    sp_ref = record.get("sales_package_ref", {})
    if not sp_ref.get("has_sales_package"):
        missing.append("sales_package_ref")
    return missing


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_learning_record(
    business_profile: dict | None = None,
    market_profile: dict | None = None,
    creative_spec: dict | None = None,
    evaluation_report: dict | None = None,
    sales_package: dict | None = None,
    prompt_contract: dict | None = None,
    config: dict | None = None,
    *,
    run_id: str,
    business_slug: str,
) -> dict:
    """Build a learning record from upstream artifacts.

    All upstream artifacts are optional — the record can be created before
    the outcome is known and with partial data.
    """
    lead_features = _extract_lead_features(business_profile, market_profile)
    generation_features = _extract_generation_features(creative_spec, prompt_contract)
    evaluation_summary = _extract_evaluation_summary(evaluation_report)
    sales_package_ref = _extract_sales_package_ref(sales_package)

    analytics_keys = _compute_analytics_keys(
        lead_features,
        evaluation_summary,
        sales_package_ref,
    )

    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "business_slug": business_slug,
        "generated_at": _deterministic_generated_at(run_id, business_slug),
        "lead_features": lead_features,
        "generation_features": generation_features,
        "evaluation_summary": evaluation_summary,
        "sales_package_ref": sales_package_ref,
        "outcome": {
            "status": "pending",
            "events": [],
            "last_updated": None,
        },
        "analytics_keys": analytics_keys,
        "missing_data": [],
        "internal": {
            "flag": "use_learning_record_contract",
            "schema_origin": "VNEXT-09",
        },
    }

    record["missing_data"] = _collect_missing_data(record)

    return record


def write_learning_record(
    record: dict,
    output_dir: str | Path,
    business_slug: str,
) -> str:
    """Write the learning record to ``<output_dir>/<business_slug>/learning_record.json``.

    Returns the path to the written file.
    """
    output_dir = Path(output_dir)
    dest = output_dir / business_slug / "learning_record.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_json(str(dest), record)
    return str(dest)
