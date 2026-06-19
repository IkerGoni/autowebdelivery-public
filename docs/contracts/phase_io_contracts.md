# Phase I/O Contracts — Standalone and Full-Run Execution

> **SUPERSEDED:** For current phase-by-phase contracts reflecting actual code state, see `docs/contracts/PIPELINE_CONTRACTS.md`. This document retains legacy/aspiring contracts. Some block/reject conditions listed here are not yet implemented.

## Purpose

Each phase must be independently executable if given valid input artifacts. This enables isolated testing, debugging, benchmarking, and replacement of individual phases without breaking the whole pipeline.

Every phase must:

1. Validate its inputs before work.
2. Produce the standard phase result envelope.
3. Write outputs to deterministic paths.
4. Avoid side effects outside its output folder unless explicitly required.
5. Return `blocked` if required input is missing.

---

## Standard folder layout

```text
runs/{run_id}/
  config/
  01_input/
  02_discovery/
  02_1_website_filter/
  03_scoring/
  04_briefs/
  04_5_enrichment/
  05_sites/
  05_5_render_capture/
  06_quality/
  07_deployments/
  08_outreach/
  09_review/
  10_sent/
  11_results/
  logs/
```

Standalone tests may use:

```text
tests/fixtures/{phase_name}/input/
tests/fixtures/{phase_name}/expected/
runs/test_{phase_name}_{timestamp}/
```

---

## Universal standalone command contract

Each phase should eventually expose a CLI shape like this:

```bash
pnpm phase:03 --input path/to/input.json --output runs/test_phase_03
```

or:

```bash
python -m pipeline.phases.phase_03 --input path/to/input.json --output runs/test_phase_03
```

Required behavior:

```text
valid input -> writes outputs and result.json
invalid input -> writes result.json with status=blocked or failed
no input -> exits non-zero and writes/prints missing input contract
```

---

## Phase 00 — Setup

### Required input

```text
project root path
chosen stack or default stack
```

### Output

```text
config/run_config.example.json
runs/.gitkeep
generated_sites/.gitkeep
packages/ or src/ folder skeleton
```

### Block if

```text
cannot write to project root
required runtime missing
```

---

## Phase 01 — User Input

### Required input

```text
niche
area
country
language
max_raw_results
max_preview_sites
price_offer
```

### Output

```text
runs/{run_id}/config/input_config.json
runs/{run_id}/01_input/query_plan.json
runs/{run_id}/01_input/result.json
```

### Block if

```text
niche/area/country missing
max_preview_sites > max_raw_results
invalid rating/review thresholds
```

---

## Phase 02 — Basic Lead Discovery

### Required input

```text
RunConfig
QueryPlan
scraper/API credentials if required by selected source
```

### Output

```text
runs/{run_id}/02_discovery/leads_raw.json
runs/{run_id}/02_discovery/leads_normalized.json
runs/{run_id}/02_discovery/discovery_report.json
runs/{run_id}/02_discovery/result.json
```

### Block if

```text
query_plan missing
selected data source cannot return website field
scraper/API unavailable
```

### Standalone test input

A fixture may provide raw Google Maps-like records instead of calling a live scraper.

---

## Phase 02.1 — Early Website Filter

### Required input

```text
leads_normalized.json containing website_raw or website field
```

### Output

```text
runs/{run_id}/02_1_website_filter/leads_no_website.json
runs/{run_id}/02_1_website_filter/skipped_has_website.json
runs/{run_id}/02_1_website_filter/manual_review_website.json
runs/{run_id}/02_1_website_filter/website_filter_report.json
runs/{run_id}/02_1_website_filter/website_resolution_checks.json
runs/{run_id}/02_1_website_filter/result.json
```

### Block if

```text
website field missing from all records
records do not include business_name or record_id
```

### MVP behavior

```text
no_website -> keep
social_only -> keep
has_website -> skip
uncertain -> manual_review or skip, configurable
invalid_url -> manual_review or skip, configurable

Optional HTTP/redirect verification applies to uncertain, repairable invalid_url, and suspicious has_website candidates.
Suspicious candidates include parked domains, dead domains, shortlinks, bio-link pages, Google Maps URLs, social redirects, SSL errors, timeout, and domain/name mismatch.
Timeout or failed check -> uncertain, never no_website.
```

