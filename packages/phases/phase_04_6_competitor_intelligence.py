"""
Phase 04.6 — Competitor Intelligence.

Generate a competitor_profile.json for each lead from curated benchmark
fixtures. The profile contains structural niche patterns (sections, CTAs,
colors, layouts) — never competitor content, images, logos, or brand marks.

Feature-flagged behind ``use_competitor_intelligence`` (default OFF).
Scope controlled by ``competitor_scope``: "none" (disabled), "fixtures_only"
(default when enabled), "curated" (future).

Inputs:
  - runs/{run_id}/config/input_config.json
  - runs/{run_id}/04_briefs/preview_ready_briefs.json

Outputs (when flag is ON):
  - runs/{run_id}/04_6_competitor_intelligence/{business_slug}/competitor_profile.json
  - runs/{run_id}/04_6_competitor_intelligence/result.json
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:  # pragma: no cover
    from pipeline.json_io import read_json, write_json
    from pipeline.result_envelope import ResultEnvelope, Status
except ModuleNotFoundError:  # pragma: no cover
    from packages.pipeline.json_io import read_json, write_json
    from packages.pipeline.result_envelope import ResultEnvelope, Status

from packages.intelligence.competitor_intelligence import (
    build_competitor_profile,
    write_competitor_profile,
)
from packages.shared.provenance import _safe_str

PHASE_SLUG = "04_6_competitor_intelligence"
PHASE_NAME = "phase_04_6_competitor_intelligence"
USE_COMPETITOR_INTELLIGENCE_FLAG = "use_competitor_intelligence"

DEFAULT_SCOPE = "fixtures_only"


def run_phase_04_6(
    run_id: str,
    workspace: str,
    config: dict | None = None,
) -> dict[str, Any]:
    """Run competitor intelligence phase if flag enabled.

    Parameters
    ----------
    run_id:
        Run identifier.
    workspace:
        Root workspace directory.
    config:
        Run-level config dict. Must contain
        ``use_competitor_intelligence: true`` to activate.

    Returns
    -------
    Result envelope dict.
    """
    cfg = config or {}

    # Feature-flag gate
    if not cfg.get(USE_COMPETITOR_INTELLIGENCE_FLAG):
        return ResultEnvelope(
            phase=PHASE_NAME,
            status=Status.SKIPPED,
            run_id=run_id,
            decisions=["use_competitor_intelligence flag is OFF"],
        ).to_dict()

    # Scope gate
    scope = _safe_str(cfg.get("competitor_scope", DEFAULT_SCOPE))
    if scope == "none":
        return ResultEnvelope(
            phase=PHASE_NAME,
            status=Status.SKIPPED,
            run_id=run_id,
            decisions=["competitor_scope is 'none'"],
        ).to_dict()

    root = Path(workspace)

    # Read briefs index
    briefs_index_path = (
        root / "runs" / run_id / "04_briefs" / "preview_ready_briefs.json"
    )
    if not briefs_index_path.exists():
        return ResultEnvelope.blocked(
            phase=PHASE_NAME,
            run_id=run_id,
            missing_fields=["preview_ready_briefs.json"],
        ).to_dict()

    briefs_index = read_json(str(briefs_index_path))
    leads = briefs_index.get("leads", briefs_index) if isinstance(briefs_index, dict) else briefs_index
    if not isinstance(leads, list):
        leads = []

    output_dir = root / "runs" / run_id / PHASE_SLUG
    output_dir.mkdir(parents=True, exist_ok=True)

    processed: list[str] = []
    errors: list[str] = []
    outputs_created: list[str] = []

    for lead in leads:
        if not isinstance(lead, dict):
            continue

        business_slug = _safe_str(lead.get("business_slug"))
        if not business_slug:
            errors.append("lead missing business_slug")
            continue

        category = _safe_str(lead.get("category", ""))
        area = _safe_str(lead.get("area", ""))

        profile = build_competitor_profile(
            category=category,
            area=area,
            config=cfg,
            run_id=run_id,
            business_slug=business_slug,
        )

        path_out = write_competitor_profile(profile, str(output_dir), business_slug)
        processed.append(business_slug)
        outputs_created.append(path_out)

    # Write phase result
    phase_result = {
        "phase": PHASE_NAME,
        "run_id": run_id,
        "processed": processed,
        "errors": errors,
        "scope": scope,
    }
    write_json(str(output_dir / "result.json"), phase_result)

    return ResultEnvelope.done(
        phase=PHASE_NAME,
        run_id=run_id,
        inputs_used=[str(briefs_index_path)],
        outputs_created=outputs_created,
        records_processed=len(processed),
        records_created=len(processed),
        decisions=[f"competitor_scope={scope}"],
    ).to_dict()
