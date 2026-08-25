"""Tests for Phase 02 Basic Lead Discovery per pipeline_data_contract.md."""

import tempfile
from pathlib import Path

import pytest

from packages.phases.phase_01_user_input import run as run_phase_01
from packages.phases.phase_02_basic_lead_discovery import (
    make_business_slug,
    make_dedupe_key,
    make_raw_place,
    make_record_id,
    normalize_place,
    run,
)
from pipeline.json_io import read_json


class TestMakeBusinessSlug:
    def test_standard_name(self):
        slug = make_business_slug("Bright Smile Dental Clinic", "rec_a1b2c3d4")
        assert slug == "bright-smile-dental-clinic-c3d4"

    def test_long_name_truncated(self):
        long_name = "A" * 60 + " Dental Clinic"
        slug = make_business_slug(long_name, "rec_test1234")
        assert len(slug) <= 57  # 50 + hyphen + 4 suffix
        assert slug.endswith("1234")

    def test_special_characters(self):
        slug = make_business_slug("Dr. Smith & Jones, DDS!", "rec_abcd1234")
        assert slug == "dr-smith-jones-dds-1234"

    def test_empty_name(self):
        slug = make_business_slug("", "rec_test12")
        assert slug == "business-st12"


class TestMakeDedupeKey:
    def test_same_business_same_key(self):
        place1 = {"business_name": "Test Clinic", "address": "123 Main St"}
        place2 = {"business_name": "Test Clinic", "address": "123 Main St"}
        assert make_dedupe_key(place1) == make_dedupe_key(place2)

    def test_different_business_different_key(self):
        place1 = {"business_name": "Test Clinic", "address": "123 Main St"}
        place2 = {"business_name": "Other Clinic", "address": "456 Oak St"}
        assert make_dedupe_key(place1) != make_dedupe_key(place2)


class TestMakeRecordId:
    def test_deterministic(self):
        id1 = make_record_id("fixture", 0)
        id2 = make_record_id("fixture", 0)
        assert id1 == id2

    def test_unique_per_index(self):
        id1 = make_record_id("fixture", 0)
        id2 = make_record_id("fixture", 1)
        assert id1 != id2


class TestMakeRawPlace:
    def test_from_fixture_data(self):
        raw_data = {
            "business_name": "Test Dental",
            "category": "Dentist",
            "rating": 4.5,
            "review_count": 100,
        }
        raw = make_raw_place("test_run", raw_data, 0)
        assert raw.business_name == "Test Dental"
        assert raw.category == "Dentist"
        assert raw.rating == 4.5
        assert raw.review_count == 100


class TestNormalizePlace:
    def test_creates_normalized(self):
        from pipeline.contracts import RawPlace
        raw = RawPlace(
            run_id="test_run",
            record_id="rec_test1",
            business_name="Test Clinic",
            category="Dentist",
            website="https://test.com",
        )
        norm = normalize_place(raw)
        assert norm.run_id == "test_run"
        assert norm.business_name == "Test Clinic"
        assert norm.business_slug == "test-clinic-est1"
        assert norm.website_raw == "https://test.com"

    def test_empty_website_note(self):
        from pipeline.contracts import RawPlace
        raw = RawPlace(
            run_id="test_run",
            record_id="rec_test2",
            business_name="Test Clinic",
            website="",
        )
        norm = normalize_place(raw)
        assert "website_field_empty" in norm.normalization_notes


