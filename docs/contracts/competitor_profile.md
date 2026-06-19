# Competitor Profile Contract — VNEXT-10

## Purpose

The `competitor_profile.json` artifact provides structural niche-pattern intelligence
derived from curated benchmark fixtures. It enables downstream phases (creative spec,
site generation) to align with category-common conventions — section layout, CTA types,
color palettes, mobile patterns — **without ever copying competitor content, images,
logos, or brand marks**.

## Feature Flag

| Flag | Default | Scope Option |
|---|---|---|
| `use_competitor_intelligence` | `false` (OFF) | `competitor_scope`: `"none"`, `"fixtures_only"`, `"curated"` (future) |

When the flag is OFF, Phase 04.6 is skipped entirely. When `competitor_scope` is
`"none"`, the phase is also skipped even if the main flag is ON.

## Schema

```json
{
  "schema_version": "1.0.0",
  "run_id": "string",
  "business_slug": "string",
  "generated_at": "ISO-8601 (deterministic)",
  "category": "string",
  "area": "string",
  "patterns": {
    "common_sections": ["hero", "services", "..."],
    "common_cta_types": ["phone_call", "contact_form", "..."],
    "pricing_visibility": "range_or_contact | insurance_based | estimate_or_contact",
    "trust_signals": ["ratings_display", "years_badge", "..."],
    "mobile_patterns": ["sticky_cta", "click_to_call", "..."],
    "color_patterns": {
      "dominant_colors": ["blue", "white", "..."],
      "accent_colors": ["orange", "red", "..."]
    },
    "layout_patterns": ["single_page_scroll", "sticky_header", "..."]
  },
  "benchmarks_used": ["auto_detailing_dallas_fixture.json"],
  "disclaimer": "Patterns derived from curated benchmarks and fixtures. No competitor content, images, logos, or brand marks are copied or reproduced.",
  "missing_data": [],
  "internal": {
    "flag": "use_competitor_intelligence",
    "scope": "fixtures_only",
    "schema_origin": "VNEXT-10"
  }
}
```

## Key Invariants

1. **No competitor content** — Patterns contain only structural metadata (section
   names, CTA types, color tokens). No text content, images, logos, brand marks,
   slogans, taglines, or exact layouts are ever included.

2. **Deterministic** — `generated_at` is derived from a SHA-256 hash of
   `(run_id, business_slug)`, not wall-clock time. Identical inputs produce
   byte-identical output.

3. **Fixture-only (v1)** — All pattern data comes from curated fixture files in
   `tests/fixtures/competitor_benchmarks/`. No live scraping or API calls.

4. **Graceful fallback** — When no fixture matches the (category, area), the profile
   returns empty pattern lists and reports `benchmark_match` in `missing_data`.

5. **Disclaimer always present** — Every profile includes the mandatory disclaimer
   about data provenance.

## Benchmark Fixtures

Located in `tests/fixtures/competitor_benchmarks/`:

| File | Category | Area |
|---|---|---|
| `auto_detailing_dallas_fixture.json` | Auto Detailing Service | Dallas, TX |
| `dental_clinic_chicago_fixture.json` | Dental Clinic | Chicago, IL |
| `hvac_service_phoenix_fixture.json` | HVAC Service | Phoenix, AZ |

## Downstream Consumers

- **Phase 04.8 (Creative Spec)** — Can merge `competitor_profile.patterns` into
  creative specifications when `use_competitor_intelligence=true`.
- **Phase 05 (Site Generation)** — Can use pattern hints for template/section selection.

## Module API

### `packages/intelligence/competitor_intelligence.py`

```python
def build_competitor_profile(
    category: str,
    area: str,
    config: dict | None = None,
    *,
    run_id: str,
    business_slug: str,
) -> dict:
    """Build competitor profile from fixture benchmarks."""

def write_competitor_profile(
    profile: dict,
    output_dir: str | Path,
    business_slug: str,
) -> str:
    """Write profile to disk. Returns absolute path."""
```

### `packages/phases/phase_04_6_competitor_intelligence.py`

```python
def run_phase_04_6(
    run_id: str,
    workspace: str,
    config: dict | None = None,
) -> dict:
    """Run competitor intelligence phase if flag enabled."""
```

## I/O Contract

| Direction | Path |
|---|---|
| Input | `runs/{run_id}/04_briefs/preview_ready_briefs.json` |
| Output | `runs/{run_id}/04_6_competitor_intelligence/{slug}/competitor_profile.json` |
| Output | `runs/{run_id}/04_6_competitor_intelligence/result.json` |
