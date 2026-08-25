"""E2E integration test for modular pipeline with real deployment verification.

This test validates the complete pipeline flow from Phase 01 to Phase 07
using the modular template generator and local_only deployer.

Key validations:
- Pipeline executes without errors
- Modular generator creates sites with correct path structure
- Deployment phase finds index.html at the right location
- Deployment record has status "live" with valid preview_url
- Quality gate approves the generated site

This test catches regressions like the /site suffix bug that was fixed in commit 46a88ee.
"""

import tempfile
from pathlib import Path

from packages.phases.phase_01_user_input import run as run_phase_01
from packages.phases.phase_02_1_website_filter import run as run_phase_02_1
from packages.phases.phase_02_basic_lead_discovery import run as run_phase_02
from packages.phases.phase_03_lead_scoring import run as run_phase_03
from packages.phases.phase_04_5_enrichment import run as run_phase_04_5
from packages.phases.phase_04_business_brief import run_phase_04
from packages.phases.phase_05_modular_site_generation import run_modular_phase_05
from packages.phases.phase_06_quality_gate import run_phase_06
from packages.phases.phase_07_deployment import run_phase_07
from packages.pipeline.json_io import read_json


def test_e2e_modular_pipeline_with_deployment():
    """
    E2E test: execute full pipeline with modular generator and verify deployment.
    
    This test uses:
    - 1 lead from fixtures (minimal viable config)
    - Modular template generator (default renderer)
    - Local_only deployer
    
    Critical assertions:
    - Deployment status = "live"
    - preview_url is not empty and starts with "file://"
    - index.html exists at 05_sites/{slug}/index.html (not /site/index.html)
    - Quality gate approves the site
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "e2e_modular_001"
        
        # ── Phase 01: User Input ──
        input_config = {
            "run_id": run_id,
            "niche": "dentists",
            "area": "Chiang Mai",
            "country": "Thailand",
            "language": "English",
            "max_raw_results": 5,
            "max_preview_sites": 1,  # Generate only 1 site for speed
            "minimum_rating": 4.0,
            "minimum_reviews": 20,
            "style_preset": "clinical_trust",  # Modular template family
            "deploy_mode": "preview_demo_mode",
            "price_offer": "$299 setup",
            "mvp_stop_threshold": 10,
            "renderer": "modular",  # Explicit: use modular generator
        }
        
        result_01 = run_phase_01(run_id, str(root), input_config=input_config)
        assert result_01["status"] == "done", f"Phase 01 failed: {result_01}"
        
        # ── Phase 02: Lead Discovery ──
        # Single lead fixture: no website, good rating/reviews
        test_lead = {
            "record_id": "rec_e2e_001",
            "source": "manual_fixture",
            "source_query": "dentists Chiang Mai",
            "business_name": "E2E Test Dental Clinic",
            "place_id": "ChIJE2E001",
            "category": "Dentist",
            "rating": 4.5,
            "review_count": 80,
            "address": "123 Test Street, Chiang Mai",
            "phone": "+66 53 999 888",
            "website": "",  # No website = good candidate
            "maps_url": "https://maps.google.com/?cid=E2E001",
            "hours": "Mon-Fri 9AM-6PM",
            "business_status": "open",
        }
        
        # Pass input_places directly to Phase 02
        result_02 = run_phase_02(run_id, str(root), input_places=[test_lead])
        assert result_02["status"] in ("done", "needs_review"), f"Phase 02 failed: {result_02}"
        
        # ── Phase 02.1: Website Filter ──
        result_02_1 = run_phase_02_1(run_id, str(root))
        assert result_02_1["status"] in ("done", "needs_review"), f"Phase 02.1 failed: {result_02_1}"
        
        # ── Phase 03: Lead Scoring ──
        config = read_json(str(root / "runs" / run_id / "config" / "input_config.json"))
        result_03 = run_phase_03(run_id, str(root), config)
        assert result_03["status"] == "done", f"Phase 03 failed: {result_03}"
        
        # ── Phase 04: Business Brief ──
        result_04 = run_phase_04(run_id, str(root))
        assert result_04["status"] == "done", f"Phase 04 failed: {result_04}"
        
        # ── Phase 04.5: Enrichment ──
        result_04_5 = run_phase_04_5(run_id, str(root))
        assert result_04_5["status"] == "done", f"Phase 04.5 failed: {result_04_5}"
        
        # ── Phase 05: Preview Site Generation (modular) ──
        result_05 = run_modular_phase_05(run_id, str(root), production_mode=False)
        assert result_05["status"] == "done", f"Phase 05 failed: {result_05}"
        
        # Verify site structure
        sites_dir = root / "runs" / run_id / "05_sites"
        assert sites_dir.exists(), "05_sites directory not created"
        
        site_slugs = [d.name for d in sites_dir.iterdir() if d.is_dir()]
        assert len(site_slugs) > 0, "No preview sites generated"
        
        test_slug = site_slugs[0]
        site_dir = sites_dir / test_slug
        
        # CRITICAL: Modular generator should create index.html at root, NOT in /site subdirectory
        index_path = site_dir / "index.html"
        assert index_path.exists(), (
            f"index.html not found at {index_path}. "
            f"Modular generator should create files at site root, not in /site subdirectory."
        )
        
        # Verify it's valid HTML
        html_content = index_path.read_text(encoding="utf-8")
        assert "<html" in html_content.lower(), "Generated file is not valid HTML"
        assert test_lead["business_name"] in html_content, "Business name not in generated site"
        
        # ── Phase 06: Quality Gate ──
        result_06 = run_phase_06(run_id, str(root))
        assert result_06["status"] == "done", f"Phase 06 failed: {result_06}"
        
        # Verify quality report approves the site
        quality_report_path = root / "runs" / run_id / "06_quality" / test_slug / "site_quality_report.json"
        assert quality_report_path.exists(), "Quality report not created"
        
        quality_report = read_json(str(quality_report_path))
        assert quality_report["status"] in ("approved_for_deploy", "approved_with_notes"), (
            f"Quality gate did not approve site: {quality_report['status']}"
        )
        
        # ── Phase 07: Deployment ──
        result_07 = run_phase_07(run_id, str(root))
        assert result_07["status"] == "done", f"Phase 07 failed: {result_07}"
        assert result_07["records_created"] >= 1, "No deployment records created"
        
        # Verify deployment record
        deployment_dir = root / "runs" / run_id / "07_deployments" / test_slug
        assert deployment_dir.exists(), "Deployment directory not created"
        
        deployment_record_path = deployment_dir / "deployment_record.json"
        assert deployment_record_path.exists(), "Deployment record not created"
        
        deployment_record = read_json(str(deployment_record_path))
        
        # CRITICAL ASSERTIONS: These would fail if the /site suffix bug returns
        assert deployment_record["deployment_status"] == "live", (
            f"Deployment status is not 'live': {deployment_record['deployment_status']}. "
            f"Error: {deployment_record.get('error', 'N/A')}"
        )
        
        assert deployment_record["preview_url"], "preview_url is empty"
        assert deployment_record["preview_url"].startswith("file://"), (
            f"Expected local file:// URL, got: {deployment_record['preview_url']}"
        )
        
        assert deployment_record["provider"] == "local_only"
        assert deployment_record["http_status"] == 200
        assert deployment_record["preview_url_type"] == "local_file"
        
        # Verify the preview_url points to the actual index.html
        preview_url = deployment_record["preview_url"]
        assert "index.html" in preview_url, f"preview_url does not reference index.html: {preview_url}"
        
        # Verify deployment logs
        deployment_logs_path = deployment_dir / "deployment_logs.txt"
        assert deployment_logs_path.exists(), "Deployment logs not created"
        
        logs = deployment_logs_path.read_text(encoding="utf-8")
        assert "status=live" in logs, "Deployment logs don't confirm live status"
        
        print("\n✅ E2E test passed!")
        print(f"   - Site generated: {test_slug}")
        print(f"   - Index.html at: {index_path}")
        print(f"   - Deployment status: {deployment_record['deployment_status']}")
        print(f"   - Preview URL: {deployment_record['preview_url']}")
        print(f"   - Quality status: {quality_report['status']}")
