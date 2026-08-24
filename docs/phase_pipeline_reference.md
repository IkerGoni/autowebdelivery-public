# Auto Web Project — MVP Phase Pipeline Reference

## Current MVP goal

Build a local-first MVP where the user selects a niche and area, the system finds Google Maps businesses with no proper website, builds simple preview websites, deploys temporary previews, generates outreach drafts, and the user manually approves/sends.

The goal is monetization validation before dashboard, CRM, billing, full automation, custom domains, or weak-website audits.

```text
niche + area
→ basic Google Maps lead discovery
→ early no-website/social-only filter
→ score only qualified leads
→ generate safe business brief
→ build preview site from fixed template
→ quality gate
→ deploy temporary preview
→ generate outreach draft
→ manual approval/send
→ track replies/sales
```

## MVP offer

```text
I found your business on Google Maps and could not find a proper website.
I made a quick preview to show what your online page could look like.
If useful, I can customize and publish it for a small one-time fee.
```

Suggested pricing test:

```text
$199–$399 one-time setup
optional $29–$79/month for hosting, edits, or maintenance
```

Initial validation target:

```text
50 raw leads
10 qualified no-website/social-only leads
3–5 preview websites
20 manually approved outreach attempts
1 serious reply or paid close
```

Default stop/pivot trigger:

```text
20 manually sent outreaches with zero replies or serious-interest events.
Configured by RunConfig.mvp_stop_threshold.
```

---

## Canonical docs

```text
/docs/mvp_pipeline_flow.md
/docs/contracts/pipeline_data_contract.md
/docs/contracts/phase_io_contracts.md
/docs/gates/fact_safety_rules.md
/docs/gates/quality_gates.md
/docs/testing/standalone_phase_testing.md
/docs/templates/site_template_spec.md
/docs/templates/generation_prompt_example.md
/docs/ops/preview_site_policy.md
```

Implementation rule: contracts beat narrative docs if conflict exists.

---

## Phase status table

| Phase | Name | MVP planning status | Main output | Current weak point |
|---|---|---:|---|---|
| 0 | Setup | Closed | repo/run folder structure | runtime assumptions |
| 1 | User input | Closed | `input_config.json`, `query_plan.json` | none material |
| 2 | Basic lead discovery | Closed | `leads_raw.json`, `leads_normalized.json` | scraper must expose website field |
| 2.1 | Early website filter | Closed | `leads_no_website.json`, `website_filter_report.json` | HTTP/redirect edge cases |
| 3 | Lead scoring | Closed | `leads_scored.csv`, `qualified_leads.json` | contactability scoring depends on available data |
| 4 | Business brief | Closed | safe brief pack per business | recipient channel may be unknown |
| 5 | Preview generation | Closed | static site + screenshots + fact report | implementation quality depends on template discipline |
| 6 | Quality gate | Closed | `site_quality_report.json` | fake-claim scan is MVP-level, not perfect |
| 7 | Deployment | Closed | live preview URL + deployment_record.json lifecycle fields | cleanup discipline |
| 8 | Outreach draft | Closed | `outreach_drafts.md/json` | channel availability |
| 9 | Manual approval pack | Closed | `review_table.csv`, `review_pack.md` | manual bottleneck |
| 10 | Manual sending | Closed | `sent_log.csv` | manual tracking consistency |
| 11 | Monetization tracking | Closed | `mvp_results.md`, objections log | small sample size |

---

## Phase 0 — Setup

Goal: prepare a repeatable local pipeline.

Sub-steps:

```text
0.1 Create project repo
0.2 Define runtime requirements
0.3 Define config schema
0.4 Define output folders
0.5 Define lead data schema
0.6 Define run ID format
0.7 Prepare manual review outputs
```

Recommended structure:

```text
auto-web-leads/
  config/
  docs/
    agent_tasks/
    contracts/
    gates/
    ops/
    research/
    templates/
    testing/
  runs/
  generated_sites/
  packages/
    lead_schema/
    scoring/
    website_filter/
    site_generator/
    outreach/
```

Orchestration rule:

