"""E2E test: full pipeline 01→09 with fixture lead, modular renderer, local_only deployer.

Verification targets for Sprint 1 Task 3:
- Phase 07: deployment status "live", preview_url not empty
- Phase 08: outreach drafts generated, count, blocked status
- Phase 09: approval pack content (links, previews, screenshots)
"""

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
from packages.phases.phase_08_outreach_generation import run_phase_08
from packages.phases.phase_09_manual_approval_pack import run_phase_09
from packages.pipeline.json_io import read_json


def test_e2e_full_pipeline_01_to_09():
    """Run full pipeline 01→09 with 1 fixture lead and verify all phases."""

    # We'll use the project's runs dir directly for traceability
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "e2e_full_001"

        # ── Phase 01: User Input ──
        input_config = {
            "run_id": run_id,
            "niche": "dentists",
            "area": "Chiang Mai",
            "country": "Thailand",
            "language": "English",
            "max_raw_results": 5,
            "max_preview_sites": 1,
            "minimum_rating": 4.0,
            "minimum_reviews": 20,
            "style_preset": "clinical_trust",
            "deploy_mode": "preview_demo_mode",
            "price_offer": "$299 setup",
            "mvp_stop_threshold": 10,
            "renderer": "modular",
        }
        result_01 = run_phase_01(run_id, str(root), input_config=input_config)
        assert result_01["status"] == "done", f"Phase 01 failed: {result_01}"

        # ── Phase 02: Lead Discovery (fixture) ──
        test_lead = {
            "record_id": "rec_e2e_full_001",
            "source": "manual_fixture",
            "source_query": "dentists Chiang Mai",
            "business_name": "E2E Full Test Dental",
            "place_id": "ChIJE2EFULL1",
            "category": "Dentist",
            "rating": 4.5,
            "review_count": 80,
            "address": "123 Test Street, Chiang Mai",
            "phone": "+66 53 999 888",
            "website": "",
            "maps_url": "https://maps.google.com/?cid=E2EFULL1",
            "hours": "Mon-Fri 9AM-6PM",
            "business_status": "open",
        }
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

        # ── Phase 05: Site Generation (modular) ──
        result_05 = run_modular_phase_05(run_id, str(root), production_mode=False)
        assert result_05["status"] == "done", f"Phase 05 failed: {result_05}"

        # Verify site structure
        sites_dir = root / "runs" / run_id / "05_sites"
        site_slugs = [d.name for d in sites_dir.iterdir() if d.is_dir()]
        assert len(site_slugs) > 0, "No preview sites generated"
        test_slug = site_slugs[0]
        site_dir = sites_dir / test_slug
        index_path = site_dir / "index.html"
        assert index_path.exists(), f"index.html not found at {index_path}"
        assert "<html" in index_path.read_text(encoding="utf-8").lower()

        # ── Phase 06: Quality Gate ──
        result_06 = run_phase_06(run_id, str(root))
        assert result_06["status"] == "done", f"Phase 06 failed: {result_06}"

        # ── Phase 07: Deployment ──
        result_07 = run_phase_07(run_id, str(root))
        assert result_07["status"] == "done", f"Phase 07 failed: {result_07}"
        assert result_07["records_created"] >= 1, "No deployment records created"

        # ▸▸ VERIFICATION: Phase 07 Deployment ▸▸
        deployment_dir = root / "runs" / run_id / "07_deployments" / test_slug
        assert deployment_dir.exists(), "Deployment directory not created"
        deployment_record_path = deployment_dir / "deployment_record.json"
        assert deployment_record_path.exists(), "Deployment record not created"
        deployment_record = read_json(str(deployment_record_path))

        p07_status = deployment_record["deployment_status"]
        p07_preview_url = deployment_record.get("preview_url", "")
        print(f"\n  Phase 07 deployment_status: {p07_status}")
        print(f"  Phase 07 preview_url: {p07_preview_url}")

        assert p07_status == "live", f"Deployment status is not 'live': {p07_status}"
        assert p07_preview_url, "preview_url is empty"
        assert "index.html" in p07_preview_url, f"preview_url missing index.html: {p07_preview_url}"
        assert deployment_record["provider"] == "local_only"
        assert deployment_record["http_status"] == 200

        # ── Phase 08: Outreach Generation ──
        result_08 = run_phase_08(run_id, str(root))
        assert result_08["status"] == "done", f"Phase 08 failed: {result_08}"

        # ▸▸ VERIFICATION: Phase 08 Outreach ▸▸
        outreach_dir = root / "runs" / run_id / "08_outreach"
        drafts_path = outreach_dir / "outreach_drafts.json"
        drafts_md_path = outreach_dir / "outreach_drafts.md"
        assert drafts_path.exists(), "outreach_drafts.json not created"
        assert drafts_md_path.exists(), "outreach_drafts.md not created"

        drafts = read_json(str(drafts_path))
        total_drafts = len(drafts)
        blocked_drafts = [d for d in drafts if d["draft_status"] == "blocked"]
        ready_drafts = [d for d in drafts if d["draft_status"] == "ready_for_review"]

        print(f"\n  Phase 08 total_drafts: {total_drafts}")
        print(f"  Phase 08 ready_for_review: {len(ready_drafts)}")
        print(f"  Phase 08 blocked: {len(blocked_drafts)}")

        assert total_drafts >= 1, f"Expected at least 1 draft, got {total_drafts}"

        for draft in drafts:
            slug = draft.get("business_slug", "?")
            status = draft.get("draft_status", "?")
            body = draft.get("body", "")
            preview_url = draft.get("preview_url", "")
            blocked_reason = draft.get("blocked_reason", "")

            print(f"  -> {slug}: status={status}")
            if status == "ready_for_review":
                assert body, f"Draft {slug} is ready but body is empty"
                assert preview_url, f"Draft {slug} is ready but preview_url is empty"
                assert draft.get("subject") or draft.get("recipient_channel") != "email", \
                    f"Draft {slug} via email has no subject"
                print(f"     subject: {draft.get('subject', 'N/A')}")
                print(f"     body length: {len(body)} chars")
                print(f"     preview_url: {preview_url[:80]}...")
            else:
                assert blocked_reason, f"Draft {slug} blocked but no reason"
                print(f"     blocked_reason: {blocked_reason}")

        # ── Phase 09: Manual Approval Pack ──
        result_09 = run_phase_09(run_id, str(root), skip_missing_stubs=False)
        assert result_09["status"] == "done", f"Phase 09 failed: {result_09}"

        # ▸▸ VERIFICATION: Phase 09 Approval Pack ▸▸
        review_dir = root / "runs" / run_id / "09_review"
        review_pack_path = review_dir / "review_pack.md"
        review_csv_path = review_dir / "review_table.csv"
        screenshots_index_path = review_dir / "screenshots_index.json"
        approval_decisions_path = review_dir / "approval_decisions.json"

        assert review_pack_path.exists(), "review_pack.md not created"
        assert review_csv_path.exists(), "review_table.csv not created"
        assert screenshots_index_path.exists(), "screenshots_index.json not created"
        assert approval_decisions_path.exists(), "approval_decisions.json not created"

        # Check review_pack.md content
        review_pack = review_pack_path.read_text(encoding="utf-8")
        assert "# Manual Approval Pack" in review_pack, "review_pack.md missing header"
        assert "Preview URL" in review_pack, "review_pack.md missing Preview URL"
        assert "Send Approval Checklist" in review_pack, "review_pack.md missing checklist"

        print(f"\n  Phase 09 records_processed: {result_09['records_processed']}")
        print("  Phase 09 outputs:")
        print(f"    - review_pack.md: {len(review_pack)} chars")

        # Check screenshots_index has real content
        screenshots_index = read_json(str(screenshots_index_path))
        if screenshots_index:
            entry = screenshots_index[0]
            print(f"    - screenshots: {entry.get('screenshot_desktop_path')}")
            assert entry.get("screenshot_desktop_path", ""), "screenshot_desktop_path empty"
            assert entry.get("screenshot_mobile_path", ""), "screenshot_mobile_path empty"

        # Check approval_decisions
        decisions = read_json(str(approval_decisions_path))
        assert len(decisions) >= 1, "No approval decisions"
        decision = decisions[0]
        assert decision["approval_status"] == "pending"
        assert decision["business_slug"] == test_slug
        print(f"    - approval_decisions: {len(decisions)} pending")

        # Check review pack has real preview URLs
        for line in review_pack.splitlines():
            if "Preview URL" in line:
                print(f"    - review_pack.md has: {line.strip()}")

        # Check review_table.csv has data
        csv_content = review_csv_path.read_text(encoding="utf-8")
        assert test_slug in csv_content, f"CSV missing business_slug {test_slug}"
        assert "preview_url" in csv_content.lower(), "CSV missing preview_url column"
        print(f"    - review_table.csv: {len(csv_content)} bytes")

        # ── SUMMARY ──
        print(f"\n{'='*60}")
        print("✅ E2E Full Pipeline 01→09 PASSED!")
        print(f"   Run ID: {run_id}")
        print(f"   Business: {test_slug}")
        print("   Phases: 01 02 02.1 03 04 04.5 05 06 07 08 09")
        print(f"{'='*60}")
        print("\nPhase 07 Results:")
        print(f"   Deployment status: {p07_status}")
        print(f"   Preview URL: {p07_preview_url}")
        print("\nPhase 08 Results:")
        print(f"   Drafts generated: {total_drafts}")
        print(f"   Ready for review: {len(ready_drafts)}")
        print(f"   Blocked: {len(blocked_drafts)}")
        print("\nPhase 09 Results:")
        print(f"   Records processed: {result_09['records_processed']}")
        print(f"   Review pack: {review_pack_path.name}")
        print(f"   Screenshots index: {'has content' if screenshots_index else 'empty'}")
        print(f"   Approval decisions: {len(decisions)} pending")
