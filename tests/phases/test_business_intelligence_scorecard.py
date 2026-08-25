"""Tests for business-intelligence sellability scorecard."""

import tempfile
from pathlib import Path

from packages.phases.business_intelligence_scorecard import score_business_intelligence
from packages.phases.phase_03_lead_scoring import run
from pipeline.json_io import read_json, write_json


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


def test_high_value_no_website_auto_detailing_outranks_restaurant_social_only():
    detailing = score_business_intelligence(_lead())
    restaurant = score_business_intelligence(
        _lead(
            business_name="Busy Burger",
            category="Restaurant",
            website_raw="https://facebook.com/busyburger",
            website_status="social_only",
        )
    )

    assert detailing["overall_score"] > restaurant["overall_score"]
    assert "high_value_service_category" in detailing["value_drivers"]
    assert "position_as_missing_website_upgrade" in detailing["prompt_hints"]


def test_enrichment_raises_score_and_prompt_hints():
    lead = _lead()
    base = score_business_intelligence(lead)
    enriched = score_business_intelligence(
        lead,
        enrichment={
            "services": ["ceramic coating", "interior detailing"],
            "photos": ["safe-context-only"],
            "business_summary": "Mobile detailing for premium vehicles.",
            "hours": {"monday": "9-5"},
        },
    )

    assert enriched["overall_score"] > base["overall_score"]
    assert "use_enriched_services_in_prompt" in enriched["prompt_hints"]
    assert "use_enriched_business_summary" in enriched["prompt_hints"]


def test_missing_enrichment_safe_risk_flags():
    score = score_business_intelligence(_lead())

    assert "missing_enrichment" in score["risk_flags"]
    assert score["confidence"] == "low"


def test_unknown_category_neutral():
    score = score_business_intelligence(_lead(category="", business_name="Mystery Local Business"))

    assert score["component_scores"]["category_value"] == 50.0
    assert "unknown_category_neutral" in score["value_drivers"]


def test_malformed_rating_and_review_count_do_not_raise_and_normalize_to_zero():
    score = score_business_intelligence(_lead(rating="not-a-rating", review_count="many"))

    assert score["component_scores"]["demand_signal"] == 50.0
    assert "strong_rating_signal" not in score["value_drivers"]
    assert "strong_review_volume_signal" not in score["value_drivers"]


def test_negative_rating_and_review_count_clamp_to_zero_demand_baseline():
    score = score_business_intelligence(_lead(rating=-4.8, review_count=-180))

    assert score["component_scores"]["demand_signal"] == 50.0
    assert "strong_rating_signal" not in score["value_drivers"]
    assert "strong_review_volume_signal" not in score["value_drivers"]


def test_phase03_output_contains_business_intelligence_and_preserves_legacy_scoring():
    with tempfile.TemporaryDirectory() as workspace:
        p021_dir = Path(workspace) / "runs" / "test_run_bi" / "02_1_website_filter"
        p021_dir.mkdir(parents=True)
        write_json(str(p021_dir / "leads_no_website.json"), [_lead()])

        result = run("test_run_bi", workspace)

        assert result["status"] == "done"
        scored = read_json(str(Path(workspace) / "runs" / "test_run_bi" / "03_scoring" / "leads_scored.json"))
        lead = scored[0]
        assert "business_intelligence" in lead
        assert "overall_score" in lead["business_intelligence"]
        assert "rating_score" in lead["scoring"]
        assert "review_score" in lead["scoring"]
        assert "contactability_score" in lead["scoring"]
        assert "lead_score" in lead["scoring"]


def test_phase03_preview_selection_uses_business_intelligence_before_legacy_score():
    with tempfile.TemporaryDirectory() as workspace:
        p021_dir = Path(workspace) / "runs" / "test_run_bi_sort" / "02_1_website_filter"
        p021_dir.mkdir(parents=True)
        write_json(
            str(p021_dir / "leads_no_website.json"),
            [
                _lead(
                    record_id="rec_restaurant",
                    business_name="Top Reviewed Restaurant",
                    business_slug="top-reviewed-restaurant",
                    category="Restaurant",
                    rating=5.0,
                    review_count=300,
                    website_raw="https://facebook.com/topreviewed",
                    website_status="social_only",
                ),
                _lead(
                    record_id="rec_detailing",
                    business_name="Sellable Mobile Detailing",
                    business_slug="sellable-mobile-detailing",
                    category="Auto Detailing Service",
                    rating=4.8,
                    review_count=180,
                    website_raw="",
                    website_status="no_website",
                ),
            ],
        )

        config = {"minimum_rating": 4.3, "minimum_reviews": 40, "max_preview_sites": 1}
        run("test_run_bi_sort", workspace, config=config)

        selected = read_json(
            str(Path(workspace) / "runs" / "test_run_bi_sort" / "03_scoring" / "selected_for_preview.json")
        )
        assert selected[0]["record_id"] == "rec_detailing"
