# Standalone Phase Testing Plan

Related fixture index: `/docs/fixtures/README.md`.

## Goal

Each phase must be runnable and testable by itself. This allows isolated debugging before connecting the full pipeline.

---

## Test fixture structure

```text
tests/fixtures/
  phase_01_user_input/
    input/valid_config.json
    input/invalid_config_missing_area.json
    expected/result_done.json
    expected/result_blocked.json
  phase_02_basic_lead_discovery/
  phase_02_1_website_filter/
  phase_03_lead_scoring/
  phase_04_business_brief_generation/
  phase_05_preview_site_generation/
  phase_06_quality_gate/
  phase_07_deployment/
  phase_08_outreach_generation/
  phase_09_manual_approval_pack/
  phase_10_manual_sending/
  phase_11_monetization_tracking/
```

---

## Required test types per phase

Every phase needs at least:

```text
1 valid happy-path fixture
1 missing-required-input fixture
1 bad-data fixture
1 edge-case fixture
```

---

## Phase-specific fixture requirements

### Phase 02.1 website filter

Fixtures must include:

```text
empty website
Facebook URL
Instagram URL
Line URL
Google Maps URL
normal business domain
malformed URL
redirect-looking URL
internationalized domain
dead domain
parked GoDaddy-style page
Linktree or bio-link URL
shortlink URL
redirect-to-Facebook URL
subdomain business URL
SSL error fixture
timeout fixture
```

Expected labels:

```text
no_website
social_only
has_website
invalid_url
uncertain
```

Expected resolution fields when HTTP/redirect verification is enabled:

```text
http_checked
http_status
final_url
redirect_chain
checked_redirect
website_resolution_status

HTTP/redirect fields must be present for every record. If no HTTP check ran, expect: `http_checked=false`, `http_status=null`, `final_url=null`, `redirect_chain=[]`, `checked_redirect=false`, `website_resolution_status=not_checked`.
```

### Phase 03 scoring

Fixtures must include:

```text
high rating/high reviews
low rating
low reviews
missing phone
closed business
duplicate business
social_only business
```

Expected outputs:

```text
component scores
lead_score
qualification_status
rejection_reasons
```

### Phase 04 brief generation

Fixtures must include:

```text
complete lead
missing hours
missing phone
missing address but maps_url present
```

Expected checks:

```text
FACTS.md contains only verified facts
MISSING_DATA.md lists missing fields
no fake claims in BUSINESS_BRIEF.md
```

### Phase 05 preview generation

Fixtures must include:

```text
valid BusinessBrief
brief with missing phone
brief with social_only status
brief with missing maps_url
brief with unknown recipient_channel routed to blocked_no_recipient_channel.json
preview_ready_briefs.json routes only reachable/manual-override briefs
blocked_no_recipient_channel.json prevents default Phase 05 input
```

Expected checks:

```text
build_status.json
screenshot_desktop.png
screenshot_mobile.png
fact_usage_report.json
no placeholder text
```

### Phase 07 deployment

Fixtures must include:

```text
approved site
unapproved site
missing provider token
failed deployment response
```

Expected checks:

```text
deployment blocked if not approved
preview_url verified if live
```

### Phase 08 outreach

Fixtures must include:

```text
valid preview URL
missing preview URL
recipient_channel = unknown without manual override
blocked_no_recipient_channel.json input
recipient_channel = contact_form
recipient_channel = facebook_message
missing price_offer
```

Expected checks:

```text
draft_status
blocked_reason
no fake relationship claim
```

---

## Required local test command pattern

Preferred:

```bash
pnpm test:phase:02_1
pnpm test:phase:03
pnpm test:phase:05
```

Alternative:

```bash
python -m pytest tests/phases/test_phase_02_1_website_filter.py
```

---

## Minimum acceptance before integration

A phase is not integration-ready until:

```text
all standalone fixtures pass
result envelope is written
output paths match phase_io_contracts.md
kill criteria are implemented
bad input returns blocked/failed, not partial fake output
```
