"""Tests for Phase 02.1 Website Filter per pipeline_data_contract.md."""

import tempfile
from pathlib import Path

import pytest

from packages.phases.phase_02_1_website_filter import (
    classify_website,
    make_website_classification,
    run,
)
from pipeline.json_io import read_json, write_json


class TestClassifyWebsite:
    def test_empty_website(self):
        status, domain_type, reasons = classify_website("")
        assert status == "no_website"
        assert domain_type == "empty"
        assert "empty_website_field" in reasons

    def test_null_website(self):
        status, domain_type, reasons = classify_website(None)
        assert status == "no_website"

    def test_business_domain(self):
        status, domain_type, reasons = classify_website("https://example.com")
        assert status == "has_website"
        assert domain_type == "business_domain"

    def test_facebook_url(self):
        status, domain_type, reasons = classify_website("https://facebook.com/business")
        assert status == "social_only"
        assert domain_type == "social"

    def test_instagram_url(self):
        status, domain_type, reasons = classify_website("https://instagram.com/business")
        assert status == "social_only"

    def test_maps_url(self):
        status, domain_type, reasons = classify_website("https://maps.google.com/?cid=123")
        assert status == "uncertain"
        assert domain_type == "maps"
        assert "maps_url_no_website" in reasons

    def test_shortlink(self):
        status, domain_type, reasons = classify_website("https://bit.ly/abc123")
        assert status == "uncertain"
        assert "shortlink_url" in reasons

    def test_bio_link(self):
        status, domain_type, reasons = classify_website("https://linktr.ee/business")
        assert status == "uncertain"
        assert "bio_link_url" in reasons

    def test_url_without_scheme(self):
        status, domain_type, reasons = classify_website("example.com")
        assert status == "has_website"
        assert domain_type == "business_domain"

    def test_line_url(self):
        status, domain_type, reasons = classify_website("https://line.me/R/ti/p/@business")
        assert status == "social_only"


class TestMakeWebsiteClassification:
    def test_creates_classification(self):
        wc = make_website_classification(
            run_id="test_run",
            record_id="rec_123",
            business_slug="test-business",
            website_raw="https://example.com",
        )
        assert wc.run_id == "test_run"
        assert wc.record_id == "rec_123"
        assert wc.business_slug == "test-business"
        assert wc.website_status == "has_website"
        assert wc.decision == "skip"

    def test_no_website_keeps(self):
        wc = make_website_classification(
            run_id="test_run",
            record_id="rec_123",
            business_slug="test-business",
            website_raw="",
        )
        assert wc.website_status == "no_website"
        assert wc.decision == "keep"

    def test_social_only_keeps(self):
        wc = make_website_classification(
            run_id="test_run",
            record_id="rec_123",
            business_slug="test-business",
            website_raw="https://facebook.com/page",
        )
        assert wc.website_status == "social_only"
        assert wc.decision == "keep"

    def test_uncertain_manual_review(self):
        wc = make_website_classification(
            run_id="test_run",
            record_id="rec_123",
            business_slug="test-business",
            website_raw="https://maps.google.com/?cid=123",
        )
        assert wc.website_status == "uncertain"
        assert wc.decision == "manual_review"

    def test_http_fields_present(self):
        wc = make_website_classification(
            run_id="test_run",
            record_id="rec_123",
            business_slug="test-business",
            website_raw="https://example.com",
        )
        assert not wc.http_checked
        assert wc.http_status is None
        assert wc.final_url is None
        assert wc.redirect_chain == []
        assert not wc.checked_redirect
        assert wc.website_resolution_status == "not_checked"


