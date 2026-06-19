# Site Template Spec — Phase 05 Preview Website Generation

## Purpose

This is the minimum build spec for generated one-page preview websites. Phase 05 must not operate as an undefined LLM black box. It must inject verified facts into a fixed structure, produce deterministic outputs, and report every fact used.

## Required page sections

Every preview site must contain these sections, in this order unless a template explicitly documents a safe variation:

1. `hero`
2. `services_or_category_overview`
3. `trust`
4. `location_and_hours`
5. `map_or_maps_link`
6. `contact_cta`
7. `footer`

## Field-to-slot mapping

| FACTS.md field | Site slot | Rule |
|---|---|---|
| `business_name` | hero heading, footer | Required. Must match exactly except HTML escaping. |
| `category` | hero subheading, overview | Required. May be used as generic category only. Do not infer specific services. |
| `rating` | trust section | Use only with `review_count`. Example: `Rated 4.6 from 82 Google reviews`. |
| `review_count` | trust section | Use only as numeric review count. Do not convert into “trusted by thousands”. |
| `address` | location section | Required unless `maps_url` exists and address is missing. |
| `phone` | CTA button, contact section | If missing, omit phone CTA. Do not invent. |
| `hours` | location/hours section | If missing, write `Hours not listed in source data`. |
| `maps_url` | map/link section | If missing, omit embed/link and flag in `fact_usage_report.json`. |
| `website_status` | internal copy/context only | May say the preview was prepared because no standard website was found only in outreach, not on the public site. |
| `recipient_channel` | not public site by default | Use only for outreach, unless it is a verified public contact method. |

## Safe copy rules

Allowed:

```text
clear category-level descriptions
neutral calls to action
location-based phrasing from verified address/area
verified rating and review count
verified phone/maps/hours
```

Forbidden unless explicitly verified:

```text
invented services
prices
staff names
years in business
licensed/certified claims
family-owned claims
award-winning claims
testimonials
before/after results
guarantees
claims like best, top-rated, #1, trusted by thousands
```

## Placeholder rules

Missing fields must be handled by omission or neutral text. Never leave visible placeholders.

Forbidden placeholder strings:

```text
Lorem ipsum
TODO
TBD
INSERT
PLACEHOLDER
[BUSINESS_NAME]
[PHONE]
[ADDRESS]
[HOURS]
Your business
Example business
Sample text
```

## Required generated files

```text
runs/{run_id}/05_sites/{business_slug}/site/
runs/{run_id}/05_sites/{business_slug}/build_status.json
runs/{run_id}/05_sites/{business_slug}/fact_usage_report.json
runs/{run_id}/05_sites/result.json

Note: real screenshots are produced by Phase 05.5 Browser Render Capture, not Phase 05 site generation.
```

Recommended screenshot viewports:

```text
desktop: 1280x800
mobile: 390x844
```

## `fact_usage_report.json` schema

```json
{
  "run_id": "",
  "record_id": "",
  "business_slug": "",
  "facts_used": [
    {
      "field": "business_name",
      "value": "",
      "source": "FACTS.md",
      "site_location": "hero.heading"
    }
  ],
  "facts_omitted": [
    {
      "field": "phone",
      "reason": "missing"
    }
  ],
  "generic_copy_blocks": [
    {
      "site_location": "overview.body",
      "text": "",
      "rationale": "generic category-level copy; no business-specific claim"
    }
  ],
  "forbidden_claim_hits": [],
  "placeholder_hits": [],
  "needs_review": false,
  "notes": []
}
```

## Implementation boundary

The MVP template may be Astro, Vite, Next static export, or plain HTML. The contract is the same: deterministic sections, verified fact injection, screenshots, and fact usage reporting.

## Design Preset System (NEW)