```text
External task trackers (e.g. Kanban) may track tasks and human gates.
The repo, docs, and run artifacts remain the source of truth.
Do not build autonomous end-to-end orchestration until the MVP gets real demand signals.
```

Output:

```text
/config/run_config.json
/runs/{run_id}/
```

---

## Phase 1 — User input

Goal: define the market and offer for one MVP run.

Required input:

```json
{
  "niche": "dentists",
  "area": "Chiang Mai",
  "country": "Thailand",
  "max_raw_results": 100,
  "max_preview_sites": 5,
  "language": "English",
  "price_offer": "$299 one-time setup"
}
```

Recommended defaults:

```json
{
  "minimum_rating": 4.3,
  "minimum_reviews": 40,
  "recent_activity_required": false,
  "style_preset": "clean_professional",
  "mvp_stop_threshold": 20
}
```

Validation rules:

```text
niche, area, country required
max_raw_results > 0
max_preview_sites > 0 and <= max_raw_results
minimum_rating between 0 and 5
minimum_reviews >= 0
language non-empty
price_offer non-empty for outreach phase
mvp_stop_threshold > 0
```

Output:

```text
input_config.json
query_plan.json
```

---

## Phase 2 — Basic lead discovery

Goal: get only basic Google Maps data needed for early filtering.

Sub-steps:

```text
2.1 Generate search queries from niche + area
2.2 Run Google Maps scraper/API
2.3 Collect basic fields only
2.4 Normalize business names, URLs, phone, address
2.5 Deduplicate by place_id or name + address
2.6 Block if website field is unavailable across all records
```

Collected fields:

```json
{
  "business_name": "",
  "place_id": "",
  "category": "",
  "rating": 0,
  "review_count": 0,
  "address": "",
  "phone": "",
  "website": "",
  "maps_url": "",
  "hours": "",
  "status": ""
}
```

Important rule: do not enrich, analyze, generate, or deploy before Phase 2.1 confirms no normal website/social-only status.

Output:

```text
leads_raw.json
leads_normalized.json
```

---

## Phase 2.1 — Early website-existence filter

Goal: remove businesses that already have a normal website as early as possible.

Sub-steps:

```text
2.1.1 Read website field from Google Maps result
2.1.2 Normalize and parse URL/domain
2.1.3 Classify website status
2.1.4 Verify uncertain/suspicious URLs with HTTP + redirect checks
2.1.5 Keep no_website/social_only records
2.1.6 Skip clean has_website records immediately
2.1.7 Log skipped/uncertain records and reason
```

Classification rules:

| Website field / result | Classification | Action |
|---|---:|---|
| empty/null | `no_website` | keep |
| Google Maps URL only | `uncertain` | manual review or skip for MVP |
| Facebook/Instagram/Line/social only | `social_only` | keep |
| Linktree/bio-link/social redirect | `social_only` or `uncertain` | keep/review |
| normal business-owned domain that loads | `has_website` | skip |
| dead/parked/placeholder domain | `uncertain` | review/skip |
| malformed unrepaired URL | `invalid_url` | review/skip |
| timeout/SSL/check failure | `uncertain` | review/skip |

Resolution fields:

```text
http_checked
http_status
final_url
redirect_chain
checked_redirect
website_resolution_status
```

All HTTP/redirect fields must be present on every record. When the check is not run, use `http_checked=false`, `http_status=null`, `final_url=null`, `redirect_chain=[]`, `checked_redirect=false`, and `website_resolution_status=not_checked`.

MVP continuation rule:

```text
continue only if website_status in ["no_website", "social_only"]
```

Out of scope:

```text
weak website audit
broken website audit
SEO audit
performance audit of existing sites
replacement of existing websites
```

Output:

```text
leads_no_website.json
skipped_has_website.json
website_filter_report.json
```

---

## Phase 3 — Lead quality scoring

Goal: rank no-website/social-only leads by sales potential.

Sub-steps:

```text
3.1 Score rating
3.2 Score review count
3.3 Score recent activity if available
3.4 Score contactability
3.5 Score business value by niche/category
3.6 Apply exclusion rules
3.7 Rank leads
3.8 Select top candidates for preview generation
```

