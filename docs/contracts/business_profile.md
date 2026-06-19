# Business Profile Contract (v1.0.0)

> **Status:** VNEXT-01 — feature-flagged (default OFF).
> **Schema version:** `1.0.0`
> **Owner:** Phase 04 (Business Brief and Recipient Routing)
> **Consumers (planned):** Phase 05 (preview generation), Phase 09 (approval
> pack), downstream copy generators.

## Purpose

`business_profile.json` is the **canonical verified-facts artifact** for a
single preview-ready lead. It exists alongside the existing Phase 04 Markdown
artifacts (FACTS.md, BUSINESS_BRIEF.md, etc.) and is intended to become the
single source of truth for downstream phases once the feature is rolled out.

Goals:

1. Give every downstream consumer a **structured, deterministic** view of the
   verified facts for one business — no more re-parsing Markdown.
2. Make **provenance and confidence** explicit on every public-safe value.
3. Make **missing data** explicit, never invented.
4. Make **forbidden public claims** a first-class field, so copy generators
   cannot accidentally produce invented years, awards, licenses, etc.
5. Isolate **internal-only signals** in a labelled block so they are never
   passed to public copy generators.

## Schema version

The artifact always carries a top-level `schema_version` string in SemVer
form. The current value is `"1.0.0"`. Breaking changes to field names, types,
or semantics require a major-version bump; additive fields are allowed under
minor versions.

## Top-level shape

```json
{
  "schema_version": "1.0.0",
  "run_id": "fixture_001",
  "business_slug": "bright-smile-clinic-complete",
  "generated_at": "2026-04-12T00:00:00Z",
  "verified_facts": {
    "business_name": {"value": "Bright Smile Clinic", "source": "selected_for_preview.json", "confidence": "verified"},
    "category":      {"value": "Dentist",             "source": "selected_for_preview.json", "confidence": "verified"},
    "rating":        {"value": 4.8,                  "source": "selected_for_preview.json", "confidence": "verified"},
    "review_count":  {"value": 132,                  "source": "selected_for_preview.json", "confidence": "verified"},
    "address":       {"value": "12 Nimman Road, Chiang Mai 50200, Thailand", "source": "selected_for_preview.json", "confidence": "verified"},
    "phone":         {"value": "+66 53 111 222",     "source": "selected_for_preview.json", "confidence": "verified"},
    "hours":         {"value": "Mon-Sat 09:00-18:00","source": "selected_for_preview.json", "confidence": "verified"},
    "maps_url":      {"value": "https://maps.google.com/?cid=111", "source": "selected_for_preview.json", "confidence": "verified"}
  },
  "inferred_strategy": {
    "website_status": {"value": "no_website",    "source": "selected_for_preview.json", "confidence": "inferred"},
    "niche":          {"value": "dentists",      "source": "input_config.json",        "confidence": "inferred"},
    "area":           {"value": "Chiang Mai",    "source": "input_config.json",        "confidence": "inferred"},
    "country":        {"value": "Thailand",      "source": "input_config.json",        "confidence": "inferred"},
    "template_family":{"value": "clinical_trust","source": "input_config.json",        "confidence": "inferred"}
  },
  "missing_data": ["hours"],
  "forbidden_public_claims": [
    "years_in_business",
    "awards",
    "licenses",
    "insurance",
    "certifications",
    "staff_credentials",
    "testimonials",
    "guarantees",
    "superlatives"
  ],
  "recipient_channel": {
    "channel": "phone",
    "value": "+66 53 111 222",
    "source": "google_maps_listing",
    "confidence": "verified"
  },
  "internal": {
    "flag": "use_business_profile_contract",
    "schema_origin": "VNEXT-01"
  }
}
```

## Field classification

### Public-safe (may be passed to copy generators)

| Field path                      | Type    | Notes                                                |
|---------------------------------|---------|------------------------------------------------------|
| `schema_version`                | string  | `"1.0.0"`.                                           |
| `run_id`                        | string  | From the run config.                                 |
| `business_slug`                 | string  | Stable identifier.                                   |
| `generated_at`                  | string  | ISO8601, deterministic — see "Determinism" below.    |
| `verified_facts.*`              | object  | One entry per present, verified public-safe field.   |
| `inferred_strategy.*`           | object  | One entry per present, inferred public-safe field.   |
| `missing_data`                  | list    | Explicit, sorted; lists fields expected but absent.  |
| `forbidden_public_claims`       | list    | Always present, never empty.                         |
| `recipient_channel`             | object  | Mirrors `recipient_channel.json`.                    |

Each `verified_facts.*` and `inferred_strategy.*` entry is a **provenance
envelope** of the shape:

```json
{"value": <any>, "source": "<source>", "confidence": "<verified|inferred|unknown>"}
```

### Internal-only (MUST NOT be passed to public copy)

| Field path       | Notes                                                       |
|------------------|-------------------------------------------------------------|
| `internal`       | Labelled block. Present in every artifact. Never forwarded. |