Phase 05 must apply a deterministic design preset chosen by this authority chain: (1) `RunConfig.style_preset` only when explicitly set as operator override, else (2) highest-confidence `design_preset_candidate.candidates[0].preset_id` from Phase 04.5, else (3) this document's niche/category mapping as fallback, else (4) `clinical_trust` as safe final fallback. Phase 05 must not invent a new preset outside this chain. Presets control palette, typography, spacing, and layout variant.

### Preset Palette Definitions

**1. Clinical Trust** — dental, medical, wellness
- Primary: #1E4055
- Secondary: #536B7D
- Accent: #00B8A9
- Background: #F2F6F8
- Surface: #FFFFFF
- Text: #1A242F
- Accent-soft: #e0f7f4
- Layout: Standard hero grid — clean, symmetrical

**2. Warm Editorial** — salon, beauty, premium hospitality
- Primary: #8B4545
- Secondary: #A0522D
- Accent: #D4A574
- Background: #FDF8F4
- Surface: #FFFFFF
- Text: #2D1B1E
- Accent-soft: #fceee0
- Layout: Centered single-column hero — intimate, editorial

**3. Industrial Reliable** — mechanic, repair, home services, trades
- Primary: #2F3A45
- Secondary: #5C6B7A
- Accent: #E8843C
- Background: #F5F3F0
- Surface: #FFFFFF
- Text: #1F2933
- Accent-soft: #fef0e6
- Layout: Split hero with icon-grid services preview — utilitarian

**4. Fresh Utility** — cleaning, home services, eco
- Primary: #2E7D5E
- Secondary: #5B8C7A
- Accent: #7FC79B
- Background: #F5F9F6
- Surface: #FFFFFF
- Text: #1E2E26
- Accent-soft: #e6f5ec
- Layout: Full-bleed hero with process-step indicators — flow-oriented

### Preset Selection Logic

1. Explicit operator override via `RunConfig.style_preset` when intentionally supplied
2. Highest-confidence Phase 04.5 `design_preset_candidate.candidates[0].preset_id`
3. Explicit niche-to-preset mapping (category lookup table) only if Phase 04.5 candidate missing
4. Secondary category clues only if both override and Phase 04.5 candidate missing
5. Safe fallback: `clinical_trust`

Approval rule: If Phase 04.5 candidate exists but Phase 05 uses a different preset without explicit operator override, flag `needs_edit`. If niche maps cleanly but safe fallback still used, flag `needs_edit` unless justified.

### Niche-to-Preset Mapping

| Niche | Preset |
|-------|--------|
| Dental clinic | Clinical Trust |
| Medical clinic | Clinical Trust |
| Wellness / spa | Clinical Trust |
| Beauty clinic / med spa | Warm Editorial |
| Hair salon / barber | Warm Editorial |
| Guesthouse / boutique hotel | Warm Editorial |
| Tour operator | Warm Editorial |
| Auto repair | Industrial Reliable |
| Home services (plumber, electrician, HVAC) | Industrial Reliable |
| Renovation / contractor | Industrial Reliable |
| Cleaning service | Fresh Utility |
| Eco / green services | Fresh Utility |
| Pet services | Fresh Utility |
| Legal services | Clinical Trust |
| Real estate broker | Industrial Reliable |

### Preset Variants (`preset_variant`)

Each preset carries a `preset_variant` string that selects an internal rendering mode within the preset family. Phase 05 must set `preset_variant` deterministically based on visual_profile signals or fall back to the preset default.

