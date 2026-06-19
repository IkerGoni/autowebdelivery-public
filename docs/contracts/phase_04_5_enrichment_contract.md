# Phase 04.5 Enrichment Contract — Public Fact Expansion Without Invention

## Purpose

Phase 04.5 sits between Phase 04 (business brief generation) and Phase 05 (preview site generation). Its job: expand verified facts with publicly available information to give copywriters richer source material — without inventing, fabricating, or hallucinating any claim. Every enriched fact must trace back to a verifiable public source or be flagged for human review.

## Inputs

| Input | Source | Required |
|---|---|---|
| `preview_ready_briefs.json` | Phase 04 output | Yes |
| Business brief folder per business | `runs/{run_id}/04_briefs/{business_slug}/` | Yes |
| `FACTS.md` | From each business brief folder | Yes |
| Enrichment source config | API keys, search configs | Conditional |

## Output Artifact Paths

All artifacts written under `runs/{run_id}/04_5_enrichment/`:

| Artifact | Path |
|---|---|
| Enriched facts | `runs/{run_id}/04_5_enrichment/{business_slug}/enriched_facts.json` |
| Source trail | `runs/{run_id}/04_5_enrichment/{business_slug}/enrichment_sources.json` |
| Public-safe fields | `runs/{run_id}/04_5_enrichment/{business_slug}/public_safe_fields.json` |
| Internal-only fields | `runs/{run_id}/04_5_enrichment/{business_slug}/internal_only_fields.json` |
| Category mapping | `runs/{run_id}/04_5_enrichment/{business_slug}/category_mapping.json` |
| Design preset candidate | `runs/{run_id}/04_5_enrichment/{business_slug}/design_preset_candidate.json` |
| Visual profile | `runs/{run_id}/04_5_enrichment/{business_slug}/visual_profile.json` |
| Copy inputs | `runs/{run_id}/04_5_enrichment/{business_slug}/copy_inputs.json` |
| Per-business result | `runs/{run_id}/04_5_enrichment/{business_slug}/result.json` |
| Phase-level result | `runs/{run_id}/04_5_enrichment/result.json` |

## Output Artifact Schemas

All schemas inherit global wrapper rules from `pipeline_data_contract.md`: each root artifact wrapper must include `run_id`, `business_slug`, `schema_version`, `created_at`, `updated_at`. Individual RECORD entries inside artifact arrays must include `run_id`, `record_id`, `phase`, `created_at`, `updated_at`.

### enriched_facts.json

```jsonc
{
  "schema_version": "1.0",
  "run_id": "string",
  "business_slug": "string",
  "generated_at": "ISO-8601",
  "facts": [
    {
      "fact_id": "string (uuid)",
      "run_id": "string",
      "record_id": "string",
      "category": "string",            // e.g. "service", "amenity", "history", "team"
      "original_fact": "string",        // from Phase 04 FACTS.md / verified_facts
      "enriched_value": "string | null", // expanded value or null if not enriched
      "enrichment_source": "string",    // URL, dataset name, or public record reference
      "source_verified": "boolean",
      "confidence": "number [0.0-1.0]",
      "contradicts_phase04": "boolean", // true if enrichment conflicts with verified fact
      "provenance": {
        "source_type": "string",        // "google_maps_api" | "google_places_api" | "yelp" | "trustpilot" | "public_directory" | "manual"
        "source_url": "string | null",
        "retrieval_timestamp": "ISO-8601",
        "field_provenance": "string"
      },
      "status": "string",              // "enriched" | "skipped" | "flagged" | "contradicted"
      "notes": "string | null",
      "created_at": "ISO-8601",
      "updated_at": "ISO-8601"
    }
  ]
}
```

### enrichment_sources.json

