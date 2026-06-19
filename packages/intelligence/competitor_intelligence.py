"""
VNEXT-10 — Competitor Intelligence v1.

Build a canonical `competitor_profile.json` artifact for each lead using curated
benchmark fixtures. The profile captures structural patterns common to a niche
(category + area) — sections, CTA types, color palettes, layout patterns —
without copying any competitor content, images, logos, or brand marks.

The module is pure-Python and deterministic: identical inputs produce
byte-identical output.

Feature flag: ``use_competitor_intelligence`` (default OFF).
Scope option:  ``competitor_scope`` — "none" (disabled), "fixtures_only"
               (default when enabled), "curated" (future).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packages.shared.forbidden_claims import FORBIDDEN_PUBLIC_CLAIMS as _FORBIDDEN_PUBLIC_CLAIMS
from packages.shared.provenance import (
    _deterministic_generated_at,
    _safe_str,
)

try:  # pragma: no cover - import-shim for tests and CLI
    from pipeline.json_io import write_json
except ModuleNotFoundError:  # pragma: no cover
    from packages.pipeline.json_io import write_json

SCHEMA_VERSION = "1.0.0"

BENCHMARK_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "tests"
    / "fixtures"
    / "competitor_benchmarks"
)

# Forbidden content categories — these must never appear in patterns output.
_FORBIDDEN_CONTENT_KEYS: tuple[str, ...] = (
    "text_content",
    "images",
    "logos",
    "brand_marks",
    "exact_layouts",
    "copy",
    "slogan",
    "tagline",
    "headline",
    "description",
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _load_all_benchmarks() -> list[dict[str, Any]]:
    """Load all benchmark fixture JSON files from BENCHMARK_DIR."""
    if not BENCHMARK_DIR.is_dir():
        return []
    benchmarks: list[dict[str, Any]] = []
    for fp in sorted(BENCHMARK_DIR.glob("*.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                benchmarks.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return benchmarks


def _match_category(category: str, fixture_category: str) -> float:
    """Score how well *category* matches *fixture_category* (0.0–1.0).

    Token-overlap scoring: each token in *category* that appears in
    *fixture_category* contributes to the score. Case-insensitive.
    """
    cat_tokens = set(_safe_str(category).lower().split())
    fix_tokens = set(_safe_str(fixture_category).lower().split())
    if not cat_tokens or not fix_tokens:
        return 0.0
    overlap = cat_tokens & fix_tokens
    return round(len(overlap) / len(cat_tokens), 2)


def _load_benchmark(category: str, area: str) -> dict | None:
    """Load the best-matching benchmark fixture for (category, area).

    Scoring: category match weight = 0.7, area match weight = 0.3.
    Returns the best benchmark if its total score > 0, else None.
    """
    benchmarks = _load_all_benchmarks()
    if not benchmarks:
        return None

    best: dict | None = None
    best_score = 0.0

    for bm in benchmarks:
        bm_cat = _safe_str(bm.get("category", ""))
        bm_area = _safe_str(bm.get("area", ""))

        cat_score = _match_category(category, bm_cat)

        # Area match: simple token overlap
        area_tokens = set(_safe_str(area).lower().replace(",", " ").split())
        bm_area_tokens = set(bm_area.lower().replace(",", " ").split())
        area_overlap = area_tokens & bm_area_tokens
        area_score = round(len(area_overlap) / max(len(area_tokens), 1), 2) if area_tokens else 0.0

        total = round(cat_score * 0.7 + area_score * 0.3, 2)

        if total > best_score:
            best_score = total
            best = bm

    return best if best_score > 0 else None


def _validate_no_copies(patterns: dict[str, Any]) -> list[str]:
    """Recursively check *patterns* for forbidden content keys at all nesting levels.

    Returns a list of violation key paths (e.g., "trust_signals[0].logos").
    Empty list means clean. Paths use dot notation for nested keys and
    bracket notation for list indices.
    """
    violations: list[str] = []

    def _walk(obj: Any, path: str = "") -> None:
        """Recursively walk dict/list structure, collecting forbidden key paths."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                normalized_key = _safe_str(key).lower()
                if normalized_key in _FORBIDDEN_CONTENT_KEYS:
                    violations.append(f"{path}{key}" if path else key)
                # Build next path
                next_path = f"{path}{key}." if path else f"{key}."
                _walk(value, next_path)
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                # For list items, strip trailing dot from path first
                # e.g., "trust_signals." -> "trust_signals[0]."
                base = path.rstrip(".") if path else ""
                list_item_path = f"{base}[{idx}]."
                _walk(item, list_item_path)

    _walk(patterns)
    return violations


def _forbidden_public_claims() -> list[str]:
    """Return the explicit blocklist of claim categories that must never appear
    in public marketing copy generated from this profile.
    """
    return list(_FORBIDDEN_PUBLIC_CLAIMS)