| Preset | Allowed `preset_variant` values | Default | Selection signal |
|--------|--------------------------------|---------|------------------|
| Clinical Trust | `clinical_soft`, `clinical_strong`, `editorial_trust` | `clinical_soft` | Deterministic mapping from `visual_profile.tone_axes` (high formality + lower energy→clinical_soft, high formality + high energy→clinical_strong, higher luxury + moderate warmth→editorial_trust) |
| Warm Editorial | `warm_inviting`, `warm_bold`, `warm_minimal` | `warm_inviting` | Deterministic mapping from `visual_profile.tone_axes` (high warmth→warm_inviting, high energy→warm_bold, lower warmth + lower energy→warm_minimal) |
| Industrial Reliable | `industrial_utility`, `industrial_premium`, `industrial_compact` | `industrial_utility` | Deterministic mapping from `visual_profile.tone_axes` (lower luxury + moderate/high formality→industrial_utility, higher luxury→industrial_premium, lower warmth + higher energy→industrial_compact) |
| Fresh Utility | `fresh_bright`, `fresh_natural`, `fresh_streamlined` | `fresh_bright` | Deterministic mapping from `visual_profile.tone_axes` (high energy→fresh_bright, high warmth + moderate energy→fresh_natural, higher formality + lower warmth→fresh_streamlined) |

Rules:
- `preset_variant` must be one of the listed values for the active preset. Invalid values are rejected; fall back to default.
- If `visual_profile` is absent or `visual_profile.tone_axes` is missing, use the default variant for the preset.
- `preset_variant` is recorded in `fact_usage_report.json` under `design_metadata.preset_variant`.
- Variant only affects internal module rendering, color saturation weighting, and spacing rhythm. Top-level section contract and palette token names are unchanged.

### Bounded Accent Override

Phase 05 may apply a limited accent-color override when `visual_profile.accent_color_candidate` is present. This override is bounded to prevent palette destruction.

Rules:
- Only the `accent` and `accent-soft` tokens may be overridden. Primary, secondary, background, surface, and text tokens are immutable per preset.
- Override value must pass WCAG 2.1 AA contrast against the preset's `background` token (minimum 4.5:1 for normal text, 3:1 for large text).
- Override value must pass WCAG 2.1 AA contrast against the preset's `surface` token using the same thresholds.
- If the override fails either contrast check, the override is rejected and the preset default accent is used. This rejection is logged in `fact_usage_report.json` under `design_metadata.accent_override_rejected_reason`.
- Accepted override is recorded in `fact_usage_report.json` under `design_metadata.accent_override`.
- Phase 06 must re-verify contrast after any accent override. If contrast fails at gate time, status is `needs_edit`.

### hero_mode Selection

The hero section's canonical rendering mode (`hero_mode`) is selected from `visual_profile.hero_mode` when present, falling back to preset-default hero mode.

| `visual_profile.hero_mode` | Meaning |
|----------------------------|---------|
| `photo` | Hero may use approved photo candidate |
| `abstract` | Hero uses preset-driven graphics only |
| `map_context` | Hero uses map or location context as primary visual signal |
| `text_first` | Hero prioritizes typography and trust chips because visual evidence is weak or unavailable |
| absent / null | preset default | Use preset's canonical default hero mode |

Rules:
- `hero_mode` allowed values are only `photo`, `abstract`, `map_context`, `text_first`.
- `hero_mode` selection must never add, remove, or reorder top-level sections.
- Selected `hero_mode` is recorded in `fact_usage_report.json` under `design_metadata.hero_mode`.
- Internal hero layout variants such as `utility_bar`, `cta_pair`, and `fact_mini_strip` may still be chosen inside hero renderer, but they are not canonical `hero_mode` values and must not appear in `visual_profile.hero_mode`.

### Implementation

- Preset palettes: CSS custom property overrides via class on <body>
- Layout variants: .layout-{variant} CSS classes
- Selection: Phase 04.5 enrichment output → passed to Phase 05 as design_preset
- Accent override: CSS custom property on accent/accent-soft tokens only, validated against WCAG contrast
- hero_mode: canonical hero rendering mode driven by `visual_profile.hero_mode`, preset-default fallback

## Copy Slot Architecture (NEW)

Phase 05 must fill distinct copy slots. Each slot has its own content — no reusing one body string across sections.

### Required Copy Slots

