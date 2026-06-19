# Phase 05 Preview Site Generation Fixtures

## Purpose

Fixtures for deterministic preview site generation from Phase 04 briefs.

## Input cases

- `brief_complete_restaurant.json` - Complete restaurant brief with all fields
- `brief_complete_clinic.json` - Complete medical clinic brief
- `brief_missing_phone.json` - Brief with phone field missing; phone CTA omitted
- `brief_unknown_hours.json` - Brief with hours missing; neutral hours text used
- `brief_with_forbidden_claim_attempt.json` - Full brief testing forbidden claim detection

## Expected outputs

Each fixture produces:
```
site/
  index.html
screenshot_desktop.png
screenshot_mobile.png
build_status.json
fact_usage_report.json
```

## Verification checks

- No placeholder text in generated HTML
- All required sections present (hero, services_or_category_overview, trust, location_and_hours, map_or_maps_link, contact_cta, footer)
- Phone CTA omitted if phone missing
- Hours neutral text "Hours not listed in source data" if missing
- No invented services or claims
- Forbidden claim hits detected and reported