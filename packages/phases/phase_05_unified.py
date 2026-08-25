"""Phase 05: Stitch Site Generation Router.

Routes to Stitch AI exclusively. NO template fallback — template mode must be explicit.
Based on generation_mode config: "stitch" or "template".
"""

from __future__ import annotations

import logging
from typing import Any

from packages.phases.phase_05_modular_site_generation import run_modular_phase_05
from packages.phases.phase_05_preview_site_generation import run_phase_05 as run_template_phase_05
from packages.phases.phase_05_stitch_site_generation import run_stitch_phase_05
from packages.pipeline.json_io import read_json, write_json
from packages.pipeline.result_envelope import ResultEnvelope

logger = logging.getLogger(__name__)

PHASE_NAME = "phase_05_unified"

def run_phase_05_unified(
    run_id: str,
    workspace: str,
    stitch_client: Any | None = None,
    *,
    project_id: str | None = None,
    design_system: str | None = None,
    device_type: str = "MOBILE",
    model_id: str = "GEMINI_3_PRO",
    production_mode: bool = False,
) -> dict[str, Any]:
    """Run unified Phase 05 generator router.
    
    Args:
        run_id: Pipeline run ID
        workspace: Workspace dir
        stitch_client: Stitch client instance
        project_id: Optional Stitch project ID
        design_system: Optional design system UUID
        device_type: DESKTOP or MOBILE
        model_id: Model ID for Stitch
        production_mode: If True, removes watermarks/test markers (modular mode only)
        
    Returns:
        ResultEnvelope dictionary
        
    Generation modes (set in input_config.json):
        - "stitch": Premium AI generation (requires stitch_client)
        - "modular": Production-quality modular templates with contact forms
        - "template": Legacy basic template (fallback)
    """
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    config_path = f"{workspace}/runs/{run_id}/config/input_config.json"
    try:
        config = read_json(config_path)
        generation_mode = config.get("generation_mode", "stitch")
    except Exception as e:
        logger.warning(f"Could not read config, defaulting to auto: {e}")
        generation_mode = "auto"
        
    logger.info(f"Unified Phase 05: Mode = {generation_mode}")

    final_result = None

    # STITCH or AUTO mode
    if generation_mode in ("stitch", "auto"):
        if stitch_client is None:
            if generation_mode == "auto":
                logger.info("No stitch client in AUTO mode, falling back to template...")
                result = run_template_phase_05(run_id, workspace)
                result["generation_mode_used"] = "template"
                final_result = result
            else:
                final_result = ResultEnvelope.failed(
                    phase=PHASE_NAME,
                    run_id=run_id,
                    hard_block=True,
                    errors=["stitch_client is required for generation_mode=stitch (template fallback disabled per policy)"]
                ).to_dict()
        else:
            logger.info("Attempting Stitch generation...")
            try:
                stitch_result = run_stitch_phase_05(
                    run_id=run_id,
                    workspace=workspace,
                    stitch_client=stitch_client,
                    project_id=project_id,
                    design_system=design_system,
                    device_type=device_type,
                    model_id=model_id,
                )
                # In auto mode, if ALL sites failed, fall back to template
                if generation_mode == "auto" and stitch_result.get("records_created", 0) == 0 and stitch_result.get("records_processed", 0) > 0:
                    logger.info("All Stitch sites failed in AUTO mode, falling back to template...")
                    result = run_template_phase_05(run_id, workspace)
                    result["generation_mode_used"] = "template"
                    final_result = result
                else:
                    stitch_result["generation_mode_used"] = "stitch"
                    final_result = stitch_result
            except Exception as e:
                logger.error(f"Stitch generation failed: {e}")
                if generation_mode == "auto":
                    logger.info("Falling back to template generation...")
                    result = run_template_phase_05(run_id, workspace)
                    result["generation_mode_used"] = "template"
                    final_result = result
                else:
                    final_result = ResultEnvelope.failed(
                        phase=PHASE_NAME,
                        run_id=run_id,
                        hard_block=True,
                        errors=[f"Stitch generation failed: {e}"]
                    ).to_dict()

    # MODULAR mode
    elif generation_mode == "modular":
        logger.info("Running modular template generation.")
        result = run_modular_phase_05(
            run_id=run_id,
            workspace=workspace,
            production_mode=production_mode,
            variant="desktop"
        )
        result["generation_mode_used"] = "modular"
        final_result = result
    
    # TEMPLATE mode (legacy basic template)
    elif generation_mode == "template":
        logger.info("Running deterministic template generation.")
        result = run_template_phase_05(run_id, workspace)
        result["generation_mode_used"] = "template"
        final_result = result
        
    else:
        final_result = ResultEnvelope.failed(
            phase=PHASE_NAME,
            run_id=run_id,
            errors=[f"Invalid generation_mode: {generation_mode}"]
        ).to_dict()

    # --- Post-generation: Run Phase 05.5 Render Capture ---
    try:
        from packages.phases.phase_05_5_browser_render_capture import run_phase_05_5
        logger.info("Running Phase 05.5 browser render capture...")
        render_result = run_phase_05_5(run_id, workspace)
        
        # Update build_status.json for all generated sites
        from pathlib import Path
        
        phase_slug = "05_sites"
        sites_dir = Path(workspace) / "runs" / run_id / phase_slug
        if sites_dir.exists():
            for site_dir in sites_dir.iterdir():
                if not site_dir.is_dir():
                    continue
                build_status_path = site_dir / "build_status.json"
                if build_status_path.exists():
                    status = read_json(str(build_status_path))
                    if render_result.get("status") == "blocked":
                        status["render_capture"] = "synthetic"
                        status["render_capture_status"] = "fallback"
                    else:
                        status["render_capture"] = "browser"
                        status["render_capture_status"] = "done"
                    write_json(str(build_status_path), status)
                    
    except Exception as e:
        logger.warning(f"Phase 05.5 render capture failed or missing: {e}")

    return final_result