| Slot | Section | Source tier | Min words | Max fallback |
|------|---------|-------------|-----------|--------------|
| hero_tagline | hero | Tier 1 (verified) | 10 | 0 (must use facts) |
| hero_supporting_line | hero | Tier 2 (category) | 15 | 1 generic sentence |
| overview_intro | services_or_category_overview | Tier 2 (category) | 40 | 1 generic paragraph |
| overview_support_block_1 | services_or_category_overview | Tier 2 or 3 | 30 | 1 category block |
| overview_support_block_2 | services_or_category_overview | Tier 2 or 3 | 30 | 1 category block |
| trust_intro | trust | Tier 1 (verified) | 10 | 0 (must use rating/review) |
| location_intro | location_and_hours | Tier 1 (verified) | 10 | 0 (must use address/hours) |
| cta_body | contact_cta | Tier 2 (category) | 15 | 1 generic call-to-action |
| footer_note | footer | Tier 1 (verified) | 5 | 1 neutral footer line |

Fallback cap for deploy-eligible status uses two tiers:
- Total fallback/generic slots across entire site: max 3
- Core slots (`hero_tagline`, `hero_supporting_line`, `trust_intro`, `cta_body`) with fallback text: max 1

### Trust Chips Rendering

Trust chips are rendered in the `trust` section. Only verified attributes from enrichment or FACTS.md may appear as trust chips.

Rules:
- Each trust chip must map to a verified attribute with a traceable source in `fact_usage_report.json`.
- Allowed chip types: `verified_rating`, `review_count`, `verified_attribute` (e.g. "wheelchair accessible", "free WiFi" — only if sourced), `verified_link` (social/web links).
- **Unverified attributes from `visual_profile` or `design_preset` must NOT appear as trust chips.** Only enrichment-confirmed attributes are eligible.
- If no verified trust data exists, render the section empty (no placeholder chips). Do not fabricate trust indicators.
- Each chip must include `source` and `source_type` metadata in `fact_usage_report.json` under `trust_chips[]`.

### Review Summary Rendering

If `review_themes` or individual review data is available, a review summary may appear in the trust section.

Rules:
- Review summary must use **aggregated themes only** (from `review_themes`), never individual review quotes unless explicitly verified and attributed.
- If review count is below 5, review summary content must be omitted entirely — do not generalize from small samples.
- Attribution requirement: any review-derived statement must include source attribution in the format `Source: Google Reviews` or equivalent platform name.
- Attribution must appear visually adjacent to the review summary content, not hidden in footer or tooltip only.
- `fact_usage_report.json` must log each review-derived statement under `review_summary[]` with `text`, `source`, and `attribution_visible` fields.

### Photo Usage (Google-Derived)

Rules for photo usage in production-eligible sites:

- **No photos derived from Google Maps/Places API in deploy-eligible production mode.** Google photo licensing does not permit redistribution in production landing pages.
- Allowed in `preview_demo_mode` only, with visible watermark and attribution: "Photo: Google Maps".
- In `production_deploy_mode`, if the operator supplies original/licensed photos, those may be used. Otherwise, the hero image area must remain image-free (solid color or CSS gradient fallback).
- Photo source and licensing status must be recorded in `fact_usage_report.json` under `photo_usage[]`.
- Phase 06 must flag any Google-derived photo in production mode as a hard reject.

### Content Modes: `preview_demo_mode` vs `production_deploy_mode`

Phase 05 must operate in one of two content modes, determined by `RunConfig.deploy_mode`.

| Mode | `deploy_mode` value | Behavior |
|------|---------------------|----------|
| Preview/Demo | `preview_demo_mode` | Full feature set including Google-derived photos, demo disclaimers, placeholder CTAs, and "preview" labels. Not deploy-eligible. |
| Production Deploy | `production_deploy_mode` | Strict safety compliance: no Google photos, no demo disclaimers, all copy must use verified facts only, CTA links must resolve to verified destinations. Required for deploy eligibility. |

