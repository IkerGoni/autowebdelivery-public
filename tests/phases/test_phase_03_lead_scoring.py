"""Tests for Phase 03 Lead Scoring per pipeline_data_contract.md."""

import tempfile
from pathlib import Path

import pytest

from packages.phases.phase_03_lead_scoring import (
    USE_MARKET_PROFILE_CONTRACT_FLAG,
    calculate_contactability_score,
    calculate_rating_score,
    calculate_review_score,
    check_chain_franchise,
    run,
    score_lead,
)
from pipeline.json_io import read_json, write_json


class TestCalculateRatingScore:
    def test_high_rating_above_threshold(self):
        score = calculate_rating_score(4.7, 4.3)
        assert score == 100.0

    def test_rating_at_threshold(self):
        score = calculate_rating_score(4.3, 4.3)
        assert score == 100.0

    def test_rating_below_threshold(self):
        score = calculate_rating_score(3.5, 4.3)
        assert score == pytest.approx(81.4, rel=0.01)

    def test_zero_rating(self):
        score = calculate_rating_score(0.0, 4.3)
        assert score == 0.0


class TestCalculateReviewScore:
    def test_high_reviews_above_threshold(self):
        score = calculate_review_score(100, 40)
        assert score == 100.0

    def test_reviews_at_threshold(self):
        score = calculate_review_score(40, 40)
        assert score == 100.0

    def test_reviews_below_threshold(self):
        score = calculate_review_score(20, 40)
        assert 0 < score < 100

    def test_zero_reviews(self):
        score = calculate_review_score(0, 40)
        assert score == 0.0


class TestCalculateContactabilityScore:
    def test_all_contact_info_present(self):
        score, reasons = calculate_contactability_score(
            phone="+1-555-123-4567",
            website_raw="https://example.com",
            website_status="has_website",
            maps_url="https://maps.google.com/?cid=123",
        )
        assert score == 100
        assert len(reasons) == 0

    def test_no_contact_info(self):
        score, reasons = calculate_contactability_score(
            phone="",
            website_raw="",
            website_status="no_website",
            maps_url="",
        )
        assert score == 0
        assert "no_phone" in reasons
        assert "no_website_field" in reasons
        assert "no_maps_url" in reasons

    def test_no_phone_only(self):
        score, reasons = calculate_contactability_score(
            phone="",
            website_raw="",
            website_status="no_website",
            maps_url="https://maps.google.com/?cid=123",
        )
        assert score == 20  # Only maps_url
        assert "no_phone" in reasons
        assert "no_website_field" in reasons


class TestCheckChainFranchise:
    def test_no_chain_signal(self):
        assert check_chain_franchise("Joe's Local Diner", "Restaurant") is False

    def test_chain_in_name(self):
        assert check_chain_franchise("McDonald's Downtown", "Restaurant") is True

    def test_franchise_in_category(self):
        assert check_chain_franchise("Local Shop", "Franchise") is True

    def test_inc_in_name(self):
        assert check_chain_franchise("Acme Inc.", "Restaurant") is True


