# Quality Gates and Kill Criteria

## Purpose

Each phase needs explicit pass, block, fail, and skip conditions. This prevents noisy runs and makes phases testable in isolation.

---

## Universal result meanings

| Status | Meaning |
|---|---|
| `done` | Phase completed and produced valid outputs. |
| `blocked` | Required input or dependency is missing. No guessing allowed. |
| `failed` | Phase attempted work but could not complete safely. |
| `needs_review` | Output exists but requires manual decision. |
| `skipped` | Record intentionally excluded by rule. |

---

## Phase 01 kill criteria

Block if:

```text
missing niche
missing area
missing country
max_preview_sites > max_raw_results
invalid thresholds
```

---

## Phase 02 kill criteria

Block if:

```text
query_plan missing
selected data source unavailable
website field unavailable from source
no records returned and no fixture mode enabled
```

Fail if:

```text
scraper crashes after retry
normalization cannot produce record_id/business_name for records
```

---

## Phase 02.1 kill criteria

Block if:

```text
website field missing from all records
business_name missing
record_id missing
```

Skip record if:

```text
website_status = has_website
business domain detected
```

Manual review or skip record if:

```text
website_status = uncertain
website_status = invalid_url
http check times out
SSL error
dead domain
parked domain
shortlink or bio-link URL
redirect chain ends on social or Google Maps URL
domain does not plausibly match business identity
```

Continue only if:

```text
website_status = no_website
website_status = social_only
```

---

## Phase 03 kill criteria

Block if:

```text
input contains no no_website/social_only leads
rating/review_count missing for all records
website_status missing
```

Reject record if:

```text
business_status = closed
rating below threshold
review_count below threshold
chain/franchise signal detected
lead_score < threshold
risk_penalty >= 20
lead_score < 60
```

Chain/franchise detection must use word boundary matching. Keywords like inc, llc, corp must match as whole words, not substrings within legitimate business names.

Do not reject solely for missing contact data in Phase 03. Missing contact data is a scoring/confidence penalty until Phase 04 recipient discovery runs.

Needs review if:

```text
strong lead but uncertain duplicate
strong lead but low contact confidence
```

---

## Phase 04 kill criteria

Block if:

```text
business_name missing
category missing
address and maps_url both missing
```

Needs review if:

```text
recipient_channel = unknown and operator wants to override into Phase 05
recipient channel is social-only and manual outreach method is unclear
```

Records with `recipient_channel=unknown` should route to `blocked_no_recipient_channel.json`, not fail Phase 04.

Fail if:

```text
brief contains unsupported claims
FACTS.md and BUSINESS_BRIEF.md contradict each other
```

---

## Phase 05 kill criteria

Block if:

```text
BusinessBrief missing
FACTS.md missing
site template missing
build runtime missing
```

Fail if:

```text
build fails
placeholder text remains
unsupported claims are inserted
required sections missing or out of order
body word count below 140
```

Safety and content-mode checks (applied by Phase 06 but listed here for reference):

```text
Google-derived photo in production_deploy_mode -> reject
review content present without visible attribution -> needs_edit
accent override fails WCAG 2.1 AA contrast -> needs_edit
same-niche copy falls below 30% niche token overlap -> needs_edit
```

Quality floor (applied by Phase 06 but listed here for reference):

```text
Meaningful body words >= 140
Unique paragraphs/cards >= 6
Meaningful CTAs >= 2 when phone + maps exist
Populated sections with distinct content >= 5/7
Duplicate sentence fragments over 8 words: zero tolerance in hero/overview/CTA
Total fallback/generic slots across entire site: max 3
Core slots (hero_tagline, hero_supporting_line, trust_intro, cta_body) with fallback text: max 1
All available core fields used or explicitly justified: phone, address, hours, maps_url, rating + review_count
Attribution visible for all review-derived content
No unsafe photo persistence in production mode
No same-niche genericity when niche signals exist
```

