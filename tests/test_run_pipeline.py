import subprocess
from pathlib import Path

from packages.pipeline.run_pipeline import run_full_pipeline


class MockCompletedProcess:
    def __init__(self, returncode, stdout, stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

def test_full_pipeline_dry_run_template(tmp_path, monkeypatch):
    # Setup workspace inside tmp_path
    workspace = tmp_path
    
    # Mock subprocess for Vercel
    def mock_run(*args, **kwargs):
        return MockCompletedProcess(0, "mock-site.vercel.app")
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    # Mock Phase 02 run method to return a valid ResultEnvelope with mock leads
    from packages.phases import phase_02_basic_lead_discovery
    from packages.pipeline import run_pipeline
    
    def mock_phase_02_run(run_id, workspace, input_places=None):
        from packages.pipeline.json_io import write_json
        from packages.pipeline.result_envelope import ResultEnvelope
        
        p2_dir = Path(workspace) / "runs" / run_id / "02_discovery"
        p2_dir.mkdir(parents=True, exist_ok=True)
        
        leads = [{
            "run_id": run_id,
            "record_id": "lead_001",
            "business_name": "Test Detailing",
            "business_slug": "test-detailing",
            "category": "auto detailing",
            "rating": 4.8,
            "review_count": 150,
            "address": "123 Main St",
            "phone": "214-556-9912",
            "website": "", # No website so it keeps
            "website_raw": "",
            "website_status": "no_website",
            "maps_url": "https://maps.google.com/?cid=123",
        }]
        write_json(str(p2_dir / "leads_raw.json"), leads)
        write_json(str(p2_dir / "leads_normalized.json"), leads)
        
        # Write discovery_report.json
        discovery_report = {
            "run_id": run_id,
            "phase": "02_discovery",
            "raw_places_count": 1,
            "normalized_places_count": 1,
            "deduped_count": 0,
            "missing_website_count": 1,
            "status": "complete",
        }
        write_json(str(p2_dir / "discovery_report.json"), discovery_report)
        
        res = ResultEnvelope.done(
            phase="phase_02_basic_lead_discovery",
            run_id=run_id,
            inputs_used=["runs/{run_id}/01_input/query_plan.json"],
            outputs_created=["02_discovery/leads_raw.json", "02_discovery/leads_normalized.json"],
            records_processed=1,
            records_created=1,
            decisions=["Mocked 1 lead discovered"]
        ).to_dict()
        write_json(str(p2_dir / "result.json"), res)
        return res
        
    monkeypatch.setattr(phase_02_basic_lead_discovery, "run", mock_phase_02_run)
    monkeypatch.setattr(run_pipeline, "run_phase_02", mock_phase_02_run)
    
    # Run the full pipeline in dry_run mode using template mode (no Stitch client required)
    summary = run_full_pipeline(
        niche="auto detailing",
        area="Frisco TX",
        workspace=str(workspace),
        generation_mode="template",
        deploy_provider="local_only",
        max_preview_sites=1,
        dry_run=True,
    )
    
    assert summary["leads_discovered"] == 15  # default return value in our orchestrator summary helper
    assert summary["leads_selected"] == 1
    assert summary["sites_generated"] == 1
    # Template-generated sites pass non-strict Phase 06 as needs_edit (acceptable
    # for preview/client review). The orchestrator counts needs_edit as passable
    # when generation_mode is template.
    assert summary["sites_approved"] == 1
    assert len(summary["errors"]) == 0
    # Pipeline stops at Phase 06 in dry_run mode (skips deploy/outreach)
    assert "06" in summary["phases_completed"]
    assert "07" not in summary["phases_completed"]


def test_vnext_13_overpass_enrichment_flag(tmp_path, monkeypatch):
    """Test that use_overpass_enrichment flag triggers OSM enrichment."""
    workspace = tmp_path
    
    def mock_run(*args, **kwargs):
        return MockCompletedProcess(0, "mock-site.vercel.app")
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    from packages.discovery import overpass_fetcher
    from packages.phases import phase_02_basic_lead_discovery
    from packages.pipeline import run_pipeline
    
    def mock_phase_02_run(run_id, workspace, input_places=None):
        from packages.pipeline.json_io import write_json
        from packages.pipeline.result_envelope import ResultEnvelope
        
        p2_dir = Path(workspace) / "runs" / run_id / "02_discovery"
        p2_dir.mkdir(parents=True, exist_ok=True)
        
        leads = [{
            "run_id": run_id,
            "record_id": "rec_abc12345",
            "business_name": "Frisco Auto Spa",
            "business_slug": "frisco-auto-spa",
            "category": "auto detailing",
            "rating": 4.8,
            "review_count": 150,
            "address": "1234 Main St, Frisco, TX",
            "phone": "(214) 555-0100",
            "website": "",
            "website_raw": "",
            "website_status": "no_website",
            "maps_url": "https://maps.google.com/?cid=123",
        }]
        write_json(str(p2_dir / "leads_raw.json"), leads)
        write_json(str(p2_dir / "leads_normalized.json"), leads)
        
        discovery_report = {
            "run_id": run_id,
            "phase": "02_discovery",
            "raw_places_count": 1,
            "normalized_places_count": 1,
            "deduped_count": 0,
            "missing_website_count": 1,
            "status": "complete",
        }
        write_json(str(p2_dir / "discovery_report.json"), discovery_report)
        
        res = ResultEnvelope.done(
            phase="phase_02_basic_lead_discovery",
            run_id=run_id,
            inputs_used=["runs/{run_id}/01_input/query_plan.json"],
            outputs_created=["02_discovery/leads_raw.json", "02_discovery/leads_normalized.json"],
            records_processed=1,
            records_created=1,
            decisions=["Mocked 1 lead discovered"]
        ).to_dict()
        write_json(str(p2_dir / "result.json"), res)
        return res
    
    monkeypatch.setattr(phase_02_basic_lead_discovery, "run", mock_phase_02_run)
    monkeypatch.setattr(run_pipeline, "run_phase_02", mock_phase_02_run)
    
    # Mock OverpassClient.discover to return test data (instance method)
    mock_result = overpass_fetcher.RawPlace(
        name="Frisco Auto Spa",
        lat=33.1507,
        lng=-96.8236,
        address="1234 Main St, Frisco, TX 75034",
        phone="(214) 555-0100",
        website="",
        osm_type="node",
        osm_id="12345678",
        tags={
            "name": "Frisco Auto Spa",
            "amenity": "car_wash",
            "opening_hours": "Mo-Fr 08:00-18:00",
        },
    )
    
    def mock_discover(self, niche, area, max_results=50):
        return [mock_result]
    
    monkeypatch.setattr(overpass_fetcher.OverpassClient, "discover", mock_discover)
    
    run_full_pipeline(
        niche="auto detailing",
        area="Frisco TX",
        workspace=str(workspace),
        generation_mode="template",
        deploy_provider="local_only",
        max_preview_sites=1,
        dry_run=True,
        vnext_flags={"use_overpass_enrichment": True},
    )
    
    # Find the run ID from the output
    run_dirs = [d for d in Path(workspace).glob("runs/run_*") if d.is_dir()]
    if run_dirs:
        run_id = run_dirs[0].name
        enrichment_file = Path(workspace) / "runs" / run_id / "04_5_enrichment" / "frisco-auto-spa" / "overpass_enrichment.json"
        assert enrichment_file.exists(), f"Overpass enrichment file should exist at {enrichment_file}"


def test_vnext_13_no_enrichment_without_flag(tmp_path, monkeypatch):
    """Test that Overpass enrichment does NOT run when flag is False."""
    workspace = tmp_path
    
    def mock_run(*args, **kwargs):
        return MockCompletedProcess(0, "mock-site.vercel.app")
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    from packages.discovery import overpass_fetcher
    from packages.phases import phase_02_basic_lead_discovery
    from packages.pipeline import run_pipeline
    
    def mock_phase_02_run(run_id, workspace, input_places=None):
        from packages.pipeline.json_io import write_json
        from packages.pipeline.result_envelope import ResultEnvelope
        
        p2_dir = Path(workspace) / "runs" / run_id / "02_discovery"
        p2_dir.mkdir(parents=True, exist_ok=True)
        
        leads = [{
            "run_id": run_id,
            "record_id": "rec_test1234",
            "business_name": "Test Business",
            "business_slug": "test-business",
            "category": "auto detailing",
            "rating": 4.5,
            "review_count": 100,
            "address": "100 Test St",
            "phone": "555-1234",
            "website": "",
            "website_raw": "",
            "website_status": "no_website",
        }]
        write_json(str(p2_dir / "leads_raw.json"), leads)
        write_json(str(p2_dir / "leads_normalized.json"), leads)
        
        res = ResultEnvelope.done(
            phase="phase_02_basic_lead_discovery",
            run_id=run_id,
            inputs_used=["runs/{run_id}/01_input/query_plan.json"],
            outputs_created=["02_discovery/leads_raw.json"],
            records_processed=1,
            records_created=1,
        ).to_dict()
        write_json(str(p2_dir / "result.json"), res)
        return res
    
    monkeypatch.setattr(phase_02_basic_lead_discovery, "run", mock_phase_02_run)
    monkeypatch.setattr(run_pipeline, "run_phase_02", mock_phase_02_run)
    
    # Track if discover was called
    discover_called = []
    
    def mock_discover(self, niche, area, max_results=50):
        discover_called.append(True)
        return []
    
    monkeypatch.setattr(overpass_fetcher.OverpassClient, "discover", mock_discover)
    
    run_full_pipeline(
        niche="auto detailing",
        area="Frisco TX",
        workspace=str(workspace),
        generation_mode="template",
        deploy_provider="local_only",
        max_preview_sites=1,
        dry_run=True,
        vnext_flags={"use_overpass_enrichment": False},
    )
    
    # Verify discover was NOT called
    assert len(discover_called) == 0, "Overpass discover should not have been called when flag is False"