---

## Phase 03 — Lead Scoring

### Required input

```text
leads_no_website.json
RunConfig scoring thresholds from runs/{run_id}/config/input_config.json
```

Note: Phase 03 was reading run_config.json which caused a mismatch — now fixed to input_config.json.

### Output

```text
runs/{run_id}/03_scoring/leads_scored.json
runs/{run_id}/03_scoring/leads_scored.csv
runs/{run_id}/03_scoring/qualified_leads.json
runs/{run_id}/03_scoring/selected_for_preview.json
runs/{run_id}/03_scoring/result.json
```

### Block if

```text
website_status not present
non-no-website leads included without explicit override
rating/review_count unavailable for all records
```

### Mechanical scoring requirement

The phase must calculate numeric component scores and record rejection reasons. Do not output subjective rankings only.

---

## Phase 04 — Business Brief Generation

### Required input

```text
selected_for_preview.json
```

### Output

```text
runs/{run_id}/04_briefs/{business_slug}/FACTS.md
runs/{run_id}/04_briefs/{business_slug}/MISSING_DATA.md
runs/{run_id}/04_briefs/{business_slug}/BUSINESS_BRIEF.md
runs/{run_id}/04_briefs/{business_slug}/CONTENT_PLAN.md
runs/{run_id}/04_briefs/{business_slug}/DESIGN.md
runs/{run_id}/04_briefs/{business_slug}/GENERATION_PROMPT.md
runs/{run_id}/04_briefs/{business_slug}/recipient_channel.json
runs/{run_id}/04_briefs/{business_slug}/RECIPIENT_CHANNEL.md optional human summary
runs/{run_id}/04_briefs/briefs_index.json
runs/{run_id}/04_briefs/preview_ready_briefs.json
runs/{run_id}/04_briefs/blocked_no_recipient_channel.json
runs/{run_id}/04_briefs/result.json
```

### Block if

```text
business_name missing
category missing
address and maps_url both missing
```

### Safety rule

Only verified facts may be written as facts. Generic copy must be clearly generic and not imply verified business-specific claims.

### Recipient channel discovery

