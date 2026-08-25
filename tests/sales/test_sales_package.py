"""Unit tests for VNEXT-08 — Sales Package Contract."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from packages.sales.sales_package import (
    _FORBIDDEN_PUBLIC_CLAIMS,
    SCHEMA_VERSION,
    _build_business_summary,
    _build_compliance_notes,
    _build_evaluation_summary,
    _build_offer,
    _build_owner_facing_summary,
    _build_preview_url,
    _build_recipient_channel,
    _build_screenshots,
    _deterministic_generated_at,
    build_sales_package,
    write_sales_package,
)
from pipeline.json_io import read_json

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
            "value": "Auto Detailing",
            "source": "business_profile.json",
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
        "address": {
            "value": "123 Main St, Dallas, TX 75201",
            "source": "business_profile.json",
            "confidence": "verified",
        },
        "phone": {
            "value": "+1-555-123-4567",
            "source": "business_profile.json",
            "confidence": "verified",
        },
    },
    "missing_data": [],
    "recipient_channel": {
        "channel": "phone",
        "value": "+1-555-123-4567",
        "source": "google_maps_listing",
        "confidence": "verified",
    },
}

_MINIMAL_BUSINESS_PROFILE = {
    "business_slug": "tiny-cafe",
    "verified_facts": {
        "business_name": {
            "value": "Tiny Cafe",
            "source": "business_profile.json",
            "confidence": "verified",
        },
    },
    "missing_data": ["category", "rating", "review_count", "address", "phone"],
}

_COMPLETE_EVALUATION_REPORT = {
    "overall_score": 82.3,
    "verdict": "pass",
    "dimensions": {
        "trust": {"score": 85},
        "conversion": {"score": 80},
        "factual_safety": {"score": 100},
        "typography": {"score": 70},
        "imagery": {"score": 60},
    },
    "forbidden_claims_check": {
        "passed": True,
        "violations": [],
    },
}

_COMPLETE_CONFIG = {
    "price_offer": "$299",
    "offer_type": "setup_only",
}

_REQUIRED_BLOCKLIST_CATEGORIES = {
    "years_in_business",
    "awards",
    "licenses",
    "insurance",
    "certifications",
    "staff_credentials",
    "testimonials",
    "guarantees",
    "superlatives",
}


# ===================================================================
# Gate A: Schema, required keys, determinism
# ===================================================================


class TestSchemaAndRequiredKeys:
    """Gate A: schema version, required top-level keys, run_id, business_slug."""

    def test_schema_version(self):
        pkg = build_sales_package(
            _COMPLETE_BUSINESS_PROFILE, run_id="run_001"
        )
        assert pkg["schema_version"] == SCHEMA_VERSION
        assert pkg["schema_version"] == "1.0.0"

    def test_run_id_propagated(self):
        pkg = build_sales_package(
            _COMPLETE_BUSINESS_PROFILE, run_id="run_abc"
        )
        assert pkg["run_id"] == "run_abc"

    def test_business_slug_propagated(self):
        pkg = build_sales_package(
            _COMPLETE_BUSINESS_PROFILE, run_id="r1"
        )
        assert pkg["business_slug"] == "north-dallas-mobile-detailing"

    def test_generated_at_present(self):
        pkg = build_sales_package(
            _COMPLETE_BUSINESS_PROFILE, run_id="r1"
        )
        assert "generated_at" in pkg
        assert pkg["generated_at"].endswith("Z")

    def test_all_required_top_level_keys(self):
        pkg = build_sales_package(
            _COMPLETE_BUSINESS_PROFILE, run_id="r1"
        )
        required_keys = {
            "schema_version",
            "run_id",
            "business_slug",
            "generated_at",
            "preview_url",
            "screenshots",
            "business_summary",
            "offer",
            "evaluation_summary",
            "recipient_channel",
            "compliance_notes",
            "owner_facing_summary",
            "missing_data",
            "forbidden_public_claims",
            "internal",
        }
        assert required_keys.issubset(set(pkg.keys())), (
            f"Missing keys: {required_keys - set(pkg.keys())}"
        )

    def test_missing_business_slug_raises(self):
        import pytest

        with pytest.raises(ValueError, match="business_slug"):
            build_sales_package({"business_slug": ""}, run_id="r1")

    def test_none_business_slug_raises(self):
        import pytest

        with pytest.raises(ValueError, match="business_slug"):
            build_sales_package({}, run_id="r1")


class TestDeterminism:
    """Gate A: identical inputs produce identical outputs."""

    def test_deterministic_generated_at(self):
        t1 = _deterministic_generated_at("run_001", "slug-a")
        t2 = _deterministic_generated_at("run_001", "slug-a")
        assert t1 == t2

    def test_different_slug_different_timestamp(self):
        t1 = _deterministic_generated_at("run_001", "slug-a")
        t2 = _deterministic_generated_at("run_001", "slug-b")
        assert t1 != t2

    def test_full_package_deterministic(self):
        pkg1 = build_sales_package(
            _COMPLETE_BUSINESS_PROFILE,
            evaluation_report=_COMPLETE_EVALUATION_REPORT,
            config=_COMPLETE_CONFIG,
            run_id="run_001",
            preview_url="https://example.com",
            screenshots={"desktop": "/desk.png", "mobile": "/mob.png"},
        )
        pkg2 = build_sales_package(
            _COMPLETE_BUSINESS_PROFILE,
            evaluation_report=_COMPLETE_EVALUATION_REPORT,
            config=_COMPLETE_CONFIG,
            run_id="run_001",
            preview_url="https://example.com",
            screenshots={"desktop": "/desk.png", "mobile": "/mob.png"},
        )
        assert pkg1 == pkg2


# ===================================================================
# Gate B: No unsupported claims, forbidden blocklist, compliance
# ===================================================================


class TestForbiddenClaims:
    """Gate B: forbidden_public_claims blocklist completeness."""

    def test_blocklist_present(self):
        pkg = build_sales_package(
            _COMPLETE_BUSINESS_PROFILE, run_id="r1"
        )
        assert "forbidden_public_claims" in pkg
        assert len(pkg["forbidden_public_claims"]) > 0

    def test_blocklist_contains_required_categories(self):
        pkg = build_sales_package(
            _COMPLETE_BUSINESS_PROFILE, run_id="r1"
        )
        claims = set(pkg["forbidden_public_claims"])
        assert _REQUIRED_BLOCKLIST_CATEGORIES.issubset(claims)

    def test_blocklist_matches_constant(self):
        assert set(_FORBIDDEN_PUBLIC_CLAIMS) == _REQUIRED_BLOCKLIST_CATEGORIES


class TestOwnerFacingSummarySafety:
    """Gate B: owner_facing_summary contains no unsupported claims."""

    def test_summary_no_forbidden_words(self):
        pkg = build_sales_package(
            _COMPLETE_BUSINESS_PROFILE, run_id="r1"
        )
        summary = pkg["owner_facing_summary"].lower()
        for claim in _FORBIDDEN_PUBLIC_CLAIMS:
            # Check the claim keyword isn't in the summary
            assert claim.replace("_", " ") not in summary, (
                f"Forbidden claim '{claim}' found in summary"
            )

    def test_summary_is_string(self):
        pkg = build_sales_package(
            _COMPLETE_BUSINESS_PROFILE, run_id="r1"
        )
        assert isinstance(pkg["owner_facing_summary"], str)

    def test_summary_complete_profile(self):
        summary = _build_owner_facing_summary(
            _COMPLETE_BUSINESS_PROFILE, None
        )
        assert "North Dallas Mobile Detailing" in summary
        assert "Auto Detailing" in summary
        assert "4.8" in summary
        assert "180" in summary

    def test_summary_minimal_profile(self):
        summary = _build_owner_facing_summary(
            _MINIMAL_BUSINESS_PROFILE, None
        )
        assert "Tiny Cafe" in summary
        # No rating/review phrase
        assert "rating" not in summary.lower()

    def test_summary_no_phone_no_booking(self):
        bp = {
            "business_slug": "no-phone-co",
            "verified_facts": {
                "business_name": {"value": "No Phone Co", "source": "bp", "confidence": "verified"},
                "category": {"value": "Plumbing", "source": "bp", "confidence": "verified"},
            },
            "missing_data": ["phone"],
        }
        summary = _build_owner_facing_summary(bp, None)
        assert "booking" not in summary.lower()
        assert "No Phone Co" in summary


class TestComplianceNotes:
    """Gate B: compliance_notes structure."""

    def test_compliance_notes_structure(self):
        notes = _build_compliance_notes(
            _COMPLETE_BUSINESS_PROFILE, _COMPLETE_EVALUATION_REPORT
        )
        assert "forbidden_claims_checked" in notes
        assert "no_unsupported_claims" in notes
        assert "missing_data_noted" in notes
        assert notes["forbidden_claims_checked"] is True
        assert notes["no_unsupported_claims"] is True

    def test_compliance_notes_no_evaluation(self):
        notes = _build_compliance_notes(_COMPLETE_BUSINESS_PROFILE, None)
        assert notes["forbidden_claims_checked"] is True
        assert notes["no_unsupported_claims"] is True

    def test_compliance_notes_missing_data(self):
        notes = _build_compliance_notes(_MINIMAL_BUSINESS_PROFILE, None)
        assert "category" in notes["missing_data_noted"]
        assert "phone" in notes["missing_data_noted"]

    def test_compliance_notes_violations_detected(self):
        eval_report = {
            "forbidden_claims_check": {
                "passed": False,
                "violations": ["#1 rated"],
            },
        }
        notes = _build_compliance_notes(_COMPLETE_BUSINESS_PROFILE, eval_report)
        assert notes["no_unsupported_claims"] is False


# ===================================================================
# Gate C: Backward compat — additive only, no change to Phase 08/09
# ===================================================================


class TestBackwardCompat:
    """Gate C: module is additive, no impact on existing phases."""

    def test_module_importable_without_side_effects(self):
        """Importing the module should not modify any existing module state."""
        import importlib
        import sys

        # Record existing modules before import
        before = set(sys.modules.keys())
        importlib.import_module("packages.sales.sales_package")
        after = set(sys.modules.keys())
        new_modules = after - before
        # Should only add sales-related modules
        for mod in new_modules:
            assert "sales" in mod or mod.startswith("packages.sales"), (
                f"Unexpected module import: {mod}"
            )

    def test_no_mutation_of_inputs(self):
        """build_sales_package should not mutate its input dicts."""
        bp = {
            "business_slug": "test-bp",
            "verified_facts": {
                "business_name": {"value": "Test", "source": "bp", "confidence": "verified"},
            },
            "missing_data": [],
        }
        bp_copy = json.loads(json.dumps(bp))
        build_sales_package(bp, run_id="r1")
        assert bp == bp_copy


# ===================================================================
# Gate D: write function, internal block, missing data, sections
# ===================================================================


class TestWriteSalesPackage:
    """Gate D: write_sales_package produces valid JSON file."""

    def test_write_creates_file(self):
        pkg = build_sales_package(
            _COMPLETE_BUSINESS_PROFILE, run_id="r1"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = write_sales_package(pkg, tmp, "north-dallas-mobile-detailing")
            assert Path(path).exists()
            data = read_json(path)
            assert data["schema_version"] == "1.0.0"
            assert data["business_slug"] == "north-dallas-mobile-detailing"

    def test_write_output_is_valid_json(self):
        pkg = build_sales_package(
            _COMPLETE_BUSINESS_PROFILE, run_id="r1"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = write_sales_package(pkg, tmp, "north-dallas-mobile-detailing")
            with open(path) as f:
                data = json.load(f)
            assert isinstance(data, dict)


class TestInternalBlock:
    """Gate D: internal block correctness."""

    def test_internal_flag(self):
        pkg = build_sales_package(
            _COMPLETE_BUSINESS_PROFILE, run_id="r1"
        )
        assert pkg["internal"]["flag"] == "use_sales_package_contract"
        assert pkg["internal"]["schema_origin"] == "VNEXT-08"


class TestMissingData:
    """Gate D: missing_data aggregation."""

    def test_missing_data_complete_profile(self):
        pkg = build_sales_package(
            _COMPLETE_BUSINESS_PROFILE,
            evaluation_report=_COMPLETE_EVALUATION_REPORT,
            config=_COMPLETE_CONFIG,
            run_id="r1",
            preview_url="https://example.com",
            screenshots={"desktop": "/d.png", "mobile": "/m.png"},
        )
        assert pkg["missing_data"] == []

    def test_missing_data_minimal(self):
        pkg = build_sales_package(
            _MINIMAL_BUSINESS_PROFILE, run_id="r1"
        )
        md = set(pkg["missing_data"])
        assert "preview_url" in md
        assert "screenshots" in md
        assert "evaluation_report" in md
        # From business_profile
        assert "category" in md
        assert "phone" in md

    def test_missing_data_sorted(self):
        pkg = build_sales_package(
            _MINIMAL_BUSINESS_PROFILE, run_id="r1"
        )
        assert pkg["missing_data"] == sorted(pkg["missing_data"])

    def test_missing_data_no_duplicate(self):
        pkg = build_sales_package(
            _MINIMAL_BUSINESS_PROFILE, run_id="r1"
        )
        assert len(pkg["missing_data"]) == len(set(pkg["missing_data"]))


class TestBusinessSummary:
    """Gate D: business_summary section."""

    def test_complete_summary(self):
        summary = _build_business_summary(_COMPLETE_BUSINESS_PROFILE)
        assert "business_name" in summary
        assert "category" in summary
        assert "rating" in summary
        assert "review_count" in summary
        assert "address" in summary
        assert "phone" in summary

    def test_minimal_summary(self):
        summary = _build_business_summary(_MINIMAL_BUSINESS_PROFILE)
        assert "business_name" in summary
        assert "category" not in summary

    def test_provenance_envelopes(self):
        summary = _build_business_summary(_COMPLETE_BUSINESS_PROFILE)
        for field, envelope in summary.items():
            assert "value" in envelope
            assert "source" in envelope
            assert "confidence" in envelope
            assert envelope["source"] == "business_profile.json"
            assert envelope["confidence"] == "verified"


class TestEvaluationSummary:
    """Gate D: evaluation_summary section."""

    def test_with_evaluation(self):
        es = _build_evaluation_summary(_COMPLETE_EVALUATION_REPORT)
        assert es["overall_score"] == 82.3
        assert es["verdict"] == "pass"
        assert "trust" in es["top_dimensions"]
        assert es["top_dimensions"]["trust"] == 85
        # Should only have top 3
        assert len(es["top_dimensions"]) == 3

    def test_without_evaluation(self):
        es = _build_evaluation_summary(None)
        assert es["overall_score"] is None
        assert es["verdict"] == "not_evaluated"
        assert es["top_dimensions"] == {}


class TestOfferSection:
    """Gate D: offer section."""

    def test_with_config(self):
        offer = _build_offer(_COMPLETE_CONFIG)
        assert offer["price"]["value"] == "$299"
        assert offer["description"]["value"] == "One-time setup"

    def test_without_config(self):
        offer = _build_offer(None)
        assert offer == {}

    def test_custom_offer_type(self):
        offer = _build_offer({"offer_type": "monthly_subscription"})
        assert offer["description"]["value"] == "monthly_subscription"


class TestPreviewUrl:
    """Gate D: preview_url section."""

    def test_with_url(self):
        pu = _build_preview_url("https://example.com", None)
        assert pu["value"] == "https://example.com"
        assert pu["source"] == "deployment"
        assert pu["confidence"] == "verified"

    def test_without_url(self):
        pu = _build_preview_url("", None)
        assert pu["value"] == ""
        assert pu["confidence"] == "unknown"


class TestScreenshots:
    """Gate D: screenshots section."""

    def test_both_screenshots(self):
        ss = _build_screenshots({"desktop": "/d.png", "mobile": "/m.png"})
        assert "desktop" in ss
        assert "mobile" in ss
        assert ss["desktop"]["source"] == "phase_05_5"

    def test_none_input(self):
        ss = _build_screenshots(None)
        assert ss == {}

    def test_partial_screenshots(self):
        ss = _build_screenshots({"desktop": "/d.png"})
        assert "desktop" in ss
        assert "mobile" not in ss


class TestRecipientChannel:
    """Gate D: recipient_channel section."""

    def test_from_business_profile(self):
        rc = _build_recipient_channel(_COMPLETE_BUSINESS_PROFILE)
        assert rc["channel"] == "phone"
        assert rc["value"] == "+1-555-123-4567"

    def test_minimal_profile(self):
        rc = _build_recipient_channel(_MINIMAL_BUSINESS_PROFILE)
        assert rc["channel"] == "unknown"
