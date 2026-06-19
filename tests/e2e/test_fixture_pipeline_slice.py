"""End-to-end fixture pipeline slice test.

Tests the pipeline from Phase 02 through Phase 09:
02 -> 02.1 -> 03 -> 04 -> 05 -> 06 -> 07 -> 09

This validates that all phases work together correctly with fixture inputs.
Note: Phase 08 outputs are stubbed in this test to keep fixture setup minimal.
"""

import shutil
import tempfile
from pathlib import Path

from packages.pipeline.json_io import read_json, write_json
from packages.phases.phase_02_basic_lead_discovery import run as run_phase_02
from packages.phases.phase_02_1_website_filter import run as run_phase_02_1
from packages.phases.phase_03_lead_scoring import run as run_phase_03
from packages.phases.phase_04_business_brief import run_phase_04
from packages.phases.phase_04_5_enrichment import run as run_phase_04_5
from packages.phases.phase_05_preview_site_generation import run_phase_05
from packages.phases.phase_06_quality_gate import run_phase_06
from packages.phases.phase_07_deployment import run_phase_07
from packages.phases.phase_09_manual_approval_pack import run_phase_09


def _setup_phase_08_stubs(root: Path, run_id: str, business_slugs: list[str], config: dict):
    """Stub Phase 08 outreach draft outputs."""
    outreach_dir = root / "runs" / run_id / "08_outreach"
    outreach_dir.mkdir(parents=True, exist_ok=True)

    drafts = []
    for slug in business_slugs:
        drafts.append({
            "run_id": run_id,
            "record_id": f"out_{slug}",
            "business_slug": slug,
            "business_name": slug.replace("-", " ").title(),
            "recipient_channel": "email",
            "recipient_value": f"contact@{slug}.example.com",
            "subject": f"Website preview for {slug}",
            "body": f"Hi, I created a website preview for your business. Check it out at https://{slug}.example.com",
            "preview_url": f"https://{slug}.example.com",
            "price_offer": config.get("price_offer", "$299 setup"),
            "draft_status": "ready_for_review",
            "blocked_reason": "",
            "personalization_fields_used": ["business_name", "preview_url"],
        })

    write_json(str(outreach_dir / "outreach_drafts.json"), drafts)
    write_json(str(outreach_dir / "result.json"), {
        "phase": "phase_08_outreach_generation",
        "status": "done",
        "run_id": run_id,
        "records_processed": len(drafts),
    })


def test_fixture_pipeline_slice_02_to_09():
    """Run the fixture pipeline from Phase 02 to Phase 09."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "fixture_slice_001"

        # Set up config (from Phase 01 output)
        config_dir = root / "runs" / run_id / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        config = {
            "run_id": run_id,
            "niche": "dentists",
            "area": "Test City",
            "country": "Test Country",
            "language": "English",
            "max_raw_results": 10,
            "max_preview_sites": 3,
            "minimum_rating": 4.3,
            "minimum_reviews": 40,
            "style_preset": None,
            "deploy_mode": "preview_demo_mode",
            "price_offer": "$299 setup",
            "mvp_stop_threshold": 20,
        }
        write_json(str(config_dir / "input_config.json"), config)

        # Set up Phase 01 input (required by Phase 02)
        input_dir = root / "runs" / run_id / "01_input"
        input_dir.mkdir(parents=True, exist_ok=True)

        # Copy Phase 02 fixture input for slice test
        fixture_src = Path(__file__).parents[2] / "tests" / "fixtures" / "phase_02_basic_lead_discovery" / "input" / "raw_places_with_websites.json"
        fixture_dst = root / "tests" / "fixtures" / "phase_02_basic_lead_discovery" / "input" / "raw_places_with_websites.json"
        fixture_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(fixture_src, fixture_dst)

        write_json(str(input_dir / "query_plan.json"), {"run_id": run_id, "queries": []})

        # Phase 02: Discovery
        result_02 = run_phase_02(run_id, str(root))
        assert result_02["status"] == "done", f"Phase 02 failed: {result_02}"

        # Phase 02.1: Website filter
        result_02_1 = run_phase_02_1(run_id, str(root))
        assert result_02_1["status"] in ("done", "needs_review"), f"Phase 02.1 failed: {result_02_1}"

        # Phase 03: Lead scoring
        result_03 = run_phase_03(run_id, str(root), config)
        assert result_03["status"] == "done", f"Phase 03 failed: {result_03}"

        # Phase 04: Business brief
        result_04 = run_phase_04(run_id, str(root))
        assert result_04["status"] == "done", f"Phase 04 failed: {result_04}"

        # Phase 04.5: Enrichment
        result_04_5 = run_phase_04_5(run_id, str(root))
        assert result_04_5["status"] == "done", f"Phase 04.5 failed: {result_04_5}"

        # Phase 05: Preview site generation
        result_05 = run_phase_05(run_id, str(root))
        assert result_05["status"] == "done", f"Phase 05 failed: {result_05}"

        # Phase 06: Quality gate
        result_06 = run_phase_06(run_id, str(root))
        assert result_06["status"] == "done", f"Phase 06 failed: {result_06}"

        # Get business slugs for Phase 08 stubs
        qualified_leads = read_json(str(root / "runs" / run_id / "03_scoring" / "selected_for_preview.json"))
        business_slugs = [lead["business_slug"] for lead in qualified_leads]

        # Phase 07: Deployment
        if business_slugs:
            result_07 = run_phase_07(run_id, str(root))
            assert result_07["status"] == "done", f"Phase 07 failed: {result_07}"

            # Stub Phase 08 outreach (not yet implemented)
            _setup_phase_08_stubs(root, run_id, business_slugs, config)

            # Phase 09: Manual approval pack
            result_09 = run_phase_09(run_id, str(root))
            assert result_09["status"] == "done", f"Phase 09 failed: {result_09}"

            # Verify final outputs
            assert (root / "runs" / run_id / "09_review" / "review_table.csv").exists()
            assert (root / "runs" / run_id / "09_review" / "review_pack.md").exists()
            assert (root / "runs" / run_id / "09_review" / "screenshots_index.json").exists()
            assert (root / "runs" / run_id / "09_review" / "approval_decisions.json").exists()

            # Verify screenshots index has both paths
            screenshots = read_json(str(root / "runs" / run_id / "09_review" / "screenshots_index.json"))
            assert len(screenshots) > 0
            for item in screenshots:
                assert item["screenshot_desktop_path"] != "", f"Missing desktop screenshot for {item}"
                assert item["screenshot_mobile_path"] != "", f"Missing mobile screenshot for {item}"