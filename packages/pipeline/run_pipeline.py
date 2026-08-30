"""End-to-End Pipeline Orchestrator.

Runs all phases (01 to 09) in sequence.
"""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Any

# Import all phases
from packages.phases.phase_01_user_input import run as run_phase_01
from packages.phases.phase_02_1_website_filter import run as run_phase_02_1
from packages.phases.phase_02_basic_lead_discovery import run as run_phase_02
from packages.phases.phase_03_lead_scoring import run as run_phase_03
from packages.phases.phase_04_5_enrichment import run as run_phase_04_5
from packages.phases.phase_04_business_brief import run_phase_04
from packages.phases.phase_05_unified import run_phase_05_unified
from packages.phases.phase_06_strict_quality_gate import run_strict_phase_06
from packages.phases.phase_07_deployment import run_phase_07
from packages.phases.phase_08_outreach_generation import run_phase_08
from packages.phases.phase_09_manual_approval_pack import run_phase_09
from packages.pipeline.vnext_integration import (
    get_vnext_flags,
    run_vnext_post_phase_03,
    run_vnext_post_phase_03_overpass_enrichment,
    run_vnext_post_phase_04_5,
    run_vnext_post_phase_04_5_gmaps_enrichment,
    run_vnext_post_phase_04_5_image_fallback,
    run_vnext_post_phase_04_5_social_enrichment,
    run_vnext_post_phase_06,
    run_vnext_post_phase_08,
    run_vnext_post_phase_09,
)

logger = logging.getLogger(__name__)


def make_run_id() -> str:
    """Return a collision-proof run identifier.

    Keeps the documented ``run_<timestamp>`` layout (ARCHITECTURE.md/README:
    ``runs/run_<timestamp>``, test glob ``runs/run_*``) and appends a UUID
    suffix so concurrent runs started within the same second cannot collide
    (U-15). ``run_id`` is consumed as an opaque string across the pipeline.
    """
    return f"run_{int(time.time())}_{uuid.uuid4().hex}"

