# Pipeline Data Contract — Auto Web Project MVP

> **NOTE:** This document contains both implemented and planned/aspiring schemas. The implemented parts are marked. For actual runtime contracts, see `docs/contracts/PIPELINE_CONTRACTS.md`.

## Purpose

This file is the canonical data contract for all phases. Every phase must read and write these objects exactly. Do not invent new field names when an existing field fits.

The pipeline must support two execution modes:

1. **Full run mode:** phases execute in order under one `run_id`.
2. **Standalone phase mode:** any phase can run independently when given its required input artifact(s).

If required input is missing, a phase must return a structured `blocked` result instead of guessing.

---

## Global rules

### Required on every record

```json
{
  "run_id": "2026-05-10_chiang-mai_dentists_001",
  "record_id": "stable_unique_id",
  "phase": "02_basic_lead_discovery",
  "created_at": "ISO-8601 timestamp",
  "updated_at": "ISO-8601 timestamp"
}
```

### Phase result envelope

Every worker must return this result envelope.

```json
{
  "phase": "03_lead_scoring",
  "status": "done | blocked | failed | needs_review",
  "run_id": "",
  "inputs_used": [],
  "outputs_created": [],
  "records_processed": 0,
  "records_created": 0,
  "records_skipped": 0,
  "missing_fields": [],
  "decisions": [],
  "risks": [],
  "errors": [],
  "next_tasks": []
}
```

### Status values

Use only these values unless a phase-specific status table says otherwise.

```text
done
blocked
failed
needs_review
skipped
```

### No guessing rule

Agents and scripts must not invent:

```text
business facts
schema fields
lead scores without inputs
contact channels
service lists
prices
staff names
history
awards
testimonials
deployment URLs
approval states
sent status
```

If data is missing, write it as `null`, empty array, or a `missing_fields` item.

---

## Object: RunConfig

Created by Phase 01.

```json
{
  "run_id": "",
  "niche": "dentists",
  "area": "Chiang Mai",
  "country": "Thailand",
  "language": "English",
  "max_raw_results": 100,
  "max_preview_sites": 5,
  "minimum_rating": 4.3,
  "minimum_reviews": 40,
  "style_preset": "clinical_trust | warm_editorial | industrial_reliable | fresh_utility | null",
  "deploy_mode": "preview_demo_mode | production_deploy_mode",
  "price_offer": "$299 one-time setup",
  "mvp_stop_threshold": 20,
  "created_at": "",
  "target_niche_cluster": "",
  "target_buyer_profile": "",
  "area_scoring_strategy": "area_first",
  "query_variants": [],
  "search_radius_km": 10,
  "center_lat": null,
  "center_lng": null,
  "excluded_categories": [],
  "excluded_name_keywords": [],
  "include_social_only": true,
  "weak_site_policy": "skip_parked",
  "enable_http_verification": true,
  "scoring_weights": {
    "rating_score": 20,
    "review_volume_score": 25,
    "contactability_score": 20,
    "category_value_score": 20,
    "freshness_score": 10,
    "confidence_score": 5,
    "risk_penalty": 40
  },
  "qualification_threshold": 65,
  "area_pre_score": true,
  "language_mode": "English",
  "bilingual_priority": false,
  "tourism_weight": 0,
  "competition_weight": 0,
  "niche_value_weight": 0
}
```

Required fields:

```text
run_id
niche
area
country
language
max_raw_results
max_preview_sites
minimum_rating
minimum_reviews
style_preset
deploy_mode
price_offer
mvp_stop_threshold
created_at
target_niche_cluster
target_buyer_profile
area_scoring_strategy
query_variants
search_radius_km
center_lat
center_lng
excluded_categories
excluded_name_keywords
include_social_only
weak_site_policy
enable_http_verification
scoring_weights
qualification_threshold
area_pre_score
language_mode
bilingual_priority
tourism_weight
competition_weight
niche_value_weight
```

`style_preset` is optional operator override. If null or omitted, Phase 05 must use `visual_profile.preset_id` when `visual_profile.json` exists, else use the highest-confidence Phase 04.5 preset candidate, then fall back to site-template niche mapping only when no Phase 04.5 candidate exists.

`deploy_mode` controls preview-versus-production rendering policy. Allowed values: `preview_demo_mode` and `production_deploy_mode`. Default is `production_deploy_mode` when field is omitted by older runs.

---

## Object: QueryPlan

Created by Phase 01, consumed by Phase 02.

