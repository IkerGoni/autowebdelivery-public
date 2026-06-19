"""
VNEXT-04 — Creative Specification Validator.

Validates a creative_spec dict against the required-fields spec defined in
creative_spec_models.py. Returns a list of validation errors (empty = valid).

Validation checks:
  1. All required top-level keys are present
  2. All required nested section keys are present
  3. generation_directives.sections is ordered by canonical strategy
  4. content_policy has explicit claim_policy
  5. No forbidden claims appear outside of the forbidden_claims list itself
  6. missing_data is present (even if empty list)
  7. evaluation_targets has explicit min_overall_score and hard_block_on
  8. internal block has correct flag and schema_origin
"""

from __future__ import annotations

import json
import re
from typing import Any

from packages.creative.creative_spec_models import (
    CANONICAL_SECTION_ORDER,
    FORBIDDEN_PUBLIC_CLAIMS,
    REQUIRED_BRAND_STRATEGY_KEYS,
    REQUIRED_BUSINESS_IDENTITY_KEYS,
    REQUIRED_CONTENT_POLICY_KEYS,
    REQUIRED_EVALUATION_TARGETS_KEYS,
    REQUIRED_GENERATION_DIRECTIVES_KEYS,
    REQUIRED_INTERNAL_KEYS,
    REQUIRED_TOP_LEVEL_KEYS,
)


def validate_creative_spec(spec: dict[str, Any]) -> list[str]:
    """Validate a creative_spec dict against the required-fields spec.

    Returns a list of validation error strings. An empty list means the spec
    is valid. Errors are human-readable and ordered by severity (missing
    top-level keys first, then nested sections).

    Parameters
    ----------
    spec:
        The creative_spec dict to validate.

    Returns
    -------
    list[str] — empty if valid, list of errors otherwise.
    """
    if not isinstance(spec, dict):
        return ["creative_spec must be a dict"]

    errors: list[str] = []

    # 1. Required top-level keys
    for key in REQUIRED_TOP_LEVEL_KEYS:
        if key not in spec:
            errors.append(f"missing required top-level key: {key!r}")

    # If missing fundamental keys, stop early — nested checks would fail.
    if errors:
        return errors

    # 2. Required nested section keys
    _check_nested_keys(errors, spec, "business_identity", REQUIRED_BUSINESS_IDENTITY_KEYS)
    _check_nested_keys(errors, spec, "brand_strategy", REQUIRED_BRAND_STRATEGY_KEYS)
    _check_nested_keys(errors, spec, "content_policy", REQUIRED_CONTENT_POLICY_KEYS)
    _check_nested_keys(errors, spec, "generation_directives", REQUIRED_GENERATION_DIRECTIVES_KEYS)
    _check_nested_keys(errors, spec, "evaluation_targets", REQUIRED_EVALUATION_TARGETS_KEYS)
    _check_nested_keys(errors, spec, "internal", REQUIRED_INTERNAL_KEYS)

    # 3. generation_directives.sections ordered by canonical strategy
    _check_section_ordering(errors, spec)

    # 4. content_policy has explicit claim_policy
    _check_claim_policy(errors, spec)

    # 5. No forbidden claims in public sections
    _check_no_forbidden_claims_in_public(errors, spec)

    # 6. missing_data is a list
    if not isinstance(spec.get("missing_data"), list):
        errors.append("missing_data must be a list")

    # 7. evaluation_targets has numeric min_overall_score
    _check_evaluation_targets(errors, spec)

    # 8. internal block validation
    _check_internal_block(errors, spec)

    return errors


def _check_nested_keys(
    errors: list[str],
    spec: dict[str, Any],
    section: str,
    required_keys: tuple[str, ...],
) -> None:
    """Check that a nested section dict contains all required keys."""
    section_data = spec.get(section)
    if not isinstance(section_data, dict):
        errors.append(f"{section!r} must be a dict")
        return
    for key in required_keys:
        if key not in section_data:
            errors.append(f"missing required key in {section!r}: {key!r}")


def _check_section_ordering(errors: list[str], spec: dict[str, Any]) -> None:
    """Check that generation_directives.sections follows canonical ordering."""
    gd = spec.get("generation_directives", {})
    if not isinstance(gd, dict):
        return
    sections = gd.get("sections")
    if not isinstance(sections, list):
        errors.append("generation_directives.sections must be a list")
        return

    # The sections must contain all canonical sections in order.
    # Extra sections are allowed after the canonical ones.
    canonical_list = list(CANONICAL_SECTION_ORDER)
    for i, canonical in enumerate(canonical_list):
        if canonical not in sections:
            errors.append(
                f"generation_directives.sections missing canonical section: {canonical!r}"
            )
        elif i < len(sections) and sections[i] != canonical:
            # Canonical section exists but not in expected position
            errors.append(
                f"generation_directives.sections[{i}] expected {canonical!r}, "
                f"got {sections[i]!r}"
            )


def _check_claim_policy(errors: list[str], spec: dict[str, Any]) -> None:
    """Check that content_policy has an explicit claim_policy value."""
    cp = spec.get("content_policy", {})
    if not isinstance(cp, dict):
        return
    claim_policy = cp.get("claim_policy")
    if not isinstance(claim_policy, str) or not claim_policy.strip():
        errors.append("content_policy.claim_policy must be a non-empty string")


def _check_no_forbidden_claims_in_public(errors: list[str], spec: dict[str, Any]) -> None:
    """Check that no forbidden claims appear in public sections (outside content_policy)."""
    # Build a version of the spec without the content_policy.forbidden_claims list
    # itself (which legitimately contains the blocklist words).
    public_sections = {k: v for k, v in spec.items() if k not in ("content_policy", "internal")}
    public_json = json.dumps(public_sections)

    for forbidden in FORBIDDEN_PUBLIC_CLAIMS:
        if re.search(r"\b" + re.escape(forbidden) + r"\b", public_json, re.IGNORECASE):
            errors.append(
                f"forbidden claim {forbidden!r} found in public sections"
            )


def _check_evaluation_targets(errors: list[str], spec: dict[str, Any]) -> None:
    """Check that evaluation_targets.min_overall_score is numeric."""
    et = spec.get("evaluation_targets", {})
    if not isinstance(et, dict):
        return
    score = et.get("min_overall_score")
    if score is not None:
        try:
            float(score)
        except (TypeError, ValueError):
            errors.append("evaluation_targets.min_overall_score must be numeric")


def _check_internal_block(errors: list[str], spec: dict[str, Any]) -> None:
    """Check that internal block has correct flag and schema_origin."""
    internal = spec.get("internal", {})
    if not isinstance(internal, dict):
        return
    if internal.get("flag") != "use_creative_spec":
        errors.append("internal.flag must be 'use_creative_spec'")
    if internal.get("schema_origin") != "VNEXT-04":
        errors.append("internal.schema_origin must be 'VNEXT-04'")
    upstream = internal.get("upstream_artifacts")
    if not isinstance(upstream, list) or len(upstream) == 0:
        errors.append("internal.upstream_artifacts must be a non-empty list")