class TestPhase021Run:
    @pytest.fixture
    def workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp

    def test_run_without_phase_02_blocked(self, workspace):
        """Phase 02.1 must be blocked without Phase 02 outputs."""
        result = run("test_run_no_p02", workspace)
        assert result["status"] == "blocked"
        assert "leads_normalized" in result["missing_fields"]

    def test_run_with_empty_input(self, workspace):
        """Phase 02.1 handles empty input."""
        # Create Phase 02 directory
        p02_dir = Path(workspace) / "runs" / "test_run" / "02_discovery"
        p02_dir.mkdir(parents=True)
        write_json(str(p02_dir / "leads_normalized.json"), [])

        result = run("test_run", workspace)
        assert result["status"] == "blocked"
        assert result["records_processed"] == 0

    def test_run_with_valid_fixture(self, workspace):
        """Full flow: Phase 02 then Phase 02.1."""
        # Create Phase 02 directory with fixture data
        p02_dir = Path(workspace) / "runs" / "test_run_p021" / "02_discovery"
        p02_dir.mkdir(parents=True)

        # Write leads_normalized.json
        fixture_leads = [
            {
                "record_id": "rec_1",
                "business_slug": "test-business-1",
                "business_name": "Business A",
                "website_raw": "",
            },
            {
                "record_id": "rec_2",
                "business_slug": "test-business-2",
                "business_name": "Business B",
                "website_raw": "https://example.com",
            },
            {
                "record_id": "rec_3",
                "business_slug": "test-business-3",
                "business_name": "Business C",
                "website_raw": "https://facebook.com/business",
            },
        ]
        write_json(str(p02_dir / "leads_normalized.json"), fixture_leads)

        result = run("test_run_p021", workspace)
        assert result["status"] == "done"
        assert result["records_processed"] == 3

        # Check outputs exist
        p021_dir = Path(workspace) / "runs" / "test_run_p021" / "02_1_website_filter"
        assert (p021_dir / "leads_no_website.json").exists()
        assert (p021_dir / "skipped_has_website.json").exists()
        assert (p021_dir / "manual_review_website.json").exists()
        assert (p021_dir / "website_filter_report.json").exists()
        assert (p021_dir / "result.json").exists()

    def test_run_keeps_no_website_and_social(self, workspace):
        """no_website and social_only leads are kept."""
        p02_dir = Path(workspace) / "runs" / "test_run_keep" / "02_discovery"
        p02_dir.mkdir(parents=True)

        write_json(str(p02_dir / "leads_normalized.json"), [
            {"record_id": "rec_1", "business_slug": "business-1", "business_name": "A", "website_raw": ""},
            {"record_id": "rec_2", "business_slug": "business-2", "business_name": "B", "website_raw": "https://fb.com/bus"},
        ])

        run("test_run_keep", workspace)

        p021_dir = Path(workspace) / "runs" / "test_run_keep" / "02_1_website_filter"
        no_website = read_json(str(p021_dir / "leads_no_website.json"))
        assert len(no_website) == 2

        skipped = read_json(str(p021_dir / "skipped_has_website.json"))
        assert len(skipped) == 0

    def test_run_skips_has_website(self, workspace):
        """has_website leads are skipped."""
        p02_dir = Path(workspace) / "runs" / "test_run_skip" / "02_discovery"
        p02_dir.mkdir(parents=True)

        write_json(str(p02_dir / "leads_normalized.json"), [
            {"record_id": "rec_1", "business_slug": "business-1", "business_name": "A", "website_raw": "https://example.com"},
        ])

        run("test_run_skip", workspace)

        p021_dir = Path(workspace) / "runs" / "test_run_skip" / "02_1_website_filter"
        skipped = read_json(str(p021_dir / "skipped_has_website.json"))
        assert len(skipped) == 1
        assert skipped[0]["record_id"] == "rec_1"

    def test_run_routes_uncertain_to_manual_review(self, workspace):
        """uncertain leads route to manual review."""
        p02_dir = Path(workspace) / "runs" / "test_run_manual" / "02_discovery"
        p02_dir.mkdir(parents=True)

        write_json(str(p02_dir / "leads_normalized.json"), [
            {"record_id": "rec_1", "business_slug": "business-1", "business_name": "A", "website_raw": "https://maps.google.com/?cid=123"},
            {"record_id": "rec_2", "business_slug": "business-2", "business_name": "B", "website_raw": "https://bit.ly/abc"},
        ])

        run("test_run_manual", workspace)

        p021_dir = Path(workspace) / "runs" / "test_run_manual" / "02_1_website_filter"
        no_website = read_json(str(p021_dir / "leads_no_website.json"))
        assert len(no_website) == 0

        skipped = read_json(str(p021_dir / "skipped_has_website.json"))
        assert len(skipped) == 0

        manual = read_json(str(p021_dir / "manual_review_website.json"))
        assert len(manual) == 2

    def test_website_filter_report_contents(self, workspace):
        """Website filter report contains expected fields."""
        p02_dir = Path(workspace) / "runs" / "test_run_report" / "02_discovery"
        p02_dir.mkdir(parents=True)

        write_json(str(p02_dir / "leads_normalized.json"), [
            {"record_id": "rec_1", "business_slug": "business-1", "business_name": "A", "website_raw": ""},
            {"record_id": "rec_2", "business_slug": "business-2", "business_name": "B", "website_raw": "https://example.com"},
        ])

        run("test_run_report", workspace)

        p021_dir = Path(workspace) / "runs" / "test_run_report" / "02_1_website_filter"
        report = read_json(str(p021_dir / "website_filter_report.json"))

        assert report["run_id"] == "test_run_report"
        assert report["records_processed"] == 2
        assert "classifications" in report
        assert len(report["classifications"]) == 2