```json
{
  "run_id": "",
  "queries": [
    {
      "query_id": "",
      "search_text": "dentists Chiang Mai",
      "niche": "dentists",
      "area": "Chiang Mai",
      "country": "Thailand",
      "max_results": 50
    }
  ]
}
```

---

## Object: RawPlace

Created by Phase 02.

```json
{
  "run_id": "",
  "record_id": "",
  "source": "google_maps_scraper | google_places_api | serpapi | apify | manual_fixture",
  "source_query": "",
  "business_name": "",
  "place_id": "",
  "category": "",
  "rating": 0,
  "review_count": 0,
  "address": "",
  "phone": "",
  "website": "",
  "maps_url": "",
  "hours": "",
  "secondary_categories": [],
  "short_public_description": "",
  "attributes": {
    "wheelchair_accessible": null,
    "parking": null,
    "wifi": null,
    "air_conditioning": null,
    "delivery": null,
    "reservation": null,
    "price_level": null
  },
  "price_level": null,
  "editorial_summary": "",
  "structured_hours": {},
  "photo_count": 0,
  "photo_metadata": [],
  "geo": {
    "lat": null,
    "lng": null,
    "neighborhood": "",
    "city_area": ""
  },
  "social_profiles": [],
  "query_rank": null,
  "business_status": "open | closed | unknown",
  "raw_payload_ref": "",
  "created_at": ""
}
```

Minimum fields for downstream processing:

```text
business_name
category
rating
review_count
address or maps_url
website
geo.lat and geo.lng
price_level
structured_hours
```

If `website` is unavailable from the data source, Phase 02 must mark the phase result `needs_review` or `blocked`; it must not continue to scoring.

---

## Object: NormalizedPlace

Created by Phase 02.

```json
{
  "run_id": "",
  "record_id": "",
  "raw_record_id": "",
  "business_name": "",
  "business_slug": "",
  "place_id": "",
  "category": "",
  "rating": 0,
  "review_count": 0,
  "address": "",
  "phone": "",
  "website_raw": "",
  "maps_url": "",
  "hours": "",
  "business_status": "open | closed | unknown",
  "dedupe_key": "",
  "normalization_notes": []
}
```

### `business_slug` rules

`business_slug` is used for folder names, URL paths, deployment names, and review tables. Generate it deterministically:

```text
lowercase
transliterate to Latin where possible
strip non-ASCII after transliteration
replace spaces and symbols with hyphen
collapse repeated hyphens
trim leading/trailing hyphens
max 50 characters before suffix
append last 4-6 characters of record_id for uniqueness
```

Example:

```text
Bright Smile Dental Clinic + rec_9f31a8 -> bright-smile-dental-clinic-31a8
```

---

## Object: WebsiteClassification

Created by Phase 02.1.

```json
{
  "run_id": "",
  "record_id": "",
  "business_slug": "",
  "website_raw": "",
  "website_normalized": "",
  "registered_domain": "",
  "domain_type": "empty | maps | social | business_domain | malformed | unknown",
  "website_status": "no_website | social_only | has_website | uncertain | invalid_url",
  "confidence": 0.0,
  "decision": "keep | skip | manual_review",
  "reason_codes": [],
  "http_checked": false,
  "http_status": null,
  "final_url": null,
  "redirect_chain": [],
  "checked_redirect": false,
  "website_resolution_status": "not_checked | live | dead | parked | social_redirect | maps_redirect | shortlink | ssl_error | timeout | unknown",
  "notes": []
}
```

HTTP field rule:

```text
All HTTP/redirect fields must be present on every WebsiteClassification record. When verification is not run, use http_checked=false, http_status=null, final_url=null, redirect_chain=[], checked_redirect=false, and website_resolution_status=not_checked.
```

Continuation rule:

```text
Keep only website_status = no_website or social_only.

Suspicious, dead, parked, social-redirecting, shortlink, Google Maps, SSL-error, and timeout cases must be classified as `uncertain` unless clear source data supports another status. Failed HTTP checks must not be converted to `no_website`.
Skip has_website.
Manual review or skip uncertain/invalid_url in MVP.
```

---

## Object: LeadScore

Created by Phase 03.

```json
{
  "run_id": "",
  "record_id": "",
  "business_slug": "",
  "website_status": "no_website | social_only",
  "rating_score": 0,
  "review_volume_score": 0,
  "contactability_score": 0,
  "category_value_score": 0,
  "freshness_score": 0,
  "confidence_score": 0,
  "risk_penalty": 0,
  "lead_score": 0,
  "qualification_status": "qualified | rejected | needs_review",
  "rejection_reasons": [],
  "scoring_notes": []
}
```

