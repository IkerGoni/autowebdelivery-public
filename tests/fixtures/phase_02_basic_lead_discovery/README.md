# Phase 02 Basic Lead Discovery Fixtures

## Purpose

Test Phase 02 normalization logic with fixture data representing raw Google Maps-like places.

## Fixture Files

### Input

- `raw_places_with_websites.json` — 3 dental clinics with websites present. Tests normal flow.
- `raw_places_without_website_field.json` — 2 dental clinics with empty/blank website fields. Should trigger needs_review.
- `raw_places_duplicate_businesses.json` — 3 records where 2 are duplicates of the same business. Tests dedupe.
- `raw_places_missing_rating_reviews.json` — 2 records with null rating/review_count. Tests null handling.

### Expected

- `leads_normalized_expected.json` — Expected normalized output for the main fixture.
- `result_done.json` — Expected result for successful run.
- `result_blocked_or_needs_review.json` — Expected result when websites missing.

## Expected Behaviors

| Fixture | Expected Status | Notes |
|---------|-----------------|-------|
| raw_places_with_websites.json | done | All records have websites |
| raw_places_without_website_field.json | needs_review | Missing website field |
| raw_places_duplicate_businesses.json | done | Dedupe removes 1 duplicate |
| raw_places_missing_rating_reviews.json | done | Null values handled as 0 |

## Key Behaviors to Verify

1. **business_slug generation** — Deterministic, lowercase, hyphenated, with ID suffix
2. **dedupe_key generation** — Same business_name + address creates same key
3. **status logic** — needs_review when any record missing website
4. **record counts** — records_processed vs records_created vs records_skipped