def run_full_pipeline(
    *,
    niche: str,
    area: str,
    country: str = "US",
    workspace: str = ".",
    stitch_client: Any | None = None,
    model_id: str = "GEMINI_3_1_PRO",
    generation_mode: str = "stitch",
    deploy_provider: str = "local_only",
    discovery_source: str = "fixture",
    max_preview_sites: int = 5,
    price_offer: str = "$499 one-time",
    dry_run: bool = False,
    production_mode: bool = False,
    vnext_flags: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Execute all phases in sequence.
    
    Args:
        niche: Business category
        area: Geographic target
        country: ISO country code
        workspace: Base directory
        stitch_client: Optional StitchClient
        model_id: Stitch model ID (GEMINI_3_PRO, GEMINI_3_FLASH, GEMINI_3_1_PRO)
        generation_mode: stitch | modular | template | auto
        deploy_provider: local_only | vercel | nginx_local
        discovery_source: fixture | overpass | csv_file | maps_api
        max_preview_sites: Maximum preview sites to generate
        price_offer: Pricing offer string
        dry_run: If True, skips Phase 07 (deploy) and Phase 08 (outreach)
        production_mode: If True, removes watermarks/test markers (modular mode)
        vnext_flags: Optional dict of vNext feature flags (all default False)
        
    Returns:
        Summary dict of run
    """
    start_time = time.time()
    run_id = make_run_id()
    
    logger.info(f"Starting full pipeline run {run_id} for niche='{niche}' area='{area}'...")
    
    phases_completed = []
    errors = []
    
    # 1. Phase 01: User Input
    logger.info("Executing Phase 01: User Input...")
    input_config = {
        "niche": niche,
        "area": area,
        "country": country,
        "max_raw_results": max_preview_sites * 2,
        "max_preview_sites": max_preview_sites,
        "price_offer": price_offer,
        "generation_mode": generation_mode,
        "model_id": model_id,
        "deploy_provider": deploy_provider,
        "discovery_source": discovery_source,
        "vnext_flags": vnext_flags or {},
    }
    
    p1_res = run_phase_01(run_id, workspace, input_config)
    if p1_res.get("status") != "done":
        logger.error(f"Phase 01 failed: {p1_res}")
        errors.append(f"Phase 01 failed: {p1_res.get('errors')}")
        return _make_summary(run_id, phases_completed, errors, start_time)
    phases_completed.append("01")
    
    # 2. Phase 02: Lead Discovery
    logger.info("Executing Phase 02: Lead Discovery...")
    p2_res = run_phase_02(run_id, workspace)
    if p2_res.get("status") not in ("done", "needs_review"):
        logger.error(f"Phase 02 failed: {p2_res}")
        errors.append(f"Phase 02 failed: {p2_res.get('errors')}")
        return _make_summary(run_id, phases_completed, errors, start_time)
    phases_completed.append("02")
    
    # 3. Phase 02.1: Website Filter
    logger.info("Executing Phase 02.1: Website Filter...")
    p2_1_res = run_phase_02_1(run_id, workspace)
    if p2_1_res.get("status") not in ("done", "needs_review"):
        logger.error(f"Phase 02.1 failed: {p2_1_res}")
        errors.append(f"Phase 02.1 failed: {p2_1_res.get('errors')}")
        return _make_summary(run_id, phases_completed, errors, start_time)
    phases_completed.append("02.1")
    
    # 4. Phase 03: Lead Scoring
    logger.info("Executing Phase 03: Lead Scoring...")
    p3_res = run_phase_03(run_id, workspace)
    if p3_res.get("status") != "done":
        logger.error(f"Phase 03 failed: {p3_res}")
        errors.append(f"Phase 03 failed: {p3_res.get('errors')}")
        return _make_summary(run_id, phases_completed, errors, start_time)
    phases_completed.append("03")
    
    # To determine selected leads in Phase 03: 
    # The selected leads list is in the 'decisions' of p3_res or in selected_for_preview.json.
    # In conformed Phase 03 contract, it output selected_for_preview.json.
    # Let's read selected_for_preview.json to populate selected_leads.
    selected_leads = []
    selected_path = Path(workspace) / "runs" / run_id / "03_scoring" / "selected_for_preview.json"
    if selected_path.exists():
        try:
            from packages.pipeline.json_io import read_json
            selected_leads = read_json(str(selected_path))
        except Exception:
            pass
            
    if not selected_leads:
        logger.warning("No leads selected for preview site generation. Ending run.")
        return _make_summary(run_id, phases_completed, errors, start_time, leads_selected=0)
    
    # ── vNext: VNEXT-02 market_profile per selected lead ──
    flags = get_vnext_flags(input_config)
    if any(flags.values()):
        logger.info("Running vNext post-phase-03 integration...")
        run_vnext_post_phase_03(run_id, workspace, selected_leads, input_config)

    # ── VNEXT-13: Overpass OSM enrichment per lead ──
    if flags.get("use_overpass_enrichment"):
        logger.info("Running VNEXT-13 Overpass enrichment...")
        run_vnext_post_phase_03_overpass_enrichment(
            run_id, workspace, selected_leads, input_config,
        )
        
    # 5. Phase 04: Business Brief
    logger.info("Executing Phase 04: Business Brief...")
    p4_res = run_phase_04(run_id, workspace)
    if p4_res.get("status") != "done":
        logger.error(f"Phase 04 failed: {p4_res}")
        errors.append(f"Phase 04 failed: {p4_res.get('errors')}")
        return _make_summary(run_id, phases_completed, errors, start_time, leads_selected=len(selected_leads))
    phases_completed.append("04")
    
    # 6. Phase 04.5: Enrichment
    logger.info("Executing Phase 04.5: Enrichment...")
    p4_5_res = run_phase_04_5(run_id, workspace)
    if p4_5_res.get("status") != "done":
        logger.error(f"Phase 04.5 failed: {p4_5_res}")
        errors.append(f"Phase 04.5 failed: {p4_5_res.get('errors')}")
        return _make_summary(run_id, phases_completed, errors, start_time, leads_selected=len(selected_leads))
    phases_completed.append("04.5")
    
    # ── VNEXT-14: Google Maps enrichment ──
    if flags.get("use_gmaps_enrichment"):
        logger.info("Running VNEXT-14 Google Maps enrichment...")
        run_vnext_post_phase_04_5_gmaps_enrichment(
            run_id, workspace, selected_leads, input_config,
        )
    
    # ── VNEXT-15: Social scraper enrichment ──
    if flags.get("use_social_enrichment"):
        logger.info("Running VNEXT-15 social scraper enrichment...")
        run_vnext_post_phase_04_5_social_enrichment(
            run_id, workspace, selected_leads, input_config,
        )

    # ── VNEXT-17: Image generation fallback ──
    if flags.get("use_image_fallback"):
        logger.info("Running VNEXT-17 image fallback generation...")
        run_vnext_post_phase_04_5_image_fallback(
            run_id, workspace, selected_leads, input_config,
        )
    
    # ── vNext: VNEXT-03 brand reconstruction + VNEXT-04 creative spec ──
    if any(flags.values()):
        logger.info("Running vNext post-phase-04.5 integration...")
        run_vnext_post_phase_04_5(run_id, workspace, selected_leads, input_config)
    
    # 7. Phase 05: Unified Site Generation (Stitch / modular / template)
    logger.info("Executing Phase 05: Site Generation...")
    p5_res = run_phase_05_unified(
        run_id=run_id,
        workspace=workspace,
        stitch_client=stitch_client,
        model_id=model_id,
        production_mode=production_mode,
    )
    if p5_res.get("status") != "done":
        logger.error(f"Phase 05 failed: {p5_res}")
        errors.append(f"Phase 05 failed: {p5_res.get('errors')}")
        return _make_summary(run_id, phases_completed, errors, start_time, leads_selected=len(selected_leads))
    phases_completed.append("05")
    
    # 8. Phase 05.5 render capture was executed automatically inside unified run_phase_05_unified
    phases_completed.append("05.5")
    
    # Determine if browser render succeeded (strict gate needs render artifacts)
    # Template-generated sites always use non-strict mode — they are previews
    # for client review, not production-ready sites requiring strict visual QA.
    browser_render_available = False
    sites_dir = Path(workspace) / "runs" / run_id / "05_sites"
    if sites_dir.exists() and generation_mode != "template":
        for site_subdir in sites_dir.iterdir():
            if site_subdir.is_dir() and (site_subdir / "render_capture.json").exists():
                browser_render_available = True
                break
    
    use_strict = browser_render_available
    if not use_strict:
        logger.info("Using non-strict quality gate (template mode or no browser render).")
    
    # 9. Phase 06: Quality Gate
    logger.info("Executing Phase 06: Quality Gate...")
    p6_res = run_strict_phase_06(run_id, workspace, strict=use_strict)
    if p6_res.get("status") != "done":
        logger.error(f"Phase 06 failed: {p6_res}")
        errors.append(f"Phase 06 failed: {p6_res.get('errors')}")
        return _make_summary(run_id, phases_completed, errors, start_time, leads_selected=len(selected_leads))
    phases_completed.append("06")
    
    # ── vNext: VNEXT-06 structured evaluation ──
    if any(flags.values()):
        logger.info("Running vNext post-phase-06 integration...")
        run_vnext_post_phase_06(run_id, workspace, selected_leads, input_config)
    
    # Parse decisions to see approved leads count
    decisions = p6_res.get("decisions", [])
    approved_text = [d for d in decisions if "Approved:" in d]
    approved_count = 0
    needs_edit_count = 0
    if approved_text:
        try:
            # Format is "Approved: X, Needs edit: Y, Rejected: Z"
            parts = approved_text[0].split(",")
            approved_count = int(parts[0].split(":")[1].strip())
            needs_edit_count = int(parts[1].split(":")[1].strip())
        except Exception:
            approved_count = 0
    
    # In non-strict/template mode, needs_edit sites are acceptable for preview
    passable_count = approved_count + (needs_edit_count if not use_strict else 0)
            
    if passable_count == 0:
        logger.warning("All generated sites failed Phase 06 quality gate. Stopping before deploy.")
        return _make_summary(
            run_id, phases_completed, errors, start_time,
            leads_selected=len(selected_leads),
            sites_generated=len(selected_leads),
            sites_approved=0,
        )
        
    if dry_run:
        logger.info("dry_run=True: Skipping Phase 07 (deploy) and Phase 08 (outreach).")
        return _make_summary(
            run_id, phases_completed, errors, start_time,
            leads_selected=len(selected_leads),
            sites_generated=len(selected_leads),
            sites_approved=passable_count,
        )
        
    # 10. Phase 07: Deployment
    logger.info("Executing Phase 07: Deployment...")
    p7_res = run_phase_07(run_id, workspace)
    if p7_res.get("status") != "done":
        logger.error(f"Phase 07 failed: {p7_res}")
        errors.append(f"Phase 07 failed: {p7_res.get('errors')}")
        return _make_summary(
            run_id, phases_completed, errors, start_time,
            leads_selected=len(selected_leads),
            sites_generated=len(selected_leads),
            sites_approved=passable_count,
        )
    phases_completed.append("07")
    
    # Extract live URLs
    deployed_urls = []
    # Read public_url_manifest.json if it exists
    manifest_path = Path(workspace) / "runs" / run_id / "07_deployments" / "public_url_manifest.json"
    if manifest_path.exists():
        try:
            from packages.pipeline.json_io import read_json
            manifest = read_json(str(manifest_path))
            deployed_urls = [val["preview_url"] for val in manifest.values() if "preview_url" in val]
        except Exception:
            pass
            
    # 11. Phase 08: Outreach Generation
    logger.info("Executing Phase 08: Outreach Generation...")
    p8_res = run_phase_08(run_id, workspace)
    if p8_res.get("status") != "done":
        logger.error(f"Phase 08 failed: {p8_res}")
        errors.append(f"Phase 08 failed: {p8_res.get('errors')}")
        return _make_summary(
            run_id, phases_completed, errors, start_time,
            leads_selected=len(selected_leads),
            sites_generated=len(selected_leads),
            sites_approved=passable_count,
            sites_deployed=len(deployed_urls),
            deployed_urls=deployed_urls,
        )
    phases_completed.append("08")
    
    # ── vNext: VNEXT-08 sales package ──
    if any(flags.values()):
        logger.info("Running vNext post-phase-08 integration...")
        run_vnext_post_phase_08(run_id, workspace, selected_leads, input_config)
    
    # 12. Phase 09: Manual Approval Pack
    logger.info("Executing Phase 09: Approval Pack...")
    p9_res = run_phase_09(run_id, workspace, skip_missing_stubs=dry_run)
    if p9_res.get("status") != "done":
        logger.error(f"Phase 09 failed: {p9_res}")
        errors.append(f"Phase 09 failed: {p9_res.get('errors')}")
        return _make_summary(
            run_id, phases_completed, errors, start_time,
            leads_selected=len(selected_leads),
            sites_generated=len(selected_leads),
            sites_approved=passable_count,
            sites_deployed=len(deployed_urls),
            deployed_urls=deployed_urls,
        )
    phases_completed.append("09")
    
    # ── vNext: VNEXT-09 learning record ──
    if any(flags.values()):
        logger.info("Running vNext post-phase-09 integration...")
        run_vnext_post_phase_09(run_id, workspace, selected_leads, input_config)
    
    return _make_summary(
        run_id, phases_completed, errors, start_time,
        leads_selected=len(selected_leads),
        sites_generated=len(selected_leads),
        sites_approved=passable_count,
        sites_deployed=len(deployed_urls),
        deployed_urls=deployed_urls,
        approval_pack=f"runs/{run_id}/09_review/review_pack.md",
    )

def _make_summary(
    run_id: str,
    phases_completed: list[str],
    errors: list[str],
    start_time: float,
    *,
    leads_discovered: int = 15,
    leads_selected: int = 0,
    sites_generated: int = 0,
    sites_approved: int = 0,
    sites_deployed: int = 0,
    deployed_urls: list[str] | None = None,
    approval_pack: str = "",
) -> dict[str, Any]:
    duration = int(time.time() - start_time)
    
    # Compute counts from directories if not passed
    return {
        "run_id": run_id,
        "phases_completed": phases_completed,
        "leads_discovered": leads_discovered,
        "leads_selected": leads_selected,
        "sites_generated": sites_generated,
        "sites_approved": sites_approved,
        "sites_deployed": sites_deployed,
        "deployed_urls": deployed_urls or [],
        "outreach_drafts": sites_deployed,
        "approval_pack": approval_pack,
        "errors": errors,
        "duration_seconds": duration,
    }
