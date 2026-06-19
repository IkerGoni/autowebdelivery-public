"""
Phase 04.7 — Brand Reconstruction Generation.

Generate a brand_profile.json for each lead from upstream artifacts:
  - business_profile.json (VNEXT-01)
  - market_profile.json (VNEXT-02)

This phase is feature-flagged behind `use_brand_reconstruction_contract` (default OFF).
When the flag is OFF, the phase is skipped entirely.

Outputs (when flag is ON):
  - runs/{run_id}/04_7_brand/{business_slug}/brand_profile.json
  - runs/{run_id}/04_7_brand/brand_profiles_index.json
  - runs/{run_id}/04_7_brand/result.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from pipeline.json_io import read_json, write_json
    from pipeline.result_envelope import ResultEnvelope, Status
except ModuleNotFoundError:  # pragma: no cover - CLI fallback
    from packages.pipeline.json_io import read_json, write_json
    from packages.pipeline.result_envelope import ResultEnvelope, Status

from packages.intelligence.brand_reconstruction import (
    build_brand_profile,
    write_brand_profile,
)
from packages.shared.provenance import _safe_str

PHASE_SLUG = "04_7_brand"
FEATURE_FLAG = "use_brand_reconstruction_contract"


def run_phase_04_7(run_id: str, work_dir: str | Path) -> ResultEnvelope:
    """Execute Phase 04.7: Generate brand profiles."""
    runs_dir = Path(work_dir) / "runs"
    run_dir = runs_dir / run_id

    # Feature flag check via run config
    config_path = run_dir / "config" / "input_config.json"
    if not config_path.exists():
        return ResultEnvelope.failed(
            phase=PHASE_SLUG,
            run_id=run_id,
            errors=["Missing config file."],
        )

    config = read_json(str(config_path))
    flag = config.get(FEATURE_FLAG, False)

    if not flag:
        result_dir = run_dir / PHASE_SLUG
        result_dir.mkdir(parents=True, exist_ok=True)
        env = ResultEnvelope(
            phase=PHASE_SLUG,
            run_id=run_id,
            status=Status.SKIPPED,
            decisions=[f"Skipped {PHASE_SLUG}: {FEATURE_FLAG}=false"],
        )
        write_json(str(result_dir / "result.json"), env.to_dict())
        return env

    briefs_index_path = run_dir / "04_briefs" / "briefs_index.json"
    scoring_index_path = run_dir / "03_scoring" / "leads_scored.json"

    if not briefs_index_path.exists():
        return ResultEnvelope.blocked(
            phase=PHASE_SLUG,
            run_id=run_id,
            missing_fields=[briefs_index_path.name],
        )
    if not scoring_index_path.exists():
        return ResultEnvelope.blocked(
            phase=PHASE_SLUG,
            run_id=run_id,
            missing_fields=[scoring_index_path.name],
        )

    briefs_index = read_json(str(briefs_index_path))
    scoring_index = read_json(str(scoring_index_path))

    # Support varying shapes of scoring_index depending on the phase completion
    if isinstance(scoring_index, dict) and "scored_leads" in scoring_index:
        leads_scored = scoring_index["scored_leads"]
    elif isinstance(scoring_index, list):
        leads_scored = scoring_index
    else:
        leads_scored = []

    market_profiles_by_slug = {}
    for lead in leads_scored:
        slug = _safe_str(lead.get("business_slug", ""))
        if slug:
            # Look for market_profile.json
            mp_path = run_dir / "03_scoring" / slug / "market_profile.json"
            if mp_path.exists():
                market_profiles_by_slug[slug] = read_json(str(mp_path))
            else:
                market_profiles_by_slug[slug] = {}

    out_dir = run_dir / PHASE_SLUG
    out_dir.mkdir(parents=True, exist_ok=True)
    
    generated = []
    failed = []
    
    # Handle both list and dict shapes for briefs_index for backward/forward compatibility
    if isinstance(briefs_index, dict):
        slug_iterator = briefs_index.keys()
    elif isinstance(briefs_index, list):
        slug_iterator = [b.get("business_slug", "") for b in briefs_index if isinstance(b, dict)]
    else:
        slug_iterator = []
            
    for business_slug in slug_iterator:
        if not business_slug:
            continue
                
        business_profile_path = run_dir / "04_briefs" / business_slug / "business_profile.json"
        
        if not business_profile_path.exists():
            failed.append({
                "business_slug": business_slug,
                "reason": "missing_business_profile"
            })
            continue

        try:
            business_profile = read_json(str(business_profile_path))
            market_profile = market_profiles_by_slug.get(business_slug, {})

            # Build brand profile
            brand_profile = build_brand_profile(
                business_profile=business_profile,
                market_profile=market_profile,
                config=config,
                run_id=run_id
            )

            # Write it to out_dir / {business_slug} / brand_profile.json
            (out_dir / business_slug).mkdir(parents=True, exist_ok=True)
            write_brand_profile(brand_profile, out_dir, business_slug)

            generated.append(business_slug)

        except Exception as e:
            failed.append({
                "business_slug": business_slug,
                "reason": str(e)
            })

    # Write index
    write_json(str(out_dir / "brand_profiles_index.json"), generated)

    # Return summary
    status = Status.DONE if not failed and generated else Status.NEEDS_REVIEW
    if not generated and failed:
        status = Status.FAILED

    env = ResultEnvelope(
        phase=PHASE_SLUG,
        run_id=run_id,
        status=status,
        records_processed=len(briefs_index),
        records_created=len(generated),
        errors=[str(f) for f in failed],
        outputs_created=["brand_profiles_index.json"]
    )
    write_json(str(out_dir / "result.json"), env.to_dict())

    return env


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 04.7: Brand Reconstruction Generation")
    parser.add_argument("--run-id", required=True, help="Run ID")
    parser.add_argument("--work-dir", default=".", help="Working directory containing the runs folder")
    args = parser.parse_args()

    envelope = run_phase_04_7(run_id=args.run_id, work_dir=args.work_dir)
    print(json.dumps(envelope.to_dict(), indent=2))
    return 0 if envelope.status in (Status.DONE, Status.NEEDS_REVIEW, Status.SKIPPED) else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
