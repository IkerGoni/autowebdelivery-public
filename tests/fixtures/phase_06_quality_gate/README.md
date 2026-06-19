# Phase 06 Quality Gate Fixtures

## Input Fixtures

### site_valid.json
Valid site with all requirements met. Should result in `approved_for_deploy`.

### site_build_failed.json
Build status is `failed`. Should result in `rejected`.

### site_fake_claims.json
HTML contains forbidden claims like "best in town", "award-winning", "#1". Should result in `rejected` for severe claims.

### site_business_name_mismatch.json
Business name in HTML doesn't match FACTS.md. Should result in `rejected`.

### site_missing_mobile_screenshot.json
Mobile screenshot file is missing. Should result in `rejected`.

### site_placeholder_text.json
HTML contains placeholder text like "Lorem ipsum" or "TODO". Should result in `rejected`.

### site_broken_cta.json
CTA links may have issues. Should result in `needs_edit`.

## Expected Output

Site with valid structure, matching business name, no forbidden claims, and both screenshots should produce `approved_for_deploy`.