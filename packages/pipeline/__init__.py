"""Auto Web Pipeline - Shared foundation for phase-based execution."""

try:
    from pipeline.artifact_paths import artifact_path
    from pipeline.contracts import NormalizedPlace, QueryPlan, RawPlace, RunConfig, RunMeta, WebsiteClassification
    from pipeline.json_io import read_json, write_json
    from pipeline.result_envelope import ResultEnvelope, Status
    from pipeline.slug import make_slug
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from packages.pipeline.artifact_paths import artifact_path
    from packages.pipeline.contracts import (
        NormalizedPlace,
        QueryPlan,
        RawPlace,
        RunConfig,
        RunMeta,
        WebsiteClassification,
    )
    from packages.pipeline.json_io import read_json, write_json
    from packages.pipeline.result_envelope import ResultEnvelope, Status
    from packages.pipeline.slug import make_slug

__all__ = [
    "NormalizedPlace",
    "QueryPlan",
    "RawPlace",
    "ResultEnvelope",
    "RunConfig",
    "RunMeta",
    "Status",
    "WebsiteClassification",
    "artifact_path",
    "make_slug",
    "read_json",
    "write_json",
]