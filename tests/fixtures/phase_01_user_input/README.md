# Phase 01 User Input Fixtures

## Purpose

Fixtures for standalone testing of Phase 01 - User Input / Run Config.

## Fixture Files

### Input Fixtures

- `valid_config_minimal.json` - Minimal valid config with defaults
- `valid_config_custom_thresholds.json` - Valid config with custom thresholds
- `invalid_config_missing_area.json` - Missing required `area` field
- `invalid_config_preview_gt_raw_results.json` - Invalid: `max_preview_sites` > `max_raw_results`

### Expected Results

- `result_done.json` - Expected result for valid input
- `result_blocked.json` - Expected result for blocked/invalid input

## Run Config Schema

Required fields:
- `niche` - Business category (e.g., "dentists")
- `area` - Geographic area (e.g., "Chiang Mai")
- `country` - Country (e.g., "Thailand")
- `max_raw_results` - Maximum leads to discover
- `max_preview_sites` - Maximum sites to generate
- `price_offer` - Offer text for outreach

Optional with defaults:
- `language` - Default: "English"
- `minimum_rating` - Default: 4.3
- `minimum_reviews` - Default: 40
- `style_preset` - Default: "clean_professional"
- `mvp_stop_threshold` - Default: 20

## Validation Rules

1. All required fields must be present and non-empty
2. `max_preview_sites` must not exceed `max_raw_results`
3. `minimum_rating` must be between 0 and 5
4. `minimum_reviews` must be non-negative