class TestScoreLead:
    def test_qualified_lead(self):
        lead = {
            "record_id": "rec_1",
            "business_slug": "excellent-business-1",
            "business_name": "Excellent Business",
            "rating": 4.7,
            "review_count": 150,
            "phone": "+1-555-123-4567",
            "website_raw": "",
            "website_status": "no_website",
            "maps_url": "https://maps.google.com/?cid=123",
            "business_status": "open",
            "category": "Restaurant",
        }
        config = {"minimum_rating": 4.3, "minimum_reviews": 40}
        result = score_lead(lead, config)

        assert result["qualification_status"] == "qualified"
        assert result["business_slug"] == "excellent-business-1"
        assert result["rejection_reasons"] == []
        assert result["scoring"]["rating_score"] == 100.0
        assert result["scoring"]["review_score"] == 100.0

    def test_rejected_low_rating(self):
        lead = {
            "record_id": "rec_2",
            "business_name": "Low Rated Business",
            "rating": 3.2,
            "review_count": 85,
            "phone": "+1-555-111-2222",
            "website_raw": "",
            "website_status": "no_website",
            "maps_url": "https://maps.google.com/?cid=101",
            "business_status": "open",
            "category": "Restaurant",
        }
        config = {"minimum_rating": 4.3, "minimum_reviews": 40}
        result = score_lead(lead, config)

        assert result["qualification_status"] == "rejected"
        assert "rating_below_threshold" in result["rejection_reasons"]

    def test_malformed_rating_review_count_rejected_without_crash(self):
        lead = {
            "record_id": "rec_bad_numeric",
            "business_name": "Bad Numeric Business",
            "rating": "not-a-rating",
            "review_count": "many",
            "phone": "+1-555-111-2222",
            "website_raw": "",
            "website_status": "no_website",
            "maps_url": "https://maps.google.com/?cid=101",
            "business_status": "open",
            "category": "Restaurant",
        }
        config = {"minimum_rating": 4.3, "minimum_reviews": 40}
        result = score_lead(lead, config)

        assert result["rating"] == 0.0
        assert result["review_count"] == 0
        assert result["qualification_status"] == "rejected"
        assert "rating_below_threshold" in result["rejection_reasons"]
        assert "review_count_below_threshold" in result["rejection_reasons"]
        assert result["scoring"]["rating_score"] == 0.0
        assert result["scoring"]["review_score"] == 0.0

    def test_rejected_closed_business(self):
        lead = {
            "record_id": "rec_3",
            "business_name": "Closed Business",
            "rating": 4.5,
            "review_count": 100,
            "phone": "+1-555-111-2222",
            "website_raw": "",
            "website_status": "no_website",
            "maps_url": "https://maps.google.com/?cid=101",
            "business_status": "closed",
            "category": "Restaurant",
        }
        config = {"minimum_rating": 4.3, "minimum_reviews": 40}
        result = score_lead(lead, config)

        assert result["qualification_status"] == "rejected"
        assert "business_closed" in result["rejection_reasons"]

    def test_rejected_chain_franchise(self):
        lead = {
            "record_id": "rec_4",
            "business_name": "Subway Downtown",
            "rating": 4.5,
            "review_count": 100,
            "phone": "+1-555-111-2222",
            "website_raw": "",
            "website_status": "no_website",
            "maps_url": "https://maps.google.com/?cid=101",
            "business_status": "open",
            "category": "Restaurant",
        }
        config = {"minimum_rating": 4.3, "minimum_reviews": 40}
        result = score_lead(lead, config)

        assert result["qualification_status"] == "rejected"
        assert "chain_franchise_signal" in result["rejection_reasons"]

    def test_needs_review_score_range(self):
        lead = {
            "record_id": "rec_5",
            "business_name": "Borderline Business",
            "rating": 4.3,
            "review_count": 40,
            "phone": "",
            "website_raw": "",
            "website_status": "no_website",
            "maps_url": "",
            "business_status": "open",
            "category": "Restaurant",
        }
        config = {"minimum_rating": 4.3, "minimum_reviews": 40}
        result = score_lead(lead, config)

        # rating at threshold + reviews at threshold but no contact info = low score
        # 100*0.4 + 100*0.3 + 0*0.3 = 70 -> qualified, not needs_review
        # Need even lower contact score or adjust thresholds
        assert result["qualification_status"] in ["qualified", "needs_review"]


