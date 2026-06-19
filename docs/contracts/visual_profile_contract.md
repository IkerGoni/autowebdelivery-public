# Visual Profile Contract — Deterministic Rendering Bundle for Phase 05

## Purpose

`visual_profile.json` is canonical visual rendering artifact produced by Phase 04.5 and consumed by Phase 05. It converts public enrichment and Places-derived signals into deterministic presentation guidance without inventing business semantics.

`design_preset_candidate.json` remains upstream recommendation artifact. `visual_profile.json` is downstream normalized bundle Phase 05 reads first for hero treatment, safe photo handling, tone shaping, trust-chip selection, attribution handling, and preview-versus-production guardrails.

This contract is spec-only. It defines artifact meaning, schema, source boundaries, and safety rules.

## Source Boundary

`visual_profile.json` may only be derived from:

- Phase 02 and Phase 04 verified business facts
- Google Places or equivalent public Places enrichment already allowed by pipeline
- Public enrichment artifacts created by Phase 04.5
- Operator-supplied preset catalog and deterministic mapping rules

`visual_profile.json` must not pull from arbitrary scraping, hidden pages, or model-invented interpretation. If source signal is absent, field stays `null`, empty array, or low-confidence.

## Artifact Path

Per business artifact path:

```text
runs/{run_id}/04_5_enrichment/{business_slug}/visual_profile.json
```

Phase-level result files still live at:

```text
runs/{run_id}/04_5_enrichment/{business_slug}/result.json
runs/{run_id}/04_5_enrichment/result.json
```

