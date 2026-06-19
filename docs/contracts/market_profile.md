# Market Profile Contract (v1.1.0)

> **Status:** VNEXT-02 — feature-flagged (default OFF).
> **Schema version:** `1.1.0`
> **Owner:** Phase 03 (Lead Scoring)
> **Consumers (planned):** VNEXT-03 (Brand Reconstruction), Phase 05 (preview
> generation), Phase 09 (approval pack), downstream copy and outreach
> generators.

## Purpose

`market_profile.json` is the **canonical sellability / strategy artifact** for
a single scored lead. It exists alongside the existing
`leads_scored.json` and the VNEXT-01 `business_profile.json`, and serves a
complementary purpose:

- `business_profile.json` (VNEXT-01) is the **verified-facts** view — what the
  lead record authoritatively says about the business.
- `market_profile.json` (VNEXT-02) is the **sellability / strategy** view —
  what the scorecard derived from that lead, structured for downstream
  generators to consume without re-parsing the scorecard output.

Goals:

1. **Split** the scorecard's "prompt hints" (which currently blur together
   sellability signals, marketing copy suggestions, and strategy inputs) into
   explicit `sellability` and `strategy_hints` blocks.
2. Make the scorecard's structured output directly consumable as a
   deterministic, provenance-bearing JSON artifact.
3. Keep `prompt_hints` as a backward-compatible alias of `value_drivers` for
   any consumer that still reads the scorecard output inline.
4. Make the existing public-safe chokepoint pattern (from VNEXT-01) reusable
   for downstream phases.

## Schema version

The artifact always carries a top-level `schema_version` string in SemVer
form. The current value is `"1.1.0"`. Breaking changes to field names, types,
or semantics require a major-version bump; additive fields are allowed under
minor versions.

## Top-level shape

```json
{
  "schema_version": "1.1.0",
  "run_id": "fixture_001",
  "business_slug": "north-dallas-mobile-detailing",
  "generated_at": "2031-02-09T00:00:00Z",
  "sellability": {
    "score": {"value": 78.4, "source": "scorecard", "confidence": "verified"},
    "category": {"value": "Auto Detailing Service", "source": "selected_for_preview.json", "confidence": "verified"},
    "website_status": {"value": "no_website", "source": "selected_for_preview.json", "confidence": "verified"},
    "demand_signal": {"value": "strong", "source": "scorecard.component_scores", "confidence": "inferred"}
  },
  "strategy_hints": {
    "positioning": ["position_as_missing_website_upgrade"],
    "value_drivers": ["high_value_service_category", "strong_rating_signal", "strong_review_volume_signal"],
    "risk_flags": ["missing_enrichment"]
  },
  "missing_data": [],
  "forbidden_public_claims": [
    "years_in_business", "awards", "licenses", "insurance",
    "certifications", "staff_credentials", "testimonials",
    "guarantees", "superlatives"
  ],
  "internal": {
    "flag": "use_market_profile_contract",
    "schema_origin": "VNEXT-02",
    "migration_phase": "prompt_hints_alias_active"
  }
}
```

## Field classification

### Public-safe (may be passed to copy generators)

| Field path            | Type   | Notes                                                         |
|-----------------------|--------|---------------------------------------------------------------|
| `schema_version`      | string | `"1.1.0"`.                                                    |
| `run_id`              | string | From the run config / scored lead.                            |
| `business_slug`       | string | Stable identifier.                                            |
| `generated_at`        | string | ISO8601, deterministic — see "Determinism" below.             |
| `sellability.score`   | object | `{value, source, confidence}`. From the scorecard.            |
| `sellability.category`| object | Lead-derived; source = `selected_for_preview.json`. Omitted if absent on lead (see "Conditional fields" below). |
| `sellability.website_status` | object | Lead-derived; source = `selected_for_preview.json`. Omitted if absent on lead (see "Conditional fields" below). |
| `sellability.demand_signal` | object | Inferred classification of the scorecard demand component. Always present. |
| `strategy_hints`      | object | Internal-only structured copy of scorecard value_drivers + risk_flags. See warning below. |
| `missing_data`        | list   | Explicit, sorted; lists fields expected but absent.           |
| `forbidden_public_claims` | list | Always present, never empty. Mirrors VNEXT-01.             |

