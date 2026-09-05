"""End-to-End Pipeline Orchestrator.

Runs all phases (01 to 09) in sequence.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
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
from packages.pipeline.failure_semantics import (
    Phase06DecisionError,
    classify_failure,
    classify_phase_status,
    parse_phase_06_decisions,
)
from packages.pipeline.slug import safe_path
from packages.pipeline.state_db import StateDB
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
from packages.shared.logging_config import set_log_context

logger = logging.getLogger(__name__)


def make_run_id() -> str:
    """Return a collision-proof run identifier.

    Keeps the documented ``run_<timestamp>`` layout (ARCHITECTURE.md/README:
    ``runs/run_<timestamp>``, test glob ``runs/run_*``) and appends a UUID
    suffix so concurrent runs started within the same second cannot collide
    (U-15). ``run_id`` is consumed as an opaque string across the pipeline.
    """
    return f"run_{int(time.time())}_{uuid.uuid4().hex}"


# ---------------------------------------------------------------------------
# R1-03: idempotency / resume helpers (active only when run_state_db is on)
# ---------------------------------------------------------------------------

# Phase key -> run-directory name under runs/<run_id>/, used for recording
# result paths and for cleaning partial artifacts before a re-run. Phase 05.5
# (render capture) runs inside phase 05 and has no directory of its own.
_PHASE_DIR_NAMES: dict[str, str] = {
    "01": "01_input",
    "02": "02_discovery",
    "02.1": "02_1_website_filter",
    "03": "03_scoring",
    "04": "04_briefs",
    "04.5": "04_5_enrichment",
    "05": "05_sites",
    "06": "06_quality",
    "07": "07_deployments",
    "08": "08_outreach",
    "09": "09_review",
}

# Phases that accept "needs_review" as a success status (all others: "done").
_PHASE_REVIEW_OK = ("02", "02.1")

_ENV_TRUTHY = {"1", "true", "yes", "on"}
_ENV_FALSY = {"0", "false", "no", "off"}


def _run_state_db_enabled(flags: dict[str, bool]) -> bool:
    """Resolve the ``run_state_db`` feature flag (R1-03).

    Precedence: a set ``RUN_STATE_DB`` environment variable (``1/true/yes/on``
    or ``0/false/no/off``) overrides the config flag, so a demo can toggle
    resume without code changes. Unset/empty env var -> config flag value.
    """
    raw = os.environ.get("RUN_STATE_DB", "").strip().lower()
    if raw in _ENV_TRUTHY:
        return True
    if raw in _ENV_FALSY:
        return False
    return bool(flags.get("run_state_db"))


def _phase_success_statuses(phase_key: str) -> tuple[str, ...]:
    return ("done", "needs_review") if phase_key in _PHASE_REVIEW_OK else ("done",)


def _resumable_execution(
    state_db: StateDB | None, run_id: str, phase_key: str, workspace: str
) -> dict | None:
    """Return the previous successful execution row for ``phase_key``, else ``None``.

    When a previous execution exists but did not succeed, its partial artifact
    directory is removed and ``None`` is returned so the phase re-runs cleanly.
    The cleanup also runs when no row was recorded at all (hard-killed phase —
    SIGKILL leaves stale artifacts but no ``phase_executions`` row).
    Always returns ``None`` when ``state_db`` is ``None`` (flag off) — no DB
    lookups happen on the legacy path.
    """
    if state_db is None:
        return None
    prev = state_db.get_phase_execution(run_id, phase_key)
    if prev is None:
        # No recorded execution: either a first run (dir absent, cleanup is a
        # no-op) or a hard-killed phase (stale dir must not survive the re-run).
        _clean_phase_artifacts(workspace, run_id, phase_key)
        return None
    if prev.get("status") in _phase_success_statuses(phase_key):
        logger.info("Phase %s already complete, skipping (resume).", phase_key)
        return prev
    _clean_phase_artifacts(workspace, run_id, phase_key)
    return None


def _clean_phase_artifacts(workspace: str, run_id: str, phase_key: str) -> None:
    """Delete a phase's partial artifact directory before a clean re-run."""
    dir_name = _PHASE_DIR_NAMES.get(phase_key)
    if not dir_name:
        return
    phase_dir = safe_path(workspace, "runs", run_id, dir_name)
    if phase_dir.exists():
        shutil.rmtree(phase_dir, ignore_errors=True)
        logger.info(
            "Removed partial artifacts for phase %s (runs/%s/%s) before re-run.",
            phase_key, run_id, dir_name,
        )