## Canonical Schema

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
  "accent_color_confidence": 0.0,
  "accent_source": "place_photo_palette | map_listing_palette | preset_default | operator_override | unknown",
  "tone_axes": {
    "formality": 0.0,
    "warmth": 0.0,
    "luxury": 0.0,
    "energy": 0.0
  },
  "trust_chip_candidates": [
    {
      "label": "string",
      "source_type": "reviews | rating | review_count | place_attribute | business_status | category | editorial_summary | operator_override",
      "source_ref": "string | null",
      "confidence": 0.0,
      "attribution_required": false
    }
  ],
  "review_summary_candidate": {
    "text": "string | null",
    "attribution_uri": "string | null",
    "attribution_required": false
  },
  "editorial_summary_candidate": {
    "text": "string | null",
    "source_uri": "string | null",
    "attribution_required": false
  },
  "photo_candidates": [
    {
      "photo_ref": "string",
      "source_type": "google_places | operator_uploaded | customer_uploaded",
      "width": null,
      "height": null,
      "aspect_ratio": null,
      "orientation": "landscape | portrait | square | unknown",
      "is_primary": false,
      "sort_order": 0,
      "selection_signals": [
        "hero_usable",
        "high_resolution",
        "landscape_safe",
        "storefront_possible",
        "interior_possible",
        "team_possible",
        "low_confidence_subject"
      ],
      "attribution_uri": "string | null",
      "attribution_required": false,
      "license_note": "string | null"
    }
  ],
  "local_visual_cues": [
    {
      "cue_type": "map_area | neighborhood | streetscape | geo_context | service_area",
      "label": "string",
      "source_ref": "string | null",
      "confidence": 0.0
    }
  ],
  "attribution_requirements": [
    {
      "asset_type": "review_summary | editorial_summary | photo | trust_chip",
      "asset_ref": "string",
      "requirement": "string"
    }
  ],
  "brand_risk_flags": [
    "low_photo_confidence",
    "no_safe_photos",
    "attribution_required",
    "review_text_truncated",
    "editorial_text_truncated",
    "generic_color_fallback",
    "map_context_only",
    "operator_review_recommended"
  ],
  "visual_personalization_score_inputs": {
    "has_photo_candidates": false,
    "photo_candidate_count": 0,
    "has_review_summary_candidate": false,
    "has_editorial_summary_candidate": false,
    "has_local_visual_cues": false,
    "local_visual_cue_count": 0,
    "accent_color_confidence": 0.0,
    "trust_chip_count": 0,
    "preset_confidence": 0.0,
    "public_signal_coverage_score": 0.0
  }
}
```

## Field Semantics

### preset_id

Canonical preset selected for rendering. Usually aligns with highest-confidence `design_preset_candidate.json` candidate unless operator override or deterministic downgrade rule applies.

### preset_variant

Optional narrower variant within canonical preset family. Must remain deterministic and renderer-safe. Examples: `clinical_soft`, `warm_inviting`, `industrial_utility`, `fresh_bright`.

### hero_mode

Allowed values only:

```text
photo
abstract
map_context
text_first
```

Meaning:

- `photo`: hero may use approved photo candidate
- `abstract`: hero uses preset-driven graphics only
- `map_context`: hero uses map/location context, not business photo as primary signal
- `text_first`: hero prioritizes typography and trust chips because visual evidence weak or unavailable

### photo_policy

Allowed values only:

```text
none
preview_demo_only
customer_owned_only
```

Meaning:

- `none`: Phase 05 must not render business imagery
- `preview_demo_only`: preview mode may use allowed third-party/public-preview imagery with required attribution; production deploy may not
- `customer_owned_only`: production deploy may render imagery only after customer-supplied or rights-cleared replacement available

### accent color fields

`accent_color_candidate` is optional color token or hex candidate. It may come from deterministic palette extraction or preset fallback only.

`accent_color_confidence` is normalized 0.0–1.0 confidence in extracted accent.

`accent_source` records source class, not generated design rationale.

### tone_axes

Continuous rendering inputs from 0.0 to 1.0:

- `formality`
- `warmth`
- `luxury`
- `energy`

Axes shape typography, spacing, and copy tone selection. They are render controls, not claimed business facts.

### trust_chip_candidates

Short trust-oriented UI chips candidate list. Chips must be grounded in public facts or public summaries already present in enrichment pipeline. No chip may imply unverified credential, guarantee, or invented differentiator.

### review_summary_candidate

Optional short review-derived summary candidate. If sourced from review text or review platform content that requires attribution, `attribution_required` must be true and `attribution_uri` populated.

### editorial_summary_candidate

Optional short editorial/public-description summary candidate. Must point to public summary source such as Places editorial description when used.

### photo_candidates

Only safe metadata and selection signals allowed. No invented subject classification beyond coarse uncertainty-aware signals. Do not store statements like "dentist smiling with patient" unless source metadata explicitly says so.

Allowed content types here:

- source references
- dimensions
- orientation
- ordering
- coarse selection signals
- attribution and license notes

Disallowed here:

- invented semantic captions
- generated alt text claiming unseen content
- made-up room/service labels
- identity guesses

### local_visual_cues

Public geo and place context cues usable for maps, section dividers, or locality framing. Must come from Places/public enrichment, not arbitrary web scraping.

### attribution_requirements

Normalized list of all asset-level attribution obligations Phase 05 and downstream deploy checks must honor.

### brand_risk_flags

List of non-fatal visual risk flags. Used to reduce rendering ambition or require human review.

### visual_personalization_score_inputs

Deterministic score-input bundle for renderers or quality gate. Inputs only, not final score. Must be traceable to actual presence/coverage of allowed public signals.

## Source and Safety Rules

1. `visual_profile.json` is downstream deterministic rendering bundle. It must not replace `design_preset_candidate.json`.
2. `design_preset_candidate.json` may contain ranked recommendations. `visual_profile.json` resolves those into single render-ready decision plus supporting evidence.
3. Photos may only use safe metadata and selection signals from allowed source systems.
4. Review/editorial text must preserve attribution requirements from source platforms.
5. If public enrichment weak, renderer must fall back to `hero_mode=text_first` or `hero_mode=abstract`.
6. If no photo candidate meets policy, set `photo_policy=none` or `customer_owned_only` and add relevant `brand_risk_flags`.
7. Visual profile must remain grounded in Places/public enrichment, not arbitrary scraping or free-form model taste.

## Preview Demo Mode vs Production Deploy Mode

Contract note:

- Preview demo mode may render `photo_policy=preview_demo_only` assets if attribution requirements are satisfied and preview clearly remains operator-generated demonstration.
- Production deploy mode must not render `preview_demo_only` assets.
- Production deploy mode may render `customer_owned_only` imagery only after customer-provided or rights-cleared replacement exists.
- If unresolved attribution requirement exists, production deploy must fail eligibility until resolved.

## Minimal Example

```json
{
  "schema_version": "1.0",
  "run_id": "2026-05-10_chiang-mai_dentists_001",
  "business_slug": "bright-smile-dental-clinic-31a8",
  "record_id": "rec_9f31a8",
  "phase": "04_5_enrichment",
  "created_at": "2026-05-10T12:00:00Z",
  "updated_at": "2026-05-10T12:00:00Z",
  "preset_id": "clinical_trust",
  "preset_variant": "clinical_soft",
  "hero_mode": "text_first",
  "photo_policy": "preview_demo_only",
  "accent_color_candidate": "#2F6FAE",
  "accent_color_confidence": 0.62,
  "accent_source": "place_photo_palette",
  "tone_axes": {
    "formality": 0.82,
    "warmth": 0.46,
    "luxury": 0.22,
    "energy": 0.39
  },
  "trust_chip_candidates": [
    {
      "label": "4.8 rating",
      "source_type": "rating",
      "source_ref": "place_id:example",
      "confidence": 0.99,
      "attribution_required": false
    }
  ],
  "review_summary_candidate": {
    "text": "Patients frequently mention gentle care and clear explanations.",
    "attribution_uri": "https://maps.google.com/...",
    "attribution_required": true
  },
  "editorial_summary_candidate": {
    "text": null,
    "source_uri": null,
    "attribution_required": false
  },
  "photo_candidates": [],
  "local_visual_cues": [
    {
      "cue_type": "neighborhood",
      "label": "Nimman area",
      "source_ref": "places_geo_context",
      "confidence": 0.74
    }
  ],
  "attribution_requirements": [
    {
      "asset_type": "review_summary",
      "asset_ref": "review_summary_candidate",
      "requirement": "Google review-derived summary requires source attribution in preview mode"
    }
  ],
  "brand_risk_flags": [
    "no_safe_photos",
    "attribution_required"
  ],
  "visual_personalization_score_inputs": {
    "has_photo_candidates": false,
    "photo_candidate_count": 0,
    "has_review_summary_candidate": true,
    "has_editorial_summary_candidate": false,
    "has_local_visual_cues": true,
    "local_visual_cue_count": 1,
    "accent_color_confidence": 0.62,
    "trust_chip_count": 1,
    "preset_confidence": 0.84,
    "public_signal_coverage_score": 0.58
  }
}
```