> **Important:** The `sellability` block is the public-safe chokepoint.
> `strategy_hints` is **internal-only** and MUST NOT be passed to public
> copy generators. It is included in the same artifact because downstream
> internal consumers (Phase 04 brief generation, VNEXT-03 brand
> reconstruction) need the structured strategy inputs; the public copy path
> is expected to project only the `sellability` block (and the
> `forbidden_public_claims` blocklist) when rendering copy.

### Internal-only (MUST NOT be passed to public copy)

| Field path      | Notes                                                                 |
|-----------------|-----------------------------------------------------------------------|
| `strategy_hints`| Internal structured strategy inputs. Never forwarded to public copy.  |
| `internal`      | Labelled block. Carries provenance + migration phase. Never forwarded.|

### Demand-signal classification

The `sellability.demand_signal.value` field is a label derived from the
scorecard's `component_scores.demand_signal` (0–100 scale):

| Component score | Label      |
|-----------------|------------|
| `>= 70.0`       | `strong`   |
| `>= 50.0`       | `moderate` |
| `< 50.0`        | `weak`     |

The classification is **inferred** (confidence = `inferred`, source =
`scorecard.component_scores`) because it is a derived label, not a lead
value.

### Conditional fields in `sellability`

The `sellability.category` and `sellability.website_status` envelopes are
**only present when the lead record has a non-empty value** for the
corresponding field. The implementation checks `_has_value(lead.get(...))`
before adding each entry. If either field is absent or empty:

- It is **omitted** from the `sellability` block entirely (no `null` or
  placeholder envelope).
- It is **added to `missing_data`** (if it is in the
  `_MARKET_PROFILE_MISSING_FIELDS` list).

`sellability.score` and `sellability.demand_signal` are always present —
they default to `0.0` and `"weak"` respectively when the scorecard is
missing or the component score is absent.

### Edge cases and fallback behavior

| Scenario | Behavior |
|----------|----------|
| `bi_score` is `None` | Treated as empty dict. Score defaults to `0.0`, demand_signal to `"weak"`, all strategy_hints lists are empty. |
| `lead.business_slug` is empty/missing | `build_market_profile()` raises `ValueError`. |
| Scorecard `component_scores.demand_signal` is non-numeric | `_safe_component_score` catches `TypeError`/`ValueError` and returns `0.0` → label `"weak"`. |
| `value_drivers` contains empty strings or `None` entries | `_split_strategy_hints` filters them out via `str(hint or "").strip()`. |
| `risk_flags` contains empty strings | Filtered the same way — only non-empty stripped values are kept. |

## Provenance and confidence enums

Each `sellability.*` entry is a **provenance envelope** of the shape:

```json
{"value": <any>, "source": "<source>", "confidence": "<verified|inferred|unknown>"}
```

| Enum value   | Meaning                                                                 |
|--------------|-------------------------------------------------------------------------|
| `verified`   | Value comes from a source considered authoritative for this run.        |
| `inferred`   | Value is derived from a non-authoritative signal (e.g. scorecard).      |
| `unknown`    | Field is present in the envelope but its provenance is unknown.        |

Recognized `source` values:

- `scorecard` — the business-intelligence scorecard overall score.
- `scorecard.component_scores` — a single scorecard component (e.g.
  `demand_signal`) used to derive a label.
- `selected_for_preview.json` — the lead record from Phase 03.

## Forbidden public claims

The `forbidden_public_claims` field is **always present and non-empty**. It
is the explicit blocklist of claim categories that downstream copy
generators MUST NOT invent. It mirrors the VNEXT-01 blocklist, byte-for-byte:

```text
years_in_business, awards, licenses, insurance, certifications,
staff_credentials, testimonials, guarantees, superlatives
```

See `docs/contracts/business_profile.md` for the rationale on each category.
The contract author for this list is `packages/intelligence/market_profile.py`.

## Missing-data policy

If a market-profile-relevant field is absent or empty on the lead record, it
is **omitted from the corresponding block** and **added to `missing_data`**.
The market profile never invents a value for an absent field.