Note: `website_status` contains only `no_website | social_only` because other statuses (`has_website`, `uncertain`, `invalid_url`) are filtered or rerouted in Phase 02.1 before reaching Phase 03 scoring.

Recommended default score weights:

```text
rating_score: 0–20
review_volume_score: 0–25
contactability_score: 0–20
category_value_score: 0–20
freshness_score: 0–10
confidence_score: 0–5
risk_penalty: 0–40 deducted
lead_score max before penalties: 100
```

Default qualification rule:

```text
rating >= 4.0
review_count >= 20
business_status != closed
website_status in [no_website, social_only]
lead_score >= 60
risk_penalty < 20
```

Contactability affects `contactability_score` and `confidence_score`; it is not a hard rejection in Phase 03 because full recipient discovery happens in Phase 04.

`scoring_notes`: Human-readable explanation of score composition and any anomalies.

---

## Object: BusinessBrief

Created by Phase 04; enriched by Phase 04.5 if enabled.

```json
{
  "run_id": "",
  "record_id": "",
  "business_slug": "",
  "verified_facts": {
    "business_name": "",
    "category": "",
    "rating": 0,
    "review_count": 0,
    "address": "",
    "phone": "",
    "hours": "",
    "maps_url": "",
    "website_status": ""
  },
  "enrichment": {
    "enriched_facts": {},
    "public_safe_fields": {},
    "internal_only_fields": {},
    "enrichment_sources": {},
    "category_mapping": {},
    "design_preset_candidate": {},
    "visual_profile": {},
    "copy_inputs": {},
    "enrichment_timestamp": "",
    "enrichment_depth_score": 0,
    "gate_result": "render_allowed | render_allowed_but_not_deploy_eligible | needs_review"
  },
  "recipient_channel": "email | contact_form | phone | facebook_message | instagram_dm | line | unknown",
  "recipient_value": "",
  "recipient_source": "",
  "recipient_confidence": "verified | inferred | unknown",
  "missing_fields": [],
  "safe_summary": "",
  "content_plan": [],
  "design_preset": "clinical_trust | warm_editorial | industrial_reliable | fresh_utility",
  "copy_inputs": {},
  "content_plan_v2": {
    "hero": { "purpose": "", "required_facts": [], "optional_facts": [], "fallback_class": "", "minimum_words": 30 },
    "services_overview": { "purpose": "", "required_facts": [], "optional_facts": [], "fallback_class": "", "minimum_words": 50 },
    "trust": { "purpose": "", "required_facts": [], "optional_facts": [], "fallback_class": "", "minimum_words": 20 },
    "location_and_hours": { "purpose": "", "required_facts": [], "optional_facts": [], "fallback_class": "", "minimum_words": 20 },
    "contact_cta": { "purpose": "", "required_facts": [], "optional_facts": [], "fallback_class": "", "minimum_words": 15 },
    "footer": { "purpose": "", "required_facts": [], "optional_facts": [], "fallback_class": "", "minimum_words": 10 }
  },
  "narrative_arc": {
    "visitor_intent": "",
    "primary_cta_strategy": "",
    "trust_assets": [],
    "allowed_persuasion_angle": "",
    "prohibited_specificity_notes": ""
  },
  "missing_data_cautions": [],
  "preview_eligibility": "render_allowed | render_allowed_but_not_deploy_eligible | needs_review | blocked",
  "forbidden_claims_removed": [],
  "generation_prompt_ref": ""
}
```

Notes:
- `content_plan` is deprecated. Use `content_plan_v2` which has per-section structure with purpose, required_facts, and fallback_class.
- `preview_eligibility` extends the enrichment gate status with `blocked` for cases where Phase 04.5 does not run at all. When Phase 04.5 runs, `preview_eligibility` aligns with `enrichment.gate_result`.

---

Created by Phase 04.5.

