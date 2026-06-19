# Fixtures README — Standalone Phase Testing

## Purpose

Fixtures let each phase run independently without live scraping, deployment, or sending. Every phase must have valid, invalid, and edge-case inputs before real runs.

## Folder convention

```text
tests/fixtures/{phase_name}/
  input/
  expected/
  README.md
```

Example:

```text
tests/fixtures/phase_02_1_website_filter/
  input/leads_normalized_edge_cases.json
  expected/website_classifications_expected.json
  README.md
```

## Fixture rules

```text
Do not use real private data.
Use synthetic business names unless testing an actual public listing manually.
Keep record_id stable.
Keep business_slug deterministic.
Include both passing and blocking cases.
Expected outputs must include status, decisions, and reason_codes.
```

## Required fixture coverage by phase

### Phase 01 — User input

```text
valid_config_minimal.json
valid_config_custom_thresholds.json
invalid_config_missing_area.json
invalid_config_preview_gt_raw_results.json
```

### Phase 02 — Lead discovery

```text
raw_places_with_websites.json
raw_places_without_website_field.json
raw_places_duplicate_businesses.json
raw_places_missing_rating_reviews.json
```

Expected behavior:

```text
normalize fields
create business_slug
block or needs_review if website field unavailable from source
preserve raw_payload_ref
```

### Phase 02.1 — Website filter

Required cases:

| Case | Expected status |
|---|---|
| empty website | `no_website` |
| null website | `no_website` |
| normal business domain | `has_website` |
| subdomain business URL | `has_website` or `uncertain` if ownership unclear |
| Facebook URL | `social_only` |
| Instagram URL | `social_only` |
| Line URL | `social_only` |
| Linktree / bio-link URL | `uncertain` or `social_only` only if clearly official |
| Google Maps URL | `uncertain` |
| shortlink | `uncertain` |
| malformed URL | `invalid_url` |
| parked GoDaddy-style page | `uncertain` |
| dead domain | `uncertain` |
| SSL error | `uncertain` |
| timeout | `uncertain` |
| redirect to Facebook | `uncertain` or `social_only`, with `website_resolution_status=social_redirect` |

Required expected fields:

```text
website_status
decision
reason_codes
http_checked
http_status
final_url
redirect_chain
checked_redirect
website_resolution_status

HTTP/redirect fields must be present for every record. If no HTTP check ran, expect: `http_checked=false`, `http_status=null`, `final_url=null`, `redirect_chain=[]`, `checked_redirect=false`, `website_resolution_status=not_checked`.
```

### Phase 03 — Lead scoring

```text
qualified_high_rating_many_reviews.json
rejected_low_rating.json
rejected_low_reviews.json
needs_review_uncertain_website.json
missing_phone_contactability_penalty.json
```

Expected behavior:

```text
numeric component scores
lead_score
qualification_status
rejection_reasons
risk_penalty
```

### Phase 04 — Business brief

```text
selected_lead_complete.json
selected_lead_missing_phone.json
selected_lead_missing_hours.json
selected_lead_social_only.json
selected_lead_unknown_recipient_channel.json
```

Expected outputs:

```text
FACTS.md
MISSING_DATA.md
BUSINESS_BRIEF.md
CONTENT_PLAN.md
DESIGN.md
GENERATION_PROMPT.md
recipient_channel.json
briefs_index.json
preview_ready_briefs.json
blocked_no_recipient_channel.json
```

### Phase 05 — Preview site generation

Phase 05 fixtures must use records from `preview_ready_briefs.json`; unknown-recipient briefs belong in blocked fixtures unless manual override is explicitly present.

```text
brief_complete_restaurant/
brief_complete_clinic/
brief_missing_phone/
brief_unknown_hours/
brief_with_forbidden_claim_attempt/
```

Expected outputs:

```text
site/
screenshot_desktop.png
screenshot_mobile.png
build_status.json
fact_usage_report.json
result.json
```

Expected checks:

```text
no placeholder text
all required sections present
phone CTA omitted if phone missing
hours neutral text if missing
no invented services or claims
```

### Phase 06 — Quality gate

```text
site_valid/
site_build_failed/
site_fake_claims/
site_business_name_mismatch/
site_missing_mobile_screenshot/
site_placeholder_text/
site_broken_cta/
```

Expected behavior:

```text
approved_for_deploy only for valid site
needs_edit for obvious repairable issues
rejected for severe mismatch or unsafe claim
fake_claim_check_method recorded
```

### Phase 07 — Deployment

```text
site_quality_approved.json
site_quality_needs_edit.json
mock_deployment_success.json
mock_deployment_http_404.json
missing_provider_token.json
```

Expected outputs:

```text
deployment_record.json
deployments.json
result.json
```

### Phase 08 — Outreach draft

```text
email_channel_valid.json
contact_form_channel_valid.json
social_message_channel_valid.json
unknown_channel_blocked.json
missing_preview_url.json
missing_price_offer.json
```

Expected behavior:

```text
ready_for_review only when recipient channel and preview_url exist
blocked when recipient_channel unknown and no manual override
opt-out line included
no forbidden wording
```

### Phase 09 — Manual approval pack

```text
complete_review_record.json
missing_desktop_screenshot_path.json
missing_mobile_screenshot_path.json
missing_outreach_draft.json
site_needs_edit.json
```

Expected outputs:

```text
review_table.csv
review_pack.md
screenshots_index.json
approval_decisions.json
```

### Phase 10 — Manual sending

```text
approved_send_records.json
no_approved_records.json
manual_confirmation_present.json
manual_confirmation_missing.json
```

Expected behavior:

```text
no automated sending
manual_send_queue and manual_send_checklist created before confirmation
sent_log only after manual confirmation
```

### Phase 11 — Monetization tracking

```text
sent_no_replies_below_threshold.json
sent_no_replies_at_threshold.json
reply_interest_event.json
paid_close_event.json
lost_event.json
```

Expected behavior:

```text
stop_or_pivot when sent count >= mvp_stop_threshold and zero replies/interest
continue_testing when below threshold
record objections and next_action
```

## Minimum local slice

Before any live scraping, build this path:

```text
Phase 02 fixture normalized leads
Phase 02.1 website filter
Phase 03 scoring
Phase 04 brief pack
Phase 05 static preview site
Phase 06 quality gate
Phase 09 review pack
```

Do not add live deployment or outreach until this slice passes.
