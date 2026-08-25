"""Phase 05 — premium Stitch site generation (additive mode).

Wraps StitchAdapter + html_sanitizer to produce the same artifact layout
as deterministic Phase 05 so Phase 05.5 and Phase 06 work unchanged.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from packages.shared.provenance import _safe_str

logger = logging.getLogger(__name__)

PHASE_NAME = "phase_05_stitch_site_generation"
PHASE_SLUG = "05_sites"
PHASE_03_SLUG = "03_scoring"
PHASE_04_5_SLUG = "04_5_enrichment"

# Maximum number of attempts when Stitch returns SVG-only / undersized HTML.
_MAX_GENERATION_ATTEMPTS = 3

_MINIMAL_CSS = "/* minimal placeholder — styles inlined in index.html */\n"

try:
    from pipeline.json_io import read_json, write_json
    from pipeline.result_envelope import ResultEnvelope
except ModuleNotFoundError:  # pragma: no cover - CLI fallback
    from packages.pipeline.json_io import read_json, write_json
    from packages.pipeline.result_envelope import ResultEnvelope

try:
    from generation.html_sanitizer import (
        sanitize_html,
        write_sanitized_html,
        write_sanitizer_report,
    )
    from generation.stitch_adapter import (
        StitchAdapter,
        StitchGenerationRequest,
    )
    from generation.stitch_prompt_builder import (
        StitchPromptInput,
        build_premium_stitch_prompt,
    )

    from phases.phase_05_preview_site_generation import write_screenshot_png
except ModuleNotFoundError:  # pragma: no cover
    from packages.generation.html_sanitizer import (
        sanitize_html,
        write_sanitized_html,
        write_sanitizer_report,
    )
    from packages.generation.stitch_adapter import (
        StitchAdapter,
        StitchGenerationRequest,
    )
    from packages.generation.stitch_prompt_builder import (
        StitchPromptInput,
        build_premium_stitch_prompt,
    )
    from packages.phases.phase_05_preview_site_generation import write_screenshot_png


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_facts_md(path: Path) -> dict[str, str]:
    facts: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("- ") or ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        facts[key.strip()] = value.strip()
    return facts


def _load_phase_04_5_context(
    root: Path, run_id: str, business_slug: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    enrich_dir = root / "runs" / run_id / PHASE_04_5_SLUG / business_slug
    vp_path = enrich_dir / "visual_profile.json"
    ci_path = enrich_dir / "copy_inputs.json"
    visual_profile = read_json(str(vp_path)) if vp_path.exists() else {}
    copy_inputs = read_json(str(ci_path)) if ci_path.exists() else {}
    return visual_profile, copy_inputs


def _load_business_intelligence(root: Path, run_id: str, business_slug: str) -> dict[str, Any]:
    scored_path = root / "runs" / run_id / PHASE_03_SLUG / "leads_scored.json"
    if not scored_path.exists():
        return {}
    scored = read_json(str(scored_path))
    if not isinstance(scored, list):
        return {}
    for row in scored:
        if not isinstance(row, dict):
            continue
        if _safe_str(row.get("business_slug")) != business_slug:
            continue
        business_intelligence = row.get("business_intelligence")
        return business_intelligence if isinstance(business_intelligence, dict) else {}
    return {}


def _load_run_config(root: Path, run_id: str) -> dict[str, Any]:
    config_path = root / "runs" / run_id / "config" / "run_config.json"
    if config_path.exists():
        return read_json(str(config_path))
    alt = root / "runs" / run_id / "config" / "input_config.json"
    if alt.exists():
        return read_json(str(alt))
    return {}


def _build_fact_usage(
    run_id: str,
    record_id: str,
    business_slug: str,
    deploy_mode: str,
    facts: dict[str, str],
    visual_profile: dict[str, Any],
    sanitizer_findings_count: int,
    hard_block: bool,
) -> dict[str, Any]:
    facts_used = [
        {"field": k, "value": v, "source": "FACTS.md", "site_location": "stitch_generated"}
        for k, v in facts.items()
    ]
    return {
        "run_id": run_id,
        "record_id": record_id,
        "business_slug": business_slug,
        "generation_mode": "premium_stitch",
        "deploy_mode": deploy_mode,
        "visual_profile": {
            "preset_id": _safe_str(visual_profile.get("preset_id")),
            "hero_mode": _safe_str(visual_profile.get("hero_mode")),
            "photo_policy": _safe_str(visual_profile.get("photo_policy")),
            "accent_color_candidate": _safe_str(visual_profile.get("accent_color_candidate")),
        },
        "facts_used": facts_used,
        "facts_omitted": [],
        "sanitizer_findings_count": sanitizer_findings_count,
        "hard_block": hard_block,
        "needs_review": bool(sanitizer_findings_count) or hard_block,
        "notes": [],
    }


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------

def build_stitch_site_record(
    root: Path,
    run_id: str,
    brief_row: dict[str, Any],
    stitch_client: Any,
    *,
    project_id: str | None = None,
    design_system: str | None = None,
    device_type: str = "MOBILE",
    model_id: str = "GEMINI_3_1_PRO",
) -> dict[str, Any]:
    """Build a single premium Stitch site record.

    Returns a build_status dict — same shape as deterministic Phase 05.
    """
    business_slug = _safe_str(brief_row.get("business_slug"))
    record_id = _safe_str(brief_row.get("record_id"))

    # --- read inputs ---
    brief_dir = root / "runs" / run_id / "04_briefs" / business_slug
    facts = _parse_facts_md(brief_dir / "FACTS.md")
    visual_profile, copy_inputs = _load_phase_04_5_context(root, run_id, business_slug)
    business_intelligence = _load_business_intelligence(root, run_id, business_slug)
    run_config = _load_run_config(root, run_id)
    
    # Load vnext flags
    from packages.pipeline.vnext_integration import get_vnext_flags
    vnext_flags = get_vnext_flags(run_config)
    
    deploy_mode = _safe_str(run_config.get("deploy_mode")) or "production_deploy_mode"

    business_name = _safe_str(facts.get("business_name")) or business_slug
    category = _safe_str(facts.get("category")) or "Local business"

    # --- build prompt ---
    creative_spec_path = brief_dir / "creative_spec.json"
    if vnext_flags.get("use_stitch_compiler") and creative_spec_path.exists():
        from packages.generation.stitch_compiler import compile_creative_spec_to_prompt
        creative_spec = read_json(str(creative_spec_path))
        logger.info("VNEXT-05: Using creative_spec via stitch_compiler for %s", business_slug)
        premium_prompt = compile_creative_spec_to_prompt(creative_spec, run_config)
    else:
        prompt_input = StitchPromptInput(
            business_name=business_name,
            business_slug=business_slug,
            category=category,
            facts=facts,
            copy_inputs=copy_inputs,
            visual_profile=visual_profile,
            business_intelligence=business_intelligence,
            deploy_mode=deploy_mode,
        )
        premium_prompt = build_premium_stitch_prompt(prompt_input)

    output_dir = root / "runs" / run_id / PHASE_SLUG / business_slug
    site_dir = output_dir / "site"
    site_dir.mkdir(parents=True, exist_ok=True)

    request = StitchGenerationRequest(
        run_id=run_id,
        record_id=record_id,
        business_slug=business_slug,
        business_name=business_name,
        prompt=premium_prompt.prompt,
        prompt_contract=premium_prompt.prompt_contract,
        output_dir=output_dir,
        project_title=f"{business_name} — {business_slug}",
        project_id=project_id,
        design_system=design_system,
        device_type=device_type,
        model_id=model_id,
    )

    # --- generate via Stitch (with retry for SVG-only output) ---
    adapter = StitchAdapter(stitch_client)
    result = None
    for attempt in range(1, _MAX_GENERATION_ATTEMPTS + 1):
        result = adapter.generate(request)
        if result.status != "retryable_error":
            break
        if attempt < _MAX_GENERATION_ATTEMPTS:
            logger.warning(
                "Stitch generation attempt %d/%d for %s returned retryable_error: %s — retrying",
                attempt, _MAX_GENERATION_ATTEMPTS, business_slug, result.errors,
            )
            # Clean output dir before retry so stale HTML doesn't confuse next attempt
            import shutil
            if output_dir.exists():
                shutil.rmtree(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            site_dir.mkdir(parents=True, exist_ok=True)
        else:
            logger.error(
                "Stitch generation failed after %d attempts for %s: %s",
                _MAX_GENERATION_ATTEMPTS, business_slug, result.errors,
            )

    # After exhausting retries on retryable_error, treat as failed
    if result.status == "retryable_error":
        result = result  # already assigned; will hit the "failed" branch below
        # Replace status with "failed" for downstream consumers
        from dataclasses import replace as _dc_replace
        result = _dc_replace(result, status="failed")

    if result.status == "failed":
        build_status = {
            "run_id": run_id,
            "record_id": record_id,
            "business_slug": business_slug,
            "status": "failed",
            "generation_mode": "premium_stitch",
            "deploy_mode": deploy_mode,
            "errors": result.errors,
            "risks": result.risks,
        }
        write_json(str(output_dir / "build_status.json"), build_status)
        return build_status

    # --- find HTML from downloaded assets ---
    html_path = result.html_path
    if html_path:
        raw_html = Path(html_path).read_text(encoding="utf-8")
    else:
        # fallback: look in output_dir
        candidates = [output_dir / "index.html", output_dir / "site" / "index.html"]
        for c in candidates:
            if c.exists():
                raw_html = c.read_text(encoding="utf-8")
                html_path = str(c)
                break
        else:
            build_status = {
                "run_id": run_id,
                "record_id": record_id,
                "business_slug": business_slug,
                "status": "failed",
                "generation_mode": "premium_stitch",
                "deploy_mode": deploy_mode,
                "errors": ["No HTML found in Stitch download"],
                "risks": ["premium_stitch_no_html"],
            }
            write_json(str(output_dir / "build_status.json"), build_status)
            return build_status

    # --- sanitize ---
    verified_facts = dict(facts)
    san_result = sanitize_html(raw_html, verified_facts=verified_facts)
    write_sanitizer_report(san_result, output_dir)

    if san_result.hard_block:
        build_status = {
            "run_id": run_id,
            "record_id": record_id,
            "business_slug": business_slug,
            "status": "hard_blocked",
            "generation_mode": "premium_stitch",
            "deploy_mode": deploy_mode,
            "hard_block_reasons": san_result.hard_block_reasons,
            "risks": ["html_sanitizer_hard_block"],
        }
        write_json(str(output_dir / "build_status.json"), build_status)
        return build_status

    # --- write sanitized HTML ---
    write_sanitized_html(san_result, site_dir / "index.html")

    # --- write minimal styles.css if none present ---
    styles_path = site_dir / "styles.css"
    if not styles_path.exists():
        styles_path.write_text(_MINIMAL_CSS, encoding="utf-8")

    # --- screenshots (deterministic placeholders) ---
    write_screenshot_png(output_dir / "screenshot_desktop.png", 1280, 800, business_name)
    write_screenshot_png(output_dir / "screenshot_mobile.png", 390, 844, business_name)

    # --- fact usage report (simplified) ---
    fact_usage = _build_fact_usage(
        run_id=run_id,
        record_id=record_id,
        business_slug=business_slug,
        deploy_mode=deploy_mode,
        facts=facts,
        visual_profile=visual_profile,
        sanitizer_findings_count=len(san_result.findings),
        hard_block=san_result.hard_block,
    )
    write_json(str(output_dir / "fact_usage_report.json"), fact_usage)

    # --- build_status ---
    build_status = {
        "run_id": run_id,
        "record_id": record_id,
        "business_slug": business_slug,
        "status": "done",
        "generation_mode": "premium_stitch",
        "deploy_mode": deploy_mode,
        "visual_profile": {
            "preset_id": _safe_str(visual_profile.get("preset_id")),
            "hero_mode": _safe_str(visual_profile.get("hero_mode")),
            "photo_policy": _safe_str(visual_profile.get("photo_policy")),
        },
        "site_path": f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/site",
        "screenshots": {
            "desktop": {
                "path": f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/screenshot_desktop.png",
                "width": 1280,
                "height": 800,
            },
            "mobile": {
                "path": f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/screenshot_mobile.png",
                "width": 390,
                "height": 844,
            },
            "capture_mode": "deterministic_fallback",
        },
        "notes": fact_usage["notes"],
    }
    write_json(str(output_dir / "build_status.json"), build_status)
    return build_status


# ---------------------------------------------------------------------------
# Phase runner
# ---------------------------------------------------------------------------

def run_stitch_phase_05(
    run_id: str,
    workspace: str,
    stitch_client: Any,
    *,
    project_id: str | None = None,
    design_system: str | None = None,
    device_type: str = "MOBILE",
    model_id: str = "GEMINI_3_1_PRO",
) -> dict[str, Any]:
    """Run premium Stitch Phase 05 over all preview-ready briefs."""
    root = Path(workspace)
    preview_ready_path = root / "runs" / run_id / "04_briefs" / "preview_ready_briefs.json"
    blocked_path = root / "runs" / run_id / "04_briefs" / "blocked_no_recipient_channel.json"

    if not preview_ready_path.exists():
        return ResultEnvelope.blocked(
            phase=PHASE_NAME,
            run_id=run_id,
            missing_fields=["preview_ready_briefs.json"],
            errors=["Phase 04 preview-ready briefs required before Phase 05 Stitch"],
            inputs_used=[],
        ).to_dict()

    preview_ready = read_json(str(preview_ready_path))
    blocked = read_json(str(blocked_path)) if blocked_path.exists() else []
    blocked_lookup = {row.get("business_slug"): row for row in blocked}

    output_root = root / "runs" / run_id / PHASE_SLUG
    output_root.mkdir(parents=True, exist_ok=True)

    build_statuses: list[dict[str, Any]] = []
    skipped_blocked = 0
    errors: list[str] = []

    for row in preview_ready:
        business_slug = _safe_str(row.get("business_slug"))
        if business_slug in blocked_lookup and not bool(row.get("manual_override", False)):
            skipped_blocked += 1
            continue
        status = build_stitch_site_record(
            root, run_id, row, stitch_client,
            project_id=project_id,
            design_system=design_system,
            device_type=device_type,
            model_id=model_id,
        )
        build_statuses.append(status)
        if status.get("status") in ("failed", "hard_blocked"):
            errors.extend(status.get("errors", []))
            errors.extend(status.get("hard_block_reasons", []))

    done_count = sum(1 for s in build_statuses if s.get("status") == "done")
    failed_count = sum(1 for s in build_statuses if s.get("status") in ("failed", "hard_blocked"))

    result = ResultEnvelope(
        phase=PHASE_NAME,
        status="done",
        run_id=run_id,
        inputs_used=[
            f"runs/{run_id}/04_briefs/preview_ready_briefs.json",
            f"runs/{run_id}/04_briefs/blocked_no_recipient_channel.json",
        ],
        outputs_created=[
            *[f"runs/{run_id}/{PHASE_SLUG}/{s['business_slug']}/site" for s in build_statuses],
            *[f"runs/{run_id}/{PHASE_SLUG}/{s['business_slug']}/site/styles.css" for s in build_statuses],
            *[f"runs/{run_id}/{PHASE_SLUG}/{s['business_slug']}/build_status.json" for s in build_statuses],
            *[f"runs/{run_id}/{PHASE_SLUG}/{s['business_slug']}/fact_usage_report.json" for s in build_statuses],
            *[f"runs/{run_id}/{PHASE_SLUG}/{s['business_slug']}/screenshot_desktop.png" for s in build_statuses],
            *[f"runs/{run_id}/{PHASE_SLUG}/{s['business_slug']}/screenshot_mobile.png" for s in build_statuses],
            f"runs/{run_id}/{PHASE_SLUG}/result.json",
        ],
        records_processed=len(preview_ready),
        records_created=done_count,
        records_skipped=skipped_blocked,
        decisions=[
            f"Generated {done_count} premium Stitch site(s)",
            f"Skipped {skipped_blocked} blocked brief(s)",
            f"Failed/hard_blocked: {failed_count}",
        ],
        risks=(
            [f"{failed_count} site(s) failed or hard_blocked"]
            if failed_count
            else []
        ),
        errors=errors,
        next_tasks=["Phase 06 — Quality Gate"],
    ).model_dump(exclude_none=True, by_alias=True)

    write_json(str(output_root / "result.json"), result)
    return result