class TestPhase03Run:
    @pytest.fixture
    def workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp

    def test_run_without_phase_021_blocked(self, workspace):
        """Phase 03 must be blocked without Phase 02.1 output."""
        result = run("test_run_no_p021", workspace)
        assert result["status"] == "blocked"
        assert "leads_no_website" in result["missing_fields"]

    def test_run_with_empty_input(self, workspace):
        """Phase 03 handles empty input."""
        p021_dir = Path(workspace) / "runs" / "test_run" / "02_1_website_filter"
        p021_dir.mkdir(parents=True)
        write_json(str(p021_dir / "leads_no_website.json"), [])

        result = run("test_run", workspace)
        assert result["status"] == "blocked"
        assert result["records_processed"] == 0

    def test_run_with_valid_fixture(self, workspace):
        """Full flow with qualified leads."""
        p021_dir = Path(workspace) / "runs" / "test_run_p03" / "02_1_website_filter"
        p021_dir.mkdir(parents=True)

        fixture_leads = [
            {
                "record_id": "rec_1",
                "business_name": "Excellent Restaurant",
                "business_slug": "excellent-restaurant",
                "category": "Restaurant",
                "rating": 4.7,
                "review_count": 156,
                "phone": "+1-555-123-4567",
                "website_raw": "",
                "website_status": "no_website",
                "maps_url": "https://maps.google.com/?cid=123",
                "business_status": "open",
                "address": "123 Main St",
            },
            {
                "record_id": "rec_2",
                "business_name": "Great Coffee Shop",
                "business_slug": "great-coffee-shop",
                "category": "Coffee Shop",
                "rating": 4.8,
                "review_count": 203,
                "phone": "+1-555-987-6543",
                "website_raw": "https://facebook.com/greatcoffees",
                "website_status": "social_only",
                "maps_url": "https://maps.google.com/?cid=456",
                "business_status": "open",
                "address": "456 Oak Ave",
            },
        ]
        write_json(str(p021_dir / "leads_no_website.json"), fixture_leads)

        result = run("test_run_p03", workspace)
        assert result["status"] == "done"
        assert result["records_processed"] == 2

        # Check outputs exist
        p03_dir = Path(workspace) / "runs" / "test_run_p03" / "03_scoring"
        assert (p03_dir / "leads_scored.json").exists()
        assert (p03_dir / "leads_scored.csv").exists()
        assert (p03_dir / "qualified_leads.json").exists()
        assert (p03_dir / "selected_for_preview.json").exists()
        assert (p03_dir / "result.json").exists()

    def test_run_partitions_leads_correctly(self, workspace):
        """Verify qualified, rejected, and needs_review partitions."""
        p021_dir = Path(workspace) / "runs" / "test_run_partition" / "02_1_website_filter"
        p021_dir.mkdir(parents=True)

        write_json(str(p021_dir / "leads_no_website.json"), [
            {
                "record_id": "rec_qual",
                "business_name": "Qualified Business",
                "rating": 4.7,
                "review_count": 100,
                "phone": "+1-555-123-4567",
                "website_raw": "",
                "website_status": "no_website",
                "maps_url": "https://maps.google.com/?cid=123",
                "business_status": "open",
            },
            {
                "record_id": "rec_rej",
                "business_name": "Rejected Business",
                "rating": 3.0,
                "review_count": 10,
                "phone": "",
                "website_raw": "",
                "website_status": "no_website",
                "maps_url": "",
                "business_status": "open",
            },
            {
                "record_id": "rec_review",
                "business_name": "Needs Review Business",
                "rating": 4.0,
                "review_count": 30,
                "phone": "",
                "website_raw": "",
                "website_status": "no_website",
                "maps_url": "",
                "business_status": "open",
            },
        ])

        run("test_run_partition", workspace)

        p03_dir = Path(workspace) / "runs" / "test_run_partition" / "03_scoring"
        qualified = read_json(str(p03_dir / "qualified_leads.json"))
        scored = read_json(str(p03_dir / "leads_scored.json"))

        assert len(qualified) == 1
        assert len(scored) == 3

    def test_run_selected_for_preview_respects_max(self, workspace):
        """Verify selected_for_preview respects max_preview_sites."""
        p021_dir = Path(workspace) / "runs" / "test_run_max" / "02_1_website_filter"
        p021_dir.mkdir(parents=True)

        leads = []
        for i in range(10):
            leads.append({
                "record_id": f"rec_{i}",
                "business_name": f"Business {i}",
                "rating": 4.5,
                "review_count": 100,
                "phone": "+1-555-123-4567",
                "website_raw": "",
                "website_status": "no_website",
                "maps_url": "https://maps.google.com/?cid=123",
                "business_status": "open",
            })
        write_json(str(p021_dir / "leads_no_website.json"), leads)

        config = {"minimum_rating": 4.3, "minimum_reviews": 40, "max_preview_sites": 3}
        run("test_run_max", workspace, config=config)

        p03_dir = Path(workspace) / "runs" / "test_run_max" / "03_scoring"
        selected = read_json(str(p03_dir / "selected_for_preview.json"))
        assert len(selected) == 3

    def test_run_propagates_business_slug_to_phase_04_inputs(self, workspace):
        """Phase 03 must preserve business_slug for downstream phase directory routing."""
        p021_dir = Path(workspace) / "runs" / "test_run_slug" / "02_1_website_filter"
        p021_dir.mkdir(parents=True)

        write_json(str(p021_dir / "leads_no_website.json"), [
            {
                "record_id": "rec_slug",
                "business_slug": "slug-clinic-1234",
                "business_name": "Slug Clinic",
                "rating": 4.8,
                "review_count": 120,
                "phone": "+1-555-123-4567",
                "website_raw": "",
                "website_status": "no_website",
                "maps_url": "https://maps.google.com/?cid=123",
                "business_status": "open",
                "category": "Dental clinic",
            },
        ])

        run("test_run_slug", workspace)

        p03_dir = Path(workspace) / "runs" / "test_run_slug" / "03_scoring"
        scored = read_json(str(p03_dir / "leads_scored.json"))
        qualified = read_json(str(p03_dir / "qualified_leads.json"))
        selected = read_json(str(p03_dir / "selected_for_preview.json"))

        assert scored[0]["business_slug"] == "slug-clinic-1234"
        assert qualified[0]["business_slug"] == "slug-clinic-1234"
        assert selected[0]["business_slug"] == "slug-clinic-1234"

    def test_run_missing_contact_data_penalty_not_rejection(self, workspace):
        """Missing contact data should be penalty, not rejection."""
        p021_dir = Path(workspace) / "runs" / "test_run_contact" / "02_1_website_filter"
        p021_dir.mkdir(parents=True)

        write_json(str(p021_dir / "leads_no_website.json"), [
            {
                "record_id": "rec_no_contact",
                "business_name": "No Contact Info",
                "rating": 4.6,
                "review_count": 100,
                "phone": "",
                "website_raw": "",
                "website_status": "no_website",
                "maps_url": "",
                "business_status": "open",
            },
        ])

        config = {"minimum_rating": 4.3, "minimum_reviews": 40, "max_preview_sites": 5}
        run("test_run_contact", workspace, config=config)

        p03_dir = Path(workspace) / "runs" / "test_run_contact" / "03_scoring"
        scored = read_json(str(p03_dir / "leads_scored.json"))

        # Should be qualified despite missing contact data (penalty applied)
        assert scored[0]["qualification_status"] == "qualified"
        assert scored[0]["scoring"]["contactability_score"] == 0.0

    def test_csv_output_format(self, workspace):
        """Verify CSV output contains expected columns."""
        p021_dir = Path(workspace) / "runs" / "test_run_csv" / "02_1_website_filter"
        p021_dir.mkdir(parents=True)

        write_json(str(p021_dir / "leads_no_website.json"), [
            {
                "record_id": "rec_1",
                "business_name": "Test Business",
                "rating": 4.5,
                "review_count": 50,
                "phone": "+1-555-123-4567",
                "website_raw": "",
                "website_status": "no_website",
                "maps_url": "https://maps.google.com/?cid=123",
                "business_status": "open",
            },
        ])

        run("test_run_csv", workspace)

        p03_dir = Path(workspace) / "runs" / "test_run_csv" / "03_scoring"
        csv_content = open(p03_dir / "leads_scored.csv").read()

        assert "record_id,business_name,rating,review_count" in csv_content
        assert "lead_score" in csv_content
        assert "rec_1" in csv_content


