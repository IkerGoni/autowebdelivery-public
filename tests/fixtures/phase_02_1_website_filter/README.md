# Phase 02.1 Website Filter Fixtures

## Purpose

Test fixtures for standalone testing of Phase 02.1 website classification logic.

## Input

- `leads_normalized_edge_cases.json` — Normalized leads with various website URL types:
  - Empty website field (should be `no_website`)
  - Normal business domain (should be `has_website`)
  - Facebook URL (should be `social_only`)
  - Google Maps URL (should be `uncertain` → manual_review)
  - Shortlink (should be `uncertain` → manual_review)
  - Instagram URL (should be `social_only`)

## Expected Outputs

- `website_classifications_expected.json` — Expected WebsiteClassification objects for each input
- `leads_no_website_expected.json` — Leads kept (no_website or social_only status)
- `skipped_has_website_expected.json` — Leads skipped (has_website status)
- `manual_review_expected.json` — Leads needing manual review (uncertain/invalid_url status)
- `result_done.json` — Expected result.json when all processing completes

## Classification Rules

Per `pipeline_data_contract.md`:

| Status | Decision |
|--------|----------|
| no_website | keep |
| social_only | keep |
| has_website | skip |
| uncertain | manual_review (or skip per config) |
| invalid_url | manual_review (or skip per config) |