def _collect_forbidden_claim_violations(obj: Any, path: str = "") -> list[str]:
    """Recursively check values for forbidden claim patterns that would appear in copy.

    Only checks string values that could be marketing copy (not section names).
    Section names like "testimonials" or "trust_signals" are allowed as they are
    structural elements, not factual claims.

    Returns a list of violation key paths.
    """
    violations: list[str] = []

    # Section name values that are structurally allowed (not claims)
    ALLOWED_SECTION_VALUES = {
        "testimonials",
        "trust_signals",
        "years_badge",
        "certification_icons",
        "rating_display",
        "review_count",
    }

    def _walk(val: Any, current_path: str) -> None:
        if isinstance(val, dict):
            for k, v in val.items():
                _walk(v, f"{current_path}{k}.")
        elif isinstance(val, list):
            for idx, item in enumerate(val):
                _walk(item, f"{current_path}[{idx}].")
        elif isinstance(val, str):
            # Skip if this is a known section name value
            if val.lower() in ALLOWED_SECTION_VALUES:
                return
            # Check for actual claim patterns (not just section names)
            val_lower = val.lower()
            for claim in _FORBIDDEN_PUBLIC_CLAIMS:
                # Only flag if it looks like an actual claim context
                # (e.g., "10 years in business" not just "testimonials section")
                if claim in val_lower and len(val) > 20:
                    violations.append(f"{current_path[:-1]}")

    _walk(obj, path)
    return violations


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def build_competitor_profile(
    category: str,
    area: str,
    config: dict | None = None,
    *,
    run_id: str,
    business_slug: str,
) -> dict[str, Any]:
    """Build competitor profile from fixture benchmarks.

    Parameters
    ----------
    category:
        Business category (e.g. "Auto Detailing Service").
    area:
        Service area (e.g. "Dallas, TX").
    config:
        Run-level config dict. Checked for ``competitor_scope``.
    run_id:
        Run identifier.
    business_slug:
        Business slug identifier.

    Returns
    -------
    A JSON-serializable dict conforming to the competitor_profile schema.
    When no benchmark matches, patterns will be empty lists/dicts.
    """
    cfg = config or {}
    scope = _safe_str(cfg.get("competitor_scope", "fixtures_only"))

    benchmark = _load_benchmark(category, area)

    if benchmark is not None:
        patterns = dict(benchmark.get("patterns", {}))
        benchmarks_used = [benchmark.get("category", "unknown")]
        bm_area = benchmark.get("area", "")
        if bm_area:
            benchmarks_used = [
                f"{benchmark.get('category', 'unknown')} ({bm_area})"
            ]
        # Derive fixture filename for traceability
        fixture_name = ""
        for fp in sorted(BENCHMARK_DIR.glob("*.json")):
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                if (
                    data.get("category") == benchmark.get("category")
                    and data.get("area") == benchmark.get("area")
                ):
                    fixture_name = fp.name
                    break
            except (json.JSONDecodeError, OSError):
                continue
        if fixture_name:
            benchmarks_used = [fixture_name]
    else:
        patterns: dict[str, Any] = {
            "common_sections": [],
            "common_cta_types": [],
            "pricing_visibility": "",
            "trust_signals": [],
            "mobile_patterns": [],
            "color_patterns": {
                "dominant_colors": [],
                "accent_colors": [],
            },
            "layout_patterns": [],
        }
        benchmarks_used: list[str] = []

    # Detect missing data
    missing: list[str] = []
    if not patterns.get("common_sections"):
        missing.append("common_sections")
    if not patterns.get("common_cta_types"):
        missing.append("common_cta_types")
    if not patterns.get("trust_signals"):
        missing.append("trust_signals")
    if not benchmarks_used:
        missing.append("benchmark_match")

    # Validate patterns and collect warnings
    warnings: list[str] = []

    # Check for forbidden content keys in patterns
    content_violations = _validate_no_copies(patterns)
    for violation in content_violations:
        warnings.append(f"Forbidden content key detected: {violation}")

    # Check patterns values for forbidden claim references
    claim_violations = _collect_forbidden_claim_violations(patterns)
    for violation in claim_violations:
        warnings.append(f"Forbidden claim reference detected: {violation}")

    profile: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "business_slug": business_slug,
        "generated_at": _deterministic_generated_at(run_id, business_slug),
        "category": category,
        "area": area,
        "patterns": patterns,
        "benchmarks_used": benchmarks_used,
        "disclaimer": (
            "Patterns derived from curated benchmarks and fixtures. "
            "No competitor content, images, logos, or brand marks are "
            "copied or reproduced."
        ),
        "missing_data": missing,
        "forbidden_public_claims": _forbidden_public_claims(),
        "warnings": warnings,
        "internal": {
            "flag": "use_competitor_intelligence",
            "scope": scope,
            "schema_origin": "VNEXT-10",
        },
    }

    return profile


def write_competitor_profile(
    profile: dict[str, Any],
    output_dir: str | Path,
    business_slug: str,
) -> str:
    """Write the profile to ``{output_dir}/{business_slug}/competitor_profile.json``.

    Returns the absolute path of the written file.
    """
    output_path = Path(output_dir) / business_slug / "competitor_profile.json"
    return write_json(str(output_path), profile)