```jsonc
{
  "schema_version": "1.0",
  "run_id": "string",
  "business_slug": "string",
  "sources": [
    {
      "source_id": "string (uuid)",
      "name": "string",
      "type": "string",               // "google_maps_api" | "google_places_api" | "yelp" | "trustpilot" | "public_directory" | "manual"
      "url": "string | null",
      "accessed_at": "ISO-8601",
      "reliability_score": "number [0.0-1.0]",
      "facts_sourced": ["string (fact_ids)"]
    }
  ],
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

### public_safe_fields.json

```jsonc
{
  "schema_version": "1.0",
  "run_id": "string",
  "business_slug": "string",
  "fields": [
    {
      "field_name": "string",
      "field_value": "string",
      "source_fact_id": "string (uuid)",
      "provenance": {
        "source_type": "string",
        "source_url": "string | null",
        "retrieval_timestamp": "ISO-8601",
        "field_provenance": "string"
      },
      "safe_for_public_copy": true,     // always true in this file
      "copy_slot_eligible": "boolean",
      "gate_status": "string",         // "render_allowed" | "render_allowed_but_not_deploy_eligible" | "needs_review"
      "notes": "string | null"
    }
  ],
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

### internal_only_fields.json

```jsonc
{
  "schema_version": "1.0",
  "run_id": "string",
  "business_slug": "string",
  "fields": [
    {
      "field_name": "string",
      "field_value": "string",
      "reason_internal_only": "string", // why it cannot appear in public copy
      "source_fact_id": "string (uuid)",
      "provenance": {
        "source_type": "string",
        "source_url": "string | null",
        "retrieval_timestamp": "ISO-8601",
        "field_provenance": "string"
      },
      "notes": "string | null"
    }
  ],
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

### category_mapping.json

```jsonc
{
  "schema_version": "1.0",
  "run_id": "string",
  "business_slug": "string",
  "mappings": [
    {
      "fact_id": "string (uuid)",
      "phase04_category": "string",
      "enrichment_category": "string",
      "design_preset_relevant": "boolean",
      "copy_slot_target": "string | null"  // target slot from copy_inputs.json
    }
  ],
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

### design_preset_candidate.json

```jsonc
{
  "schema_version": "1.0",
  "run_id": "string",
  "business_slug": "string",
  "candidates": [
    {
      "preset_id": "clinical_trust | warm_editorial | industrial_reliable | fresh_utility",
      "preset_label": "Clinical Trust | Warm Editorial | Industrial Reliable | Fresh Utility",
      "palette": {},                     // color/token mapping object
      "layout_variant": "string",        // e.g. "hero_with_image", "split_testimonial", "full_width_hero"
      "tone_words": ["string"],          // tone descriptors: "authoritative", "warm", "technical", etc.
      "mapping_reason": "string",        // why this preset fits the enriched data
      "confidence": "number [0.0-1.0]"
    }
  ],
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

The `preset_id` value must come from the fixed canonical catalog used by Phase 05 rendering: `clinical_trust | warm_editorial | industrial_reliable | fresh_utility`. `preset_label` is the matching display label: `Clinical Trust | Warm Editorial | Industrial Reliable | Fresh Utility`. Phase 04.5 may rank up to 3 candidates, but each candidate must use this canonical preset catalog so the Phase 04.5 -> Phase 05 handoff stays deterministic. The candidate object fields (`preset_id`, `preset_label`, `palette`, `layout_variant`, `tone_words`, `mapping_reason`, `confidence`) are the prescribed structure.

`design_preset_candidate.json` remains recommendation artifact. Phase 05 must not treat it as final rendering contract when `visual_profile.json` exists.

### visual_profile.json

Canonical deterministic rendering bundle for Phase 05.

```jsonc
{
  "schema_version": "1.0",
  "run_id": "string",
  "business_slug": "string",
  "record_id": "string",
  "phase": "04_5_enrichment",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "preset_id": "clinical_trust | warm_editorial | industrial_reliable | fresh_utility",
  "preset_variant": "string | null",
  "hero_mode": "photo | abstract | map_context | text_first",
  "photo_policy": "none | preview_demo_only | customer_owned_only",
  "accent_color_candidate": "string | null",
  "accent_color_confidence": "number [0.0-1.0]",
  "accent_source": "place_photo_palette | map_listing_palette | preset_default | operator_override | unknown",
  "tone_axes": {
    "formality": "number [0.0-1.0]",
    "warmth": "number [0.0-1.0]",
    "luxury": "number [0.0-1.0]",
    "energy": "number [0.0-1.0]"
  },
  "trust_chip_candidates": [
    {
      "label": "string",
      "source_type": "reviews | rating | review_count | place_attribute | business_status | category | editorial_summary | operator_override",
      "source_ref": "string | null",
      "confidence": "number [0.0-1.0]",
      "attribution_required": "boolean"
    }
  ],
  "review_summary_candidate": {
    "text": "string | null",
    "attribution_uri": "string | null",
    "attribution_required": "boolean"
  },
  "editorial_summary_candidate": {
    "text": "string | null",
    "source_uri": "string | null",
    "attribution_required": "boolean"
  },
  "photo_candidates": [
    {
      "photo_ref": "string",
      "source_type": "google_places | operator_uploaded | customer_uploaded",
      "width": "number | null",
      "height": "number | null",
      "aspect_ratio": "number | null",
      "orientation": "landscape | portrait | square | unknown",
      "is_primary": "boolean",
      "sort_order": "integer",
      "selection_signals": ["string"],
      "attribution_uri": "string | null",
      "attribution_required": "boolean",
      "license_note": "string | null"
    }
  ],
  "local_visual_cues": [
    {
      "cue_type": "map_area | neighborhood | streetscape | geo_context | service_area",
      "label": "string",
      "source_ref": "string | null",
      "confidence": "number [0.0-1.0]"
    }
  ],
  "attribution_requirements": [
    {
      "asset_type": "review_summary | editorial_summary | photo | trust_chip",
      "asset_ref": "string",
      "requirement": "string"
    }
  ],
  "brand_risk_flags": ["string"],
  "visual_personalization_score_inputs": {
    "has_photo_candidates": "boolean",
    "photo_candidate_count": "integer",
    "has_review_summary_candidate": "boolean",
    "has_editorial_summary_candidate": "boolean",
    "has_local_visual_cues": "boolean",
    "local_visual_cue_count": "integer",
    "accent_color_confidence": "number [0.0-1.0]",
    "trust_chip_count": "integer",
    "preset_confidence": "number [0.0-1.0]",
    "public_signal_coverage_score": "number [0.0-1.0]"
  }
}
```

Rules:

- `visual_profile.json` must be derived from Places/public enrichment and verified Phase 04 facts, not arbitrary scraping
- `photo_candidates[]` may include only safe metadata and selection signals, not invented image semantics
- `review_summary_candidate` and `editorial_summary_candidate` must preserve source attribution requirements
- `hero_mode` and `photo_policy` must support preview demo mode versus production deploy mode distinctions
- if `photo_policy=preview_demo_only`, Phase 05 may use those assets only in preview demo mode with attribution
- production deploy mode must not use `preview_demo_only` imagery

### copy_inputs.json

```jsonc
{
  "schema_version": "1.0",
  "run_id": "string",
  "business_slug": "string",
  "slots": {
    "hero_tagline": "string | null",
    "hero_supporting_line": "string | null",
    "overview_intro": "string | null",
    "overview_support_block_1": "string | null",
    "overview_support_block_2": "string | null",
    "trust_intro": "string | null",
    "location_intro": "string | null",
    "cta_body": "string | null",
    "footer_note": "string | null"
  },
  "slot_provenance": {
    "hero_tagline": { "source_fact_id": "string | null", "enrichment_used": "boolean" },
    "hero_supporting_line": { "source_fact_id": "string | null", "enrichment_used": "boolean" },
    "overview_intro": { "source_fact_id": "string | null", "enrichment_used": "boolean" },
    "overview_support_block_1": { "source_fact_id": "string | null", "enrichment_used": "boolean" },
    "overview_support_block_2": { "source_fact_id": "string | null", "enrichment_used": "boolean" },
    "trust_intro": { "source_fact_id": "string | null", "enrichment_used": "boolean" },
    "location_intro": { "source_fact_id": "string | null", "enrichment_used": "boolean" },
    "cta_body": { "source_fact_id": "string | null", "enrichment_used": "boolean" },
    "footer_note": { "source_fact_id": "string | null", "enrichment_used": "boolean" }
  },
  "gate_status": "string",            // "render_allowed" | "render_allowed_but_not_deploy_eligible" | "needs_review"
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

### result.json (per-business)

```jsonc
{
  "schema_version": "1.0",
  "phase": "04_5_enrichment",
  "status": "done | blocked | failed | needs_review",
  "run_id": "string (uuid)",
  "business_slug": "string",
  "started_at": "ISO-8601",
  "completed_at": "ISO-8601",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "inputs_used": [
    "runs/{run_id}/04_briefs/{business_slug}/FACTS.md"
  ],
  "outputs_created": [
    "runs/{run_id}/04_5_enrichment/{business_slug}/enriched_facts.json",
    "runs/{run_id}/04_5_enrichment/{business_slug}/enrichment_sources.json",
    "runs/{run_id}/04_5_enrichment/{business_slug}/public_safe_fields.json",
    "runs/{run_id}/04_5_enrichment/{business_slug}/internal_only_fields.json",
    "runs/{run_id}/04_5_enrichment/{business_slug}/category_mapping.json",
    "runs/{run_id}/04_5_enrichment/{business_slug}/design_preset_candidate.json",
    "runs/{run_id}/04_5_enrichment/{business_slug}/visual_profile.json",
    "runs/{run_id}/04_5_enrichment/{business_slug}/copy_inputs.json",
    "runs/{run_id}/04_5_enrichment/{business_slug}/result.json"
  ],
  "records_processed": "integer",
  "records_created": "integer",
  "records_skipped": "integer",
  "scores": {
    "data_depth_score": "number [0-100]",       // coverage of enriched facts vs possible enrichment surface
    "public_copy_ready_score": "number [0-100]", // % of fields safe for public copy
    "trust_signal_score": "number [0-100]",      // strength of verifiable trust signals
    "local_context_score": "number [0-100]",     // richness of local/geo context
    "missing_core_fields_count": "integer"       // core fields that remain unenriched
  },
  "gates": {
    "render_allowed": "boolean",
    "render_allowed_but_not_deploy_eligible": "boolean",
    "needs_review": "boolean"
  },
  "missing_fields": ["string"],
  "decisions": ["string"],
  "risks": ["string"],
  "errors": ["string"],
  "flags": ["string"],
  "summary": "string",
  "next_tasks": ["string"]
}
```

### result.json (phase-level)

Located at `runs/{run_id}/04_5_enrichment/result.json`. Follows the standard phase result envelope from `pipeline_data_contract.md`:

```jsonc
{
  "phase": "04_5_enrichment",
  "status": "done | blocked | failed | needs_review",
  "run_id": "string",
  "inputs_used": [],
  "outputs_created": [],
  "records_processed": "integer",
  "records_created": "integer",
  "records_skipped": "integer",
  "missing_fields": [],
  "decisions": [],
  "risks": [],
  "errors": [],
  "next_tasks": []
}
```

## Scoring Model

| Score | Range | Definition |
|---|---|---|
| `data_depth_score` | 0-100 | Percentage of verified facts that received meaningful enrichment. 100 = every fact expanded with at least one public source. |
| `public_copy_ready_score` | 0-100 | Percentage of enriched fields classified as `public_safe_fields`. Penalized for internal-only or flagged fields. |
| `trust_signal_score` | 0-100 | Measures strength of verifiable trust signals (reviews, certifications, years in business, team bios). Higher when multiple corroborating sources exist. |
| `local_context_score` | 0-100 | Richness of geographic, demographic, and market context. Penalized for generic/national-only enrichment. |
| `missing_core_fields_count` | integer (0+) | Count of core business fields (name, address, phone, primary service area, hours) that remain unenriched or unverifiable. |

Scoring thresholds:

- `data_depth_score` >= 70 and `public_copy_ready_score` >= 80: enrichment surface strong
- `trust_signal_score` >= 60: sufficient trust for CTA presence
- `local_context_score` < 40: flag geo enrichment gap
- `missing_core_fields_count` > 3: block deploy eligibility until resolved

## Gating Rules

### Gate Status Values

| Status | Meaning |
|---|---|
| `render_allowed` | All enriched facts pass safety and verification checks. Safe to render in preview. |
| `render_allowed_but_not_deploy_eligible` | Content is safe for preview rendering but contains gaps or low-confidence enrichment preventing production deploy. |
| `needs_review` | One or more enriched values conflict with verified facts, lack sourcing, or require human judgment before any render. |

### Gate Logic

1. If any field in `contradicts_phase04: true` → set gate to `needs_review`.
2. Else if `missing_core_fields_count > 3` → set gate to `render_allowed_but_not_deploy_eligible`.
3. Else → set gate to `render_allowed`.

A single `needs_review` flag overrides `render_allowed`. Highest-severity gate wins.

## Field Policy

### public_safe_fields

Fields that may appear in public-facing copy without restriction:

- Business name (verified)
- Verified service names and descriptions
- Verified physical address and service area
- Verified contact information (phone, email)
- Verified operating hours
- Publicly sourced team bios (name, title, verified credential)
- Verified awards, certifications (with source citation)
- Verified community involvement / sponsorships
- Verified customer review excerpts (attributed)

### internal_only_fields

Fields that must NEVER appear in public copy, stored only for operator reference:

- Raw enrichment confidence scores for individual facts
- Internal contradiction flags and notes
- Unverified service claims pending review
- Pricing estimates, competitor pricing, or market rate data
- Employee personal information beyond public bios
- Lead source data or CRM identifiers
- Internal workflow metadata (timestamps, pipeline stage markers)
- Any field derived from a single low-reliability source (< 0.4 reliability_score)

## Design Preset Candidate Rules

1. Presets are selected based on enriched category distribution and tone signals.
2. A preset candidate must map to at least 3 enriched fact categories to qualify.
3. `tone_words` pulled from verified service descriptions, review language, and business self-description.
4. `confidence` calculated as average enrichment confidence across mapped facts, weighted by category importance (core categories weighted 2x).
5. Maximum 3 preset candidates generated per business. Ranked by confidence descending.
6. If `trust_signal_score < 40`, the candidate's `tone_words` should not include authority-signaling tones; prefer approachachable or local-oriented tone words instead.

Each candidate must use canonical fields `preset_id`, `preset_label`, `palette`, `layout_variant`, `tone_words`, `mapping_reason`, and `confidence`. `preset_id` must be one of `clinical_trust | warm_editorial | industrial_reliable | fresh_utility`; free-form preset names are not allowed in this handoff.

## Copy Input Slot Rules

The following slots are populated during enrichment and passed to Phase 05:

| Slot Name | Type | Source |
|---|---|---|
| `hero_tagline` | string | Primary service tagline, enriched from verified service description |
| `hero_supporting_line` | string | Secondary qualifier, enriched from trust signals or differentiators |
| `overview_intro` | string | Business overview opening, synthesized from verified facts |
| `overview_support_block_1` | string | First support paragraph; enriched from service detail or history |
| `overview_support_block_2` | string | Second support paragraph; enriched from differentiators or community involvement |
| `trust_intro` | string | Trust section opener; sourced from verified credentials, years, or review signals |
| `location_intro` | string | Location/service area intro; enriched from geo context data |
| `cta_body` | string | Call-to-action body copy; generated from service + location context |
| `footer_note` | string | Footer legal/compliance note; enriched from verified credentials or licenses |

**Slot population rules:**

- A slot is only populated if its source fact has `source_verified: true`.
- If a slot's source fact is missing, the slot value is `null` and flagged in `result.json`.
- Slots drawing from contradicted enrichment data must have `gate_status: "needs_review"`.
- No slot may contain unverified pricing, staffing numbers, or guarantee language.

## Contradiction Handling

1. **Detection**: During enrichment, if an enriched value for a fact conflicts with the verified facts from Phase 04's `FACTS.md`, the system sets `contradicts_phase04: true` on that fact record.
2. **Public copy exclusion**: If `contradicts_phase04: true`, the enriched value is NOT used in any `public_safe_fields` entry or copy input slot.
3. **Flag propagation**: Any slot sourcing a contradicted fact gets `gate_status: "needs_review"` in `copy_inputs.json`.
4. **Operator notification**: Contradicted facts are listed in `result.json` → `flags` with a human-readable description.
5. **Resolution**: Only a human operator or Phase 04 re-verification can resolve a contradiction. The enrichment layer never overrides a Phase 04 verified fact.
6. **Logging**: All contradictions logged in `enrichment_sources.json` with the conflicting source identified.

## Integration with Phase 04, 05, and 06

### Phase 04 (Input)
- Reads `runs/{run_id}/04_briefs/preview_ready_briefs.json` to get the list of businesses to enrich.
- Reads each business's `runs/{run_id}/04_briefs/{business_slug}/FACTS.md` as primary input.
- Treats all Phase 04 verified facts as ground truth. No enrichment value may contradict them.
- Inherits the `run_id`, `business_slug`, and `record_id` from Phase 04 context.

### Phase 05 (Output Consumer)
- Writes `copy_inputs.json` with populated slots for Phase 05 preview site generation.
- Passes `result.json` scores so Phase 05 can adjust copy tone and ambition level.
- Phase 05 must NOT use slots marked `needs_review` in its generated copy unless cleared by operator.
- Passes `design_preset_candidate.json` as ranked recommendation and `visual_profile.json` as final deterministic rendering contract.
- `visual_profile.json` controls `hero_mode`, `photo_policy`, attribution obligations, and safe visual personalization signals.

Mode note:
- preview demo mode may use `photo_policy=preview_demo_only` assets with required attribution
- production deploy mode must not use `preview_demo_only` assets
- production deploy mode may use `customer_owned_only` assets only after customer-provided or rights-cleared replacement exists

### Phase 06 (Downstream)
- Phase 06 (quality gate) reads `public_safe_fields.json` and `internal_only_fields.json` to enforce field-level rendering restrictions.
- Phase 06 reads `result.json` → `gates` to determine if preview is deploy-ready or operator review required.
- `internal_only_fields.json` content is excluded from all rendered preview output.

## Block Conditions

Phase 04.5 must return `blocked` status if:

```text
BusinessBrief folder missing for a selected business
FACTS.md missing
enrichment source config unavailable (API keys etc.)
```

## Non-Goals / Prohibited Behavior

The enrichment layer MUST NOT:

1. **Invent services**. No fabricating service offerings not verified in Phase 04.
2. **Invent pricing**. No generating, estimating, or inferring price points, packages, or cost ranges.
3. **Invent staff names or roles**. No creating employee names, titles, or team structures beyond what is publicly verifiable.
4. **Fabricate years in business**. No claiming tenure unless explicitly verified.
5. **Invent certifications or licenses**. No generating credentials unless sourced from public records.
6. **Fabricate testimonials or reviews**. No generating customer quotes or satisfaction claims.
7. **Invent guarantees or warranties**. No generating promise language.
8. **Fabricate amenities**. No adding facilities, features, or capabilities not verified.
9. **Generate operational claims**. No making claims about capacity, throughput, response times, or service levels without verified source.
10. **Override Phase 04 verified facts**. Enrichment expands, never contradicts or replaces verified data.
11. **Use single low-reliability sources**. No fact enriched from only one source with reliability_score < 0.5 may enter `public_safe_fields`.
12. **Hallucinate source citations**. Every `enrichment_source` must correspond to a real, retrievable public record or dataset.