The blocklist of fields that the contract authoritatively refuses to surface
through the public-safe chokepoint is the `_INTERNAL_ONLY_FIELDS` set in
`packages/intelligence/business_profile.py`. It includes scoring internals
(`lead_score`, `lead_score_components`, `lead_score_reasons`,
`lead_score_band`, `scoring_internal`, `scoring_breakdown`), routing
internals (`recipient_confidence`, `recipient_confidence_detail`), and
process-detail fields (`manual_override_reason`).

## Provenance and confidence enums

| Enum value   | Meaning                                                                |
|--------------|------------------------------------------------------------------------|
| `verified`   | The value comes from a source considered authoritative for this run     |
|              | (currently: `selected_for_preview.json` for lead fields).               |
| `inferred`   | The value is derived from a non-authoritative signal (config, social).  |
| `unknown`    | The field is present in the envelope but its provenance is unknown.    |

`source` is a free-form string that names the artifact the value came from.
Today the only recognized sources are:

- `selected_for_preview.json` — the lead record from Phase 03.
- `input_config.json` — the run-level config from Phase 01.
- `google_maps_listing` — phone was present on the Google Maps record.
- `social_profile` — derived from a `social_platform:*` reason code.
- `unknown` — no source could be identified.

## Forbidden public claims

The `forbidden_public_claims` field is **always present and non-empty**. It
is the explicit blocklist of claim categories that downstream copy
generators MUST NOT invent. The current categories are:

| Category            | Rationale                                                                                          |
|---------------------|----------------------------------------------------------------------------------------------------|
| `years_in_business` | Cannot be inferred from a Google Maps lead; would require registered-business-date data we do not have. |
| `awards`            | Awards require verifiable external recognition; we have no source.                                 |
| `licenses`          | Professional licenses are jurisdiction-specific and require primary-source verification.           |
| `insurance`         | Insurance details are confidential; we have no source.                                             |
| `certifications`    | Same as licenses — requires primary-source verification.                                           |
| `staff_credentials`| Staff data is PII and we have no source.                                                           |
| `testimonials`      | We do not collect or store testimonials; quoting invented ones would be misleading.               |
| `guarantees`        | Service guarantees are contractual; we have no source.                                             |
| `superlatives`      | Marketing superlatives ("best", "#1", etc.) invite unsupported claims and legal risk.             |

The contract author (this module) is the single source of truth for this
list. Downstream phases may consult it but MUST NOT shrink it without
bumping the schema major version.

## Missing-data policy

If a public-safe verified_facts field is absent or empty on the lead
record, it is **omitted from `verified_facts`** and **added to
`missing_data`**. The profile never invents a value for an absent field.

Copy generators are expected to read `missing_data` and either omit the
claim entirely or render an explicit "not on file" marker. They MUST NOT
look up or guess the value from any other source.

`missing_data` is sorted lexicographically so it is reproducible.

## Determinism guarantee

`generated_at` is **derived deterministically** from `(run_id,
business_slug)`. The algorithm is:

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
- Distinct `(run_id, business_slug)` pairs almost always produce distinct
  timestamps (collision rate ≈ 1 / 3650 per `run_id`).

The full profile is otherwise free of nondeterministic inputs: there is no
`uuid`, no `random`, no `time.time()`, and no environment-variable reading.
Two consecutive calls to `build_business_profile(lead, config, run_id=...)`
with the same inputs return byte-identical dicts.

## Backward compatibility and rollback

- The artifact is **opt-in** via the
  `use_business_profile_contract` config flag. The flag defaults to `False`
  in every code path and is NOT set in any default config.
- When the flag is off, Phase 04 produces exactly the same Markdown
  artifacts and `briefs_index.json` shape it always did. The existing
  `tests/phases/test_phase_04_business_brief.py` assertions against
  `tests/fixtures/phase_04_business_brief_generation/expected/*.json` are
  preserved byte-for-byte.
- When the flag is on, the only new filesystem artifact is
  `runs/{run_id}/04_briefs/{business_slug}/business_profile.json` per
  business, plus a per-row entry in `outputs_created` in `result.json`.
- **Rollback** is the default state: stop setting
  `use_business_profile_contract=True` and no new artifacts are produced
  and no consumer is required to read the file. Old Phase 04 outputs
  remain valid indefinitely.

## Versioning rules

- Additive optional fields → minor version bump.
- Renaming or removing a field → major version bump.
- Changing the meaning of an enum value → major version bump.
- Changing the `forbidden_public_claims` list in a way that would
  invalidate downstream copy generators → major version bump.

## Test coverage

Unit tests live in `tests/intelligence/test_business_profile.py`. Phase 04
flag tests live in `tests/phases/test_phase_04_business_brief.py` under
`TestBusinessProfileContractFlag`. The contract is exercised end-to-end
through the existing `selected_lead_*.json` fixtures.
