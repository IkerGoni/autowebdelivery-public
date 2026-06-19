# Sales Package Contract (v1.0.0)

> **Status:** VNEXT-08 — feature-flagged (default OFF).
> **Schema version:** `1.0.0`
> **Owner:** Phase 08 (Sales Package generation)
> **Consumers (planned):** Phase 09 (approval pack), owner-facing communications.

## Purpose

`sales_package.json` is the **structured owner-facing sales package** artifact
for a single preview-ready lead. It aggregates data from upstream artifacts
(business_profile, market_profile, creative_spec, evaluation_report) into a
single, deterministic package that is independent of outreach message text.

Goals:

1. Make the owner-facing sales package a **structured artifact** independent of
   outreach message text.
2. Aggregate all relevant data from upstream phases into one canonical location.
3. Generate a **deterministic, template-based** owner-facing summary (no LLM).
4. Maintain **provenance and confidence** on every value.
5. Ensure **compliance** by surfacing forbidden claims checks and missing data.

## Schema version

The artifact always carries a top-level `schema_version` string in SemVer
form. The current value is `"1.0.0"`. Breaking changes to field names, types,
or semantics require a major-version bump; additive fields are allowed under
minor versions.

## Top-level shape

```json
{
  "schema_version": "1.0.0",
  "run_id": "run_001",
  "business_slug": "north-dallas-mobile-detailing",
  "generated_at": "2026-04-15T00:00:00Z",
  "preview_url": {
    "value": "https://example.com",
    "source": "deployment",
    "confidence": "verified"
  },
  "screenshots": {
    "desktop": {
      "value": "/path/to/desktop.png",
      "source": "phase_05_5",
      "confidence": "verified"
    },
    "mobile": {
      "value": "/path/to/mobile.png",
      "source": "phase_05_5",
      "confidence": "verified"
    }
  },
  "business_summary": {
    "business_name": {
      "value": "North Dallas Mobile Detailing",
      "source": "business_profile.json",
      "confidence": "verified"
    },
    "category": {
      "value": "Auto Detailing",
      "source": "business_profile.json",
      "confidence": "verified"
    },
    "rating": {
      "value": 4.8,
      "source": "business_profile.json",
      "confidence": "verified"
    },
    "review_count": {
      "value": 180,
      "source": "business_profile.json",
      "confidence": "verified"
    },
    "address": {
      "value": "123 Main St, Dallas, TX 75201",
      "source": "business_profile.json",
      "confidence": "verified"
    },
    "phone": {
      "value": "+1-555-123-4567",
      "source": "business_profile.json",
      "confidence": "verified"
    }
  },
  "offer": {
    "price": {
      "value": "$299",
      "source": "input_config.json",
      "confidence": "verified"
    },
    "description": {
      "value": "One-time setup",
      "source": "input_config.json",
      "confidence": "verified"
    }
  },
  "evaluation_summary": {
    "overall_score": 82.3,
    "verdict": "pass",
    "top_dimensions": {
      "factual_safety": 100,
      "trust": 85,
      "conversion": 80
    }
  },
  "recipient_channel": {
    "channel": "phone",
    "value": "+1-555-123-4567",
    "source": "google_maps_listing",
    "confidence": "verified"
  },
  "compliance_notes": {
    "forbidden_claims_checked": true,
    "no_unsupported_claims": true,
    "missing_data_noted": []
  },
  "owner_facing_summary": "A professional website for North Dallas Mobile Detailing showcasing their Auto Detailing services with a 4.8 rating from 180 reviews and easy booking.",
  "missing_data": [],
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
  "internal": {
    "flag": "use_sales_package_contract",
    "schema_origin": "VNEXT-08"
  }
}
```

## Field descriptions

### preview_url
Live URL of the deployed site. Provenance envelope with source `"deployment"`.
Empty string with confidence `"unknown"` if not yet deployed.

### screenshots
Desktop and mobile screenshot paths/URLs. Source is `"phase_05_5"`.
Absent if no screenshots were provided.

### business_summary
Key business facts extracted from `business_profile.json` verified_facts.
Each field is a provenance envelope. Fields present only if the upstream data
exists (no invented values).

### offer
Pricing offer from `input_config.json`. Contains `price` and `description`.
Description is derived from `offer_type`: `"setup_only"` → `"One-time setup"`.

