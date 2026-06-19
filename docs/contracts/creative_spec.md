# Creative Specification Contract — VNEXT-04

**Status:** Active (feature-flagged)
**Schema version:** 1.0.0
**Module:** `packages/creative/creative_spec_builder.py`
**Validator:** `packages/creative/creative_spec_validator.py`
**Models:** `packages/creative/creative_spec_models.py`
**Phase runner:** `packages/phases/phase_04_8_creative_spec.py`
**Feature flag:** `use_creative_spec` (default: OFF)
**Depends on:** VNEXT-01 (business_profile), VNEXT-02 (market_profile), VNEXT-03 (brand_profile)

## Purpose

The creative specification is the **single source of truth before website generation**.
It merges verified facts (VNEXT-01), sellability/strategy (VNEXT-02), and
brand tone/trust/emotion (VNEXT-03) into a unified generation directive with:

- Explicit **content policy** (what claims are allowed/forbidden)
- Explicit **section ordering** by strategic priority
- Explicit **evaluation targets** (quality gates)
- Explicit **missing data handling** (omit or neutral)

No LLM is involved — the spec is built deterministically from upstream artifacts.

## Output path

```
runs/{run_id}/04_8_creative_spec/{business_slug}/creative_spec.json
```

## Schema

```json
{
  "schema_version": "1.0.0",
  "run_id": "<from run>",
  "business_slug": "<from lead>",
  "generated_at": "<deterministic from (run_id, business_slug)>",
  "business_identity": {
    "business_name": {"value": "...", "source": "business_profile.json", "confidence": "verified"},
    "category": {"value": "...", "source": "business_profile.json", "confidence": "verified"},
    "phone": {"value": "...", "source": "business_profile.json", "confidence": "verified"},
    "address": {"value": "...", "source": "business_profile.json", "confidence": "verified"},
    "hours": {"value": "...", "source": "business_profile.json", "confidence": "verified"}
  },
  "brand_strategy": {
    "tone": {"value": "professional", "source": "brand_profile.json", "confidence": "inferred"},
    "trust_posture": {"value": "credential_safe", "source": "brand_profile.json", "confidence": "inferred"},
    "emotional_goals": ["confidence", "reliability"],
    "color_direction": {"primary_hint": "blue", "mood": "clean_professional"}
  },
  "sellability": {
    "overall_score": 78.4,
    "demand_signal": "strong",
    "website_status": "no_website",
    "positioning": ["position_as_missing_website_upgrade"]
  },
  "content_policy": {
    "forbidden_claims": [
      "years_in_business", "awards", "licenses", "insurance",
      "certifications", "staff_credentials", "testimonials",
      "guarantees", "superlatives"
    ],
    "missing_data_handling": "omit_or_neutral",
    "claim_policy": "verified_facts_only"
  },
  "generation_directives": {
    "template_family": "industrial_reliable",
    "sections": ["hero", "services", "about", "contact", "cta"],
    "required_cta": "contact_form_or_phone",
    "mobile_first": true
  },
  "evaluation_targets": {
    "min_overall_score": 70,
    "hard_block_on": ["broken_links", "missing_stylesheet", "horizontal_overflow"]
  },
  "missing_data": [],
  "internal": {
    "flag": "use_creative_spec",
    "schema_origin": "VNEXT-04",
    "upstream_artifacts": ["business_profile.json", "market_profile.json", "brand_profile.json"]
  }
}
```

## Section ordering strategy

The `generation_directives.sections` list is ordered by strategic priority:

1. **hero** — first impression, business name + category
2. **services** — what they offer
3. **about** — trust building (rating, reviews, location)
4. **contact** — conversion (phone, hours, address)
5. **cta** — final conversion prompt

## Inputs

- `business_profile.json` (VNEXT-01) — verified facts for business_identity
- `market_profile.json` (VNEXT-02) — sellability scores, positioning hints
- `brand_profile.json` (VNEXT-03) — brand tone, trust posture, emotional goals, colour direction
- Run config — template_family, niche, area, etc.

## Pass conditions

1. Creative spec validates against required fields (validator returns empty list)
2. Required sections are ordered by strategy (hero → services → about → contact → cta)
3. Claim policy is explicit (`verified_facts_only`)
4. Missing fact behavior is explicit (`omit_or_neutral`)
5. Evaluation targets are explicit (min_overall_score, hard_block_on)
6. Fixture output is deterministic (same inputs → same output)
7. Existing pipeline still works when `use_creative_spec=false`
8. All tests in `tests/creative/` and `tests/phases/test_phase_04_8_creative_spec.py` pass

## Validation

```python
from packages.creative.creative_spec_validator import validate_creative_spec

errors = validate_creative_spec(spec)
# errors == [] means valid
```

The validator checks:
- All required top-level and nested keys are present
- Sections follow canonical ordering
- Claim policy is explicit and non-empty
- No forbidden claims appear in public sections
- Missing data is a list
- Evaluation targets are numeric
- Internal block has correct flag and schema_origin

## Public API

```python
from packages.creative.creative_spec_builder import (
    build_creative_spec,
    write_creative_spec,
)
from packages.creative.creative_spec_validator import validate_creative_spec

# Build the spec
spec = build_creative_spec(
    business_profile, market_profile, brand_profile, config,
    run_id="run_123",
)

# Validate
errors = validate_creative_spec(spec)

# Write to disk
path = write_creative_spec(spec, "runs/run_123/04_8_creative_spec", business_slug)
```

## Phase runner

```bash
python3 -m packages.phases.phase_04_8_creative_spec --run-id fixture_001 --project-root .
```

## Determinism

`generated_at` is derived from SHA-256 of `(run_id|business_slug)` mapped to
a fixed epoch (2026-01-01) plus a day offset. Identical inputs always produce
byte-identical output.

## Feature flag

The `use_creative_spec` flag controls whether Phase 04.8 runs. When OFF (default),
the phase is skipped entirely and returns status `"skipped"`. Downstream consumers
must check this flag before relying on `creative_spec.json`.

Default: OFF.

## Non-goals

- Do NOT generate copy or content
- Do NOT make LLM calls
- Do NOT override upstream artifact values
- Do NOT introduce new claim categories beyond the shared blocklist
