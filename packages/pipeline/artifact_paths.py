"""Artifact path builder for phase outputs per pipeline_data_contract.md.

R0-02 (F-02): directory components (``phase``, ``run_id``, ``artifact_type``)
are validated with the slug charset before joining; filenames must be plain
names — no separators, no ``..``.
"""

from pathlib import Path

from packages.pipeline.slug import validate_slug


def _safe_filename(filename: str) -> str:
    if (
        not isinstance(filename, str)
        or not filename
        or filename in {".", ".."}
        or "/" in filename
        or "\\" in filename
        or "\x00" in filename
    ):
        raise ValueError(f"unsafe artifact filename: {filename!r}")
    return filename


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
    base = Path(workspace) / validate_slug(phase, field="phase") / validate_slug(run_id, field="run_id") / validate_slug(artifact_type, field="artifact_type")
    base.mkdir(parents=True, exist_ok=True)
    return str(base / _safe_filename(filename))


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