Rules:
- Default mode is `production_deploy_mode` unless `RunConfig.deploy_mode` explicitly sets `preview_demo_mode`.
- `preview_demo_mode` output must include a visible banner: "This is a preview site — not the final production version."
- `production_deploy_mode` sites are subject to all Phase 06 hard-reject conditions including unsafe photo persistence.
- Mode is recorded in `fact_usage_report.json` under `deploy_mode`.

---

## Internal Module Variants (NEW)

Each required section may use internal module variants. The top-level section contract (hero, services_or_category_overview, trust, location_and_hours, map_or_maps_link, contact_cta, footer) is preserved — variants are internal only.

### hero variants:
- utility_bar: compact info bar + heading
- cta_pair: dual CTA buttons
- fact_mini_strip: rating + hours + location in a compact row

### services_or_category_overview variants:
- service_category_cards: grid of category-purpose cards
- process_steps: numbered process/steps indicators
- differentiator_trio: three differentiators
- local_context_cards: area/neighborhood context cards

### trust variants:
- review_summary_card: rating display + review count
- public_attribute_list: verified attributes from enrichment
- verified_links_row: social/web links

### location_and_hours variants:
- hours_card + map_card + neighborhood_line

### contact_cta variants:
- primary_cta + alternate_cta + verified_channels_row

Variant selection is driven by design preset and available data, not arbitrary.

## Credibility Floor Metrics (NEW)

These are the minimum metrics for a site to be considered deploy-eligible. Phase 06 scores against these floors.

| Metric | Floor | How measured |
|--------|-------|-------------|
| Meaningful body words | >= 140 | word count on rendered page |
| Unique paragraphs/cards | >= 6 | structural element count |
| Meaningful CTAs | >= 2 when phone + maps exist | visible CTA elements |
| Populated sections with distinct content | >= 5 of 7 | section content analysis |
| Duplicate sentence fragments > 8 words | 0 in hero/overview/CTA | text similarity check |
| Fallback text visible in core slots | <= 1 | copy slot analysis |
| Core fields used or justified | all available | fact_usage_report.json |
| Attribution visible for review-derived content | required if review summary present | visual + `fact_usage_report.json` check |
| Contrast pass after accent override | required if override applied | WCAG 2.1 AA automated check |
| Unsafe Google-derived photo absent | 0 in `production_deploy_mode` | image source scan |
| Same-niche genericity check | pass if niche signals present | compare output against niche copy catalog |

### Scorecard/Gates Additional Checks

The following checks apply at Phase 06 gate time and on the quality scorecard:

**Attribution Visibility**
- If review summary or review-derived content exists, visible attribution ("Source: Google Reviews" or equivalent) is present adjacent to the content
- Attribution text is not hidden behind tooltips, collapsed sections, or footer-only placement
- Check method: visual inspection + `fact_usage_report.json` `review_summary[].attribution_visible` field

**Contrast After Accent Override**
- If `design_metadata.accent_override` is present, automated WCAG 2.1 AA contrast check passes for accent against both background and surface tokens
- If contrast fails, gate status is `needs_edit`
- Check method: programmatic contrast ratio computation against CSS custom property values

**Unsafe Photo Persistence**
- No Google Maps/Places-derived photos present when `deploy_mode` = `production_deploy_mode`
- If Google-derived photos are found, gate status is `reject`
- Check method: image URL pattern scan against known Google Maps photo domains + `fact_usage_report.json` `photo_usage[]` source field

**Same-Niche Genericity**
- If Phase 04.5 enrichment provided niche-specific signals (category keywords, review themes, attribute list), output copy must not be generic to the point of losing niche identity
- Automated check: compare rendered copy against niche copy catalog entries — flag if < 30% niche-specific token overlap
- If generic copy exceeds niche copy, flag `needs_edit` with failure code `same_niche_genericity`

Failure codes for these checks:
- `missing_attribution` — review content present without visible attribution
- `contrast_fail` — accent override fails WCAG AA contrast
- `unsafe_photo_production` — Google-derived photo in production mode
- `same_niche_genericity` — output too generic for detected niche