Required sections:

```text
hero
category/services overview
trust section using rating/review count only
location/hours
contact CTA
Google Maps link/embed
footer
```

---

## Phase 06 — Multi-Axis Quality Gate

### Purpose

Phase 06 now operates as a multi-axis credibility gate, not just a safety/existence check. Thin or generic pages that pass safety must still fail credibility scoring.

### Four Score Axes

| Axis | Weight | Score range | What it measures |
|------|--------|-------------|------------------|
| Safety | 25 | 0-25 | No invented claims, no forbidden phrases, no placeholder text |
| Data utilization | 25 | 0-25 | Core facts used, enrichment fields used, field coverage ratio |
| Copy quality | 25 | 0-25 | Word count, duplicate detection, CTA match, readability, no banned phrasing |
| Visual credibility | 25 | 0-25 | Preset match, layout coherence, screenshot quality, text density |

Total score: 0-100.

### Scoring methods

Safety score:
- Start at 25
- -25 for any forbidden claim (hard reject)
- -10 for placeholder text remaining
- -5 per missing required section
- -5 for meta/tool language in public body

Data utilization score:
- Start at 25
- -4 for each core fact available but unused (phone, address, hours, maps_url, rating, review_count)
- -3 for each available enrichment field unused
- -2 for each missing fact not in missing_fields list
- Score = max(0, 25 - deductions)

Copy quality score:
- Start at 25
- -10 for body word count < 140
- -5 for duplicate core copy across hero/overview/CTA
- -5 for banned phrase detected
- -3 per visible fallback slot beyond first
- -3 for CTA absent when contact path exists
- -2 for word count 140-200 (marginal)

Visual credibility score:
- Start at 25
- -10 for missing screenshot; planned strict mode should also reject synthetic or non-Phase 05.5 screenshot provenance
- -5 for wrong or fallback preset when niche maps cleanly
- -5 for low text density (< 0.5)
- -3 for viewport overflow
- -3 for broken images or links
- -2 for duplicate text signals > 0
- -5 for accent override that fails WCAG 2.1 AA contrast
- -3 for trust chips rendered from unverified attributes

### Credibility Score Thresholds

| Score | Status | Action |
|-------|--------|--------|
| >= 90 | APPROVED | Deploy eligible |
| 70-89 | NEEDS_REVIEW | Human review, may deploy |
| 50-69 | NEEDS_EDIT | Auto-reject, regenerate or edit |
| < 50 | REJECTED | Serious issues, investigate root cause |

### Hard Reject Conditions (any one = REJECTED regardless of score)

business_name missing or mismatch
required section missing or out of order
forbidden claim detected
placeholder text remains
screenshot_desktop.png or screenshot_mobile.png missing (current); synthetic or non-Phase 05.5 provenance should hard-reject only in planned strict visual scoring mode
page fails to render
2+ available core facts omitted without justification
CTA absent despite available contact path
body word count below 140
duplicate core copy across hero/overview/CTA
more than 3 fallback/generic slots across entire site
more than 1 core slot (hero_tagline, hero_supporting_line, trust_intro, cta_body) showing fallback text
Google-derived photo present in production_deploy_mode

### Needs-Edit Conditions (triggers NEEDS_EDIT even if score >= 70)

safe but thin copy
wrong or fallback preset
low visual density
one key fact omitted
only one CTA when multiple contact paths exist
over-reliance on fallback text
accent override fails WCAG 2.1 AA contrast
same-niche copy below 30% niche token overlap when niche signals exist
trust chips rendered from unverified attributes
review-derived content present without visible attribution

### Failure Taxonomy (stable codes)

thin_copy
duplicate_copy
generic_design
wrong_preset
fake_screenshot
missing_core_fact_usage
weak_cta
excess_fallback_text
meta_language
low_data_depth
missing_attribution
contrast_fail
unsafe_photo_production
same_niche_genericity
unverified_trust_chip

