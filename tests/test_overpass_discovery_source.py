"""Integration tests for the 'overpass' discovery source in Phase 02.

Validates that Phase 02 routes to the Overpass fetcher when
discovery_source="overpass" in the run config, using mocked API calls
so no real network requests are made.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from packages.discovery.overpass_fetcher import (
    RawPlace as OverpassRawPlace,
)
from packages.discovery.overpass_fetcher import (
    overpass_to_raw_place_dicts,
)
from packages.phases.phase_02_basic_lead_discovery import (
    _resolve_discovery_input,
)
from packages.phases.phase_02_basic_lead_discovery import (
    run as run_phase_02,
)
from pipeline.json_io import read_json, write_json

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Create a minimal workspace with Phase 01 outputs ready."""
    run_id = "test_overpass_run"
    run_dir = tmp_path / "runs" / run_id
    config_dir = run_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    # Phase 01 input config
    input_config = {
        "niche": "auto detailing",
        "area": "Frisco TX",
        "country": "US",
        "language": "English",
        "price_offer": "$499",
        "discovery_source": "overpass",
    }
    write_json(str(config_dir / "input_config.json"), input_config)

    # Phase 01 output directory (marks Phase 01 as done)
    phase_01_dir = run_dir / "01_input"
    phase_01_dir.mkdir(parents=True, exist_ok=True)
    write_json(str(phase_01_dir / "run_config.json"), {
        "run_id": run_id,
        "niche": "auto detailing",
        "area": "Frisco TX",
    })
    write_json(str(phase_01_dir / "query_plan.json"), {
        "run_id": run_id,
        "queries": [],
    })

    return tmp_path