class TestPhase02Run:
    @pytest.fixture
    def workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp

    def test_run_without_phase_01_blocked(self, workspace):
        """Phase 02 must be blocked without Phase 01 outputs."""
        result = run("test_run_no_phase01", workspace)
        assert result["status"] == "blocked"
        assert "RunConfig" in result["missing_fields"] or "QueryPlan" in result["missing_fields"]

    def test_run_with_valid_fixture(self, workspace):
        """Full flow: Phase 01 then Phase 02."""
        # Run Phase 01 first
        config = {
            "niche": "dentists",
            "area": "Chiang Mai",
            "country": "Thailand",
            "max_raw_results": 100,
            "max_preview_sites": 5,
            "price_offer": "$299 setup",
        }
        run_phase_01("test_run_p02", workspace, config)

        # Phase 02: Discovery
        # Load fixture input directly (workspace is temp dir, no fixture there)
        fixture_path = Path.cwd() / "tests" / "fixtures" / "phase_02_basic_lead_discovery" / "input" / "raw_places_with_websites.json"
        input_places = read_json(str(fixture_path))

        # Run Phase 02 with explicit input
        result = run("test_run_p02", workspace, input_places)
        assert result["status"] == "done"  # All 3 fixture records have websites
        assert result["run_id"] == "test_run_p02"

        # Check artifacts exist
        assert Path(workspace, "runs", "test_run_p02", "02_discovery", "leads_raw.json").exists()
        assert Path(workspace, "runs", "test_run_p02", "02_discovery", "leads_normalized.json").exists()
        assert Path(workspace, "runs", "test_run_p02", "02_discovery", "discovery_report.json").exists()

    def test_run_with_all_websites(self, workspace):
        """Phase 02 completes with 'done' when all records have websites."""
        # Run Phase 01 first
        config = {
            "niche": "dentists",
            "area": "Chiang Mai",
            "country": "Thailand",
            "max_raw_results": 100,
            "max_preview_sites": 5,
            "price_offer": "$299 setup",
        }
        run_phase_01("test_run_all_web", workspace, config)

        # Run Phase 02 with fixture that has websites
        input_places = [
            {
                "record_id": "rec_1",
                "business_name": "Clinic A",
                "category": "Dentist",
                "website": "https://clinica.com",
            },
            {
                "record_id": "rec_2",
                "business_name": "Clinic B",
                "category": "Dentist",
                "website": "https://clinicb.com",
            },
        ]
        result = run("test_run_all_web", workspace, input_places)
        assert result["status"] == "done"
        assert result["records_processed"] == 2
        assert result["records_created"] == 2
        assert result["missing_fields"] == []

    def test_dedupe_behavior(self, workspace):
        """Duplicate businesses are removed."""
        # Run Phase 01 first
        config = {
            "niche": "dentists",
            "area": "Chiang Mai",
            "country": "Thailand",
            "max_raw_results": 100,
            "max_preview_sites": 5,
            "price_offer": "$299 setup",
        }
        run_phase_01("test_run_dedupe", workspace, config)

        # Run Phase 02 with duplicate records
        input_places = [
            {
                "record_id": "rec_dup1",
                "business_name": "Same Clinic",
                "address": "123 Main St",
                "website": "https://sameclinic.com",
            },
            {
                "record_id": "rec_dup2",
                "business_name": "Same Clinic",
                "address": "123 Main St",
                "website": "https://sameclinic.com",
            },
        ]
        result = run("test_run_dedupe", workspace, input_places)
        assert result["records_processed"] == 2
        assert result["records_created"] == 1  # One deduped
        assert result["records_skipped"] == 1

    def test_null_rating_review_defaults(self, workspace):
        """Null rating/review_count become 0."""
        # Run Phase 01 first
        config = {
            "niche": "dentists",
            "area": "Chiang Mai",
            "country": "Thailand",
            "max_raw_results": 100,
            "max_preview_sites": 5,
            "price_offer": "$299 setup",
        }
        run_phase_01("test_run_nulls", workspace, config)

        input_places = [
            {
                "record_id": "rec_null",
                "business_name": "New Clinic",
                "category": "Dentist",
                "rating": None,
                "review_count": None,
                "website": "https://newclinic.com",
            },
        ]
        run("test_run_nulls", workspace, input_places)

        normalized = read_json(f"{workspace}/runs/test_run_nulls/02_discovery/leads_normalized.json")
        assert normalized[0]["rating"] == 0.0
        assert normalized[0]["review_count"] == 0

    def test_discovery_report_contents(self, workspace):
        """Discovery report contains expected fields."""
        # Run Phase 01 first
        config = {
            "niche": "dentists",
            "area": "Chiang Mai",
            "country": "Thailand",
            "max_raw_results": 100,
            "max_preview_sites": 5,
            "price_offer": "$299 setup",
        }
        run_phase_01("test_run_report", workspace, config)

        input_places = [
            {"record_id": "rec_1", "business_name": "A", "category": "Dentist", "website": ""},
            {"record_id": "rec_2", "business_name": "B", "category": "Dentist", "website": "https://b.com"},
        ]
        run("test_run_report", workspace, input_places)

        report = read_json(f"{workspace}/runs/test_run_report/02_discovery/discovery_report.json")
        assert report["raw_places_count"] == 2
        assert report["normalized_places_count"] == 2
        assert report["missing_website_count"] == 1