```json
{
  "run_id": "",
  "record_id": "",
  "phase": "04_5_enrichment",
  "business_slug": "",
  "enriched_facts": {
    "path": "runs/{run_id}/04_5_enrichment/{business_slug}/enriched_facts.json",
    "facts": [
      {
        "fact_id": "",
        "record_id": "",
        "category": "",
        "original_fact": "",
        "enriched_value": null,
        "enrichment_source": "",
        "source_verified": false,
        "confidence": 0.0,
        "contradicts_phase04": false,
        "provenance": {
          "source_type": "google_maps_api | google_places_api | yelp | trustpilot | public_directory | manual",
          "source_url": null,
          "retrieval_timestamp": "",
          "field_provenance": ""
        },
        "status": "enriched | skipped | flagged | contradicted",
        "notes": null,
        "created_at": "",
        "updated_at": ""
      }
    ]
  },
  "public_safe_fields": {
    "path": "runs/{run_id}/04_5_enrichment/{business_slug}/public_safe_fields.json",
    "fields": [
      {
        "field_name": "",
        "field_value": "",
        "source_fact_id": "",
        "provenance": {
          "source_type": "",
          "source_url": null,
          "retrieval_timestamp": "",
          "field_provenance": ""
        },
        "safe_for_public_copy": true,
        "copy_slot_eligible": false,
        "gate_status": "render_allowed | render_allowed_but_not_deploy_eligible | needs_review",
        "notes": null
      }
    ]
  },
  "internal_only_fields": {
    "path": "runs/{run_id}/04_5_enrichment/{business_slug}/internal_only_fields.json",
    "fields": [
      {
        "field_name": "",
        "field_value": "",
        "reason_internal_only": "",
        "source_fact_id": "",
        "provenance": {
          "source_type": "",
          "source_url": null,
          "retrieval_timestamp": "",
          "field_provenance": ""
        },
        "notes": null
      }
    ]
  },
  "category_mapping": {
    "path": "runs/{run_id}/04_5_enrichment/{business_slug}/category_mapping.json",
    "mappings": [
      {
        "fact_id": "",
        "phase04_category": "",
        "enrichment_category": "",
        "design_preset_relevant": false,
        "copy_slot_target": null
      }
    ]
  },
  "design_preset_candidate": {
    "path": "runs/{run_id}/04_5_enrichment/{business_slug}/design_preset_candidate.json",
    "candidates": [
      {
        "preset_id": "clinical_trust | warm_editorial | industrial_reliable | fresh_utility",
        "preset_label": "Clinical Trust | Warm Editorial | Industrial Reliable | Fresh Utility",
        "palette": {},
        "layout_variant": "",
        "tone_words": [],
        "mapping_reason": "",
        "confidence": 0.0
      }
    ]
  },
  "copy_inputs": {
    "path": "runs/{run_id}/04_5_enrichment/{business_slug}/copy_inputs.json",
    "slots": {
      "hero_tagline": null,
      "hero_supporting_line": null,
      "overview_intro": null,
      "overview_support_block_1": null,
      "overview_support_block_2": null,
      "trust_intro": null,
      "location_intro": null,
      "cta_body": null,
      "footer_note": null
    },
    "slot_provenance": {
      "hero_tagline": {"source_fact_id": "", "enrichment_used": false},
      "hero_supporting_line": {"source_fact_id": "", "enrichment_used": false},
      "overview_intro": {"source_fact_id": "", "enrichment_used": false},
      "overview_support_block_1": {"source_fact_id": "", "enrichment_used": false},
      "overview_support_block_2": {"source_fact_id": "", "enrichment_used": false},
      "trust_intro": {"source_fact_id": "", "enrichment_used": false},
      "location_intro": {"source_fact_id": "", "enrichment_used": false},
      "cta_body": {"source_fact_id": "", "enrichment_used": false},
      "footer_note": {"source_fact_id": "", "enrichment_used": false}
    },
    "gate_status": "render_allowed | render_allowed_but_not_deploy_eligible | needs_review"
  },
  "scoring": {
    "data_depth_score": 0,
    "public_copy_ready_score": 0,
    "trust_signal_score": 0,
    "local_context_score": 0,
    "missing_core_fields_count": 0
  },
  "gate_result": "render_allowed | render_allowed_but_not_deploy_eligible | needs_review",
  "enrichment_sources": {
    "path": "runs/{run_id}/04_5_enrichment/{business_slug}/enrichment_sources.json",
    "sources": [
      {
        "source_id": "",
        "name": "",
        "type": "google_maps_api | google_places_api | yelp | trustpilot | public_directory | manual",
        "url": null,
        "accessed_at": "",
        "reliability_score": 0.0,
        "facts_sourced": []
      }
    ]
  },
  "enrichment_timestamp": ""
}
```

Gate logic:

```text
If any enriched fact has contradicts_phase04=true -> needs_review.
Else if missing_core_fields_count > 3 -> render_allowed_but_not_deploy_eligible.
Else -> render_allowed.
```

---

## Object: VisualProfile (NEW)

Canonical deterministic rendering bundle for Phase 05. Created by Phase 04.5.