# Result-envelope keys that may carry per-record failure lists (R1-05).
_FAILED_ITEM_KEYS = ("failed_records", "failed_leads", "failed_items")

# Envelope keys mirrored into the recorded counts block (R1-06).
_COUNT_KEYS = ("records_succeeded", "records_failed", "records_processed", "records_created", "records_skipped")


def _phase_result_path(workspace: str, run_id: str, phase_key: str) -> Path | None:
    """Result-envelope path for ``phase_key``, or ``None`` when it has no directory."""
    dir_name = _PHASE_DIR_NAMES.get(phase_key)
    return safe_path(workspace, "runs", run_id, dir_name) / "result.json" if dir_name else None


def _join_errors(errors: Any) -> str:
    """Join an envelope ``errors`` list into one human-readable message."""
    if isinstance(errors, list) and errors:
        return "; ".join(str(item) for item in errors)
    return str(errors or "")


def _phase_counts(result: dict, *, success: bool) -> dict[str, int]:
    """Counts block for the recorded result payload (R1-06).

    Envelope count keys are mirrored when present; when the envelope carries no
    succeeded/failed counts, a status-derived ``1`` succeeded (or failed) is stored.
    """
    counts: dict[str, int] = {}
    for key in _COUNT_KEYS:
        value = result.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            counts[key] = value
    if "records_succeeded" not in counts and "records_failed" not in counts:
        counts["records_succeeded" if success else "records_failed"] = 1
    return counts


def _record_dead_letters(
    state_db: StateDB, run_id: str, phase_key: str, result: dict, failure: dict
) -> None:
    """Write dead letters for a failed phase result (R1-05; callers gate on the flag).

    One dead letter per item when the envelope carries a failed-item list under a
    known key, otherwise one dead letter for the failed phase itself.
    """
    category = failure["category"]
    detail = failure["error"]
    for key in _FAILED_ITEM_KEYS:
        items = result.get(key)
        if isinstance(items, list) and items:
            for item in items:
                record = item if isinstance(item, dict) else {"value": item}
                item_detail = str(item.get("error") or detail) if isinstance(item, dict) else detail
                state_db.record_dead_letter(run_id, phase_key, record, category, detail=item_detail)
            return
    state_db.record_dead_letter(
        run_id,
        phase_key,
        {"phase": phase_key, "status": str(result.get("status", "unknown")), "errors": result.get("errors") or []},
        category,
        detail=detail,
    )


def _record_phase_execution(
    state_db: StateDB | None,
    run_id: str,
    phase_key: str,
    result: Any,
    workspace: str,
    *,
    duration_ms: int | None = None,
) -> dict | None:
    """Write-through record of one phase execution (no-op when the flag is off).

    Returns the serialized failure context (R1-04) when the result is a failure
    outcome, else ``None``. The context is built regardless of the flag so the
    run summary and logs carry structured failures on the legacy path too; the
    DB writes (payload with counts/failure, dead letters) only happen when
    ``state_db`` is present.
    """
    failure: dict | None = None
    artifact_path = _phase_result_path(workspace, run_id, phase_key)
    if isinstance(result, dict):
        status = str(result.get("status", "unknown"))
        if status not in _phase_success_statuses(phase_key):
            failure = classify_failure(
                phase_key,
                status=status,
                error=_join_errors(result.get("errors")),
                run_id=run_id,
                artifact=str(artifact_path) if artifact_path else None,
            ).to_dict()
            logger.error("Phase %s failure classified: %s", phase_key, json.dumps(failure))
    if state_db is None or not isinstance(result, dict):
        return failure
    success = str(result.get("status", "unknown")) in _phase_success_statuses(phase_key)
    payload = dict(result)
    payload["counts"] = _phase_counts(result, success=success)
    if failure is not None:
        payload["failure"] = failure
    state_db.record_phase_execution(
        run_id,
        phase_key,
        str(result.get("status", "unknown")),
        result=payload,
        result_path=str(artifact_path) if artifact_path else None,
        duration_ms=duration_ms,
    )
    if artifact_path is not None and artifact_path.exists():
        state_db.record_artifact(run_id, phase_key, "outputs", str(artifact_path))
    if failure is not None:
        _record_dead_letters(state_db, run_id, phase_key, result, failure)
    return failure