Phase 04 must classify available recipient channels without aggressive scraping. Allowed values:

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
email must be explicitly visible in source data or on a verified page
contact_form requires a real URL
social_only businesses may use the relevant social messaging channel
unknown does not fail Phase 04
unknown blocks automated outreach drafting unless manually overridden
```

`recipient_channel.json` must contain this structured object. `RECIPIENT_CHANNEL.md` is optional and must not be treated as the machine-readable artifact:

```json
{
  "business_slug": "",
  "recipient_channel": "email | contact_form | phone | facebook_message | instagram_dm | line | unknown",
  "recipient_value": "",
  "recipient_source": "google_maps_listing | social_profile | contact_page | manual | unknown",
  "recipient_confidence": "verified | inferred | unknown",
  "discovery_notes": ""
}
```

Expect `recipient_channel=unknown` on many records in typical runs. This is not a Phase 04 failure; it is a data availability limit.

Phase 04 must route briefs after recipient discovery:

```text
recipient_channel != unknown -> preview_ready_briefs.json
recipient_channel = unknown -> blocked_no_recipient_channel.json
manual override -> preview_ready_briefs.json with manual_override=true and manual_override_reason populated
```

`preview_ready_briefs.json` is the default input list for Phase 05. `blocked_no_recipient_channel.json` must not feed Phase 05 unless manually overridden.

---

## Phase 05 — Preview Site Generation

### Required input

```text
runs/{run_id}/04_briefs/preview_ready_briefs.json
BusinessBrief folder for each selected business
FACTS.md
CONTENT_PLAN.md
DESIGN.md
GENERATION_PROMPT.md
runs/{run_id}/04_5_enrichment/{business_slug}/visual_profile.json (if Phase 04.5 ran)
```

`blocked_no_recipient_channel.json` must not feed Phase 05 unless the record has `manual_override=true`.

### Output

```text
runs/{run_id}/05_sites/{business_slug}/site/
runs/{run_id}/05_sites/{business_slug}/build_status.json
runs/{run_id}/05_sites/{business_slug}/fact_usage_report.json
runs/{run_id}/05_sites/{business_slug}/result.json
```

### Block if

```text
FACTS.md missing
business_name missing
site template unavailable
build tool unavailable
```

### Failure if

```text
build fails
placeholder text remains
unsupported claims are inserted
```

---

## Phase 04.5 — Business Intelligence Enrichment (NEW)

### Purpose

Enriches Phase 04 business briefs with deeper public data without crossing into invention. Increases fact density for higher-quality preview sites.

### Required input

```text
runs/{run_id}/04_briefs/preview_ready_briefs.json
BusinessBrief folder for each business
FACTS.md
enrichment_sources/ (API keys, search configs)
```

### Output

```text
runs/{run_id}/04_5_enrichment/{business_slug}/enriched_facts.json
runs/{run_id}/04_5_enrichment/{business_slug}/enrichment_sources.json
runs/{run_id}/04_5_enrichment/{business_slug}/public_safe_fields.json
runs/{run_id}/04_5_enrichment/{business_slug}/internal_only_fields.json
runs/{run_id}/04_5_enrichment/{business_slug}/category_mapping.json
runs/{run_id}/04_5_enrichment/{business_slug}/design_preset_candidate.json
runs/{run_id}/04_5_enrichment/{business_slug}/visual_profile.json
runs/{run_id}/04_5_enrichment/{business_slug}/copy_inputs.json
runs/{run_id}/04_5_enrichment/{business_slug}/result.json
runs/{run_id}/04_5_enrichment/result.json
```

### Block if

```text
BusinessBrief missing
FACTS.md missing
enrichment API keys unavailable
```

### MVP behavior

```text
Best-effort enrichment applies when phase runs but public data is sparse.
If enrichment source config/API keys are unavailable -> block phase.
If enrichment contradicts core facts -> mark needs_review.
Else if missing_core_fields_count > 3 -> mark render_allowed_but_not_deploy_eligible.
Else -> render_allowed.

`design_preset_candidate.json` remains ranked recommendation artifact. `visual_profile.json` is required deterministic rendering bundle for Phase 05. It must be derived from Places/public enrichment and Phase 04 verified facts, not arbitrary scraping.