Pass rules:

```text
rating >= configured threshold
review_count >= configured threshold
business appears open
not chain/franchise
not duplicate
website_status in ["no_website", "social_only"]
```

Contactability is scored, not used as a hard rejection. Missing contact data reduces score/confidence. Phase 4 is responsible for recipient channel discovery.

Scoring model:

```text
lead_score =
  rating_score
+ review_volume_score
+ contactability_score
+ category_value_score
+ freshness_score
+ confidence_score
- risk_penalty
```

Default weights:

```text
rating_score: 0-20
review_volume_score: 0-25
contactability_score: 0-20
category_value_score: 0-20
freshness_score: 0-10
confidence_score: 0-5
risk_penalty: 0-40 deducted
qualification threshold: lead_score >= 65
```

Recent activity rule:

```text
Prefer reviews/photos/posts within 90 days.
If unavailable from scraper, use as enrichment/manual-review signal, not a blocker.
```

Output:

```text
leads_scored.csv
qualified_leads.json
selected_for_preview.json
```

---

## Phase 4 — Business brief generation

Goal: create safe, structured input for website generation.

Sub-steps:

```text
4.1 Create business folder
4.2 Extract verified facts
4.3 Mark missing fields
4.4 Generate safe business summary
4.5 Generate content outline
4.6 Choose design preset
4.7 Create GENERATION_PROMPT.md
4.8 Discover recipient_channel from already available public data
```

Allowed recipient channels:

```text
email
contact_form
phone
facebook_message
instagram_dm
line
unknown
```

Rules:

```text
Do not aggressively scrape emails in MVP.
Email must be explicitly visible from source data or a verified page.
Contact form must have a real URL.
Social-only businesses may use social messaging.
unknown does not fail Phase 4, but blocks Phase 8 unless manually overridden.
```

Files per business:

```text
/businesses/{business_slug}/
  FACTS.md
  MISSING_DATA.md
  BUSINESS_BRIEF.md
  CONTENT_PLAN.md
  DESIGN.md
  GENERATION_PROMPT.md
  recipient_channel.json
  RECIPIENT_CHANNEL.md optional human summary
```

Verified facts:

```text
business name
category
rating
review count
address
phone
hours if available
Google Maps URL
website_status
recipient_channel
```

Output:

```text
site_brief_pack/
preview_ready_briefs.json
blocked_no_recipient_channel.json
```

Only `preview_ready_briefs.json` should feed Phase 5 by default. Briefs with `recipient_channel=unknown` go to `blocked_no_recipient_channel.json` unless manually overridden.

---

## Phase 5 — Preview website generation

Goal: build a simple one-page preview site from the fixed template spec.

Required input:

```text
preview_ready_briefs.json
BusinessBrief folder for each selected business
FACTS.md
CONTENT_PLAN.md
DESIGN.md
GENERATION_PROMPT.md
```

Do not use `blocked_no_recipient_channel.json` as Phase 5 input unless the record has an explicit manual override.

Canonical docs:

```text
/docs/templates/site_template_spec.md
/docs/templates/generation_prompt_example.md
```

Recommended stack for MVP:

```text
Astro static output or plain HTML/Tailwind
Tailwind
simple reusable templates
Playwright screenshots
```

Required sections:

```text
hero
category/services overview
trust section using rating/review count only
location and hours
contact CTA
Google Maps link/embed
footer
```

Sub-steps:

```text
5.1 Create site project from documented template
5.2 Inject verified business facts
5.3 Generate safe page copy
5.4 Render required layout sections
5.5 Add CTA buttons using verified contact data
5.6 Add maps/contact section
5.7 Run build locally
5.8 Save desktop/mobile screenshots
5.9 Emit fact_usage_report.json
5.10 Flag errors for manual review
```

Output:

```text
/generated_sites/{business_slug}/
  build_status.json
  fact_usage_report.json
  screenshot_desktop.png
  screenshot_mobile.png
```

---

## Phase 6 — Quality gate

Goal: make sure the generated preview is safe to show.

