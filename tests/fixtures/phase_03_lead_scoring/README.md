# Phase 03 Lead Scoring Fixtures

## Input fixtures

- `qualified_high_rating_many_reviews.json` - Two qualified leads with high ratings and many reviews
- `rejected_low_rating.json` - Lead with rating below threshold
- `rejected_low_reviews.json` - Lead with review count below threshold
- `needs_review_uncertain_website.json` - Lead that should go to needs_review status
- `missing_phone_contactability_penalty.json` - Lead with missing contact data (penalty only, not rejection)

## Expected outputs

- `leads_scored_expected.json` - Expected scored leads output
- `result_done.json` - Expected result envelope for successful run

## Scoring logic

Component scores (0-100 each):
- `rating_score` - Based on meeting minimum_rating threshold
- `review_score` - Based on meeting minimum_reviews threshold (logarithmic scaling)
- `contactability_score` - Based on phone, website, and maps_url availability

Overall `lead_score` = rating_score * 0.4 + review_score * 0.3 + contactability_score * 0.3

## Qualification statuses

- `qualified` - lead_score >= 50
- `needs_review` - 30 <= lead_score < 50
- `rejected` - lead_score < 30 or hard rejection criteria

## Hard rejection criteria

- `business_closed` - business_status = "closed"
- `chain_franchise_signal` - chain/franchise keywords detected
- `score_below_threshold` - lead_score < 30 without other hard reject reasons