The list of fields considered for `missing_data` is:

```text
category, website_status, phone, address, rating, review_count
```

This is intentionally a strict subset of the lead-derived fields — the
market profile is a *strategy* artifact, so it only surfaces gaps that
matter for sellability.

`missing_data` follows the fixed field order defined in
`_MARKET_PROFILE_MISSING_FIELDS` (`category`, `website_status`, `phone`,
`address`, `rating`, `review_count`), so it is deterministic and
reproducible for identical inputs.

## Strategy hints split

The `strategy_hints` block is derived from the scorecard's `value_drivers`
list (not the scorecard's `prompt_hints` alias):

| Scorecard value_driver prefix | Market profile bucket   |
|-------------------------------|-------------------------|
| `position_as_*`               | `strategy_hints.positioning` |
| (anything else)               | `strategy_hints.value_drivers` |

`strategy_hints.risk_flags` mirrors the scorecard's `risk_flags` list
verbatim, in the same order.

A value_driver that starts with `position_as_` is *only* surfaced in
`positioning` and never duplicated in `value_drivers`.

## Determinism guarantee

`generated_at` is **derived deterministically** from `(run_id,
business_slug)` using the same algorithm as VNEXT-01
(`packages/intelligence/business_profile.py`):

1. Compute `digest = sha256(f"{run_id}|{business_slug}".encode("utf-8"))`.
2. Take the first 8 hex chars of `digest` as a 32-bit unsigned integer.
3. Take that integer modulo 3650 (≈ 10 years) as a day offset.
4. Return the ISO8601 string `2026-01-01T00:00:00Z + day_offset days`,
   rendered in UTC.

This guarantees:

- Identical `(run_id, business_slug)` → identical `generated_at` across
  processes, machines, and time zones.
- No wall-clock dependence: rerunning the build at any later time produces
  the same value.

The full profile is otherwise free of nondeterministic inputs: there is no
`uuid`, no `random`, no `time.time()`, and no environment-variable reading.

## Scorecard integration (additive)

The scorecard (`packages/phases/business_intelligence_scorecard.py`) gained a
new top-level key in its return value:

```python
"strategy_hints": {
    "positioning":  [<value_drivers starting with "position_as_">],
    "value_drivers": [<value_drivers NOT starting with "position_as_">],
    "risk_flags":    [<risk_flags>],
}
```

This is **additive**: the existing `prompt_hints` key is preserved as a
byte-identical copy of `value_drivers`, and no existing key is removed or
renamed. Any consumer that reads `score_business_intelligence()` output
will continue to see `prompt_hints` exactly as before.

## Backward compatibility and rollback

- The artifact is **opt-in** via the `use_market_profile_contract` config
  flag. The flag defaults to `False` in every code path and is NOT set in
  any default config.
- When the flag is OFF, Phase 03 produces **byte-identical output** to the
  pre-VNEXT-02 baseline: `leads_scored.json`, `qualified_leads.json`,
  `selected_for_preview.json`, `leads_scored.csv`, and `result.json` are
  unchanged in shape and content. The scorecard's `strategy_hints` key
  *is* added (it is additive), but it is not surfaced to the filesystem
  unless the flag is on.
- When the flag is ON, the only new filesystem artifact is
  `runs/{run_id}/03_scoring/{business_slug}/market_profile.json` per
  scored business, plus a per-row entry in `outputs_created` in
  `result.json`.
- **Rollback** is the default state: stop setting
  `use_market_profile_contract=True` and no new artifacts are produced
  and no consumer is required to read the file. Old Phase 03 outputs
  remain valid indefinitely.

## Versioning rules

- Additive optional fields → minor version bump.
- Renaming or removing a field → major version bump.
- Changing the meaning of an enum value → major version bump.
- Changing the `forbidden_public_claims` list in a way that would
  invalidate downstream copy generators → major version bump.

## Test coverage

Unit tests live in `tests/intelligence/test_market_profile.py`. Phase 03
flag tests live in `tests/phases/test_phase_03_lead_scoring.py` under
`TestMarketProfileContractFlag`. The contract is exercised end-to-end
through the standard Phase 03 lead fixtures.
