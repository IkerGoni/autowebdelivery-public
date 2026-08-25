"""Integration tests for social-only detection in Phase 02."""

from pathlib import Path

import pytest

from packages.phases import phase_02_basic_lead_discovery as phase_02


class TestSocialOnlyIntegration:
    """Test social-only detection integrated into Phase 02."""

    def test_normalize_place_detects_facebook(self):
        """Test that normalize_place detects Facebook URLs."""
        raw = phase_02.RawPlace(
            run_id="test_run",
            record_id="rec_123",
            business_name="Test Business",
            website="https://facebook.com/testbiz",
            address="123 Main St",
        )
        
        normalized = phase_02.normalize_place(raw)
        
        assert normalized.social_only_presence is True
        assert "social_only_presence_detected" in normalized.normalization_notes

    def test_normalize_place_detects_instagram(self):
        """Test that normalize_place detects Instagram URLs."""
        raw = phase_02.RawPlace(
            run_id="test_run",
            record_id="rec_456",
            business_name="Test Shop",
            website="https://instagram.com/testshop",
            address="456 Oak Ave",
        )
        
        normalized = phase_02.normalize_place(raw)
        
        assert normalized.social_only_presence is True
        assert "social_only_presence_detected" in normalized.normalization_notes

    def test_normalize_place_owned_domain_not_social_only(self):
        """Test that owned domains are NOT marked as social-only."""
        raw = phase_02.RawPlace(
            run_id="test_run",
            record_id="rec_789",
            business_name="Real Business",
            website="https://realbusiness.com",
            address="789 Elm St",
        )
        
        normalized = phase_02.normalize_place(raw)
        
        assert normalized.social_only_presence is False
        assert "social_only_presence_detected" not in normalized.normalization_notes

    def test_normalize_place_empty_website_not_social_only(self):
        """Test that empty websites are NOT marked as social-only."""
        raw = phase_02.RawPlace(
            run_id="test_run",
            record_id="rec_000",
            business_name="No Website Business",
            website="",
            address="000 Pine Ln",
        )
        
        normalized = phase_02.normalize_place(raw)
        
        assert normalized.social_only_presence is False
        assert "website_field_empty" in normalized.normalization_notes
        assert "social_only_presence_detected" not in normalized.normalization_notes

    def test_phase_02_run_tracks_social_only_count(self, workspace):
        """Test that Phase 02 run tracks social_only_count in discovery report."""
        run_id = "test_social_count"
        
        # Setup Phase 01 artifacts
        phase_02._setup_phase_01(workspace, run_id)
        
        # Input with mix of social-only and owned domains
        input_places = [
            {
                "business_name": "Facebook Only Biz",
                "website": "https://facebook.com/biz1",
                "address": "123 Main St",
                "rating": 4.5,
                "review_count": 100,
            },
            {
                "business_name": "Instagram Only Shop",
                "website": "https://instagram.com/shop2",
                "address": "456 Oak Ave",
                "rating": 4.7,
                "review_count": 80,
            },
            {
                "business_name": "Owned Domain Co",
                "website": "https://owneddomain.com",
                "address": "789 Elm St",
                "rating": 4.8,
                "review_count": 120,
            },
            {
                "business_name": "No Website Inc",
                "website": "",
                "address": "000 Pine Ln",
                "rating": 4.6,
                "review_count": 90,
            },
        ]
        
        phase_02.run(run_id, workspace, input_places)
        
        # Check discovery report
        discovery_report_path = Path(workspace) / "runs" / run_id / "02_discovery" / "discovery_report.json"
        assert discovery_report_path.exists()
        
        from packages.pipeline.json_io import read_json
        report = read_json(str(discovery_report_path))
        
        assert report["social_only_count"] == 2  # Facebook + Instagram
        assert report["missing_website_count"] == 1  # No Website Inc
        assert report["normalized_places_count"] == 4

    def test_phase_02_social_only_in_normalized_output(self, workspace):
        """Test that social_only_presence field appears in normalized output."""
        run_id = "test_social_field"
        
        # Setup Phase 01
        phase_02._setup_phase_01(workspace, run_id)
        
        input_places = [
            {
                "business_name": "Social Only",
                "website": "https://facebook.com/page",
                "address": "123 St",
                "rating": 4.5,
                "review_count": 50,
            },
        ]
        
        phase_02.run(run_id, workspace, input_places)
        
        # Check normalized output
        leads_path = Path(workspace) / "runs" / run_id / "02_discovery" / "leads_normalized.json"
        
        from packages.pipeline.json_io import read_json
        leads = read_json(str(leads_path))
        
        assert len(leads) == 1
        assert leads[0]["social_only_presence"] is True
        assert "social_only_presence_detected" in leads[0]["normalization_notes"]


@pytest.fixture
def workspace(tmp_path):
    """Create a temporary workspace for testing."""
    return str(tmp_path)


# Helper function for Phase 01 setup
def _setup_phase_01(workspace: str, run_id: str):
    """Setup Phase 01 artifacts needed for Phase 02 to run."""
    from pathlib import Path

    from packages.pipeline.json_io import write_json
    
    config_dir = Path(workspace) / "runs" / run_id / "config"
    phase_dir = Path(workspace) / "runs" / run_id / "01_input"
    
    config_dir.mkdir(parents=True, exist_ok=True)
    phase_dir.mkdir(parents=True, exist_ok=True)
    
    # Minimal config
    write_json(
        str(config_dir / "input_config.json"),
        {
            "niche": "test",
            "area": "test",
            "discovery_source": "direct",
        },
    )
    
    # Minimal Phase 01 result
    write_json(
        str(phase_dir / "result.json"),
        {
            "status": "done",
            "phase": "phase_01_input",
        },
    )


# Monkey-patch the helper into phase_02 module for tests
phase_02._setup_phase_01 = _setup_phase_01