This is a quality gate for the generated preview, not an audit of the business's existing website.

Required checks:

```text
build passes
homepage loads
desktop screenshot exists
mobile screenshot exists
business name correct
phone/address correct
CTA links work
no fake testimonials/prices/awards
no forbidden claims from fact_safety_rules.md
no placeholder text left
no broken internal links
```

Fake-claim MVP method:

```text
Run regex/string scan against forbidden claims list.
Scan built HTML and generated copy.
Flag hits as needs_review unless severe.
```

Output:

```text
site_quality_report.json
```

---

## Phase 7 — Deployment

Goal: publish a temporary preview site to a live URL.

MVP deployment target:

```text
Vercel free/preview deployment first
Netlify or Cloudflare Pages as fallback
```

Sub-steps:

```text
7.1 Create deployment project/name
7.2 Deploy static site
7.3 Store preview URL
7.4 Verify URL loads
7.5 Save deployment logs
7.6 Populate deployment_record.json takedown fields
```

Naming format:

```text
{run_id}-{business_slug}
```

Preview lifecycle:

```text
default takedown_after_days: 30
remove immediately if business requests removal
operator owns cleanup
```

Output:

```text
deployment_record.json
```

---

## Phase 8 — Outreach draft generation

Goal: generate short, specific outreach drafts for manual approval.

Email angle:

```text
I found your business on Google Maps.
I could not find a proper website.
I made a quick preview.
If useful, I can customize and publish it for a small one-time fee.
```

Sub-steps:

```text
8.1 Confirm recipient_channel is available or manual override exists
8.2 Generate subject line
8.3 Generate short body
8.4 Insert preview URL
8.5 Insert business-specific reason
8.6 Insert price offer
8.7 Generate optional follow-up
8.8 Save draft
```

Blocked condition:

```text
recipient_channel = unknown and no manual override
```

Output:

```text
outreach_drafts.md
outreach_drafts.json
```

---

## Phase 9 — Manual approval pack

Goal: give the user a simple review artifact before sending anything.

Review states:

```text
send
edit
skip
needs_rebuild
needs_more_info
```

Review table fields:

```text
business_name
category
rating
review_count
phone
address
website_status
recipient_channel
lead_score
preview_url
screenshot_path
screenshot_desktop_path
screenshot_mobile_path
email_subject
approval_status
notes
```

Output:

```text
review_table.csv
review_pack.md
```

---

## Phase 10 — Manual sending

Goal: user sends only approved outreach messages.

Sub-steps:

```text
10.1 Review site preview
10.2 Review outreach draft
10.3 Edit if needed
10.4 Send manually from selected inbox/channel
10.5 Record sent date, channel, status
```

Output:

```text
approved_send_records.json
manual_send_queue.json
manual_send_checklist.md
sent_log.json
sent_log.csv
```

No automated sending in MVP.
Manual confirmation file is required before sent_log artifacts are written.

---

## Phase 11 — Monetization tracking

Goal: decide whether the MVP monetizes.

Sub-steps:

```text
11.1 Track sent messages
11.2 Track replies
11.3 Track serious interest
11.4 Track paid closes
11.5 Record objections
11.6 Decide continue, adjust, or stop
```

Success criteria:

```text
50 raw leads
10 qualified no-website/social-only leads
3–5 preview sites
20 outreach attempts
1 serious reply or paid close
```

Stop/pivot criterion:

```text
No replies or serious-interest events after RunConfig.mvp_stop_threshold manually reviewed sends.
Default threshold: 20.
```

Output:

```text
mvp_results.md
objections_log.csv
monetization_events.json
monetization_segment_analytics.json
next_iteration_decision.md
```

---

## Current build priority

Do next:

```text
1. Implement Phase 2 fixture-based basic lead discovery.
2. Implement Phase 2.1 website filter with HTTP/redirect checks.
3. Implement Phase 5 template-rendered preview for one fixture business.
4. Implement Phase 6 fake-claim/string quality gate.
5. Run one local end-to-end fixture path before scraping real businesses.
```

Research still useful, but do not let research block the first fixture-based local slice.
