"""Unit tests for VNEXT-01 — Business Profile Contract."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from packages.intelligence.business_profile import (
    SCHEMA_VERSION,
    _forbidden_public_claims,
    _missing_data,
    _provenance,
    _public_safe,
    build_business_profile,
    write_business_profile,
)
from pipeline.json_io import read_json

FIXTURE_DIR = Path.cwd() / "tests" / "fixtures" / "phase_04_business_brief_generation"


def _load_lead(name: str):
    return read_json(str(FIXTURE_DIR / "input" / name))[0]


_BASE_CONFIG = {
    "niche": "dentists",
    "area": "Chiang Mai",
    "country": "Thailand",
    "style_preset": "clinical_trust",
}


# ---------------------------------------------------------------------------
# Required blocklist categories (per spec, at least these must be present)
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestSchemaVersion:
    def test_schema_version_present(self):
        profile = build_business_profile(
            {"business_slug": "x-clinic", "business_name": "X"},
            _BASE_CONFIG,
            run_id="fixture_001",
        )
        assert profile["schema_version"] == SCHEMA_VERSION
        assert profile["schema_version"] == "1.1.0"
        assert profile["run_id"] == "fixture_001"
        assert profile["business_slug"] == "x-clinic"


class TestBuildBusinessProfileMinimal:
    def test_build_business_profile_minimal_lead(self):
        lead = {"business_slug": "tiny-cafe", "business_name": "Tiny Cafe"}
        profile = build_business_profile(lead, _BASE_CONFIG, run_id="r1")

        # Required top-level keys
        for key in (
            "schema_version",
            "run_id",
            "business_slug",
            "generated_at",
            "verified_facts",
            "inferred_strategy",
            "missing_data",
            "forbidden_public_claims",
            "recipient_channel",
            "internal",
        ):
            assert key in profile

        # Only business_name is present on the lead → only it appears in verified_facts
        assert set(profile["verified_facts"].keys()) == {"business_name"}
        assert profile["verified_facts"]["business_name"]["value"] == "Tiny Cafe"

        # Everything else is missing_data
        expected_missing = {
            "address", "phone", "hours", "maps_url",
            "category", "rating", "review_count",
        }
        assert set(profile["missing_data"]) == expected_missing

        # Strategy signals come from config
        assert profile["inferred_strategy"]["niche"]["value"] == "dentists"
        assert profile["inferred_strategy"]["area"]["value"] == "Chiang Mai"
        assert profile["inferred_strategy"]["country"]["value"] == "Thailand"
        assert profile["inferred_strategy"]["template_family"]["value"] == "clinical_trust"
        # website_status absent because the lead has no website_status
        assert "website_status" not in profile["inferred_strategy"]


class TestBuildBusinessProfileComplete:
    def test_build_business_profile_complete_lead(self):
        lead = _load_lead("selected_lead_complete.json")
        profile = build_business_profile(lead, _BASE_CONFIG, run_id="fixture_001")

        # All lead fields appear as verified
        for field in (
            "business_name", "category", "rating", "review_count",
            "address", "phone", "hours", "maps_url",
        ):
            assert field in profile["verified_facts"], f"missing verified_facts.{field}"
            envelope = profile["verified_facts"][field]
            assert envelope["confidence"] == "verified"
            assert envelope["source"] == "selected_for_preview.json"

        # No missing data
        assert profile["missing_data"] == []

        # website_status is in inferred_strategy
        assert profile["inferred_strategy"]["website_status"]["value"] == "no_website"
        assert profile["inferred_strategy"]["website_status"]["confidence"] == "inferred"

        # Recipient channel is the phone
        assert profile["recipient_channel"]["channel"] == "phone"
        assert profile["recipient_channel"]["confidence"] == "verified"


class TestFactualSafety:
    def test_verified_facts_do_not_invent_licenses_awards_years(self):
        # A lead with no license/award/year/etc. data → those must NOT appear
        # as verified_facts values, and the blocklist MUST be present.
        lead = {
            "business_slug": "bare-bones-clinic",
            "business_name": "Bare Bones Clinic",
            "address": "1 Test St",
        }
        profile = build_business_profile(lead, _BASE_CONFIG, run_id="r1")

        for forbidden in (
            "years_in_business", "awards", "licenses", "insurance",
            "certifications", "staff_credentials", "testimonials",
            "guarantees", "superlatives",
        ):
            assert forbidden not in profile["verified_facts"], (
                f"verified_facts must not invent {forbidden!r}"
            )

        # The blocklist is present and explicit
        assert "forbidden_public_claims" in profile
        for forbidden in (
            "years_in_business", "awards", "licenses", "insurance",
            "certifications", "staff_credentials", "testimonials",
            "guarantees", "superlatives",
        ):
            assert forbidden in profile["forbidden_public_claims"], (
                f"forbidden_public_claims must list {forbidden!r}"
            )


class TestForbiddenClaims:
    def test_forbidden_public_claims_blocklist_includes_expected_categories(self):
        blocklist = _forbidden_public_claims()
        assert isinstance(blocklist, list)
        for category in _REQUIRED_BLOCKLIST_CATEGORIES:
            assert category in blocklist, f"missing blocklist category {category!r}"

        # Also verify it is also embedded in the profile
        profile = build_business_profile(
            {"business_slug": "x", "business_name": "X"},
            _BASE_CONFIG,
            run_id="r1",
        )
        for category in _REQUIRED_BLOCKLIST_CATEGORIES:
            assert category in profile["forbidden_public_claims"]

    def test_internal_only_fields_not_exposed_public(self):
        # Build a profile where the lead has internal-only fields attached.
        # None of them should appear at the top level, in verified_facts, or
        # in inferred_strategy.
        lead = {
            "business_slug": "x-cafe",
            "business_name": "X Cafe",
            "lead_score": 87,
            "lead_score_components": {"website": 50, "rating": 37},
            "lead_score_reasons": ["high_rating"],
            "lead_score_band": "A",
            "recipient_confidence": "verified",
            "recipient_confidence_detail": "raw_detail",
            "manual_override_reason": "internal_process_quirk",
            "scoring_internal": {"foo": 1},
            "scoring_breakdown": {"bar": 2},
            "address": "1 Test St",
        }
        profile = build_business_profile(lead, _BASE_CONFIG, run_id="r1")

        public_payload = {
            "verified_facts": profile["verified_facts"],
            "inferred_strategy": profile["inferred_strategy"],
        }
        serialized = json.dumps(public_payload, default=str)

        for forbidden in (
            "lead_score", "lead_score_components", "lead_score_reasons",
            "lead_score_band", "recipient_confidence_detail",
            "manual_override_reason", "scoring_internal", "scoring_breakdown",
        ):
            assert forbidden not in profile, f"top-level exposes {forbidden!r}"
            assert forbidden not in serialized, f"public payload leaks {forbidden!r}"

        # Top-level keys are exactly the public-safe set
        expected_keys = {
            "schema_version", "run_id", "business_slug", "generated_at",
            "verified_facts", "inferred_strategy", "missing_data",
            "forbidden_public_claims", "recipient_channel", "internal",
        }
        assert set(profile.keys()) == expected_keys

        # public_safe chokepoint refuses internal-only fields
        try:
            _public_safe("lead_score", 99, source="x", confidence="verified")
        except ValueError:
            pass
        else:
            raise AssertionError("_public_safe should refuse internal-only fields")


class TestProvenance:
    def test_provenance_and_confidence_present_on_public_safe_fields(self):
        lead = _load_lead("selected_lead_complete.json")
        profile = build_business_profile(lead, _BASE_CONFIG, run_id="fixture_001")

        for section in ("verified_facts", "inferred_strategy"):
            for field, envelope in profile[section].items():
                assert "value" in envelope, f"{section}.{field} missing value"
                assert "source" in envelope, f"{section}.{field} missing source"
                assert "confidence" in envelope, f"{section}.{field} missing confidence"
                assert envelope["confidence"] in {"verified", "inferred", "unknown", "enriched"}, (
                    f"{section}.{field} has bad confidence {envelope['confidence']!r}"
                )

    def test_provenance_helper_shape(self):
        env = _provenance("business_name", "selected_for_preview.json", "verified")
        assert env == {"source": "selected_for_preview.json", "confidence": "verified"}


class TestMissingData:
    def test_missing_data_explicit_not_invented(self):
        # A lead with no phone → phone must be in missing_data, NOT in
        # verified_facts, and NOT invented by the strategy section.
        lead = _load_lead("selected_lead_missing_phone.json")
        profile = build_business_profile(lead, _BASE_CONFIG, run_id="fixture_001")

        assert "phone" in profile["missing_data"]
        assert "phone" not in profile["verified_facts"]
        assert "phone" not in profile["inferred_strategy"]

        # The helper itself surfaces the missing fields
        assert "phone" in _missing_data(lead)

        # No fabricated phone value should be discoverable anywhere in the
        # public payload
        public = {
            "verified_facts": profile["verified_facts"],
            "inferred_strategy": profile["inferred_strategy"],
        }
        assert "phone" not in json.dumps(public, default=str)


class TestDeterminism:
    def test_deterministic_for_fixed_inputs(self):
        lead = _load_lead("selected_lead_complete.json")
        a = build_business_profile(lead, _BASE_CONFIG, run_id="fixture_001")
        b = build_business_profile(lead, _BASE_CONFIG, run_id="fixture_001")

        # Byte-identical dicts
        assert a == b
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)

        # generated_at is stable
        assert a["generated_at"] == b["generated_at"]

        # Different run_id or business_slug should (with overwhelming
        # probability) change generated_at — this catches accidental
        # hard-coding.
        c = build_business_profile(lead, _BASE_CONFIG, run_id="different_run_xyz")
        assert c["generated_at"] != a["generated_at"]


class TestWriteBusinessProfile:
    def test_write_business_profile_writes_under_business_slug_dir(self):
        lead = _load_lead("selected_lead_complete.json")
        profile = build_business_profile(lead, _BASE_CONFIG, run_id="fixture_001")

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            ret = write_business_profile(profile, out, lead["business_slug"])
            assert ret.endswith("business_profile.json")
            assert Path(ret).is_file()

            target = out / lead["business_slug"] / "business_profile.json"
            assert target.exists()
            on_disk = json.loads(target.read_text(encoding="utf-8"))
            assert on_disk["schema_version"] == SCHEMA_VERSION
            assert on_disk["business_slug"] == lead["business_slug"]
            assert on_disk["run_id"] == "fixture_001"


class TestRecipientChannelMirror:
    def test_recipient_channel_for_social_only(self):
        lead = _load_lead("selected_lead_social_only.json")
        profile = build_business_profile(lead, _BASE_CONFIG, run_id="fixture_001")
        assert profile["recipient_channel"]["channel"] == "facebook_message"
        assert profile["recipient_channel"]["confidence"] == "inferred"

    def test_recipient_channel_for_unknown(self):
        lead = _load_lead("selected_lead_unknown_recipient_channel.json")
        profile = build_business_profile(lead, _BASE_CONFIG, run_id="fixture_001")
        assert profile["recipient_channel"]["channel"] == "unknown"
        assert profile["recipient_channel"]["confidence"] == "unknown"

    def test_recipient_channel_for_complete(self):
        lead = _load_lead("selected_lead_complete.json")
        profile = build_business_profile(lead, _BASE_CONFIG, run_id="fixture_001")
        assert profile["recipient_channel"]["channel"] == "phone"
        assert profile["recipient_channel"]["confidence"] == "verified"


class TestRequiresBusinessSlug:
    def test_missing_business_slug_raises(self):
        import pytest

        with pytest.raises(ValueError):
            build_business_profile({"business_name": "x"}, _BASE_CONFIG, run_id="r1")


# ---------------------------------------------------------------------------
# VNEXT-16: Enrichment consumption tests
# ---------------------------------------------------------------------------


class TestEnrichmentConsumption:
    """business_profile must consume Overpass, Google Maps, and Social enrichment data."""

    def test_gmaps_enrichment_fills_rating_and_review_count(self):
        """When gmaps_enrichment is provided, it fills missing rating and review_count."""
        lead = {"business_slug": "test-cafe", "business_name": "Test Cafe"}
        gmaps = {
            "business_name": "Test Cafe",
            "rating": 4.5,
            "review_count": 89,
            "review_snippets": ["Great service!", "Highly recommended"],
            "description": "A cozy cafe",
            "source_url": "https://maps.google.com/...",
        }
        profile = build_business_profile(
            lead, _BASE_CONFIG, run_id="r1",
            gmaps_enrichment=gmaps,
        )
        # Rating and review_count should come from enrichment
        assert profile["verified_facts"]["rating"]["value"] == 4.5
        assert profile["verified_facts"]["rating"]["confidence"] == "enriched"
        assert profile["verified_facts"]["review_count"]["value"] == 89
        assert profile["verified_facts"]["review_count"]["confidence"] == "enriched"
        # maps_url should be filled from source_url
        assert profile["verified_facts"]["maps_url"]["value"] == "https://maps.google.com/..."

    def test_lead_data_takes_precedence_over_enrichment(self):
        """Lead data (source of truth) should always win over enrichment."""
        lead = {
            "business_slug": "existing-cafe",
            "business_name": "Existing Cafe",
            "rating": 3.0,
            "review_count": 10,
        }
        gmaps = {
            "rating": 4.5,
            "review_count": 200,
        }
        profile = build_business_profile(
            lead, _BASE_CONFIG, run_id="r1",
            gmaps_enrichment=gmaps,
        )
        # Lead values should take precedence
        assert profile["verified_facts"]["rating"]["value"] == 3.0
        assert profile["verified_facts"]["rating"]["confidence"] == "verified"
        assert profile["verified_facts"]["review_count"]["value"] == 10
        assert profile["verified_facts"]["review_count"]["confidence"] == "verified"

    def test_enrichment_reduces_missing_data(self):
        """Fields filled by enrichment should not appear in missing_data."""
        lead = {"business_slug": "no-data-shop", "business_name": "No Data Shop"}
        gmaps = {"rating": 4.0, "review_count": 50}
        profile = build_business_profile(
            lead, _BASE_CONFIG, run_id="r1",
            gmaps_enrichment=gmaps,
        )
        # rating and review_count should not be in missing_data
        assert "rating" not in profile["missing_data"]
        assert "review_count" not in profile["missing_data"]
        # But other fields still are
        for f in ("address", "phone", "hours", "category"):
            assert f in profile["missing_data"]

    def test_enrichment_section_present_with_gmaps(self):
        """When enrichment data is provided, an enrichment section appears."""
        lead = {"business_slug": "test-shop", "business_name": "Test Shop"}
        gmaps = {"rating": 4.0, "review_count": 50, "description": "Great shop",
                 "review_snippets": ["Nice place"], "source_url": "http://maps.google.com/"}
        profile = build_business_profile(
            lead, _BASE_CONFIG, run_id="r1",
            gmaps_enrichment=gmaps,
        )
        assert "enrichment" in profile
        assert "google_maps" in profile["enrichment"]
        assert profile["enrichment"]["google_maps"]["rating"] == 4.0

    def test_enrichment_section_with_overpass(self):
        """Overpass OSM data appears in the enrichment section."""
        lead = {"business_slug": "osm-shop", "business_name": "OSM Shop"}
        overpass = {
            "osm_type": "node",
            "osm_tags": {"category": "car_repair", "hours": "Mo-Fr 09:00-18:00"},
            "enrichment_source": "overpass",
        }
        profile = build_business_profile(
            lead, _BASE_CONFIG, run_id="r1",
            overpass_enrichment=overpass,
        )
        assert "enrichment" in profile
        assert "overpass" in profile["enrichment"]
        assert profile["enrichment"]["overpass"]["osm_type"] == "node"
        # OSM hours should fill verified_facts.hours
        assert profile["verified_facts"]["hours"]["value"] == "Mo-Fr 09:00-18:00"
        assert profile["verified_facts"]["hours"]["confidence"] == "enriched"

    def test_enrichment_section_with_social(self):
        """Social scraper data appears in the enrichment section."""
        lead = {"business_slug": "social-shop", "business_name": "Social Shop"}
        social = {
            "platform": "facebook",
            "username": "socialshop",
            "profile_url": "https://facebook.com/socialshop",
            "about_text": "We are a great shop!",
            "follower_count": 250,
            "post_count": 30,
            "is_verified": False,
            "enrichment_source": "social_scraper",
        }
        profile = build_business_profile(
            lead, _BASE_CONFIG, run_id="r1",
            social_enrichment=social,
        )
        assert "enrichment" in profile
        assert "social" in profile["enrichment"]
        assert profile["enrichment"]["social"]["platform"] == "facebook"
        assert profile["enrichment"]["social"]["follower_count"] == 250

    def test_enrichment_all_three_sources(self):
        """All three enrichment sources can be present simultaneously."""
        lead = {"business_slug": "all-sources", "business_name": "All Sources Shop"}
        overpass = {"osm_type": "way", "osm_tags": {"category": "restaurant"}, "enrichment_source": "overpass"}
        gmaps = {"rating": 4.2, "review_count": 100, "review_snippets": [], "source_url": ""}
        social = {"platform": "instagram", "username": "allshop", "follower_count": 500,
                  "post_count": 40, "is_verified": True, "enrichment_source": "social_scraper"}
        profile = build_business_profile(
            lead, _BASE_CONFIG, run_id="r1",
            overpass_enrichment=overpass,
            gmaps_enrichment=gmaps,
            social_enrichment=social,
        )
        assert "enrichment" in profile
        assert "overpass" in profile["enrichment"]
        assert "google_maps" in profile["enrichment"]
        assert "social" in profile["enrichment"]
        # Internal should list all sources
        assert "overpass" in profile["internal"]["enrichment_sources"]
        assert "gmaps" in profile["internal"]["enrichment_sources"]
        assert "social" in profile["internal"]["enrichment_sources"]

    def test_no_enrichment_no_enrichment_section(self):
        """Without enrichment data, no enrichment section should appear."""
        lead = {"business_slug": "plain", "business_name": "Plain"}
        profile = build_business_profile(lead, _BASE_CONFIG, run_id="r1")
        assert "enrichment" not in profile