### evaluation_summary
Top-level evaluation metrics from `evaluation_report.json`:
- `overall_score`: numeric or `null` if no evaluation
- `verdict`: `"pass"`, `"fail"`, or `"not_evaluated"`
- `top_dimensions`: up to 3 highest-scoring dimension scores

### recipient_channel
Contact channel for reaching the business owner, extracted from
`business_profile.json`. Mirrors the recipient_channel shape from VNEXT-01.

### compliance_notes
Compliance verification:
- `forbidden_claims_checked`: always `true` (module always runs the check)
- `no_unsupported_claims`: `true` if no violations detected
- `missing_data_noted`: sorted list of missing data fields from business_profile

### owner_facing_summary
Template-based, deterministic, 1-2 sentence summary. No LLM involved.

Template: `"A professional website for {business_name} showcasing their
{category} services{rating_phrase}{contact_phrase}."`

- `rating_phrase`: `" with a {rating} rating from {review_count} reviews"` if
  both rating and review_count are present
- `contact_phrase`: `" and easy booking"` if phone is present

### missing_data
Aggregated missing data signals across all sources:
- From `business_profile.missing_data`
- `"preview_url"` if no deployment URL
- `"screenshots"` if no screenshots provided
- Individual screenshot types if partially missing
- `"evaluation_report"` if no evaluation was run

Always sorted and deduplicated.

### forbidden_public_claims
Explicit blocklist of claim categories that must never appear in public copy.
Always present, always non-empty. Same blocklist as VNEXT-01.

### internal
Labelled block identifying the feature flag and schema origin. Never forwarded
to public copy.

## Owner-facing summary generation

The summary is generated purely from template substitution:

```
"A professional website for {business_name} showcasing their {category} services{rating_phrase}{contact_phrase}."
```

Where:
- `{business_name}` — from verified_facts, or `"your business"` if absent
- `{category}` — from verified_facts; `" their {category} services"` if present, `" their services"` if absent
- `{rating_phrase}` — `" with a {rating} rating from {review_count} reviews"` if both present
- `{contact_phrase}` — `" and easy booking"` if phone present

No LLM, no randomness, fully deterministic.

## Provenance and confidence enums

Same as VNEXT-01:

| Enum value   | Meaning                                                                |
|--------------|------------------------------------------------------------------------|
| `verified`   | Value from authoritative source for this run                           |
| `inferred`   | Value derived from non-authoritative signal                            |
| `unknown`    | Value present but provenance unknown                                   |

Sources:
- `business_profile.json` — verified facts from VNEXT-01
- `input_config.json` — run-level config (pricing, offer type)
- `deployment` — live URL from Phase 07
- `phase_05_5` — screenshots from Phase 05.5
- `google_maps_listing` — phone from Google Maps record
- `evaluation_report.json` — evaluation metrics from VNEXT-06

## Determinism guarantee

`generated_at` uses the same algorithm as VNEXT-01 but with a different
namespace prefix (`"sales_pkg|"`) to avoid collision:

1. `digest = sha256(f"sales_pkg|{run_id}|{business_slug}".encode("utf-8"))`
2. First 8 hex chars → 32-bit unsigned int
3. Modulo 3650 → day offset
4. `2026-01-01T00:00:00Z + day_offset days`

All other fields are free of nondeterministic inputs. Two consecutive calls
with identical inputs produce byte-identical dicts.

## Backward compatibility and rollback

- The artifact is **opt-in** via the `use_sales_package_contract` config flag.
  The flag defaults to `False` and is NOT set in any default config.
- When the flag is off, existing Phase 08/09 produce exactly the same output.
- When the flag is on, the only new filesystem artifact is
  `runs/{run_id}/{business_slug}/sales_package.json`.
- **Rollback** is the default state: stop setting the flag and no new artifacts
  are produced.

## Versioning rules

- Additive optional fields → minor version bump
- Renaming or removing a field → major version bump
- Changing the meaning of an enum value → major version bump
- Changing `forbidden_public_claims` in a way that invalidates downstream →
  major version bump

## Test coverage

Unit tests live in `tests/sales/test_sales_package.py`. Four gate structure:

- **Gate A:** Schema, required keys, determinism (10 tests)
- **Gate B:** No unsupported claims in owner_facing_summary, forbidden
  blocklist, compliance notes (11 tests)
- **Gate C:** Backward compat — additive only (2 tests)
- **Gate D:** Write function, internal block, missing data, sections (18 tests)

Total: 41 tests.