Full schema defined in [`visual_profile_contract.md`](visual_profile_contract.md).

```json
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

Source rules:

```text
- Derived from Places/public enrichment and verified Phase 04 facts only, not arbitrary scraping
- photo_candidates[] contains only safe metadata and selection signals, not invented image semantics
- review_summary_candidate and editorial_summary_candidate preserve source attribution requirements
- hero_mode and photo_policy must support preview demo vs production deploy mode distinctions
```

Preview demo vs production deploy:

```text
- preview demo mode may render photo_policy=preview_demo_only assets with required attribution
- production deploy mode must NOT use preview_demo_only assets
- production deploy mode may use customer_owned_only assets only after rights-cleared replacement exists
- unresolved attribution_requirement blocks production deploy eligibility
```

---

## Object: Phase05_5BrowserRender

Created by Phase 05.5.

```json
{
  "run_id": "",
  "record_id": "",
  "business_slug": "",
  "desktop_screenshot_path": "",
  "mobile_screenshot_path": "",
  "dom_metrics": {
    "heading_count": 0,
    "visible_cta_count": 0,
    "section_count": 0,
    "section_order": [],
    "duplicate_text_signals": 0,
    "viewport_overflow": false,
    "broken_image_count": 0,
    "broken_link_count": 0,
    "missing_stylesheet": false,
    "text_density_estimate": 0.0
  },
  "asset_load_log": [],
  "console_log": [],
  "layout_summary": {},
  "render_timestamp": ""
}
```

---

## Object: RecipientChannelArtifact

Structured content for `recipient_channel.json`, created by Phase 04. `RECIPIENT_CHANNEL.md` is optional and may summarize the same object for humans, but scripts must read `recipient_channel.json`.

```json
{
  "business_slug": "",
  "recipient_channel": "email | contact_form | phone | facebook_message | instagram_dm | line | unknown",
  "recipient_value": "",
  "recipient_source": "google_maps_listing | social_profile | contact_page | manual | unknown",
  "recipient_confidence": "verified | inferred | unknown",
  "discovery_notes": ""
}
```

Operational note:

```text
Expect recipient_channel=unknown on many or most records in typical runs. This is a data reality, not a Phase 04 failure. Unknown blocks automated outreach drafting unless manually overridden.
```

## Object: Phase04BriefRouting

Created by Phase 04 to prevent preview generation for unreachable leads.

`preview_ready_briefs.json`:

```json
[
  {
    "business_slug": "",
    "brief_path": "",
    "recipient_channel": "email | contact_form | phone | facebook_message | instagram_dm | line | unknown",
    "manual_override": false,
    "manual_override_reason": ""
  }
]
```

If `recipient_channel=unknown` appears in `preview_ready_briefs.json`, `manual_override` must be `true` and `manual_override_reason` must be populated. Otherwise the record belongs in `blocked_no_recipient_channel.json`.

`blocked_no_recipient_channel.json`:

```json
[
  {
    "business_slug": "",
    "brief_path": "",
    "recipient_channel": "unknown",
    "blocked_reason": "recipient_channel is unknown; manual recipient discovery or override required"
  }
]
```

## Object: PreviewSite

Created by Phase 05.

Ownership note: preview site is operator-generated marketing preview. It must not imply business approved, requested, or owns site before explicit acceptance.

```json
{
  "run_id": "",
  "record_id": "",
  "business_slug": "",
  "site_path": "generated_sites/business_slug",
  "framework": "astro | next_static | vite_react | plain_html",
  "build_command": "",
  "build_status": "passed | failed | needs_review",
  "facts_used": [],
  "placeholder_fields": [],
  "known_issues": [],
  "ownership_disclaimer_required": true,
  "ownership_disclaimer_status": "present | missing | needs_review"
}
```

---

## Object: SiteQualityReport

Created by Phase 06 or folded checks in Phase 05/07 for MVP.

Phase 06 now uses a four-axis credibility scoring model.

### Four Score Axes

1. Safety score (0-25) — no invented claims, no forbidden phrases, no placeholder text
2. Data utilization score (0-25) — core facts used, enrichment fields used, field coverage ratio
3. Copy quality score (0-25) — word count, duplicate detection, CTA match, readability
4. Visual credibility score (0-25) — preset match, layout coherence, screenshot quality, text density

### Credibility Score Thresholds

- >= 90: APPROVED — deploy
- 70-89: NEEDS_REVIEW — human review, may deploy
- 50-69: NEEDS_EDIT — auto-reject, regenerate or edit
- < 50: REJECTED — serious issues, investigate root cause

### Hard Reject Conditions (any one = REJECTED)

- Business name missing/mismatch
- Required section missing or out of order
- Forbidden claim detected
- Placeholder text remains
- Screenshot missing or synthetic
- Page fails to render
- 2+ core facts omitted without justification
- CTA absent despite available contact path
- Body word count below 140
- Duplicate core copy across hero/overview/CTA
- More than 1 core slot showing fallback text

### Needs-Edit Conditions

- Safe but thin copy
- Wrong or fallback preset
- Low visual density
- One non-critical fact omitted
- Only one CTA when multiple contact paths exist
- Over-reliance on fallback text

Report Schema

site_quality_report.json:
```json
{
  "status": "approved | needs_review | needs_edit | rejected",
  "score": 0,
  "score_breakdown": {
    "safety": 0,
    "data_utilization": 0,
    "copy_quality": 0,
    "visual_credibility": 0
  },
  "failure_codes": [],
  "missing_fact_usage": [],
  "copy_flags": [],
  "visual_flags": [],
  "deploy_eligible": false,
  "reviewer_notes": ""
}
```

Failure taxonomy codes: thin_copy, duplicate_copy, generic_design, wrong_preset, fake_screenshot, missing_core_fact_usage, weak_cta, excess_fallback_text, meta_language, low_data_depth

Deploy gating rule:

```text
deploy_eligible=true only when status=approved.
status=needs_review may deploy only by explicit human override outside this object.
status=needs_edit or rejected must set deploy_eligible=false.
```

---

## Object: DeploymentRecord

Created by Phase 07.

Phase 07 must block deployment when SiteQualityReport.deploy_eligible != true or SiteQualityReport.status != approved, unless explicit human override exists.

```json
{
  "run_id": "",
  "record_id": "",
  "business_slug": "",
  "site_path": "",
  "provider": "vercel | netlify | cloudflare_pages | github_pages | local_only",
  "deployment_status": "live | failed | needs_review",
  "preview_url": "",
  "verified_at": "",
  "http_status": 0,
  "deployment_logs_ref": "",
  "cleanup_required": true,
  "takedown_after_days": 30,
  "takedown_due_at": "",
  "takedown_status": "not_due | removed | overdue | removal_requested"
}
```

---

## Object: OutreachDraft

Created by Phase 08.

```json
{
  "run_id": "",
  "record_id": "",
  "business_slug": "",
  "business_name": "",
  "recipient_channel": "email | contact_form | phone | facebook_message | instagram_dm | line | unknown",
  "recipient_value": "",
  "subject": "",
  "body": "",
  "preview_url": "",
  "price_offer": "",
  "draft_status": "ready_for_review | needs_edit | blocked",
  "blocked_reason": "",
  "personalization_fields_used": []
}
```

---

## Object: ApprovalDecision

Created by Phase 09.

```json
{
  "run_id": "",
  "record_id": "",
  "business_slug": "",
  "approval_status": "send | edit | skip | needs_rebuild | needs_more_info",
  "site_review_status": "approved | rejected | needs_edit",
  "outreach_review_status": "approved | rejected | needs_edit",
  "screenshot_path": "",
  "screenshot_desktop_path": "",
  "screenshot_mobile_path": "",
  "reviewer_notes": "",
  "approved_at": ""
}
```

---

## Object: ScreenshotsIndex

Created by Phase 09 as `screenshots_index.json`.

```json
[
  {
    "business_slug": "",
    "screenshot_desktop_path": "",
    "screenshot_mobile_path": ""
  }
]
```

## Object: SentOutreach

Created by Phase 10.

```json
{
  "run_id": "",
  "record_id": "",
  "business_slug": "",
  "sent_status": "sent | not_sent | failed",
  "sent_channel": "email | contact_form | phone | facebook_message | instagram_dm | whatsapp | line",
  "sent_at": "",
  "sender_account": "",
  "message_ref": "",
  "notes": ""
}
```

Note: `sent_channel` may include channels not present in `OutreachDraft.recipient_channel`; it records how the operator actually sent the message.

---

## Object: MonetizationEvent

Created by Phase 11.

```json
{
  "run_id": "",
  "record_id": "",
  "business_slug": "",
  "event_type": "reply | serious_interest | objection | meeting_booked | paid_close | lost | no_response",
  "event_at": "",
  "value": 0,
  "currency": "USD",
  "objection_category": "",
  "notes": "",
  "next_action": ""
}
```