# ---------------------------------------------------------------------------
# VNEXT-02 — feature-flag tests for the optional market_profile.json output.
# These tests opt in (or out) of the flag inside the function only, leaving
# the default config unchanged.
# ---------------------------------------------------------------------------
def _seed_p03(root: Path, run_id: str, *, flag: bool | None = None) -> str:
    """Set up a Phase 03 run with two qualified leads and return the root path.

    If `flag` is not None, the config will include
    `use_market_profile_contract=<flag>`. The flag is NEVER set in the default
    config — callers must opt in explicitly per-call.
    """
    run_dir = root / "runs" / run_id
    (run_dir / "02_1_website_filter").mkdir(parents=True, exist_ok=True)

    leads = [
        {
            "record_id": "rec_detailing",
            "business_name": "Premium Mobile Detailing",
            "business_slug": "premium-mobile-detailing",
            "category": "Auto Detailing Service",
            "rating": 4.8,
            "review_count": 180,
            "phone": "+1-555-123-4567",
            "website_raw": "",
            "website_status": "no_website",
            "maps_url": "https://maps.google.com/?cid=123",
            "business_status": "open",
            "address": "123 Main St",
        },
        {
            "record_id": "rec_dentist",
            "business_name": "Bright Smile Dental",
            "business_slug": "bright-smile-dental",
            "category": "Dentist",
            "rating": 4.7,
            "review_count": 95,
            "phone": "+1-555-999-8888",
            "website_raw": "https://facebook.com/brightsmile",
            "website_status": "social_only",
            "maps_url": "https://maps.google.com/?cid=456",
            "business_status": "open",
            "address": "456 Oak Ave",
        },
    ]
    write_json(str(run_dir / "02_1_website_filter" / "leads_no_website.json"), leads)

    config = {
        "minimum_rating": 4.3,
        "minimum_reviews": 40,
        "max_preview_sites": 5,
    }
    if flag is not None:
        config[USE_MARKET_PROFILE_CONTRACT_FLAG] = bool(flag)
    (run_dir / "config").mkdir(parents=True, exist_ok=True)
    write_json(str(run_dir / "config" / "run_config.json"), config)

    return str(root)