def _make_overpass_results() -> list[OverpassRawPlace]:
    """Create sample Overpass RawPlace results (mimics API response)."""
    return [
        OverpassRawPlace(
            name="Frisco Auto Spa",
            lat=33.1507,
            lng=-96.8236,
            address="1234 Main St, Frisco, TX 75034",
            phone="(214) 555-0100",
            website="https://friscoautospa.example.com",
            osm_type="node",
            osm_id="12345678",
            tags={
                "name": "Frisco Auto Spa",
                "amenity": "car_wash",
                "phone": "(214) 555-0100",
                "website": "https://friscoautospa.example.com",
                "addr:street": "Main St",
                "addr:housenumber": "1234",
                "addr:city": "Frisco",
                "addr:state": "TX",
                "opening_hours": "Mo-Fr 08:00-18:00",
            },
        ),
        OverpassRawPlace(
            name="Detail Kings Frisco",
            lat=33.1549,
            lng=-96.8173,
            address="567 Oak Ave, Frisco, TX 75035",
            phone="(214) 555-0200",
            website="",
            osm_type="way",
            osm_id="87654321",
            tags={
                "name": "Detail Kings Frisco",
                "shop": "car_repair",
                "phone": "(214) 555-0200",
                "addr:street": "Oak Ave",
                "addr:housenumber": "567",
                "addr:city": "Frisco",
                "addr:state": "TX",
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tests — Adapter
# ---------------------------------------------------------------------------

class TestOverpassAdapter:
    """Tests for overpass_to_raw_place_dicts adapter."""

    def test_converts_fields_correctly(self):
        results = _make_overpass_results()
        dicts = overpass_to_raw_place_dicts(results, "auto detailing", "Frisco TX")

        assert len(dicts) == 2

        d = dicts[0]
        assert d["business_name"] == "Frisco Auto Spa"
        assert d["address"] == "1234 Main St, Frisco, TX 75034"
        assert d["phone"] == "(214) 555-0100"
        assert d["website"] == "https://friscoautospa.example.com"
        assert d["source"] == "overpass"
        assert d["source_query"] == "auto detailing in Frisco TX"
        assert d["place_id"] == "osm_node_12345678"
        assert d["category"] == "Car Wash"
        assert d["hours"] == "Mo-Fr 08:00-18:00"

    def test_category_from_shop_tag(self):
        results = _make_overpass_results()
        dicts = overpass_to_raw_place_dicts(results, "auto detailing", "Frisco TX")

        # Second result has shop=car_repair
        assert dicts[1]["category"] == "Car Repair"

    def test_empty_results(self):
        dicts = overpass_to_raw_place_dicts([], "niche", "area")
        assert dicts == []

    def test_defaults_for_unavailable_fields(self):
        results = _make_overpass_results()
        dicts = overpass_to_raw_place_dicts(results, "niche", "area")

        for d in dicts:
            assert d["rating"] == 0.0
            assert d["review_count"] == 0
            assert d["business_status"] == "unknown"
            assert d["raw_payload_ref"] == ""


# ---------------------------------------------------------------------------
# Tests — Phase 02 routing
# ---------------------------------------------------------------------------

class TestPhase02OverpassRouting:
    """Tests that _resolve_discovery_input routes to overpass correctly."""

    def test_routes_to_overpass_when_configured(self, workspace: Path):
        """Phase 02 routes to overpass when discovery_source='overpass'."""
        _mock_results = overpass_to_raw_place_dicts(
            _make_overpass_results(), "auto detailing", "Frisco TX"
        )

        with (
            patch(
                "packages.phases.phase_02_basic_lead_discovery.fetch_overpass_leads",
                create=True,
            ) as _mock_fetch,
            # We need to patch the import inside the function
            patch(
                "packages.discovery.overpass_fetcher.OverpassClient.discover",
                return_value=_make_overpass_results(),
            ),
        ):
            result = _resolve_discovery_input("test_overpass_run", workspace)

        # The function should have called OverpassClient.discover internally
        # via fetch_overpass_leads and returned converted dicts
        assert result is not None
        assert len(result) == 2
        assert result[0]["business_name"] == "Frisco Auto Spa"
        assert result[0]["source"] == "overpass"

    def test_returns_none_when_niche_missing(self, workspace: Path):
        """Returns None when niche is missing from config."""
        config_path = workspace / "runs" / "test_overpass_run" / "config" / "input_config.json"
        config = read_json(str(config_path))
        config["niche"] = ""
        config["discovery_source"] = "overpass"
        write_json(str(config_path), config)

        result = _resolve_discovery_input("test_overpass_run", workspace)
        assert result is None

    def test_returns_none_when_area_missing(self, workspace: Path):
        """Returns None when area is missing from config."""
        config_path = workspace / "runs" / "test_overpass_run" / "config" / "input_config.json"
        config = read_json(str(config_path))
        config["area"] = ""
        config["discovery_source"] = "overpass"
        write_json(str(config_path), config)

        result = _resolve_discovery_input("test_overpass_run", workspace)
        assert result is None

    def test_returns_none_when_no_config_file(self, tmp_path: Path):
        """Returns None when no config file exists (no niche/area)."""
        run_dir = tmp_path / "runs" / "no_config_run"
        config_dir = run_dir / "config"
        # Don't create config file
        config_dir.mkdir(parents=True, exist_ok=True)

        result = _resolve_discovery_input("no_config_run", tmp_path)
        # Falls through to fixture which won't exist, so None
        assert result is None


# ---------------------------------------------------------------------------
# Tests — Full Phase 02 run with mocked Overpass
# ---------------------------------------------------------------------------

class TestPhase02OverpassFullRun:
    """Test full Phase 02 execution with overpass discovery source."""

    def test_full_run_with_mocked_overpass(self, workspace: Path):
        """Full Phase 02 run produces expected output files."""
        mock_overpass_results = _make_overpass_results()

        with patch(
            "packages.discovery.overpass_fetcher.OverpassClient.discover",
            return_value=mock_overpass_results,
        ):
            result = run_phase_02("test_overpass_run", str(workspace))

        assert result["status"] in ("done", "needs_review")
        assert result["records_processed"] == 2
        assert result["records_created"] == 2

        # Check output files exist
        discovery_dir = workspace / "runs" / "test_overpass_run" / "02_discovery"
        assert (discovery_dir / "leads_raw.json").exists()
        assert (discovery_dir / "leads_normalized.json").exists()
        assert (discovery_dir / "discovery_report.json").exists()
        assert (discovery_dir / "result.json").exists()

        # Validate leads_raw.json content
        leads_raw = read_json(str(discovery_dir / "leads_raw.json"))
        assert len(leads_raw) == 2
        assert leads_raw[0]["business_name"] == "Frisco Auto Spa"
        assert leads_raw[0]["source"] == "overpass"

        # Validate leads_normalized.json content
        leads_norm = read_json(str(discovery_dir / "leads_normalized.json"))
        assert len(leads_norm) == 2
        assert leads_norm[0]["business_name"] == "Frisco Auto Spa"
        assert leads_norm[0]["business_slug"] != ""
        assert leads_norm[0]["dedupe_key"] != ""

    def test_blocked_when_niche_missing(self, workspace: Path):
        """Phase 02 returns blocked when niche is missing."""
        config_path = workspace / "runs" / "test_overpass_run" / "config" / "input_config.json"
        config = read_json(str(config_path))
        config["niche"] = ""
        config["discovery_source"] = "overpass"
        write_json(str(config_path), config)

        result = run_phase_02("test_overpass_run", str(workspace))
        assert result["status"] == "blocked"

    def test_blocked_when_area_missing(self, workspace: Path):
        """Phase 02 returns blocked when area is missing."""
        config_path = workspace / "runs" / "test_overpass_run" / "config" / "input_config.json"
        config = read_json(str(config_path))
        config["area"] = ""
        config["discovery_source"] = "overpass"
        write_json(str(config_path), config)

        result = run_phase_02("test_overpass_run", str(workspace))
        assert result["status"] == "blocked"

    def test_empty_overpass_results(self, workspace: Path):
        """Phase 02 handles empty Overpass results gracefully."""
        with patch(
            "packages.discovery.overpass_fetcher.OverpassClient.discover",
            return_value=[],
        ):
            result = run_phase_02("test_overpass_run", str(workspace))

        # Empty results → 0 records processed
        assert result["records_processed"] == 0
        assert result["records_created"] == 0

    def test_deduplication_with_overpass(self, workspace: Path):
        """Overpass results are deduplicated like other sources."""
        # Create two identical results
        dupe_results = [
            OverpassRawPlace(
                name="Same Business",
                lat=33.0,
                lng=-96.0,
                address="100 Main St",
                phone="",
                website="",
                osm_type="node",
                osm_id="111",
                tags={"name": "Same Business"},
            ),
            OverpassRawPlace(
                name="Same Business",
                lat=33.0,
                lng=-96.0,
                address="100 Main St",
                phone="",
                website="",
                osm_type="node",
                osm_id="112",
                tags={"name": "Same Business"},
            ),
        ]

        with patch(
            "packages.discovery.overpass_fetcher.OverpassClient.discover",
            return_value=dupe_results,
        ):
            result = run_phase_02("test_overpass_run", str(workspace))

        assert result["records_processed"] == 2
        # One should be deduped
        assert result["records_skipped"] == 1
        assert result["records_created"] == 1
