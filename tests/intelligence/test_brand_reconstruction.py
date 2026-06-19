"""Unit tests for VNEXT-03 — Brand Reconstruction Contract."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from packages.intelligence.brand_reconstruction import (
    SCHEMA_VERSION,
    _forbidden_public_claims,
    _infer_brand_tone,
    _infer_color_direction,
    _infer_emotional_goals,
    _infer_trust_posture,
    _missing_data,
    build_brand_profile,
    write_brand_profile,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------
def _business_profile(**overrides):
    bp = {
        "schema_version": "1.0.0",
        "run_id": "r1",
        "business_slug": "north-dallas-mobile-detailing",
        "generated_at": "2027-03-15T00:00:00Z",
        "verified_facts": {
            "business_name": {
                "value": "North Dallas Mobile Detailing",
                "source": "selected_for_preview.json",
                "confidence": "verified",
            },
            "category": {
                "value": "Auto Detailing Service",
                "source": "selected_for_preview.json",
                "confidence": "verified",
            },
        },
        "inferred_strategy": {},
        "missing_data": [],
        "forbidden_public_claims": [
            "years_in_business", "awards", "licenses", "insurance",
            "certifications", "staff_credentials", "testimonials",
            "guarantees", "superlatives",
        ],
        "internal": {
            "flag": "use_business_profile_contract",
            "schema_origin": "VNEXT-01",
        },
    }
    bp.update(overrides)
    return bp


def _market_profile(**overrides):
    mp = {
        "schema_version": "1.0.0",
        "run_id": "r1",
        "business_slug": "north-dallas-mobile-detailing",
        "generated_at": "2027-03-15T00:00:00Z",
        "sellability": {
            "score": {"value": 75.0, "source": "scorecard", "confidence": "verified"},
            "category": {
                "value": "Auto Detailing Service",
                "source": "selected_for_preview.json",
                "confidence": "verified",
            },
            "website_status": {
                "value": "no_website",
                "source": "selected_for_preview.json",
                "confidence": "verified",
            },
            "demand_signal": {
                "value": "strong",
                "source": "scorecard.component_scores",
                "confidence": "inferred",
            },
        },
        "strategy_hints": {
            "positioning": ["position_as_missing_website_upgrade"],
            "value_drivers": ["high_value_service_category"],
            "risk_flags": [],
        },
        "missing_data": [],
        "forbidden_public_claims": [
            "years_in_business", "awards", "licenses", "insurance",
            "certifications", "staff_credentials", "testimonials",
            "guarantees", "superlatives",
        ],
        "internal": {
            "flag": "use_market_profile_contract",
            "schema_origin": "VNEXT-02",
        },
    }
    mp.update(overrides)
    return mp


_BASE_CONFIG = {
    "niche": "auto-detailing",
    "area": "Dallas",
    "country": "US",
    "style_preset": "industrial_reliable",
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


# ---------------------------------------------------------------------------
# Gate A — Contract Quality
# ---------------------------------------------------------------------------
class TestSchemaVersion:
    def test_schema_version_present(self):
        bp = _business_profile()
        mp = _market_profile()
        profile = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        assert profile["schema_version"] == SCHEMA_VERSION
        assert profile["schema_version"] == "1.1.0"
        assert profile["run_id"] == "r1"
        assert profile["business_slug"] == "north-dallas-mobile-detailing"


class TestRequiredTopLevelKeys:
    def test_all_required_keys_present(self):
        bp = _business_profile()
        mp = _market_profile()
        profile = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        for key in (
            "schema_version",
            "run_id",
            "business_slug",
            "generated_at",
            "brand_tone",
            "trust_posture",
            "emotional_goals",
            "color_direction",
            "missing_data",
            "forbidden_public_claims",
            "internal",
        ):
            assert key in profile, f"missing top-level key {key!r}"


class TestBrandToneStructure:
    def test_brand_tone_has_primary_secondary_voice(self):
        bp = _business_profile()
        mp = _market_profile()
        profile = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        bt = profile["brand_tone"]
        for key in ("primary", "secondary", "voice"):
            assert key in bt, f"brand_tone missing {key!r}"
            entry = bt[key]
            assert "value" in entry
            assert "source" in entry
            assert "confidence" in entry

    def test_brand_tone_auto_detailing(self):
        bt = _infer_brand_tone("Auto Detailing Service")
        assert bt["primary"]["value"] == "professional"
        assert bt["secondary"]["value"] == "warm"
        assert bt["voice"]["value"] == "authoritative_approachable"

    def test_brand_tone_dental(self):
        bt = _infer_brand_tone("Dental Clinic")
        assert bt["primary"]["value"] == "clinical"
        assert bt["secondary"]["value"] == "warm_professional"
        assert bt["voice"]["value"] == "reassuring_authoritative"

    def test_brand_tone_legal(self):
        bt = _infer_brand_tone("Law Office")
        assert bt["primary"]["value"] == "authoritative"
        assert bt["secondary"]["value"] == "formal"
        assert bt["voice"]["value"] == "authoritative_formal"

    def test_brand_tone_home_services(self):
        bt = _infer_brand_tone("HVAC Repair")
        assert bt["primary"]["value"] == "reliable"
        assert bt["secondary"]["value"] == "friendly_professional"
        assert bt["voice"]["value"] == "friendly_reliable"

    def test_brand_tone_restaurant(self):
        bt = _infer_brand_tone("Italian Restaurant")
        assert bt["primary"]["value"] == "warm"
        assert bt["secondary"]["value"] == "casual_inviting"
        assert bt["voice"]["value"] == "casual_inviting"

    def test_brand_tone_unknown_category(self):
        bt = _infer_brand_tone("Some Unknown Category")
        assert bt["primary"]["value"] == "professional"
        assert bt["secondary"]["value"] == "neutral_approachable"
        assert bt["voice"]["value"] == "neutral_approachable"


class TestTrustPosture:
    def test_trust_posture_structure(self):
        bp = _business_profile()
        mp = _market_profile()
        profile = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        tp = profile["trust_posture"]
        assert "value" in tp
        assert "source" in tp
        assert "confidence" in tp

    def test_trust_posture_from_market_profile(self):
        bp = _business_profile()
        mp = _market_profile()
        profile = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        # Category "Auto Detailing Service" matches "detailing" keyword in
        # _TRUST_POSTURE_RULES, so source is inferred_from_category.
        assert profile["trust_posture"]["source"] == "inferred_from_category"
        assert profile["trust_posture"]["confidence"] == "inferred"
        assert profile["trust_posture"]["value"] == "credential_safe"

    def test_trust_posture_none_market_profile(self):
        tp = _infer_trust_posture(None)
        assert tp["value"] == "credential_safe"
        assert tp["confidence"] == "inferred"


class TestEmotionalGoals:
    def test_emotional_goals_is_list(self):
        bp = _business_profile()
        mp = _market_profile()
        profile = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        assert isinstance(profile["emotional_goals"], list)
        assert len(profile["emotional_goals"]) >= 1

    def test_emotional_goals_auto_detailing(self):
        eg = _infer_emotional_goals("Auto Detailing Service")
        assert "confidence" in eg
        assert "reliability" in eg

    def test_emotional_goals_dental(self):
        eg = _infer_emotional_goals("Dental Clinic")
        assert "trust" in eg
        assert "safety" in eg

    def test_emotional_goals_unknown(self):
        eg = _infer_emotional_goals("Unknown Business")
        assert "confidence" in eg
        assert "clarity" in eg


class TestColorDirection:
    def test_color_direction_structure(self):
        bp = _business_profile()
        mp = _market_profile()
        profile = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        cd = profile["color_direction"]
        for key in ("primary_hint", "mood"):
            assert key in cd
            entry = cd[key]
            assert "value" in entry
            assert "source" in entry
            assert "confidence" in entry

    def test_color_direction_auto_detailing(self):
        cd = _infer_color_direction("Auto Detailing Service")
        assert cd["primary_hint"]["value"] == "blue"
        assert cd["mood"]["value"] == "clean_professional"

    def test_color_direction_dental(self):
        cd = _infer_color_direction("Dental Clinic")
        assert cd["primary_hint"]["value"] == "white"
        assert cd["mood"]["value"] == "calming_clean"

    def test_color_direction_legal(self):
        cd = _infer_color_direction("Law Office")
        assert cd["primary_hint"]["value"] == "navy"
        assert cd["mood"]["value"] == "professional_gravity"

    def test_color_direction_home_services(self):
        cd = _infer_color_direction("HVAC Repair")
        assert cd["primary_hint"]["value"] == "orange"
        assert cd["mood"]["value"] == "warm_reliable"

    def test_color_direction_restaurant(self):
        cd = _infer_color_direction("Italian Restaurant")
        assert cd["primary_hint"]["value"] == "warm_red"
        assert cd["mood"]["value"] == "cozy_vibrant"

    def test_color_direction_unknown(self):
        cd = _infer_color_direction("Unknown Category")
        assert cd["primary_hint"]["value"] == "gray"
        assert cd["mood"]["value"] == "clean_neutral"


# ---------------------------------------------------------------------------
# Gate B — Factual Safety
# ---------------------------------------------------------------------------
class TestNoInventedClaims:
    def test_no_forbidden_claims_in_brand_tone(self):
        bp = _business_profile()
        mp = _market_profile()
        profile = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        brand_json = json.dumps(profile["brand_tone"])
        for forbidden in _REQUIRED_BLOCKLIST_CATEGORIES:
            assert forbidden not in brand_json, f"brand_tone contains forbidden claim {forbidden!r}"

    def test_no_forbidden_claims_in_entire_profile(self):
        bp = _business_profile()
        mp = _market_profile()
        profile = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        # The forbidden_public_claims list itself will contain these words,
        # so we exclude that key from the check.
        profile_copy = {k: v for k, v in profile.items() if k != "forbidden_public_claims"}
        safe_json = json.dumps(profile_copy)
        for forbidden in _REQUIRED_BLOCKLIST_CATEGORIES:
            assert forbidden not in safe_json, f"profile contains forbidden claim {forbidden!r}"

    def test_forbidden_blocklist_present_with_9_categories(self):
        bp = _business_profile()
        mp = _market_profile()
        profile = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        assert "forbidden_public_claims" in profile
        for category in _REQUIRED_BLOCKLIST_CATEGORIES:
            assert category in profile["forbidden_public_claims"]

    def test_all_values_marked_as_inferred(self):
        """All brand values should be marked with confidence=inferred, never verified."""
        bp = _business_profile()
        mp = _market_profile()
        profile = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        # brand_tone entries
        for key in ("primary", "secondary", "voice"):
            assert profile["brand_tone"][key]["confidence"] == "inferred"
        # trust_posture
        assert profile["trust_posture"]["confidence"] == "inferred"
        # color_direction entries
        for key in ("primary_hint", "mood"):
            assert profile["color_direction"][key]["confidence"] == "inferred"

    def test_missing_data_lowers_confidence(self):
        """When category is missing, missing_data should contain 'category'."""
        bp = _business_profile(verified_facts={}, inferred_strategy={})
        mp = _market_profile()
        profile = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        assert "category" in profile["missing_data"]

    def test_no_hallucinated_details(self):
        """Profile should not contain any fabricated business details."""
        bp = _business_profile()
        mp = _market_profile()
        profile = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        profile_json = json.dumps(profile)
        # These are specific fabricated details that should never appear
        for hallucination in (
            "10 years", "15 years", "since 1990", "established in",
            "award-winning", "licensed and insured", "fully insured",
            "certified technician", "our team of experts",
            "five-star", "best in", "number one",
        ):
            assert hallucination not in profile_json.lower(), (
                f"profile contains hallucinated detail: {hallucination!r}"
            )

    def test_forbidden_public_claims_helper(self):
        blocklist = _forbidden_public_claims()
        assert isinstance(blocklist, list)
        for category in _REQUIRED_BLOCKLIST_CATEGORIES:
            assert category in blocklist


# ---------------------------------------------------------------------------
# Gate C — Determinism
# ---------------------------------------------------------------------------
class TestDeterminism:
    def test_deterministic_for_fixed_inputs(self):
        bp = _business_profile()
        mp = _market_profile()
        a = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        b = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")

        assert a == b
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
        assert a["generated_at"] == b["generated_at"]

    def test_different_run_id_changes_generated_at(self):
        bp = _business_profile()
        mp = _market_profile()
        a = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        c = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="different_run_xyz")
        assert c["generated_at"] != a["generated_at"]

    def test_same_inputs_same_brand_tone(self):
        bp = _business_profile()
        mp = _market_profile()
        a = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        b = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        assert a["brand_tone"] == b["brand_tone"]
        assert a["emotional_goals"] == b["emotional_goals"]
        assert a["color_direction"] == b["color_direction"]


# ---------------------------------------------------------------------------
# Gate D — Orchestrator Readiness
# ---------------------------------------------------------------------------
class TestWriteBrandProfile:
    def test_write_brand_profile_writes_under_business_slug_dir(self):
        bp = _business_profile()
        mp = _market_profile()
        profile = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            slug = bp["business_slug"]
            ret = write_brand_profile(profile, out, slug)
            assert ret.endswith("brand_profile.json")
            assert Path(ret).is_file()

            target = out / slug / "brand_profile.json"
            assert target.exists()
            on_disk = json.loads(target.read_text(encoding="utf-8"))
            assert on_disk["schema_version"] == SCHEMA_VERSION
            assert on_disk["business_slug"] == slug
            assert on_disk["run_id"] == "r1"


class TestRequiresBusinessSlug:
    def test_missing_business_slug_raises(self):
        import pytest

        with pytest.raises(ValueError):
            build_brand_profile(
                {"schema_version": "1.0.0"},
                _market_profile(),
                _BASE_CONFIG,
                run_id="r1",
            )


class TestInternalBlock:
    def test_internal_block_has_flag_and_schema_origin(self):
        bp = _business_profile()
        mp = _market_profile()
        profile = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        assert profile["internal"]["flag"] == "use_brand_reconstruction_contract"
        assert profile["internal"]["schema_origin"] == "VNEXT-03"

    def test_forbidden_public_claims_present_in_internal(self):
        bp = _business_profile()
        mp = _market_profile()
        profile = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        assert "forbidden_public_claims" in profile
        assert isinstance(profile["forbidden_public_claims"], list)
        assert len(profile["forbidden_public_claims"]) == 9


class TestMissingDataExplicit:
    def test_missing_category_reported(self):
        bp = _business_profile(verified_facts={}, inferred_strategy={})
        mp = _market_profile()
        profile = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        assert "category" in profile["missing_data"]

    def test_no_missing_data_when_all_present(self):
        bp = _business_profile()
        mp = _market_profile()
        profile = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        assert profile["missing_data"] == []

    def test_missing_data_via_helper_no_market_profile(self):
        bp = _business_profile()
        result = _missing_data(bp, None)
        assert "market_profile" in result

    def test_missing_data_via_helper_no_strategy_hints(self):
        bp = _business_profile()
        mp = _market_profile(strategy_hints=None)
        result = _missing_data(bp, mp)
        assert "strategy_hints" in result


# ---------------------------------------------------------------------------
# VNEXT-16: Brand reconstruction reads enrichment from business_profile
# ---------------------------------------------------------------------------


class TestBrandReconstructionWithEnrichment:
    """build_brand_profile must read enrichment from business_profile."""

    def _bp_with_enrichment(self, **enrichment_kwargs):
        """Helper to build a business_profile with enrichment section."""
        bp = _business_profile()
        enrichment: dict[str, Any] = {}
        for key, val in enrichment_kwargs.items():
            if val is not None:
                enrichment[key] = val
        if enrichment:
            bp["enrichment"] = enrichment
        return bp

    def test_no_enrichment_no_enrichment_signals(self):
        """Without enrichment data, no enrichment_signals key should appear."""
        bp = _business_profile()
        mp = _market_profile()
        profile = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        assert "enrichment_signals" not in profile
        assert profile["internal"]["enrichment_consumed"] is False

    def test_gmaps_enrichment_signals_appear(self):
        """GMB enrichment data in business_profile produces enrichment_signals."""
        bp = self._bp_with_enrichment(google_maps={
            "rating": 4.5,
            "review_count": 100,
            "review_snippets": ["Excellent!", "Great work"],
            "differentiators": ["mobile service"],
            "owner_signals": ["owner involved"],
            "source_url": "",
        })
        mp = _market_profile()
        profile = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        assert "enrichment_signals" in profile
        assert "gmaps_review_signals" in profile["enrichment_signals"]
        gs = profile["enrichment_signals"]["gmaps_review_signals"]
        assert gs["has_reviews"] is True
        assert gs["avg_rating"] == 4.5
        assert gs["sentiment_hint"] == "positive"
        assert gs["has_differentiators"] is True
        assert gs["has_owner_signals"] is True

    def test_gmaps_low_rating_sentiment(self):
        """Rating below 4.0 yields neutral sentiment hint."""
        bp = self._bp_with_enrichment(google_maps={
            "rating": 3.2,
            "review_count": 10,
            "review_snippets": ["Okay"],
            "source_url": "",
        })
        mp = _market_profile()
        profile = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        gs = profile["enrichment_signals"]["gmaps_review_signals"]
        assert gs["sentiment_hint"] == "neutral"

    def test_social_enrichment_signals_appear(self):
        """Social enrichment data in business_profile produces enrichment_signals."""
        bp = self._bp_with_enrichment(social={
            "platform": "instagram",
            "username": "testbusiness",
            "profile_url": "https://instagram.com/testbusiness",
            "about_text": "We provide great services",
            "follower_count": 500,
            "post_count": 60,
            "is_verified": True,
            "business_category": "Local Business",
            "enrichment_source": "social_scraper",
        })
        mp = _market_profile()
        profile = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        assert "enrichment_signals" in profile
        assert "social_presence_signals" in profile["enrichment_signals"]
        ss = profile["enrichment_signals"]["social_presence_signals"]
        assert ss["has_social_presence"] is True
        assert ss["follower_count"] == 500
        assert ss["brand_maturity"] == "established"
        assert ss["is_verified"] is True

    def test_social_emerging_maturity(self):
        """Few followers/posts yields emerging brand maturity."""
        bp = self._bp_with_enrichment(social={
            "follower_count": 5,
            "post_count": 3,
            "enrichment_source": "social_scraper",
        })
        mp = _market_profile()
        profile = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        ss = profile["enrichment_signals"]["social_presence_signals"]
        assert ss["brand_maturity"] == "emerging"

    def test_overpass_enrichment_signals_appear(self):
        """Overpass OSM enrichment data produces enrichment_signals."""
        bp = self._bp_with_enrichment(overpass={
            "osm_type": "node",
            "osm_tags": {"category": "restaurant", "hours": "09:00-18:00"},
            "enrichment_source": "overpass",
        })
        mp = _market_profile()
        profile = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        assert "enrichment_signals" in profile
        assert "overpass_osm_signals" in profile["enrichment_signals"]
        oss = profile["enrichment_signals"]["overpass_osm_signals"]
        assert oss["has_osm_data"] is True
        assert oss["osm_category"] == "restaurant"

    def test_all_enrichment_sources(self):
        """All three enrichment sources can appear simultaneously."""
        bp = self._bp_with_enrichment(
            google_maps={"rating": 4.0, "review_count": 20, "source_url": ""},
            social={"follower_count": 100, "post_count": 30, "enrichment_source": "social_scraper"},
            overpass={"osm_type": "way", "osm_tags": {"category": "cafe"}, "enrichment_source": "overpass"},
        )
        mp = _market_profile()
        profile = build_brand_profile(bp, mp, _BASE_CONFIG, run_id="r1")
        assert "gmaps_review_signals" in profile["enrichment_signals"]
        assert "social_presence_signals" in profile["enrichment_signals"]
        assert "overpass_osm_signals" in profile["enrichment_signals"]
        assert profile["internal"]["enrichment_consumed"] is True
