"""
Phase 04.8 — Creative Specification Generation.

Generate a creative_spec.json for each lead from upstream artifacts:
  - business_profile.json (VNEXT-01)
  - market_profile.json (VNEXT-02)
  - brand_profile.json (VNEXT-03)

This phase is feature-flagged behind `use_creative_spec` (default OFF).
When the flag is OFF, the phase is skipped entirely.

Outputs (when flag is ON):
  - runs/{run_id}/04_8_creative_spec/{business_slug}/creative_spec.json
  - runs/{run_id}/04_8_creative_spec/creative_specs_index.json
  - runs/{run_id}/04_8_creative_spec/result.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from pipeline.json_io import read_json, write_json
    from pipeline.result_envelope import ResultEnvelope, Status
except ModuleNotFoundError:  # pragma: no cover - CLI fallback
    from packages.pipeline.json_io import read_json, write_json
    from packages.pipeline.result_envelope import ResultEnvelope, Status

from packages.creative.creative_spec_builder import (
    build_creative_spec,
    write_creative_spec,
)
from packages.creative.creative_spec_models import FEATURE_FLAG
from packages.creative.creative_spec_validator import validate_creative_spec
from packages.shared.provenance import _safe_str

PHASE_SLUG = "04_8_creative_spec"
PHASE_NAME = "phase_04_8_creative_spec"


def run_phase_04_8(run_id: str, workspace: str) -> dict[str, Any]:
    """Run Phase 04.8 — Creative Specification Generation.

    This phase reads upstream artifacts (business_profile, market_profile,
    brand_profile) and generates a unified creative_spec.json per business.

    Feature-flagged: only runs when `use_creative_spec` is truthy in config.

    Parameters
    ----------
    run_id:
        Run identifier.
    workspace:
        Root workspace directory.

    Returns
    -------
    Result envelope dict.
    """
    root = Path(workspace)
    config_path = root / "runs" / run_id / "config" / "input_config.json"
    briefs_index_path = root / "runs" / run_id / "04_briefs" / "briefs_index.json"

    # Check for required inputs
    missing_fields: list[str] = []
    if not config_path.exists():
        missing_fields.append("input_config.json")
    if not briefs_index_path.exists():
        missing_fields.append("briefs_index.json")

    if missing_fields:
        return ResultEnvelope.blocked(
            phase=PHASE_NAME,
            run_id=run_id,
            missing_fields=missing_fields,
            inputs_used=[],
            errors=["Phase 04 outputs required before Phase 04.8"],
        ).to_dict()

    config = read_json(str(config_path))

    # Feature flag check — skip entirely if OFF
    if not bool(config.get(FEATURE_FLAG, False)):
        return ResultEnvelope(
            phase=PHASE_NAME,
            status=Status.SKIPPED,
            run_id=run_id,
            inputs_used=[f"runs/{run_id}/config/input_config.json"],
            outputs_created=[],
            records_processed=0,
            records_created=0,
            records_skipped=0,
            missing_fields=[],
            decisions=[f"Skipped: {FEATURE_FLAG} flag is OFF"],
            risks=[],
            errors=[],
            next_tasks=[],
        ).model_dump(exclude_none=True, by_alias=True)

    briefs_index = read_json(str(briefs_index_path))
    if not isinstance(briefs_index, list):
        return ResultEnvelope.failed(
            phase=PHASE_NAME,
            run_id=run_id,
            errors=["briefs_index.json is not a list"],
        ).to_dict()

    output_dir = root / "runs" / run_id / PHASE_SLUG
    output_dir.mkdir(parents=True, exist_ok=True)

    specs_index: list[dict[str, Any]] = []
    validation_errors_all: list[str] = []
    outputs_created: list[str] = []

    for entry in briefs_index:
        business_slug = _safe_str(entry.get("business_slug"))
        if not business_slug:
            continue

        # Load upstream artifacts
        bp_path = root / "runs" / run_id / "04_briefs" / business_slug / "business_profile.json"
        mp_path = root / "runs" / run_id / "04_briefs" / business_slug / "market_profile.json"
        brp_path = root / "runs" / run_id / "04_briefs" / business_slug / "brand_profile.json"

        # Build from available artifacts; use empty dicts for missing ones
        business_profile = read_json(str(bp_path)) if bp_path.exists() else {}
        market_profile = read_json(str(mp_path)) if mp_path.exists() else {}
        brand_profile = read_json(str(brp_path)) if brp_path.exists() else {}

        # Need at least a business_slug to proceed
        if not business_profile.get("business_slug"):
            business_profile.setdefault("business_slug", business_slug)

        spec = build_creative_spec(
            business_profile,
            market_profile,
            brand_profile,
            config,
            run_id=run_id,
        )

        # Validate the spec
        validation_errors = validate_creative_spec(spec)
        if validation_errors:
            validation_errors_all.extend(
                f"[{business_slug}] {err}" for err in validation_errors
            )

        # Write the spec
        write_creative_spec(spec, output_dir, business_slug)
        outputs_created.append(
            f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/creative_spec.json"
        )

        specs_index.append({
            "business_slug": business_slug,
            "schema_version": spec["schema_version"],
            "validation_errors": validation_errors,
            "generated_at": spec["generated_at"],
        })

    # Write index
    index_path = output_dir / "creative_specs_index.json"
    write_json(str(index_path), specs_index)
    outputs_created.append(f"runs/{run_id}/{PHASE_SLUG}/creative_specs_index.json")

    # Determine status
    status = "done"
    decisions: list[str] = [
        f"Generated {len(specs_index)} creative specs",
    ]
    risks: list[str] = []

    if validation_errors_all:
        status = "needs_review"
        risks.append(
            f"Validation errors in {len(validation_errors_all)} creative specs"
        )

    # Write result
    result_path = output_dir / "result.json"
    result = ResultEnvelope(
        phase=PHASE_NAME,
        status=status,
        run_id=run_id,
        inputs_used=[
            f"runs/{run_id}/config/input_config.json",
            f"runs/{run_id}/04_briefs/briefs_index.json",
        ],
        outputs_created=outputs_created,
        records_processed=len(briefs_index),
        records_created=len(specs_index),
        records_skipped=len(briefs_index) - len(specs_index),
        missing_fields=[],
        decisions=decisions,
        risks=risks,
        errors=validation_errors_all,
        next_tasks=["Phase 05 — Preview Site Generation"],
    ).model_dump(exclude_none=True, by_alias=True)
    write_json(str(result_path), result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 04.8 — Creative Specification Generation")
    parser.add_argument("--run-id", default="fixture_001", help="Run ID (default: fixture_001)")
    parser.add_argument("--project-root", default=".", help="Project root (default: current directory)")
    args = parser.parse_args()

    result = run_phase_04_8(args.run_id, args.project_root)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
