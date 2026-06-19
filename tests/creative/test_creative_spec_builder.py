"""Unit tests for VNEXT-04 — Creative Specification Builder."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from packages.creative.creative_spec_builder import (
    SCHEMA_VERSION,
    _deterministic_generated_at,
    _extract_brand_tone,
    _extract_color_direction,
    _extract_emotional_goals,
    _extract_trust_posture,
    _extract_verified_fact,
    build_creative_spec,
    write_creative_spec,
)


# ---------------------------------------------------------------------------
# Test helpers — mirrors VNEXT-01/02/03 fixture pattern
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
            "phone": {
                "value": "+1-555-123-4567",
                "source": "selected_for_preview.json",
                "confidence": "verified",
            },
            "address": {
                "value": "123 Main St, Dallas, TX",
                "source": "selected_for_preview.json",
                "confidence": "verified",
            },
            "hours": {
                "value": "Mon-Sat 9-5",
                "source": "selected_for_preview.json",
                "confidence": "verified",
            },
        },
        "inferred_strategy": {},
        "missing_data": [],
        "forbidden_public_claims": [],
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
            "score": {"value": 78.4, "source": "scorecard", "confidence": "verified"},
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
        "forbidden_public_claims": [],
        "internal": {
            "flag": "use_market_profile_contract",
            "schema_origin": "VNEXT-02",
        },
    }
    mp.update(overrides)
    return mp


def _brand_profile(**overrides):
    brp = {
        "schema_version": "1.0.0",
        "run_id": "r1",
        "business_slug": "north-dallas-mobile-detailing",
        "generated_at": "2027-03-15T00:00:00Z",
        "brand_tone": {
            "primary": {"value": "professional", "source": "inferred_from_category", "confidence": "inferred"},
            "secondary": {"value": "warm", "source": "inferred_from_category", "confidence": "inferred"},
            "voice": {"value": "authoritative_approachable", "source": "inferred_from_category", "confidence": "inferred"},
        },
        "trust_posture": {
            "value": "credential_safe",
            "source": "inferred_from_market_profile",
            "confidence": "inferred",
        },
        "emotional_goals": ["confidence", "reliability"],
        "color_direction": {
            "primary_hint": {"value": "blue", "source": "category_defaults", "confidence": "inferred"},
            "mood": {"value": "clean_professional", "source": "category_defaults", "confidence": "inferred"},
        },
        "missing_data": [],
        "forbidden_public_claims": [],
        "internal": {
            "flag": "use_brand_reconstruction_contract",
            "schema_origin": "VNEXT-03",
        },
    }
    brp.update(overrides)
    return brp


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
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        assert spec["schema_version"] == SCHEMA_VERSION
        assert spec["schema_version"] == "1.0.0"
        assert spec["run_id"] == "r1"
        assert spec["business_slug"] == "north-dallas-mobile-detailing"


class TestRequiredTopLevelKeys:
    def test_all_required_keys_present(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        for key in (
            "schema_version",
            "run_id",
            "business_slug",
            "generated_at",
            "business_identity",
            "brand_strategy",
            "sellability",
            "content_policy",
            "generation_directives",
            "evaluation_targets",
            "missing_data",
            "internal",
        ):
            assert key in spec, f"missing top-level key {key!r}"


class TestBusinessIdentity:
    def test_business_identity_has_required_keys(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        bi = spec["business_identity"]
        for key in ("business_name", "category", "phone", "address", "hours"):
            assert key in bi, f"business_identity missing {key!r}"
            entry = bi[key]
            assert "value" in entry
            assert "source" in entry
            assert "confidence" in entry

    def test_business_identity_values_from_business_profile(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        bi = spec["business_identity"]
        assert bi["business_name"]["value"] == "North Dallas Mobile Detailing"
        assert bi["category"]["value"] == "Auto Detailing Service"
        assert bi["phone"]["value"] == "+1-555-123-4567"
        assert bi["address"]["value"] == "123 Main St, Dallas, TX"
        assert bi["hours"]["value"] == "Mon-Sat 9-5"

    def test_business_identity_source_is_business_profile(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        for key in ("business_name", "category", "phone", "address", "hours"):
            assert spec["business_identity"][key]["source"] == "business_profile.json"

    def test_missing_business_identity_field_unknown_confidence(self):
        bp = _business_profile(verified_facts={"business_name": {"value": "Test", "source": "x", "confidence": "verified"}})
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        # category, phone, address, hours are missing from verified_facts
        for key in ("category", "phone", "address", "hours"):
            assert spec["business_identity"][key]["confidence"] == "unknown"
            assert spec["business_identity"][key]["value"] == ""


class TestBrandStrategy:
    def test_brand_strategy_has_required_keys(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        bs = spec["brand_strategy"]
        assert "tone" in bs
        assert "trust_posture" in bs
        assert "emotional_goals" in bs
        assert "color_direction" in bs

    def test_brand_strategy_tone_from_brand_profile(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        assert spec["brand_strategy"]["tone"]["value"] == "professional"
        assert spec["brand_strategy"]["tone"]["confidence"] == "inferred"

    def test_brand_strategy_trust_posture(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        assert spec["brand_strategy"]["trust_posture"]["value"] == "credential_safe"

    def test_brand_strategy_emotional_goals(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        assert spec["brand_strategy"]["emotional_goals"] == ["confidence", "reliability"]

    def test_brand_strategy_color_direction(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        cd = spec["brand_strategy"]["color_direction"]
        assert cd["primary_hint"] == "blue"
        assert cd["mood"] == "clean_professional"


class TestSellability:
    def test_sellability_has_required_fields(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        s = spec["sellability"]
        assert "overall_score" in s
        assert "demand_signal" in s
        assert "website_status" in s
        assert "positioning" in s

    def test_sellability_score_from_market_profile(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        assert spec["sellability"]["overall_score"] == 78.4
        assert spec["sellability"]["demand_signal"] == "strong"
        assert spec["sellability"]["website_status"] == "no_website"

    def test_sellability_positioning_from_market_profile(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        assert spec["sellability"]["positioning"] == ["position_as_missing_website_upgrade"]


class TestContentPolicy:
    def test_content_policy_structure(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        cp = spec["content_policy"]
        assert "forbidden_claims" in cp
        assert "missing_data_handling" in cp
        assert "claim_policy" in cp

    def test_content_policy_forbidden_claims(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        fc = spec["content_policy"]["forbidden_claims"]
        assert len(fc) == 9
        for cat in _REQUIRED_BLOCKLIST_CATEGORIES:
            assert cat in fc

    def test_content_policy_explicit_rules(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        cp = spec["content_policy"]
        assert cp["missing_data_handling"] == "omit_or_neutral"
        assert cp["claim_policy"] == "verified_facts_only"


class TestGenerationDirectives:
    def test_generation_directives_structure(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        gd = spec["generation_directives"]
        assert "template_family" in gd
        assert "sections" in gd
        assert "required_cta" in gd
        assert "mobile_first" in gd

    def test_generation_directives_template_family(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        assert spec["generation_directives"]["template_family"] == "industrial_reliable"

    def test_generation_directives_sections_canonical_order(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        sections = spec["generation_directives"]["sections"]
        assert sections == ["hero", "services", "about", "contact", "cta"]

    def test_generation_directives_cta(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        assert spec["generation_directives"]["required_cta"] == "contact_form_or_phone"

    def test_generation_directives_mobile_first(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        assert spec["generation_directives"]["mobile_first"] is True


class TestEvaluationTargets:
    def test_evaluation_targets_structure(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        et = spec["evaluation_targets"]
        assert "min_overall_score" in et
        assert "hard_block_on" in et

    def test_evaluation_targets_values(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        et = spec["evaluation_targets"]
        assert et["min_overall_score"] == 70
        assert "broken_links" in et["hard_block_on"]
        assert "missing_stylesheet" in et["hard_block_on"]
        assert "horizontal_overflow" in et["hard_block_on"]


class TestInternal:
    def test_internal_block(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        internal = spec["internal"]
        assert internal["flag"] == "use_creative_spec"
        assert internal["schema_origin"] == "VNEXT-04"
        assert "business_profile.json" in internal["upstream_artifacts"]
        assert "market_profile.json" in internal["upstream_artifacts"]
        assert "brand_profile.json" in internal["upstream_artifacts"]


# ---------------------------------------------------------------------------
# Gate B — Factual Safety
# ---------------------------------------------------------------------------
class TestNoInventedClaims:
    def test_no_forbidden_claims_in_public_sections(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        # Exclude content_policy (which legitimately lists them) and internal
        public_spec = {k: v for k, v in spec.items() if k not in ("content_policy", "internal")}
        public_json = json.dumps(public_spec).lower()
        for forbidden in _REQUIRED_BLOCKLIST_CATEGORIES:
            assert forbidden not in public_json, f"public section contains forbidden claim {forbidden!r}"

    def test_forbidden_blocklist_present_in_content_policy(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        for category in _REQUIRED_BLOCKLIST_CATEGORIES:
            assert category in spec["content_policy"]["forbidden_claims"]

    def test_claim_policy_is_explicit(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        assert spec["content_policy"]["claim_policy"] == "verified_facts_only"


# ---------------------------------------------------------------------------
# Gate C — Determinism
# ---------------------------------------------------------------------------
class TestDeterminism:
    def test_deterministic_for_fixed_inputs(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        a = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        b = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")

        assert a == b
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
        assert a["generated_at"] == b["generated_at"]

    def test_different_run_id_changes_generated_at(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        a = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        c = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="different_run_xyz")
        assert c["generated_at"] != a["generated_at"]

    def test_deterministic_generated_at_matches_pattern(self):
        ts = _deterministic_generated_at("r1", "north-dallas-mobile-detailing")
        assert ts.endswith("Z")
        # Verify it parses as ISO8601
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        assert parsed >= datetime(2026, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Gate D — Missing Data
# ---------------------------------------------------------------------------
class TestMissingDataExplicit:
    def test_missing_data_is_list(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        assert isinstance(spec["missing_data"], list)

    def test_missing_data_aggregated_from_upstream(self):
        bp = _business_profile(missing_data=["phone", "hours"])
        mp = _market_profile(missing_data=["rating"])
        brp = _brand_profile(missing_data=["category"])
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        assert "phone" in spec["missing_data"]
        assert "hours" in spec["missing_data"]
        assert "rating" in spec["missing_data"]
        assert "category" in spec["missing_data"]

    def test_missing_data_no_duplicates(self):
        bp = _business_profile(missing_data=["phone"])
        mp = _market_profile(missing_data=["phone"])
        brp = _brand_profile(missing_data=["phone"])
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        assert spec["missing_data"].count("phone") == 1

    def test_no_missing_data_when_all_present(self):
        bp = _business_profile(missing_data=[])
        mp = _market_profile(missing_data=[])
        brp = _brand_profile(missing_data=[])
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        assert spec["missing_data"] == []


# ---------------------------------------------------------------------------
# Gate E — Orchestrator Readiness
# ---------------------------------------------------------------------------
class TestWriteCreativeSpec:
    def test_write_creative_spec_writes_under_business_slug_dir(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            slug = bp["business_slug"]
            ret = write_creative_spec(spec, out, slug)
            assert ret.endswith("creative_spec.json")
            assert Path(ret).is_file()

            target = out / slug / "creative_spec.json"
            assert target.exists()
            on_disk = json.loads(target.read_text(encoding="utf-8"))
            assert on_disk["schema_version"] == SCHEMA_VERSION
            assert on_disk["business_slug"] == slug
            assert on_disk["run_id"] == "r1"


class TestRequiresBusinessSlug:
    def test_missing_business_slug_raises(self):
        import pytest

        with pytest.raises(ValueError):
            build_creative_spec(
                {"schema_version": "1.0.0"},
                _market_profile(),
                _brand_profile(),
                _BASE_CONFIG,
                run_id="r1",
            )


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------
class TestHelperFunctions:
    def test_extract_verified_fact(self):
        bp = _business_profile()
        assert _extract_verified_fact(bp, "business_name") == "North Dallas Mobile Detailing"
        assert _extract_verified_fact(bp, "nonexistent") is None

    def test_extract_brand_tone(self):
        brp = _brand_profile()
        assert _extract_brand_tone(brp) == "professional"

    def test_extract_trust_posture(self):
        brp = _brand_profile()
        assert _extract_trust_posture(brp) == "credential_safe"

    def test_extract_emotional_goals(self):
        brp = _brand_profile()
        assert _extract_emotional_goals(brp) == ["confidence", "reliability"]

    def test_extract_color_direction(self):
        brp = _brand_profile()
        cd = _extract_color_direction(brp)
        assert cd["primary_hint"] == "blue"
        assert cd["mood"] == "clean_professional"

    def test_extract_overall_score(self):
        mp = _market_profile()
        assert _extract_verified_fact({"verified_facts": {}}, "x") is None
        from packages.creative.creative_spec_builder import _extract_overall_score
        assert _extract_overall_score(mp) == 78.4

    def test_extract_demand_signal(self):
        from packages.creative.creative_spec_builder import _extract_demand_signal
        mp = _market_profile()
        assert _extract_demand_signal(mp) == "strong"

    def test_extract_website_status(self):
        from packages.creative.creative_spec_builder import _extract_website_status
        mp = _market_profile()
        assert _extract_website_status(mp) == "no_website"

    def test_extract_positioning(self):
        from packages.creative.creative_spec_builder import _extract_positioning
        mp = _market_profile()
        assert _extract_positioning(mp) == ["position_as_missing_website_upgrade"]


class TestEmptyUpstreamArtifacts:
    def test_empty_business_profile_uses_defaults(self):
        bp = {"business_slug": "test-biz", "missing_data": []}
        mp = _market_profile()
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        assert spec["business_identity"]["business_name"]["value"] == ""
        assert spec["business_identity"]["business_name"]["confidence"] == "unknown"

    def test_empty_market_profile_uses_defaults(self):
        bp = _business_profile()
        mp = {"sellability": {}, "strategy_hints": {}, "missing_data": []}
        brp = _brand_profile()
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        assert spec["sellability"]["overall_score"] == 0.0
        assert spec["sellability"]["demand_signal"] == "unknown"

    def test_empty_brand_profile_uses_defaults(self):
        bp = _business_profile()
        mp = _market_profile()
        brp = {"brand_tone": {}, "trust_posture": {}, "emotional_goals": [], "color_direction": {}, "missing_data": []}
        spec = build_creative_spec(bp, mp, brp, _BASE_CONFIG, run_id="r1")
        assert spec["brand_strategy"]["tone"]["value"] == "professional"
        assert spec["brand_strategy"]["trust_posture"]["value"] == "credential_safe"
        assert spec["brand_strategy"]["emotional_goals"] == []