### Report Schema (site_quality_report.json)

```json
{
  "status": "approved | needs_review | needs_edit | rejected",
  "score": 0,
  "score_breakdown": {
    "safety": 0,
    "data_utilization": 0,
    "copy_quality": 0,
    "visual_credibility": 0
  },
  "failure_codes": [],
  "missing_fact_usage": [],
  "copy_flags": [],
  "visual_flags": [],
  "deploy_eligible": false,
  "reviewer_notes": ""
}
```

### Required input

```text
runs/{run_id}/05_sites/{business_slug}/ (full site folder)
runs/{run_id}/04_briefs/{business_slug}/FACTS.md
runs/{run_id}/04_briefs/{business_slug}/DESIGN.md
runs/{run_id}/05_sites/{business_slug}/build_status.json
runs/{run_id}/05_sites/{business_slug}/fact_usage_report.json
runs/{run_id}/05_sites/{business_slug}/screenshot_desktop.png (exists under 05_sites; may be legacy Phase 05 output or refreshed by Phase 05.5)
runs/{run_id}/05_sites/{business_slug}/screenshot_mobile.png (exists under 05_sites; may be legacy Phase 05 output or refreshed by Phase 05.5)
```

Current implementation note: Phase 06 currently checks for screenshot existence only. Phase 05.5 browser evidence such as `render_capture.json` and `dom_metrics.json` is available when Phase 05.5 runs, but Phase 06 does not yet require or score those files. Strict visual scoring should add Phase 05.5 provenance and DOM/render metric consumption in a future integration step.

### Output

```text
runs/{run_id}/06_quality/{business_slug}/site_quality_report.json
runs/{run_id}/06_quality/{business_slug}/credibility_score.json
runs/{run_id}/06_quality/result.json
```

### Block if

```text
site folder missing
FACTS.md missing
```

### Fake-claim check method

MVP method: regex/string scan against generated HTML and generated copy. Use forbidden claims list in fact_safety_rules.md plus default terms:

award-winning
best in town
#1
top-rated
trusted by thousands
family owned
licensed
certified
guaranteed
testimonial
review says
prices from
years in business

Result handling:

minor or ambiguous hit -> needs_review
clear fake factual claim -> rejected
verified claim in FACTS.md -> allowed, must appear in fact_usage_report.json

---

## Phase 07 kill criteria

Block if:

```text
site_quality_report status != approved or deploy_eligible != true, and no explicit override
hosting provider token missing
site folder missing
```

Fail if:

```text
deployment command fails
preview URL missing
preview URL returns non-2xx/3xx status
wrong business site deployed
```

Needs review if:

```text
takedown_after_days missing
cleanup_required is false without explicit local_only reason
```

---

## Phase 08 kill criteria

Block if:

```text
preview_url missing
business_name missing
price_offer missing
no recipient channel
recipient_channel = unknown and no manual override exists
```

Fail if:

```text
email claims prior relationship
email says business requested preview
email contains fake facts
email missing preview URL
```

---

## Phase 09 kill criteria

Block if:

```text
preview URL missing
outreach draft missing
lead score missing
screenshot_desktop_path missing
screenshot_mobile_path missing
```

Needs review if:

```text
site approved but outreach needs edit
outreach approved but site needs edit
contact method uncertain
```

---

## Phase 10 kill criteria

Block if:

```text
no records have approval_status=send
manual sent confirmation missing
```

Do not send if:

```text
approval_status != send
site_review_status != approved
outreach_review_status != approved
```

---

## Phase 11 kill criteria

Block if:

```text
sent_log missing
no sent outreach records
```

Decision criteria:

```text
continue: serious replies or paid close exists
adjust: replies exist but objections repeat
stop/pivot: no replies or serious-interest events after `RunConfig.mvp_stop_threshold` manually reviewed sends; default threshold = 20
```
