# Brand Profile Contract (VNEXT-03)

**Schema Version:** 1.1.0  
**Phase:** 04.7 — Brand Reconstruction Generation  
**Feature Flag:** `use_brand_reconstruction_contract` (default: OFF)

---

## Purpose

Produce a canonical `brand_profile.json` artifact for each scored lead. The brand profile sits alongside:

- `business_profile.json` (VNEXT-01) — verified-facts view
- `market_profile.json` (VNEXT-02) — sellability/strategy view
- `brand_profile.json` (VNEXT-03) — brand tone/trust/emotional view

The brand profile maps category keywords to deterministic brand tone, trust posture, emotional goals, and colour direction. No LLM is involved; all mapping is static and deterministic.

---

## Artifact Location

```
runs/{run_id}/04_7_brand/{business_slug}/brand_profile.json
```

---

## Required Input

| Source | Required | Description |
|--------|----------|-------------|
| `runs/{run_id}/04_briefs/{business_slug}/business_profile.json` | Yes | BusinessProfile with verified_facts.category |
| `runs/{run_id}/03_scoring/{business_slug}/market_profile.json` | Optional | MarketProfile with strategy_hints |

---

## Output Schema

```json
{
  "schema_version": "1.1.0",
  "run_id": "string",
  "business_slug": "string",
  "generated_at": "ISO-8601 timestamp (deterministic)",
  "brand_tone": {
    "primary": {"value": "string", "source": "string", "confidence": "inferred"},
    "secondary": {"value": "string", "source": "string", "confidence": "inferred"},
    "voice": {"value": "string", "source": "string", "confidence": "inferred"}
  },
  "trust_posture": {
    "value": "string",
    "source": "string",
    "confidence": "inferred"
  },
  "emotional_goals": ["string", ...],
  "color_direction": {
    "primary_hint": {"value": "string", "source": "string", "confidence": "inferred"},
    "mood": {"value": "string", "source": "string", "confidence": "inferred"}
  },
  "missing_data": ["string", ...],
  "forbidden_public_claims": ["string", ...],
  "enrichment_signals": {"gmaps_review_signals": {...}} (optional),
  "internal": {
    "flag": "use_brand_reconstruction_contract",
    "schema_origin": "VNEXT-03",
    "enrichment_consumed": true|false
  }
}
```

---

## Category-to-Brand Mapping

### Auto Detailing
- Keywords: `auto detail`, `detailing`, `ceramic coating`, `paint protection`, `ppf`, `mobile detail`
- Primary tone: `professional`
- Secondary tone: `warm`
- Voice: `authoritative_approachable`
- Trust posture: `credential_safe`
- Emotional goals: `confidence`, `reliability`
- Color hint: `blue`
- Mood: `clean_professional`

### Dental/Medical
- Keywords: `dentist`, `dental`, `med spa`, `medical`, `clinic`, `orthodontist`
- Primary tone: `clinical`
- Secondary tone: `warm_professional`
- Voice: `reassuring_authoritative`
- Trust posture: `conservative`
- Emotional goals: `trust`, `safety`
- Color hint: `white`
- Mood: `calming_clean`

### Legal
- Keywords: `law`, `attorney`, `legal`, `lawyer`, `solicitor`
- Primary tone: `authoritative`
- Secondary tone: `formal`
- Voice: `authoritative_formal`
- Trust posture: `authoritative`
- Emotional goals: `trust`, `confidence`
- Color hint: `navy`
- Mood: `professional_gravity`

### Home Services/Trades
- Keywords: `hvac`, `plumb`, `roof`, `electrician`, `landscap`, `pest control`, `home service`, `handyman`
- Primary tone: `reliable`
- Secondary tone: `friendly_professional`
- Voice: `friendly_reliable`
- Trust posture: `credential_safe`
- Emotional goals: `safety`, `competence`
- Color hint: `orange`
- Mood: `warm_reliable`

### Restaurant/Cafe
- Keywords: `restaurant`, `cafe`, `coffee`, `bakery`, `bar `, `food truck`, `fast food`, `pizzeria`, `bistro`
- Primary tone: `warm`
- Secondary tone: `casual_inviting`
- Voice: `casual_inviting`
- Trust posture: `experience_safe`
- Emotional goals: `comfort`, `celebration`
- Color hint: `warm_red`
- Mood: `cozy_vibrant`

### Default/Fallback
- Primary tone: `professional`
- Secondary tone: `neutral_approachable`
- Voice: `neutral_approachable`
- Trust posture: `credential_safe`
- Emotional goals: `confidence`, `clarity`
- Color hint: `gray`
- Mood: `clean_neutral`

---

## Forbidden Public Claims

The following claim categories must never appear in public marketing copy generated from this profile:

```
years_in_business, awards, licenses, insurance, certifications, staff_credentials, testimonials, guarantees, superlatives
```

---

## Missing Data Detection

The brand profile reports missing data that lowers confidence:

- `category` — if category is absent from `verified_facts` or `inferred_strategy.niche`
- `strategy_hints` — if market_profile lacks strategy_hints section
- `market_profile` — if market_profile is entirely missing

---

## Determinism

`generated_at` is derived from SHA-256 of `(run_id, business_slug)` mapped to a fixed epoch plus a day offset. Identical inputs produce byte-identical output across processes and machines (no wall-clock dependence).

---

## Enrichment Signals

When enrichment data is present in `business_profile.enrichment`, the profile includes an optional `enrichment_signals` object:

```json
{
  "gmaps_review_signals": {
    "has_reviews": bool,
    "avg_rating": float,
    "review_count": int,
    "review_snippet_count": int,
    "sentiment_hint": "positive" | "neutral" | "none"
  },
  "social_presence_signals": {
    "has_social_presence": bool,
    "follower_count": int,
    "post_count": int,
    "is_verified": bool,
    "social_category": string,
    "platform": string,
    "brand_maturity": "established" | "emerging" | "unknown"
  },
  "overpass_osm_signals": {
    "has_osm_data": bool,
    "osm_category": string
  }
}
```

---

## Phase Outputs

When feature flag is ON:

| Path | Artifact |
|------|----------|
| `runs/{run_id}/04_7_brand/{business_slug}/brand_profile.json` | Per-business brand profile |
| `runs/{run_id}/04_7_brand/brand_profiles_index.json` | Index of generated slugs |
| `runs/{run_id}/04_7_brand/result.json` | ResultEnvelope |

---

## Block Conditions

- Missing `business_slug` in business_profile
- Missing `business_profile.json` for a given slug

---

## Integration Points

| Consumer | Usage |
|----------|-------|
| Stitch prompt compiler | Reads `brand_tone`, `trust_posture`, `color_direction` for template guidance |
| Copy generators | Uses `emotional_goals` to guide messaging tone |

---

## Non-Goals

- No logo generation
- No full brand guidelines
- No inference of owner biography, years in business, licenses, insurance, awards, testimonials
- All values are inferred, never verified