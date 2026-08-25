"""Phase 01: User Input / Run Config.

Validates user input, creates RunConfig and QueryPlan artifacts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.contracts import QueryPlan, RunConfig
from pipeline.json_io import read_json, write_json
from pipeline.result_envelope import ResultEnvelope

PHASE_NAME = "phase_01_user_input"


def validate_config(config: dict[str, Any]) -> list[str]:
    """Validate required fields and constraints.

    Returns list of missing/invalid field names.
    """
    missing = []
    errors = []

    # Required fields
    required_fields = [
        "niche",
        "area",
        "country",
        "max_raw_results",
        "max_preview_sites",
        "price_offer",
    ]
    for field in required_fields:
        if field not in config or config[field] is None or config[field] == "":
            missing.append(field)

    # Threshold constraints
    if (
        "max_preview_sites" in config
        and "max_raw_results" in config
        and config["max_preview_sites"] > config["max_raw_results"]
    ):
        errors.append("max_preview_sites exceeds max_raw_results")

    # Generation mode validation
    valid_modes = ["stitch", "modular", "template", "auto"]
    if "generation_mode" in config and config["generation_mode"] not in valid_modes:
        errors.append(f"generation_mode must be one of {valid_modes}")

    # Deploy provider validation
    valid_providers = ["local_only", "vercel", "nginx_local"]
    if "deploy_provider" in config and config["deploy_provider"] not in valid_providers:
        errors.append(f"deploy_provider must be one of {valid_providers}")

    # Rating threshold validation
    if "minimum_rating" in config:
        rating = config["minimum_rating"]
        if rating is not None and (rating < 0 or rating > 5):
            errors.append("minimum_rating must be between 0 and 5")

    # Reviews threshold validation
    if "minimum_reviews" in config:
        reviews = config["minimum_reviews"]
        if reviews is not None and reviews < 0:
            errors.append("minimum_reviews must be non-negative")

    return missing + errors


def make_run_config(config: dict[str, Any], run_id: str) -> RunConfig:
    """Create RunConfig from input dict with defaults."""
    return RunConfig(
        run_id=run_id,
        niche=config.get("niche", ""),
        area=config.get("area", ""),
        country=config.get("country", ""),
        language=config.get("language", "English"),
        max_raw_results=config.get("max_raw_results", 100),
        max_preview_sites=config.get("max_preview_sites", 5),
        minimum_rating=config.get("minimum_rating", 4.3),
        minimum_reviews=config.get("minimum_reviews", 40),
        style_preset=config.get("style_preset", "clinical_trust"),
        deploy_mode=config.get("deploy_mode", "preview_demo_mode" if config.get("generation_mode") == "template" else "production_deploy_mode"),
        price_offer=config.get("price_offer", ""),
        offer_type=config.get("offer_type", "setup_only"),
        offer_price=config.get("offer_price", ""),
        currency=config.get("currency", ""),
        pricing_market=config.get("pricing_market", f"{config.get('area', '')}, {config.get('country', '')}".strip(", ")),
        pricing_notes=config.get("pricing_notes", ""),
        mvp_stop_threshold=config.get("mvp_stop_threshold", 20),
        generation_mode=config.get("generation_mode", "stitch"),
        deploy_provider=config.get("deploy_provider", "local_only"),
    )


def make_query_plan(run_config: RunConfig) -> QueryPlan:
    """Create QueryPlan from RunConfig."""
    query_text = f"{run_config.niche} {run_config.area}"
    return QueryPlan(
        run_id=run_config.run_id,
        queries=[
            {
                "query_id": "q_001",
                "search_text": query_text,
                "niche": run_config.niche,
                "area": run_config.area,
                "country": run_config.country,
                "max_results": run_config.max_raw_results // 2,
            }
        ],
    )


def run(
    run_id: str,
    workspace: str,
    input_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute Phase 01 and return result envelope.

    Args:
        run_id: Run identifier
        workspace: Base workspace directory
        input_config: User input dict. If None, reads from fixture path.

    Returns:
        Result envelope dict
    """
    workspace_path = Path(workspace)

    if input_config is None:
        input_path = workspace_path / "tests" / "fixtures" / PHASE_NAME / "input" / "valid_config_minimal.json"
        if not input_path.exists():
            return ResultEnvelope.blocked(
                phase=PHASE_NAME,
                run_id=run_id,
                missing_fields=["input_config"],
                inputs_used=[],
            ).to_dict()
        input_config = read_json(str(input_path))

    # Validate input
    validation_errors = validate_config(input_config)
    if validation_errors:
        return ResultEnvelope.blocked(
            phase=PHASE_NAME,
            run_id=run_id,
            missing_fields=validation_errors,
            inputs_used=[],
        ).to_dict()

    # Create run config
    run_config = make_run_config(input_config, run_id)

    # Create output directories
    config_dir = workspace_path / "runs" / run_id / "config"
    phase_dir = workspace_path / "runs" / run_id / "01_input"
    config_dir.mkdir(parents=True, exist_ok=True)
    phase_dir.mkdir(parents=True, exist_ok=True)

    # Write artifacts
    input_config_path = config_dir / "input_config.json"
    query_plan_path = phase_dir / "query_plan.json"
    result_path = phase_dir / "result.json"

    write_json(str(input_config_path), run_config.model_dump())
    query_plan = make_query_plan(run_config)
    write_json(str(query_plan_path), query_plan.model_dump())

    # Create result
    result = ResultEnvelope.done(
        phase=PHASE_NAME,
        run_id=run_id,
        inputs_used=["input_config"],
        outputs_created=[
            "config/input_config.json",
            "01_input/query_plan.json",
            "01_input/result.json",
        ],
        records_processed=1,
        records_created=2,
        decisions=[f"Created run config for {run_id}", f"Created query plan with {len(query_plan.queries)} query"],
    ).to_dict()

    write_json(str(result_path), result)

    return result


if __name__ == "__main__":
    import sys
    workspace = sys.argv[1] if len(sys.argv) > 1 else "."
    run_id = sys.argv[2] if len(sys.argv) > 2 else "test_run"
    result = run(workspace, run_id)
    print(f"Phase 01 complete: {result['status']}")