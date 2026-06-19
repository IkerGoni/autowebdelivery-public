"""Artifact path builder for phase outputs per pipeline_data_contract.md."""

from pathlib import Path


def artifact_path(
    workspace: str,
    phase: str,
    run_id: str,
    artifact_type: str,
    filename: str,
) -> str:
    """
    Build standardized artifact path.

    Args:
        workspace: Base workspace directory
        phase: Phase name (e.g., "phase_01")
        run_id: Run identifier
        artifact_type: Type of artifact (e.g., "inputs", "outputs", "cache")
        filename: Artifact filename

    Returns:
        Absolute path string
    """
    base = Path(workspace) / phase / run_id / artifact_type
    base.mkdir(parents=True, exist_ok=True)
    return str(base / filename)


def input_path(
    workspace: str,
    phase: str,
    run_id: str,
    filename: str,
) -> str:
    """Build path for input artifact."""
    return artifact_path(workspace, phase, run_id, "inputs", filename)


def output_path(
    workspace: str,
    phase: str,
    run_id: str,
    filename: str,
) -> str:
    """Build path for output artifact."""
    return artifact_path(workspace, phase, run_id, "outputs", filename)


def cache_path(
    workspace: str,
    phase: str,
    run_id: str,
    filename: str,
) -> str:
    """Build path for cache artifact."""
    return artifact_path(workspace, phase, run_id, "cache", filename)