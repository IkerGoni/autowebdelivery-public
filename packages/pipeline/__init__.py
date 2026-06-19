"""Auto Web Pipeline - Shared foundation for phase-based execution."""

try:
    from pipeline.contracts import RunConfig, QueryPlan, RawPlace, NormalizedPlace, RunMeta, WebsiteClassification
    from pipeline.result_envelope import ResultEnvelope, Status
    from pipeline.artifact_paths import artifact_path
    from pipeline.json_io import read_json, write_json
    from pipeline.slug import make_slug
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from packages.pipeline.contracts import RunConfig, QueryPlan, RawPlace, NormalizedPlace, RunMeta, WebsiteClassification
    from packages.pipeline.result_envelope import ResultEnvelope, Status
    from packages.pipeline.artifact_paths import artifact_path
    from packages.pipeline.json_io import read_json, write_json
    from packages.pipeline.slug import make_slug

__all__ = [
    "RunConfig",
    "QueryPlan",
    "RawPlace",
    "NormalizedPlace",
    "RunMeta",
    "WebsiteClassification",
    "ResultEnvelope",
    "Status",
    "artifact_path",
    "read_json",
    "write_json",
    "make_slug",
]