def _elapsed_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def lead_fingerprint(lead: dict[str, Any]) -> str:
    """Stable fingerprint for a lead: sha256 over normalized (name, address, place_id).

    Text fields are trimmed and lower-cased; ``place_id`` falls back to
    ``maps_url`` when the discovery source does not provide a Google place id.
    """
    name = str(lead.get("business_name") or lead.get("name") or "").strip().lower()
    address = str(lead.get("address") or "").strip().lower()
    place_id = str(lead.get("place_id") or lead.get("maps_url") or "").strip()
    payload = json.dumps([name, address, place_id], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _dedupe_selected_leads(
    state_db: StateDB | None, run_id: str, selected_leads: list
) -> tuple[list, list[str]]:
    """Cross-run lead dedupe via ``lead_fingerprints`` (R1-03, minimal scope).

    Returns ``(new_leads, skipped_slugs)``. Coverage is deliberately narrow and
    honest: only the orchestrator-level lead list is filtered (the
    ``leads_selected`` summary count and the vNext post-phase helpers). Phase
    modules read their own on-disk artifacts and are not filtered, and the
    pass runs when phase 03 executed freshly in the current invocation; on
    resume the read-only ``_filter_leads_on_resume`` takes over instead.
    """
    if state_db is None:
        return selected_leads, []
    new_leads: list = []
    skipped: list[str] = []
    for lead in selected_leads:
        if not isinstance(lead, dict):
            new_leads.append(lead)
            continue
        fingerprint = lead_fingerprint(lead)
        if state_db.record_lead_fingerprint(fingerprint, run_id, "03"):
            new_leads.append(lead)
        else:
            skipped.append(
                str(lead.get("business_slug") or lead.get("business_name") or lead.get("record_id") or "unknown")
            )
    for slug in skipped:
        logger.info(
            "Lead '%s' already processed in a previous run, skipping (fingerprint dedupe).", slug
        )
    return new_leads, skipped

def _filter_leads_on_resume(state_db: StateDB, run_id: str, selected_leads: list) -> list:
    """Resume-path lead filter: drop leads fingerprinted by OTHER runs.

    Read-only on purpose — no new fingerprints are written. Leads kept by this
    run's original attempt are recorded under this ``run_id`` and must survive
    the resume, while leads already handled by an earlier run must not re-enter
    phase 04+ just because phase 03 was skipped on resume.
    """
    kept: list = []
    for lead in selected_leads:
        if not isinstance(lead, dict):
            kept.append(lead)
            continue
        if state_db.has_fingerprint(lead_fingerprint(lead), exclude_run_id=run_id):
            logger.info(
                "Lead '%s' already processed in a previous run, skipping on resume (fingerprint).",
                str(lead.get("business_slug") or lead.get("business_name") or lead.get("record_id") or "unknown"),
            )
        else:
            kept.append(lead)
    return kept

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
    run_id: str | None = None,
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
        run_id: Optional explicit run id. When omitted a fresh id is generated;
            pass the id of an interrupted run to resume it (requires the
            ``run_state_db`` flag, see below).

    Returns:
        Summary dict of run

    Resume & idempotency (R1-03): with the ``run_state_db`` flag enabled, run
    state is mirrored into ``<workspace>/runs/state.db``. Re-invoking with the
    same ``run_id`` skips already-completed phases, cleans partial artifacts of
    failed ones, and dedupes repeat leads via ``lead_fingerprints``. Enable via
    ``vnext_flags={"run_state_db": True}`` or the ``RUN_STATE_DB=1`` env var.
    With the flag off, behavior is unchanged and no DB is created.
    """
    flags = get_vnext_flags({"vnext_flags": vnext_flags or {}})
    if not _run_state_db_enabled(flags):
        return _run_full_pipeline_impl(
            niche=niche,
            area=area,
            country=country,
            workspace=workspace,
            stitch_client=stitch_client,
            model_id=model_id,
            generation_mode=generation_mode,
            deploy_provider=deploy_provider,
            discovery_source=discovery_source,
            max_preview_sites=max_preview_sites,
            price_offer=price_offer,
            dry_run=dry_run,
            production_mode=production_mode,
            vnext_flags=vnext_flags,
            run_id=run_id,
            state_db=None,
        )

    resolved_run_id = run_id or make_run_id()
    with StateDB(workspace) as db:
        db.record_run_start(
            resolved_run_id,
            summary={
                "niche": niche,
                "area": area,
                "country": country,
                "generation_mode": generation_mode,
            },
        )
        try:
            summary = _run_full_pipeline_impl(
                niche=niche,
                area=area,
                country=country,
                workspace=workspace,
                stitch_client=stitch_client,
                model_id=model_id,
                generation_mode=generation_mode,
                deploy_provider=deploy_provider,
                discovery_source=discovery_source,
                max_preview_sites=max_preview_sites,
                price_offer=price_offer,
                dry_run=dry_run,
                production_mode=production_mode,
                vnext_flags=vnext_flags,
                run_id=resolved_run_id,
                state_db=db,
            )
        except Exception as exc:
            failure_ctx = classify_failure("pipeline", status=None, error=str(exc), run_id=resolved_run_id)
            logger.error("Run %s failed unhandled: %s", resolved_run_id, json.dumps(failure_ctx.to_dict()))
            db.record_run_finish(
                resolved_run_id,
                status="failed",
                summary={"errors": ["unhandled exception during run"], "failures": [failure_ctx.to_dict()]},
            )
            raise
        db.record_run_finish(
            resolved_run_id,
            status="failed" if summary.get("errors") else "done",
            summary=summary,
        )
        return summary


def _run_full_pipeline_impl(
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
    run_id: str | None = None,
    state_db: StateDB | None = None,
) -> dict[str, Any]:
    """Phase-dispatch body of :func:`run_full_pipeline` (see it for the contract)."""
    start_time = time.time()
    run_id = run_id or make_run_id()

    with set_log_context(run_id=run_id):

        logger.info(f"Starting full pipeline run {run_id} for niche='{niche}' area='{area}'...")

        phases_completed = []
        errors = []
        failures: list[dict] = []
        phase_03_ran_fresh = False

        def _finish_summary(*args: Any, **kwargs: Any) -> dict[str, Any]:
            """Summary shim: every summary carries failures + phase metrics (R1-04/R1-06)."""
            return _make_summary(
                *args,
                failures=failures,
                phase_metrics=state_db.phase_metrics(run_id) if state_db is not None else None,
                **kwargs,
            )

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

        with set_log_context(phase="01"):
            if _resumable_execution(state_db, run_id, "01", workspace) is not None:
                phases_completed.append("01")
            else:
                p1_start = time.monotonic()
                p1_res = run_phase_01(run_id, workspace, input_config)
                p1_failure = _record_phase_execution(
                    state_db, run_id, "01", p1_res, workspace, duration_ms=_elapsed_ms(p1_start)
                )
                if p1_res.get("status") != "done":
                    logger.error(f"Phase 01 failed: {p1_res}")
                    errors.append(f"Phase 01 failed: {p1_res.get('errors')}")
                    failures.append(p1_failure)
                    return _finish_summary(run_id, phases_completed, errors, start_time)
                phases_completed.append("01")

        # 2. Phase 02: Lead Discovery
        logger.info("Executing Phase 02: Lead Discovery...")
        with set_log_context(phase="02"):
            if _resumable_execution(state_db, run_id, "02", workspace) is not None:
                phases_completed.append("02")
            else:
                p2_start = time.monotonic()
                p2_res = run_phase_02(run_id, workspace)
                p2_failure = _record_phase_execution(
                    state_db, run_id, "02", p2_res, workspace, duration_ms=_elapsed_ms(p2_start)
                )
                if p2_res.get("status") not in ("done", "needs_review"):
                    logger.error(f"Phase 02 failed: {p2_res}")
                    errors.append(f"Phase 02 failed: {p2_res.get('errors')}")
                    failures.append(p2_failure)
                    return _finish_summary(run_id, phases_completed, errors, start_time)
                phases_completed.append("02")

        # 3. Phase 02.1: Website Filter
        logger.info("Executing Phase 02.1: Website Filter...")
        with set_log_context(phase="02.1"):
            if _resumable_execution(state_db, run_id, "02.1", workspace) is not None:
                phases_completed.append("02.1")
            else:
                p2_1_start = time.monotonic()
                p2_1_res = run_phase_02_1(run_id, workspace)
                p2_1_failure = _record_phase_execution(
                    state_db, run_id, "02.1", p2_1_res, workspace, duration_ms=_elapsed_ms(p2_1_start)
                )
                if p2_1_res.get("status") not in ("done", "needs_review"):
                    logger.error(f"Phase 02.1 failed: {p2_1_res}")
                    errors.append(f"Phase 02.1 failed: {p2_1_res.get('errors')}")
                    failures.append(p2_1_failure)
                    return _finish_summary(run_id, phases_completed, errors, start_time)
                phases_completed.append("02.1")

        # 4. Phase 03: Lead Scoring
        logger.info("Executing Phase 03: Lead Scoring...")
        with set_log_context(phase="03"):
            if _resumable_execution(state_db, run_id, "03", workspace) is not None:
                phases_completed.append("03")
            else:
                phase_03_ran_fresh = True
                p3_start = time.monotonic()
                p3_res = run_phase_03(run_id, workspace)
                p3_failure = _record_phase_execution(
                    state_db, run_id, "03", p3_res, workspace, duration_ms=_elapsed_ms(p3_start)
                )
                if p3_res.get("status") != "done":
                    logger.error(f"Phase 03 failed: {p3_res}")
                    errors.append(f"Phase 03 failed: {p3_res.get('errors')}")
                    failures.append(p3_failure)
                    return _finish_summary(run_id, phases_completed, errors, start_time)
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

        # ── R1-03: cross-run lead fingerprint dedupe. Fresh phase 03 records
        # fingerprints and filters; on resume a read-only filter re-applies the
        # cross-run exclusion without touching this run's own fingerprints. ──
        if phase_03_ran_fresh:
            selected_leads, _dedupe_skipped = _dedupe_selected_leads(state_db, run_id, selected_leads)
        elif state_db is not None:
            selected_leads = _filter_leads_on_resume(state_db, run_id, selected_leads)

        if not selected_leads:
            logger.warning("No leads selected for preview site generation. Ending run.")
            return _finish_summary(run_id, phases_completed, errors, start_time, leads_selected=0)

        # ── vNext: VNEXT-02 market_profile per selected lead ──
        flags = get_vnext_flags(input_config)
        # run_state_db is pipeline infrastructure, not a creative capability —
        # exclude it so enabling resume does not trip any() vNext gating below.
        flags.pop("run_state_db", None)
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
        with set_log_context(phase="04"):
            if _resumable_execution(state_db, run_id, "04", workspace) is not None:
                phases_completed.append("04")
            else:
                p4_start = time.monotonic()
                p4_res = run_phase_04(run_id, workspace)
                p4_failure = _record_phase_execution(
                    state_db, run_id, "04", p4_res, workspace, duration_ms=_elapsed_ms(p4_start)
                )
                if p4_res.get("status") != "done":
                    logger.error(f"Phase 04 failed: {p4_res}")
                    errors.append(f"Phase 04 failed: {p4_res.get('errors')}")
                    failures.append(p4_failure)
                    return _finish_summary(run_id, phases_completed, errors, start_time, leads_selected=len(selected_leads))
                phases_completed.append("04")

        # 6. Phase 04.5: Enrichment
        logger.info("Executing Phase 04.5: Enrichment...")
        with set_log_context(phase="04.5"):
            if _resumable_execution(state_db, run_id, "04.5", workspace) is not None:
                phases_completed.append("04.5")
            else:
                p4_5_start = time.monotonic()
                p4_5_res = run_phase_04_5(run_id, workspace)
                p4_5_failure = _record_phase_execution(
                    state_db, run_id, "04.5", p4_5_res, workspace, duration_ms=_elapsed_ms(p4_5_start)
                )
                if p4_5_res.get("status") != "done":
                    logger.error(f"Phase 04.5 failed: {p4_5_res}")
                    errors.append(f"Phase 04.5 failed: {p4_5_res.get('errors')}")
                    failures.append(p4_5_failure)
                    return _finish_summary(run_id, phases_completed, errors, start_time, leads_selected=len(selected_leads))
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
        with set_log_context(phase="05"):
            if _resumable_execution(state_db, run_id, "05", workspace) is not None:
                phases_completed.append("05")
            else:
                p5_start = time.monotonic()
                p5_res = run_phase_05_unified(
                    run_id=run_id,
                    workspace=workspace,
                    stitch_client=stitch_client,
                    model_id=model_id,
                    production_mode=production_mode,
                )
                p5_failure = _record_phase_execution(
                    state_db, run_id, "05", p5_res, workspace, duration_ms=_elapsed_ms(p5_start)
                )
                if p5_res.get("status") != "done":
                    logger.error(f"Phase 05 failed: {p5_res}")
                    errors.append(f"Phase 05 failed: {p5_res.get('errors')}")
                    failures.append(p5_failure)
                    return _finish_summary(run_id, phases_completed, errors, start_time, leads_selected=len(selected_leads))
                phases_completed.append("05")

        # 8. Phase 05.5 render capture was executed automatically inside unified run_phase_05_unified
        phases_completed.append("05.5")
        if state_db is not None and state_db.get_phase_execution(run_id, "05.5") is None:
            state_db.record_phase_execution(
                run_id,
                "05.5",
                "done",
                result={"status": "done", "note": "render capture executed inside phase 05"},
            )

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
        with set_log_context(phase="06"):
            if _resumable_execution(state_db, run_id, "06", workspace) is not None:
                phases_completed.append("06")
                # Skipped phases return no fresh envelope; parse the recorded one.
                prev06 = state_db.get_phase_execution(run_id, "06") if state_db else None
                if prev06 and not prev06.get("result_json"):
                    logger.warning(
                        "Phase 06 row is done but result_json is missing; restoring empty decisions."
                    )
                p6_res = json.loads(prev06["result_json"]) if prev06 and prev06.get("result_json") else {"decisions": []}
            else:
                p6_start = time.monotonic()
                p6_res = run_strict_phase_06(run_id, workspace, strict=use_strict)
                p6_failure = _record_phase_execution(
                    state_db, run_id, "06", p6_res, workspace, duration_ms=_elapsed_ms(p6_start)
                )
                if p6_res.get("status") != "done":
                    logger.error(f"Phase 06 failed: {p6_res}")
                    errors.append(f"Phase 06 failed: {p6_res.get('errors')}")
                    failures.append(p6_failure)
                    return _finish_summary(run_id, phases_completed, errors, start_time, leads_selected=len(selected_leads))
                phases_completed.append("06")

        # ── vNext: VNEXT-06 structured evaluation ──
        if any(flags.values()):
            logger.info("Running vNext post-phase-06 integration...")
            run_vnext_post_phase_06(run_id, workspace, selected_leads, input_config)

        # Parse decisions to see approved leads count (U-09: structured parse,
        # fail-closed — a malformed/missing decision line is an explicit hard
        # failure, never a silent fallback to count 0).
        try:
            phase_06_counts = parse_phase_06_decisions(p6_res.get("decisions", []))
        except Phase06DecisionError as exc:
            semantics = classify_phase_status("failed")
            failure_ctx = classify_failure("06", status="failed", error=str(exc), run_id=run_id)
            logger.error(
                "Phase 06 decision parsing failed (%s, fail-closed): %s",
                semantics.failure_class.value,
                exc,
            )
            logger.error("Phase 06 failure classified: %s", json.dumps(failure_ctx.to_dict()))
            errors.append(
                f"Phase 06 decision parsing failed — {semantics.failure_class.value} "
                f"(fail-closed, U-09): {exc}"
            )
            failures.append(failure_ctx.to_dict())
            return _finish_summary(
                run_id, phases_completed, errors, start_time,
                leads_selected=len(selected_leads),
                sites_generated=len(selected_leads),
                sites_approved=0,
            )
        approved_count = phase_06_counts.approved
        needs_edit_count = phase_06_counts.needs_edit

        # In non-strict/template mode, needs_edit sites are acceptable for preview
        passable_count = approved_count + (needs_edit_count if not use_strict else 0)

        if passable_count == 0:
            logger.warning("All generated sites failed Phase 06 quality gate. Stopping before deploy.")
            return _finish_summary(
                run_id, phases_completed, errors, start_time,
                leads_selected=len(selected_leads),
                sites_generated=len(selected_leads),
                sites_approved=0,
            )

        if dry_run:
            logger.info("dry_run=True: Skipping Phase 07 (deploy) and Phase 08 (outreach).")
            return _finish_summary(
                run_id, phases_completed, errors, start_time,
                leads_selected=len(selected_leads),
                sites_generated=len(selected_leads),
                sites_approved=passable_count,
            )

        # 10. Phase 07: Deployment
        logger.info("Executing Phase 07: Deployment...")
        with set_log_context(phase="07"):
            if _resumable_execution(state_db, run_id, "07", workspace) is not None:
                phases_completed.append("07")
            else:
                p7_start = time.monotonic()
                p7_res = run_phase_07(run_id, workspace)
                p7_failure = _record_phase_execution(
                    state_db, run_id, "07", p7_res, workspace, duration_ms=_elapsed_ms(p7_start)
                )
                if p7_res.get("status") != "done":
                    logger.error(f"Phase 07 failed: {p7_res}")
                    errors.append(f"Phase 07 failed: {p7_res.get('errors')}")
                    failures.append(p7_failure)
                    return _finish_summary(
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
        with set_log_context(phase="08"):
            if _resumable_execution(state_db, run_id, "08", workspace) is not None:
                phases_completed.append("08")
            else:
                p8_start = time.monotonic()
                p8_res = run_phase_08(run_id, workspace)
                p8_failure = _record_phase_execution(
                    state_db, run_id, "08", p8_res, workspace, duration_ms=_elapsed_ms(p8_start)
                )
                if p8_res.get("status") != "done":
                    logger.error(f"Phase 08 failed: {p8_res}")
                    errors.append(f"Phase 08 failed: {p8_res.get('errors')}")
                    failures.append(p8_failure)
                    return _finish_summary(
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
        with set_log_context(phase="09"):
            if _resumable_execution(state_db, run_id, "09", workspace) is not None:
                phases_completed.append("09")
            else:
                p9_start = time.monotonic()
                p9_res = run_phase_09(run_id, workspace, skip_missing_stubs=dry_run)
                p9_failure = _record_phase_execution(
                    state_db, run_id, "09", p9_res, workspace, duration_ms=_elapsed_ms(p9_start)
                )
                if p9_res.get("status") != "done":
                    logger.error(f"Phase 09 failed: {p9_res}")
                    errors.append(f"Phase 09 failed: {p9_res.get('errors')}")
                    failures.append(p9_failure)
                    return _finish_summary(
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

        return _finish_summary(
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
    failures: list[dict] | None = None,
    phase_metrics: list[dict] | None = None,
) -> dict[str, Any]:
    duration = int(time.time() - start_time)

    # Compute counts from directories if not passed
    summary = {
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
        "failures": failures or [],
        "duration_seconds": duration,
    }
    if phase_metrics is not None:
        summary["phase_metrics"] = phase_metrics
    return summary
