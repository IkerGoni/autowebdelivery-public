# Stitch Compiler Contract (VNEXT-05)

**Version:** `stitch_compiler_v1`
**Feature flag:** `use_stitch_compiler` (default: `false`)
**Depends on:** VNEXT-04 (`creative_spec.json`)

## Purpose

The Stitch Compiler translates a `creative_spec.json` (VNEXT-04) into the
existing Stitch prompt generation path. It is a **translator, not a replacement** —
it constructs a `StitchPromptInput` from the creative_spec, then delegates to
`build_premium_stitch_prompt()`.

## Data Flow

```
creative_spec.json
       │
       ▼
 ┌─────────────────┐
 │ stitch_compiler │  compile_creative_spec_to_prompt()
 └─────────────────┘
       │
       ▼
 StitchPromptInput  (existing dataclass)
       │
       ▼
 build_premium_stitch_prompt()  (existing builder)
       │
       ▼
 PremiumStitchPrompt  (existing, augmented with compiler provenance)
```

## Entry Points

### Primary: `compile_creative_spec_to_prompt(creative_spec, config)`

```python
from packages.generation.stitch_compiler import compile_creative_spec_to_prompt

result = compile_creative_spec_to_prompt(creative_spec, config)
# result: PremiumStitchPrompt
```

**Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `creative_spec` | `dict[str, Any]` | Yes | Output of `build_creative_spec()` (VNEXT-04) |
| `config` | `dict[str, Any]` | Yes | Run-level config with optional overrides |

**`config` keys used by the compiler:**

| Key | Default | Description |
|---|---|---|
| `niche` | `"local business"` | Niche label for prompt context |
| `area` | `""` (falls back to `facts["area"]`) | Geographic area for prompt context |
| `deploy_mode` | `"production_deploy_mode"` | Deployment mode identifier |

**Raises:**

| Exception | Condition |
|---|---|
| `ValueError` | `business_name` is missing or empty in `business_identity` |
| `ValueError` | `business_slug` is missing or empty at top level |
| `ValueError` | `category` is missing or empty in `business_identity` |

### Compatibility: `build_prompt_from_creative_spec(creative_spec, config=None)`

```python
from packages.generation.stitch_prompt_builder import build_prompt_from_creative_spec

result = build_prompt_from_creative_spec(creative_spec)
# result: PremiumStitchPrompt
```

> **Note:** The compatibility wrapper lives in `stitch_prompt_builder.py` (not the compiler). It delegates to `compile_creative_spec_to_prompt()` internally. The `config` parameter is optional and defaults to `{}`.

## Translation Rules

| creative_spec field | → StitchPromptInput field |
|---|---|
| `business_identity.business_name` (envelope) | `business_name` |
| `business_identity.category` (envelope) | `category` |
| `business_slug` | `business_slug` |
| `business_identity.{phone,address,hours}` (verified) | `facts` dict |
| `brand_strategy.tone` + `color_direction` | `design_style` (feeling) |
| `content_policy.forbidden_claims` | `forbidden_claims` |
| `generation_directives.sections` | `required_sections` (mapped to builder IDs) |
| `sellability` | `business_intelligence.prompt_hints` |

## Section Mapping

Creative spec uses short section names; the compiler maps them to the
existing builder's internal IDs:

| creative_spec section | builder section ID |
|---|---|
| `hero` | `hero_with_above_fold_cta` |
| `services` | `service_or_package_cards` |
| `about` | `verified_local_service_summary` |
| `contact` | `service_area_or_location` |
| `cta` | `final_cta` |

If sections are empty or missing, `DEFAULT_REQUIRED_SECTIONS` is used.

## Envelope Extraction

creative_spec uses provenance envelopes: `{value, source, confidence}`.

- Only fields with `confidence == "verified"` are included in `facts`
- Fields with other confidence values are tracked in `omitted_facts`
- Empty values are excluded from facts

## Compiler Contract Extensions

When compiled via the compiler, the `prompt_contract` includes a `compiler` section:

