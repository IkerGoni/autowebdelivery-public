"""Unit tests for VNEXT-02 — Market Profile Contract."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from packages.intelligence.market_profile import (
    SCHEMA_VERSION,
    _classify_demand_signal,
    _forbidden_public_claims,
    _missing_data,
    _split_strategy_hints,
    build_market_profile,
    write_market_profile,
)
from packages.phases.business_intelligence_scorecard import score_business_intelligence


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------
def _lead(**overrides):
    lead = {
        "record_id": "rec_1",
        "business_name": "North Dallas Mobile Detailing",
        "business_slug": "north-dallas-mobile-detailing",
        "category": "Auto Detailing Service",
        "rating": 4.8,
        "review_count": 180,
        "phone": "+1-555-123-4567",
        "website_raw": "",
        "website_status": "no_website",
        "maps_url": "https://maps.google.com/?cid=123",
        "business_status": "open",
        "address": "123 Main St",
    }
    lead.update(overrides)
    return lead


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


def _bi_score(lead, enrichment=None):
    return score_business_intelligence(lead, enrichment=enrichment)


# ---------------------------------------------------------------------------
# Gate A — Contract Quality
# ---------------------------------------------------------------------------
class TestSchemaVersion:
    def test_schema_version_present(self):
        lead = _lead()
        bi = _bi_score(lead)
        profile = build_market_profile(lead, _BASE_CONFIG, run_id="r1", bi_score=bi)
        assert profile["schema_version"] == SCHEMA_VERSION
        assert profile["run_id"] == "r1"
        assert profile["business_slug"] == "north-dallas-mobile-detailing"


class TestRequiredTopLevelKeys:
    def test_all_required_keys_present(self):
        lead = _lead()
        bi = _bi_score(lead)
        profile = build_market_profile(lead, _BASE_CONFIG, run_id="r1", bi_score=bi)
        for key in (
            "schema_version",
            "run_id",
            "business_slug",
            "generated_at",
            "sellability",
            "strategy_hints",
            "missing_data",
            "forbidden_public_claims",
            "internal",
        ):
            assert key in profile, f"missing top-level key {key!r}"


class TestSellabilityScoreFromScorecard:
    def test_sellability_score_matches_bi_overall(self):
        lead = _lead()
        bi = _bi_score(lead)
        profile = build_market_profile(lead, _BASE_CONFIG, run_id="r1", bi_score=bi)
        assert profile["sellability"]["score"]["value"] == bi["overall_score"]
        assert profile["sellability"]["score"]["source"] == "scorecard"
        assert profile["sellability"]["score"]["confidence"] == "verified"

    def test_sellability_category_from_lead(self):
        lead = _lead()
        bi = _bi_score(lead)
        profile = build_market_profile(lead, _BASE_CONFIG, run_id="r1", bi_score=bi)
        assert profile["sellability"]["category"]["value"] == "Auto Detailing Service"
        assert profile["sellability"]["category"]["source"] == "selected_for_preview.json"
        assert profile["sellability"]["category"]["confidence"] == "verified"

    def test_sellability_website_status_from_lead(self):
        lead = _lead()
        bi = _bi_score(lead)
        profile = build_market_profile(lead, _BASE_CONFIG, run_id="r1", bi_score=bi)
        assert profile["sellability"]["website_status"]["value"] == "no_website"
        assert profile["sellability"]["website_status"]["confidence"] == "verified"

    def test_sellability_demand_signal_classified(self):
        lead = _lead()
        bi = _bi_score(lead)
        profile = build_market_profile(lead, _BASE_CONFIG, run_id="r1", bi_score=bi)
        ds = profile["sellability"]["demand_signal"]
        assert ds["value"] in ("strong", "moderate", "weak")
        assert ds["source"] == "scorecard.component_scores"
        assert ds["confidence"] == "inferred"

    def test_sellability_demand_signal_strong_for_high_score(self):
        lead = _lead(rating=4.9, review_count=200)
        bi = _bi_score(lead)
        profile = build_market_profile(lead, _BASE_CONFIG, run_id="r1", bi_score=bi)
        # High rating + high reviews should give strong demand signal
        assert profile["sellability"]["demand_signal"]["value"] == "strong"


class TestSellabilityDemandSignalClassification:
    def test_strong_threshold(self):
        assert _classify_demand_signal(70.0) == "strong"
        assert _classify_demand_signal(95.0) == "strong"

    def test_moderate_threshold(self):
        assert _classify_demand_signal(50.0) == "moderate"
        assert _classify_demand_signal(69.9) == "moderate"

    def test_weak(self):
        assert _classify_demand_signal(49.9) == "weak"
        assert _classify_demand_signal(0.0) == "weak"


class TestStrategyHintsSeparated:
    def test_strategy_hints_has_three_keys(self):
        lead = _lead()
        bi = _bi_score(lead)
        profile = build_market_profile(lead, _BASE_CONFIG, run_id="r1", bi_score=bi)
        assert set(profile["strategy_hints"].keys()) == {
            "positioning", "value_drivers", "risk_flags",
        }

    def test_positioning_separated_from_value_drivers(self):
        lead = _lead()
        bi = _bi_score(lead)
        profile = build_market_profile(lead, _BASE_CONFIG, run_id="r1", bi_score=bi)
        # For no_website, score_website_need returns position_as_missing_website_upgrade
        pos = profile["strategy_hints"]["positioning"]
        drivers = profile["strategy_hints"]["value_drivers"]
        for p in pos:
            assert p.startswith("position_as_")
        for d in drivers:
            assert not d.startswith("position_as_")

    def test_risk_flags_passed_through(self):
        lead = _lead()
        bi = _bi_score(lead)
        profile = build_market_profile(lead, _BASE_CONFIG, run_id="r1", bi_score=bi)
        assert profile["strategy_hints"]["risk_flags"] == bi["risk_flags"]


class TestMissingDataExplicit:
    def test_missing_phone_reported(self):
        lead = _lead(phone="")
        bi = _bi_score(lead)
        profile = build_market_profile(lead, _BASE_CONFIG, run_id="r1", bi_score=bi)
        assert "phone" in profile["missing_data"]

    def test_all_present_means_empty_missing_data(self):
        lead = _lead()
        bi = _bi_score(lead)
        profile = build_market_profile(lead, _BASE_CONFIG, run_id="r1", bi_score=bi)
        assert profile["missing_data"] == []

    def test_missing_data_via_helper(self):
        lead = _lead(rating="", review_count=None)
        assert "rating" in _missing_data(lead)
        assert "review_count" in _missing_data(lead)


# ---------------------------------------------------------------------------
# Gate B — Factual Safety
# ---------------------------------------------------------------------------
class TestNoInventedClaims:
    def test_no_invented_competitive_claims_in_sellability(self):
        lead = _lead()
        bi = _bi_score(lead)
        profile = build_market_profile(lead, _BASE_CONFIG, run_id="r1", bi_score=bi)
        sellability_json = json.dumps(profile["sellability"])
        for forbidden in (
            "years_in_business", "awards", "licenses", "insurance",
            "certifications", "staff_credentials", "testimonials",
            "guarantees", "superlatives",
        ):
            assert forbidden not in sellability_json

    def test_forbidden_blocklist_present_with_9_categories(self):
        lead = _lead()
        bi = _bi_score(lead)
        profile = build_market_profile(lead, _BASE_CONFIG, run_id="r1", bi_score=bi)
        assert "forbidden_public_claims" in profile
        for category in _REQUIRED_BLOCKLIST_CATEGORIES:
            assert category in profile["forbidden_public_claims"]

    def test_strategy_hints_excluded_from_sellability(self):
        lead = _lead()
        bi = _bi_score(lead)
        profile = build_market_profile(lead, _BASE_CONFIG, run_id="r1", bi_score=bi)
        # sellability should NOT contain positioning, value_drivers, or risk_flags keys
        sellability_keys = set(profile["sellability"].keys())
        assert "positioning" not in sellability_keys
        assert "value_drivers" not in sellability_keys
        assert "risk_flags" not in sellability_keys

    def test_forbidden_public_claims_helper(self):
        blocklist = _forbidden_public_claims()
        assert isinstance(blocklist, list)
        for category in _REQUIRED_BLOCKLIST_CATEGORIES:
            assert category in blocklist


# ---------------------------------------------------------------------------
# Gate C — Backward Compat
# ---------------------------------------------------------------------------
class TestPromptHintsAlias:
    def test_prompt_hints_still_works(self):
        lead = _lead()
        score = _bi_score(lead)
        # prompt_hints is still an alias for value_drivers
        assert score["prompt_hints"] == score["value_drivers"]
        assert score["prompt_hints"] is not score["value_drivers"]  # must be a copy

    def test_strategy_hints_always_present_in_scorecard(self):
        lead = _lead()
        score = _bi_score(lead)
        assert "strategy_hints" in score
        assert "positioning" in score["strategy_hints"]
        assert "value_drivers" in score["strategy_hints"]
        assert "risk_flags" in score["strategy_hints"]

    def test_none_bi_score_safe(self):
        lead = _lead()
        profile = build_market_profile(lead, _BASE_CONFIG, run_id="r1", bi_score=None)
        assert profile["sellability"]["score"]["value"] == 0.0
        assert profile["strategy_hints"]["positioning"] == []
        assert profile["strategy_hints"]["value_drivers"] == []
        assert profile["strategy_hints"]["risk_flags"] == []


# ---------------------------------------------------------------------------
# Gate D — Orchestrator Readiness
# ---------------------------------------------------------------------------
class TestWriteMarketProfile:
    def test_write_market_profile_writes_under_business_slug_dir(self):
        lead = _lead()
        bi = _bi_score(lead)
        profile = build_market_profile(lead, _BASE_CONFIG, run_id="r1", bi_score=bi)

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            ret = write_market_profile(profile, out, lead["business_slug"])
            assert ret.endswith("market_profile.json")
            assert Path(ret).is_file()

            target = out / lead["business_slug"] / "market_profile.json"
            assert target.exists()
            on_disk = json.loads(target.read_text(encoding="utf-8"))
            assert on_disk["schema_version"] == SCHEMA_VERSION
            assert on_disk["business_slug"] == lead["business_slug"]
            assert on_disk["run_id"] == "r1"


class TestDeterminism:
    def test_deterministic_for_fixed_inputs(self):
        lead = _lead()
        bi = _bi_score(lead)
        a = build_market_profile(lead, _BASE_CONFIG, run_id="r1", bi_score=bi)
        b = build_market_profile(lead, _BASE_CONFIG, run_id="r1", bi_score=bi)

        assert a == b
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
        assert a["generated_at"] == b["generated_at"]

    def test_different_run_id_changes_generated_at(self):
        lead = _lead()
        bi = _bi_score(lead)
        a = build_market_profile(lead, _BASE_CONFIG, run_id="r1", bi_score=bi)
        c = build_market_profile(lead, _BASE_CONFIG, run_id="different_run_xyz", bi_score=bi)
        assert c["generated_at"] != a["generated_at"]


class TestInternalBlock:
    def test_internal_block_has_flag_and_schema_origin(self):
        lead = _lead()
        bi = _bi_score(lead)
        profile = build_market_profile(lead, _BASE_CONFIG, run_id="r1", bi_score=bi)
        assert profile["internal"]["flag"] == "use_market_profile_contract"
        assert profile["internal"]["schema_origin"] == "VNEXT-02"
        assert profile["internal"]["migration_phase"] == "prompt_hints_alias_active"


class TestRequiresBusinessSlug:
    def test_missing_business_slug_raises(self):
        import pytest
        with pytest.raises(ValueError):
            build_market_profile(
                {"business_name": "x"}, _BASE_CONFIG, run_id="r1",
            )


class TestSplitStrategyHints:
    def test_split_separates_positioning(self):
        result = _split_strategy_hints(
            ["position_as_missing_website_upgrade", "high_value_service_category"],
            ["missing_enrichment"],
        )
        assert result["positioning"] == ["position_as_missing_website_upgrade"]
        assert result["value_drivers"] == ["high_value_service_category"]
        assert result["risk_flags"] == ["missing_enrichment"]

    def test_split_empty_inputs(self):
        result = _split_strategy_hints([], [])
        assert result == {"positioning": [], "value_drivers": [], "risk_flags": []}
