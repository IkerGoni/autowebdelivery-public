"""Unit tests for VNEXT-09 — Learning Record Contract (learning_record.py)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from pipeline.json_io import read_json
from packages.learning.learning_record import (
    SCHEMA_VERSION,
    _compute_analytics_keys,
    _compute_score_band,
    _deterministic_generated_at,
    _extract_evaluation_summary,
    _extract_generation_features,
    _extract_lead_features,
    _extract_sales_package_ref,
    _has_value,
    build_learning_record,
    write_learning_record,
)
from packages.shared.forbidden_claims import FORBIDDEN_PUBLIC_CLAIMS as _FORBIDDEN_PUBLIC_CLAIMS


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_COMPLETE_BUSINESS_PROFILE = {
    "schema_version": "1.0.0",
    "run_id": "run_001",
    "business_slug": "north-dallas-mobile-detailing",
    "generated_at": "2026-04-12T00:00:00Z",
    "verified_facts": {
        "business_name": {
            "value": "North Dallas Mobile Detailing",
            "source": "business_profile.json",
            "confidence": "verified",
        },
        "category": {
            "value": "Auto Detailing Service",
            "source": "selected_for_preview.json",
            "confidence": "verified",
        },
        "area": {
            "value": "Dallas, TX",
            "source": "selected_for_preview.json",
            "confidence": "verified",
        },
        "rating": {
            "value": 4.8,
            "source": "business_profile.json",
            "confidence": "verified",
        },
        "review_count": {
            "value": 180,
            "source": "business_profile.json",
            "confidence": "verified",
        },
    },
}

_COMPLETE_MARKET_PROFILE = {
    "schema_version": "1.0.0",
    "run_id": "run_001",
    "business_slug": "north-dallas-mobile-detailing",
    "category": {
        "value": "Auto Detailing Service",
        "source": "selected_for_preview.json",
        "confidence": "verified",
    },
    "website_status": {
        "value": "no_website",
        "source": "market_profile.json",
        "confidence": "verified",
    },
}

_COMPLETE_CREATIVE_SPEC = {
    "schema_version": "1.0.0",
    "template_family": {
        "value": "industrial_reliable",
        "source": "creative_spec.json",
        "confidence": "inferred",
    },
    "sections": {
        "value": ["hero", "services", "about", "contact", "cta"],
        "source": "creative_spec.json",
        "confidence": "inferred",
    },
}

_COMPLETE_EVALUATION_REPORT = {
    "schema_version": "1.0.0",
    "overall_score": {
        "value": 82.3,
        "source": "evaluation_report.json",
        "confidence": "verified",
    },
    "verdict": {
        "value": "pass",
        "source": "evaluation_report.json",
        "confidence": "verified",
    },
    "factual_safety": {
        "value": 100,
        "source": "evaluation_report.json",
        "confidence": "verified",
    },
    "hard_failures": {
        "value": [],
        "source": "evaluation_report.json",
        "confidence": "verified",
    },
}

_COMPLETE_SALES_PACKAGE = {
    "schema_version": "1.0.0",
    "offer": {
        "price": {
            "value": "$299",
            "source": "sales_package.json",
            "confidence": "verified",
        },
    },
}

_COMPLETE_PROMPT_CONTRACT = {
    "prompt_hash": {
        "value": "abc123def456",
        "source": "stitch_prompt_contract.json",
        "confidence": "verified",
    },
    "compiler_version": {
        "value": "stitch_compiler_v1",
        "source": "stitch_prompt_contract.json",
        "confidence": "verified",
    },
}


# ---------------------------------------------------------------------------
# Tests — build with all artifacts present
# ---------------------------------------------------------------------------


class TestBuildWithAllArtifacts:
    """Build a record with every upstream artifact present."""

    def test_full_build_has_all_sections(self):
        rec = build_learning_record(
            business_profile=_COMPLETE_BUSINESS_PROFILE,
            market_profile=_COMPLETE_MARKET_PROFILE,
            creative_spec=_COMPLETE_CREATIVE_SPEC,
            evaluation_report=_COMPLETE_EVALUATION_REPORT,
            sales_package=_COMPLETE_SALES_PACKAGE,
            prompt_contract=_COMPLETE_PROMPT_CONTRACT,
            run_id="run_001",
            business_slug="north-dallas-mobile-detailing",
        )
        for key in (
            "schema_version", "run_id", "business_slug", "generated_at",
            "lead_features", "generation_features", "evaluation_summary",
            "sales_package_ref", "outcome", "analytics_keys",
            "missing_data", "internal",
        ):
            assert key in rec, f"Missing top-level key: {key}"

    def test_full_build_lead_features(self):
        rec = build_learning_record(
            business_profile=_COMPLETE_BUSINESS_PROFILE,
            market_profile=_COMPLETE_MARKET_PROFILE,
            run_id="run_001",
            business_slug="north-dallas-mobile-detailing",
        )
        lf = rec["lead_features"]
        assert lf["category"]["value"] == "Auto Detailing Service"
        assert lf["area"]["value"] == "Dallas, TX"
        assert lf["rating"]["value"] == 4.8
        assert lf["review_count"]["value"] == 180
        assert lf["website_status"]["value"] == "no_website"

    def test_full_build_generation_features(self):
        rec = build_learning_record(
            creative_spec=_COMPLETE_CREATIVE_SPEC,
            prompt_contract=_COMPLETE_PROMPT_CONTRACT,
            run_id="run_001",
            business_slug="north-dallas-mobile-detailing",
        )
        gf = rec["generation_features"]
        assert gf["template_family"]["value"] == "industrial_reliable"
        assert gf["sections"]["value"] == ["hero", "services", "about", "contact", "cta"]
        assert gf["prompt_hash"]["value"] == "abc123def456"
        assert gf["compiler_version"]["value"] == "stitch_compiler_v1"

    def test_full_build_evaluation_summary(self):
        rec = build_learning_record(
            evaluation_report=_COMPLETE_EVALUATION_REPORT,
            run_id="run_001",
            business_slug="north-dallas-mobile-detailing",
        )
        es = rec["evaluation_summary"]
        assert es["overall_score"]["value"] == 82.3
        assert es["verdict"]["value"] == "pass"
        assert es["factual_safety"]["value"] == 100

    def test_full_build_sales_package_ref(self):
        rec = build_learning_record(
            sales_package=_COMPLETE_SALES_PACKAGE,
            run_id="run_001",
            business_slug="north-dallas-mobile-detailing",
        )
        sp = rec["sales_package_ref"]
        assert sp["has_sales_package"] is True
        assert sp["offer_price"]["value"] == "$299"


# ---------------------------------------------------------------------------
# Tests — build with minimal / no artifacts
# ---------------------------------------------------------------------------


class TestBuildMinimal:
    """Build with just run_id and business_slug."""

    def test_minimal_build_succeeds(self):
        rec = build_learning_record(
            run_id="run_min",
            business_slug="test-biz",
        )
        assert rec["schema_version"] == SCHEMA_VERSION
        assert rec["run_id"] == "run_min"
        assert rec["business_slug"] == "test-biz"

    def test_minimal_build_empty_sections(self):
        rec = build_learning_record(
            run_id="run_min",
            business_slug="test-biz",
        )
        assert rec["lead_features"] == {}
        assert rec["generation_features"] == {}
        assert rec["evaluation_summary"] == {}

    def test_minimal_build_outcome_pending(self):
        rec = build_learning_record(
            run_id="run_min",
            business_slug="test-biz",
        )
        assert rec["outcome"]["status"] == "pending"
        assert rec["outcome"]["events"] == []
        assert rec["outcome"]["last_updated"] is None

    def test_minimal_build_missing_data_populated(self):
        rec = build_learning_record(
            run_id="run_min",
            business_slug="test-biz",
        )
        assert "lead_features" in rec["missing_data"]
        assert "generation_features" in rec["missing_data"]
        assert "evaluation_summary" in rec["missing_data"]
        assert "sales_package_ref" in rec["missing_data"]


# ---------------------------------------------------------------------------
# Tests — _extract_lead_features
# ---------------------------------------------------------------------------


class TestExtractLeadFeatures:
    def test_extracts_all_fields(self):
        lf = _extract_lead_features(_COMPLETE_BUSINESS_PROFILE, _COMPLETE_MARKET_PROFILE)
        assert "category" in lf
        assert "area" in lf
        assert "rating" in lf
        assert "review_count" in lf
        assert "website_status" in lf

    def test_handles_none_inputs(self):
        lf = _extract_lead_features(None, None)
        assert lf == {}

    def test_category_from_market_profile_fallback(self):
        """If business_profile has no category, fall back to market_profile."""
        bp = {"verified_facts": {"rating": {"value": 4.5, "source": "x", "confidence": "verified"}}}
        mp = {"category": {"value": "Plumber", "source": "x", "confidence": "verified"}}
        lf = _extract_lead_features(bp, mp)
        assert lf["category"]["value"] == "Plumber"


# ---------------------------------------------------------------------------
# Tests — _extract_generation_features
# ---------------------------------------------------------------------------


class TestExtractGenerationFeatures:
    def test_extracts_all_fields(self):
        gf = _extract_generation_features(_COMPLETE_CREATIVE_SPEC, _COMPLETE_PROMPT_CONTRACT)
        assert "template_family" in gf
        assert "sections" in gf
        assert "prompt_hash" in gf
        assert "compiler_version" in gf

    def test_handles_none_inputs(self):
        gf = _extract_generation_features(None, None)
        assert gf == {}


# ---------------------------------------------------------------------------
# Tests — _extract_evaluation_summary
# ---------------------------------------------------------------------------


class TestExtractEvaluationSummary:
    def test_extracts_all_fields(self):
        es = _extract_evaluation_summary(_COMPLETE_EVALUATION_REPORT)
        assert es["overall_score"]["value"] == 82.3
        assert es["verdict"]["value"] == "pass"

    def test_handles_none(self):
        es = _extract_evaluation_summary(None)
        assert es == {}


# ---------------------------------------------------------------------------
# Tests — _extract_sales_package_ref
# ---------------------------------------------------------------------------


class TestExtractSalesPackageRef:
    def test_with_package(self):
        ref = _extract_sales_package_ref(_COMPLETE_SALES_PACKAGE)
        assert ref["has_sales_package"] is True
        assert ref["offer_price"]["value"] == "$299"

    def test_without_package(self):
        ref = _extract_sales_package_ref(None)
        assert ref["has_sales_package"] is False


# ---------------------------------------------------------------------------
# Tests — _compute_score_band
# ---------------------------------------------------------------------------


class TestComputeScoreBand:
    def test_unknown_none(self):
        assert _compute_score_band(None) == "unknown"

    def test_low(self):
        assert _compute_score_band(49.9) == "low"
        assert _compute_score_band(0) == "low"

    def test_medium(self):
        assert _compute_score_band(50) == "medium"
        assert _compute_score_band(69.9) == "medium"

    def test_high(self):
        assert _compute_score_band(70) == "high"
        assert _compute_score_band(84.9) == "high"

    def test_premium(self):
        assert _compute_score_band(85) == "premium"
        assert _compute_score_band(100) == "premium"


# ---------------------------------------------------------------------------
# Tests — _compute_analytics_keys
# ---------------------------------------------------------------------------


class TestComputeAnalyticsKeys:
    def test_full_analytics(self):
        lf = {"category": {"value": "Auto Detailing Service"}, "website_status": {"value": "no_website"}}
        es = {"overall_score": {"value": 82.3}}
        sp = {"has_sales_package": True}
        keys = _compute_analytics_keys(lf, es, sp)
        assert keys["niche"] == "auto_detailing_service"
        assert keys["score_band"] == "high"
        assert keys["creative_strategy"] == "missing_website_upgrade"
        assert keys["channel"] == "phone"
        assert keys["outcome_category"] == "pending"

    def test_has_website_strategy(self):
        lf = {"website_status": {"value": "has_website"}}
        keys = _compute_analytics_keys(lf, {}, {})
        assert keys["creative_strategy"] == "website_redesign"

    def test_unknown_strategy(self):
        lf = {}
        keys = _compute_analytics_keys(lf, {}, {})
        assert keys["creative_strategy"] == "unknown"


# ---------------------------------------------------------------------------
# Tests — deterministic generated_at
# ---------------------------------------------------------------------------


class TestDeterministicTimestamp:
    def test_deterministic(self):
        ts1 = _deterministic_generated_at("run_001", "slug-a")
        ts2 = _deterministic_generated_at("run_001", "slug-a")
        assert ts1 == ts2

    def test_different_slugs_different_timestamps(self):
        ts1 = _deterministic_generated_at("run_001", "slug-a")
        ts2 = _deterministic_generated_at("run_001", "slug-b")
        assert ts1 != ts2

    def test_iso_format(self):
        ts = _deterministic_generated_at("run_001", "slug-a")
        # Must start with 2025-
        assert ts.startswith("2025-")
        assert "T" in ts


# ---------------------------------------------------------------------------
# Tests — write_learning_record
# ---------------------------------------------------------------------------


class TestWriteLearningRecord:
    def test_writes_file(self):
        rec = build_learning_record(run_id="run_w", business_slug="write-biz")
        with tempfile.TemporaryDirectory() as tmp:
            path = write_learning_record(rec, tmp, "write-biz")
            assert Path(path).exists()
            loaded = read_json(path)
            assert loaded["schema_version"] == SCHEMA_VERSION

    def test_creates_subdirectory(self):
        rec = build_learning_record(run_id="run_w2", business_slug="nested-biz")
        with tempfile.TemporaryDirectory() as tmp:
            path = write_learning_record(rec, tmp, "nested-biz")
            assert "nested-biz" in path
            assert Path(path).exists()


# ---------------------------------------------------------------------------
# Tests — forbidden public claims and schema
# ---------------------------------------------------------------------------


class TestSchemaAndCompliance:
    def test_schema_version(self):
        rec = build_learning_record(run_id="r", business_slug="s")
        assert rec["schema_version"] == "1.0.0"

    def test_internal_block(self):
        rec = build_learning_record(run_id="r", business_slug="s")
        assert rec["internal"]["flag"] == "use_learning_record_contract"
        assert rec["internal"]["schema_origin"] == "VNEXT-09"

    def test_no_forbidden_claims(self):
        rec = build_learning_record(
            business_profile=_COMPLETE_BUSINESS_PROFILE,
            market_profile=_COMPLETE_MARKET_PROFILE,
            run_id="r",
            business_slug="s",
        )
        record_json = json.dumps(rec)
        for claim in _FORBIDDEN_PUBLIC_CLAIMS:
            assert claim not in record_json, f"Forbidden claim '{claim}' found in record"

    def test_has_value_utility(self):
        assert _has_value(None) is False
        assert _has_value("") is False
        assert _has_value([]) is False
        assert _has_value({}) is False
        assert _has_value("hello") is True
        assert _has_value(42) is True
        assert _has_value([1]) is True

    def test_missing_data_empty_when_all_present(self):
        rec = build_learning_record(
            business_profile=_COMPLETE_BUSINESS_PROFILE,
            market_profile=_COMPLETE_MARKET_PROFILE,
            creative_spec=_COMPLETE_CREATIVE_SPEC,
            evaluation_report=_COMPLETE_EVALUATION_REPORT,
            sales_package=_COMPLETE_SALES_PACKAGE,
            run_id="r",
            business_slug="s",
        )
        assert rec["missing_data"] == []