```json
{
  "compiler": {
    "compiler_version": "stitch_compiler_v1",
    "creative_spec_hash": "<sha256 of canonical creative_spec JSON>",
    "included_facts": ["business_name", "category", "phone", "address", "hours"],
    "omitted_facts": {
      "hours": "not in business_identity"
    },
    "compiler_decisions": {
      "feeling_derived_from": "brand_strategy.tone",
      "sections_from": "generation_directives.sections"
    },
    "forbidden_claims": ["certifications", "guarantees", ...]
  },
  "prompt_version": "premium_stitch_prompt_v2",
  "prompt_sha256": "...",
  "business_slug": "...",
  "...": "existing contract fields"
}
```

## Metadata Extensions

```json
{
  "compiler_version": "stitch_compiler_v1",
  "creative_spec_hash": "<sha256>",
  "prompt_version": "premium_stitch_prompt_v2",
  "prompt_sha256": "...",
  "business_slug": "...",
  "facts_included": [...],
  "facts_missing": [...],
  "deploy_mode": "...",
  "word_count": 123
}
```

## Feature Flag Behavior

- **`use_stitch_compiler = false` (default):** Pipeline uses existing
  `build_premium_stitch_prompt()` with `StitchPromptInput` directly.
  No compiler involvement.

- **`use_stitch_compiler = true`:** Pipeline reads `creative_spec.json`,
  calls `compile_creative_spec_to_prompt()`, which translates and delegates
  to the existing builder.

Both paths produce `PremiumStitchPrompt`; the compiler path adds provenance.

## Validation

```bash
# Compiler + existing builder tests
python3 -m pytest tests/generation/test_stitch_compiler.py tests/generation/test_stitch_prompt_builder.py -v

# Full suite (must remain 742+ passing)
python3 -m pytest tests/ -q --tb=line

# Lint
ruff check packages/generation/ tests/generation/
```

## Rollback

Set `use_stitch_compiler = false` in run config. The existing builder path
is completely untouched and all existing tests pass unmodified.

## Edge Cases

| Scenario | Behavior |
|---|---|
| Empty `generation_directives.sections` | Falls back to `DEFAULT_REQUIRED_SECTIONS` |
| Missing `generation_directives` key | Falls back to `DEFAULT_REQUIRED_SECTIONS` |
| Unknown section name (not in map) | Passed through as-is; builder handles gracefully |
| `brand_strategy.tone` = `"professional"` | Treated as default — not included in feeling phrase |
| `brand_strategy.tone` missing | Feeling = `"premium local-business website"` |
| `business_identity` has field with `confidence != "verified"` | Field goes to `omitted_facts` with reason, excluded from `facts` |
| `business_identity` has field with empty value | Field goes to `omitted_facts` with reason `"empty value"` |
| `business_identity` field missing entirely | Goes to `omitted_facts` with reason `"not in business_identity"` |
| Minimal spec (only `business_name`, `category`, `slug`) | Compiler works; uses defaults for sections, feeling, forbidden_claims |
| `sellability.positioning` has unknown hint | Ignored — only recognized hints are passed through |
| `content_policy` missing | `forbidden_claims` defaults to `[]` |

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `ValueError: creative_spec must contain business_name` | `business_identity.business_name` envelope has empty value or missing | Check that `business_name` is set in the creative_spec envelope with a non-empty `value` |
| `ValueError: creative_spec must contain business_slug` | Top-level `business_slug` field is missing or empty | Ensure `creative_spec["business_slug"]` is a non-empty string |
| `ValueError: creative_spec must contain category` | `business_identity.category` envelope has empty value | Check `business_identity.category` has a non-empty `value` |
| Prompt uses default sections despite `sections` being set | `generation_directives.sections` is empty list or not a list | Ensure `sections` is a non-empty list of strings |
| `compiler` key missing from `prompt_contract` | Using the old path (`build_premium_stitch_prompt` directly) | Use `compile_creative_spec_to_prompt()` or `build_prompt_from_creative_spec()` instead |
| Facts not appearing in prompt | Fact confidence is not `"verified"` | Set `confidence: "verified"` in the business_identity envelope |
| Test suite count changed | Test file was modified | Update the count in this doc's Files table |

## Files

| File | Description |
|---|---|
| `packages/generation/stitch_compiler.py` | Compiler implementation |
| `packages/generation/stitch_prompt_builder.py` | Existing builder + compatibility wrapper |
| `tests/generation/test_stitch_compiler.py` | 25 compiler-specific tests |
| `tests/generation/test_stitch_prompt_builder.py` | Existing builder tests (unmodified) |
| `docs/contracts/stitch_compiler.md` | This document |