Mode note:
- preview demo mode may use `photo_policy=preview_demo_only` assets with required attribution
- production deploy mode must not use `preview_demo_only` assets
- production deploy mode may use `customer_owned_only` assets only after rights-cleared replacement exists
```

---

## Phase 05.5 — Browser Render Capture (NEW)

### Purpose

Captures real browser screenshots and DOM metrics for Phase 06 quality assessment. Replaces synthetic/fake PNG generation.

### Required input

```text
Generated site files from Phase 05
Browser automation tooling (Playwright or similar)
```

### Output

```text
runs/{run_id}/05_sites/{business_slug}/screenshot_desktop.png (real)
runs/{run_id}/05_sites/{business_slug}/screenshot_mobile.png (real)
runs/{run_id}/05_sites/{business_slug}/render_capture.json
runs/{run_id}/05_sites/{business_slug}/dom_metrics.json
runs/{run_id}/05_sites/{business_slug}/asset_load_log.json
runs/{run_id}/05_sites/{business_slug}/console_log.json
runs/{run_id}/05_sites/{business_slug}/layout_summary.json
runs/{run_id}/05_5_render_capture/result.json
```

Phase 05.5 intentionally writes its aggregate result envelope to `runs/{run_id}/05_5_render_capture/result.json` so it does not overwrite the Phase 05 aggregate or per-business result files under `05_sites`.

### Block if

```text
Site folder missing
Browser automation tooling unavailable
```

### Metrics measured

```text
screenshot dimensions, missing stylesheet detection, heading count, visible CTA count,
visible text density estimate, section count/order, duplicate text signals,
viewport overflow, broken image count, broken link count
```

---

## Phase 06 — Quality Gate

### MVP position

Phase 06 is a thin generated-site safety gate. It can be run as a standalone phase or folded into Phase 05/07 during MVP, but the checks must still exist.

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

Current implementation note: Phase 06 only enforces the screenshot file existence checks above. Phase 05.5 can also produce `render_capture.json`, `dom_metrics.json`, and related browser evidence, but Phase 06 does not yet consume those artifacts for scoring. Planned strict visual scoring should require Phase 05.5 provenance and use render/DOM metrics once Phase 06 integration is implemented.

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

### Reject if

```text
build failed
business facts mismatch
fake claims found
CTA broken
desktop or mobile screenshot missing
```

---

## Phase 07 — Deployment

### Required input

```text
generated site folder
site_quality_report.json or explicit override
```

### Output

```text
runs/{run_id}/07_deployments/deployments.json
runs/{run_id}/07_deployments/{business_slug}/deployment_record.json
runs/{run_id}/07_deployments/{business_slug}/deployment_logs.txt
runs/{run_id}/07_deployments/result.json
```

### Block if

```text
site_quality_report has deploy_eligible != true or status != approved, and no override exists
provider token missing when provider requires token
site folder missing
```

### Failure if

```text
deployment URL does not load
HTTP status is not 2xx/3xx
provider deploy command fails
```

---

## Phase 08 — Outreach Draft Generation

### Required input

```text
DeploymentRecord with live preview_url
BusinessBrief
LeadScore
RunConfig price_offer
```

### Output

```text
runs/{run_id}/08_outreach/outreach_drafts.json
runs/{run_id}/08_outreach/outreach_drafts.md
runs/{run_id}/08_outreach/result.json
```

### Block if

```text
preview_url missing
business_name missing
price_offer missing
no recipient channel exists
```

### Required wording constraints

```text
No claim that the business requested the site.
No claim of partnership.
No pressure language.
No fake urgency.
```

---

## Phase 09 — Manual Approval Pack

### Required input

```text
OutreachDraft
DeploymentRecord
LeadScore
BusinessBrief
```

### Output

```text
runs/{run_id}/09_review/review_table.csv
runs/{run_id}/09_review/review_pack.md
runs/{run_id}/09_review/screenshots_index.json
runs/{run_id}/09_review/approval_decisions.json
runs/{run_id}/09_review/result.json
```

`screenshots_index.json` schema:

```json
[
  {
    "business_slug": "",
    "screenshot_desktop_path": "",
    "screenshot_mobile_path": ""
  }
]
```

### Block if

```text
preview_url missing
outreach draft missing
review status schema missing
```

---

## Phase 10 — Manual Sending

### Required input

```text
approval_decisions.json with approval_status=send
outreach_drafts.json
```

### Output

```text
runs/{run_id}/10_sent/sent_log.csv
runs/{run_id}/10_sent/sent_log.json
runs/{run_id}/10_sent/result.json
```

### Block if

```text
no approved records
manual sent confirmation missing
```

### MVP rule

No automated sending. Manual send or manual draft creation only.

Allowed sent channels:

```text
email
contact_form
phone
facebook_message
instagram_dm
whatsapp
line
```

---

## Phase 11 — Monetization Tracking

### Required input

```text
sent_log.json
manual reply/sales updates
```

### Output

```text
runs/{run_id}/11_results/mvp_results.md
runs/{run_id}/11_results/objections_log.csv
runs/{run_id}/11_results/monetization_events.json
runs/{run_id}/11_results/monetization_segment_analytics.json
runs/{run_id}/11_results/next_iteration_decision.md
runs/{run_id}/11_results/result.json
```

### Segment analytics

`monetization_segment_analytics.json` aggregates sent volume and manual outcome events by:

```text
niche
area
recipient_channel
template_family
offer_type|offer_price|currency|pricing_market
```

Each segment contains:

```text
total_sent
reply_count
serious_interest_count
meeting_count
paid_conversion_count
objection_count
reply_rate
paid_conversion_rate
```

### Block if

```text
sent_log missing
no run_id
```

### Decision rule

Do not scale automation until the run shows measurable demand: replies, serious interest, or paid close. Default stop/pivot threshold: 20 manually sent outreaches with zero replies or serious-interest events, configurable by `RunConfig.mvp_stop_threshold`.
