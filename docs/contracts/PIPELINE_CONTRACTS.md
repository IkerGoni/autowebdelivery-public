# Pipeline Contracts — Phase by Phase (Living Document)

**Status:** reflects actual code state as of 2026-05-14
**Branch:** main

---

## Pipeline Map

```
01  input           → config/input_config.json, 01_input/query_plan.json
02  discovery       → 02_discovery/leads_raw.json, leads_normalized.json
02.1 website filter → 02_1_website_filter/leads_no_website.json, skipped_has_website.json
03  scoring         → 03_scoring/leads_scored.json, selected_for_preview.json
04  business brief  → 04_briefs/{slug}/FACTS.md, BUSINESS_BRIEF.md, CONTENT_PLAN.md, DESIGN.md
04.5 enrichment     → 04_5_enrichment/{slug}/enriched_facts.json, visual_profile.json, copy_inputs.json
05  preview site    → 05_sites/{slug}/site/index.html, styles.css, build_status.json
05.5 render capture → 05_sites/{slug}/screenshot_desktop.png, screenshot_mobile.png, render_capture.json, dom_metrics.json; 05_5_render_capture/result.json
06  quality gate    → 06_quality/{slug}/site_quality_report.json, credibility_score.json
07  deployment      → 07_deployments/{slug}/deployment_record.json
08  outreach        → 08_outreach/outreach_drafts.json
09  approval pack   → 09_review/review_table.csv, review_pack.md, approval_decisions.json
10  manual sending   → 10_sent/send_queue.json, sent_log.json
11  monetization    → 11_results/monetization_summary.json, objections_log.json
```

---

## Phase 01 — User Input / Run Config

**File:** `packages/phases/phase_01_user_input.py`
**Entry:** `run(run_id, workspace, input_config=None) -> dict`

### Inputs
| Source | Required | Description |
|--------|----------|-------------|
| `input_config` dict or fixture JSON | Yes | User-supplied config. If None, reads from `tests/fixtures/phase_01_user_input/input/valid_config_minimal.json` |

### Required config fields
```
niche, area, country, max_raw_results, max_preview_sites, price_offer
```

### Validation rules
- `max_preview_sites` must not exceed `max_raw_results`
- `minimum_rating` must be 0–5 if present
- `minimum_reviews` must be >= 0 if present

### Outputs
| Path | Artifact |
|------|----------|
| `runs/{run_id}/config/input_config.json` | RunConfig serialized |
| `runs/{run_id}/01_input/query_plan.json` | QueryPlan with 1 query: `"{niche} {area}"` |
| `runs/{run_id}/01_input/result.json` | ResultEnvelope |

### Block conditions
- Missing required config fields
- Fixture file not found when `input_config` is None

### RunConfig fields (actual code)
```
run_id, niche, area, country, language="English"
max_raw_results=100, max_preview_sites=5
minimum_rating=4.3, minimum_reviews=40
style_preset="clinical_trust"
deploy_mode="production_deploy_mode"
price_offer, offer_type="setup_only", offer_price="", currency=""
pricing_market="", pricing_notes=""
mvp_stop_threshold=20
created_at (auto)
```

---

## Phase 02 — Basic Lead Discovery

**File:** `packages/phases/phase_02_basic_lead_discovery.py`
**Entry:** `run(run_id, workspace) -> dict`

### Inputs
| Source | Required | Description |
|--------|----------|-------------|
| `runs/{run_id}/01_input/query_plan.json` | Yes | Query plan from Phase 01 |
| `tests/fixtures/phase_02_basic_lead_discovery/input/raw_places_with_websites.json` | Fixture mode | Raw Google Maps-like records |

### Outputs
| Path | Artifact |
|------|----------|
| `runs/{run_id}/02_discovery/leads_raw.json` | RawPlace records |
| `runs/{run_id}/02_discovery/leads_normalized.json` | NormalizedPlace records with slugs |
| `runs/{run_id}/02_discovery/discovery_report.json` | Summary stats |
| `runs/{run_id}/02_discovery/result.json` | ResultEnvelope |

### business_slug generation rules
```
lowercase → transliterate → strip non-ASCII
spaces/symbols → hyphen → collapse repeats → trim
max 50 chars + last 4-6 of record_id
```

### Block conditions
- `query_plan.json` missing
- Fixture file not found

---

## Phase 02.1 — Website Filter

**File:** `packages/phases/phase_02_1_website_filter.py`
**Entry:** `run(run_id, workspace) -> dict`

### Inputs
| Source | Required |
|--------|----------|
| `runs/{run_id}/02_discovery/leads_normalized.json` | Yes |

### Outputs
| Path | Artifact |
|------|----------|
| `runs/{run_id}/02_1_website_filter/leads_no_website.json` | Kept leads |
| `runs/{run_id}/02_1_website_filter/skipped_has_website.json` | Skipped leads |
| `runs/{run_id}/02_1_website_filter/manual_review_website.json` | Uncertain leads |
| `runs/{run_id}/02_1_website_filter/website_filter_report.json` | Summary |
| `runs/{run_id}/02_1_website_filter/website_resolution_checks.json` | Per-record HTTP checks |
| `runs/{run_id}/02_1_website_filter/result.json` | ResultEnvelope |

### Classification decision table
| website_status | decision |
|----------------|----------|
| no_website | keep |
| social_only | keep |
| has_website | skip |
| uncertain | manual_review |
| invalid_url | manual_review |

### HTTP verification
- `http_checked=False` when not run
- Failed checks → `uncertain`, never `no_website`
- Suspicious (parked, dead, social-redirect, shortlink, SSL error, timeout) → `uncertain`

---

## Phase 03 — Lead Scoring

**File:** `packages/phases/phase_03_lead_scoring.py`
**Entry:** `run(run_id, workspace, config=None) -> dict`

### Inputs
| Source | Required |
|--------|----------|
| `runs/{run_id}/02_1_website_filter/leads_no_website.json` | Yes |
| `runs/{run_id}/config/input_config.json` | Yes (scoring thresholds) |

### Outputs
| Path | Artifact |
|------|----------|
| `runs/{run_id}/03_scoring/leads_scored.json` | All scored leads |
| `runs/{run_id}/03_scoring/leads_scored.csv` | CSV export |
| `runs/{run_id}/03_scoring/qualified_leads.json` | Pass threshold |
| `runs/{run_id}/03_scoring/selected_for_preview.json` | Top N by score |
| `runs/{run_id}/03_scoring/result.json` | ResultEnvelope |

### Scoring model (actual code)
```
rating_score:     0-100 (linear, threshold = minimum_rating)
review_score:     0-100 (logarithmic, threshold = minimum_reviews)
contactability:   0-100 (phone + maps_url presence)
lead_score = rating_score * 0.4 + review_score * 0.3 + contactability * 0.3
```

### Qualification rules (actual code)
```
rating >= threshold (default 4.3)
review_count >= threshold (default 40)
website_status in [no_website, social_only]
```

### Known gaps (vs HANDOFF plan)
- No `category_value_score`, `freshness_score`, `confidence_score`, `risk_penalty`
- Chain detection uses simple keyword match (no word boundary)
- `website_status` defaults to `no_website` if missing (permissive)
- Config path bug fixed: reads `input_config.json` (not `run_config.json`)

---

## Phase 04 — Business Brief Generation

**File:** `packages/phases/phase_04_business_brief.py`
**Entry:** `run_phase_04(run_id, workspace) -> dict`

### Inputs
| Source | Required |
|--------|----------|
| `runs/{run_id}/03_scoring/selected_for_preview.json` | Yes |

### Outputs (per business)
| Path | Artifact |
|------|----------|
| `04_briefs/{slug}/FACTS.md` | Verified facts |
| `04_briefs/{slug}/MISSING_DATA.md` | Missing fields log |
| `04_briefs/{slug}/BUSINESS_BRIEF.md` | Business summary |
| `04_briefs/{slug}/CONTENT_PLAN.md` | Per-section content plan |
| `04_briefs/{slug}/DESIGN.md` | Design preset selection |
| `04_briefs/{slug}/GENERATION_PROMPT.md` | Generation instructions |
| `04_briefs/{slug}/recipient_channel.json` | Channel classification |

### Outputs (aggregate)
| Path | Artifact |
|------|----------|
| `04_briefs/briefs_index.json` | All briefs index |
| `04_briefs/preview_ready_briefs.json` | Briefs with known channel |
| `04_briefs/blocked_no_recipient_channel.json` | Briefs with unknown channel |
| `04_briefs/result.json` | ResultEnvelope |

### Recipient channel values
```
email, contact_form, phone, facebook_message, instagram_dm, line, unknown
```

### Routing logic
```
channel != unknown  → preview_ready_briefs.json
channel = unknown   → blocked_no_recipient_channel.json
manual override     → preview_ready_briefs.json (manual_override=true)
```

### Block conditions
- `selected_for_preview.json` missing
- `business_name` or `category` missing from record

---

## Phase 04.5 — Business Intelligence Enrichment

**File:** `packages/phases/phase_04_5_enrichment.py`
**Entry:** `run(run_id, workspace) -> dict`

### Inputs
| Source | Required |
|--------|----------|
| `runs/{run_id}/04_briefs/preview_ready_briefs.json` | Yes |
| `runs/{run_id}/config/input_config.json` | Yes |
| Per-business brief folder | Yes |

### Outputs (per business)
| Path | Artifact |
|------|----------|
| `04_5_enrichment/{slug}/enriched_facts.json` | Enriched data |
| `04_5_enrichment/{slug}/enrichment_sources.json` | Source tracking |
| `04_5_enrichment/{slug}/public_safe_fields.json` | Public-safe subset |
| `04_5_enrichment/{slug}/internal_only_fields.json` | Internal-only subset |
| `04_5_enrichment/{slug}/category_mapping.json` | Niche → preset mapping |
| `04_5_enrichment/{slug}/design_preset_candidate.json` | Ranked preset candidates |
| `04_5_enrichment/{slug}/visual_profile.json` | Rendering bundle for Phase 05 |
| `04_5_enrichment/{slug}/copy_inputs.json` | Copy generation inputs |
| `04_5_enrichment/{slug}/result.json` | Per-business result |

### Outputs (aggregate)
| Path | Artifact |
|------|----------|
| `04_5_enrichment/result.json` | ResultEnvelope |

### Enrichment gate
```
contradicts core facts → needs_review
missing_core_fields > 3 → render_allowed_but_not_deploy_eligible
otherwise → render_allowed
```

### Design presets (4 families)
| Preset | Niche mapping |
|--------|---------------|
| clinical_trust | dental, medical, wellness |
| warm_editorial | salon, beauty, hospitality |
| industrial_reliable | mechanic, repair, trades |
| fresh_utility | cleaning, home services, eco |

---

## Phase 05 — Preview Site Generation

**File:** `packages/phases/phase_05_preview_site_generation.py`
**Entry:** `run_phase_05(run_id, workspace) -> dict`

### Inputs
| Source | Required |
|--------|----------|
| `runs/{run_id}/04_briefs/preview_ready_briefs.json` | Yes |
| Per-business brief folder (FACTS.md, CONTENT_PLAN.md, DESIGN.md) | Yes |
| `runs/{run_id}/04_5_enrichment/{slug}/visual_profile.json` | If Phase 04.5 ran |

### Outputs (per business)
| Path | Artifact |
|------|----------|
| `05_sites/{slug}/site/index.html` | Generated HTML |
| `05_sites/{slug}/site/styles.css` | Generated CSS |
| `05_sites/{slug}/build_status.json` | Build metadata |
| `05_sites/{slug}/fact_usage_report.json` | Fact utilization |
| `05_sites/{slug}/result.json` | Per-business result |

### Outputs (aggregate)
| Path | Artifact |
|------|----------|
| `05_sites/result.json` | ResultEnvelope |

### Template system
- Base: `packages/templates/preview_site/base.html`
- Styles: `packages/templates/preview_site/styles.css`
- Modular sections: `templates/modular/sections/{family}/{section}.html`
- Supports flat legacy (`_mobile` suffix) and v2 (`mobile_v2/`, `desktop_v2/` subdirs)

### Block conditions
- FACTS.md missing
- business_name missing
- Template files unavailable

---

## Phase 05.5 — Browser Render Capture

**File:** `packages/phases/phase_05_5_browser_render_capture.py`
**Entry:** `run_phase_05_5(run_id, workspace, capture_backend=None) -> dict`

### Inputs
| Source | Required |
|--------|----------|
| `runs/{run_id}/05_sites/{slug}/site/index.html` | Yes |
| Browser automation tooling / renderer implementation | Yes |

### Outputs (per business, written under Phase 05 site folder)
| Path | Artifact |
|------|----------|
| `05_sites/{slug}/screenshot_desktop.png` | Desktop browser screenshot |
| `05_sites/{slug}/screenshot_mobile.png` | Mobile browser screenshot |
| `05_sites/{slug}/render_capture.json` | Capture metadata and artifact references |
| `05_sites/{slug}/dom_metrics.json` | DOM and page structure metrics |
| `05_sites/{slug}/asset_load_log.json` | Stylesheet/image/link loading summary |
| `05_sites/{slug}/console_log.json` | Browser console messages/errors |
| `05_sites/{slug}/layout_summary.json` | Viewport/layout summary |

### Outputs (aggregate)
| Path | Artifact |
|------|----------|
| `05_5_render_capture/result.json` | ResultEnvelope |

Phase 05.5 intentionally writes its aggregate result envelope to `runs/{run_id}/05_5_render_capture/result.json` so it does not overwrite Phase 05's aggregate `05_sites/result.json` or per-business `05_sites/{slug}/result.json`.

### Block / failure conditions
- `runs/{run_id}/05_sites` missing
- Business site folder or `site/index.html` missing
- Unsafe run/output path resolution
- Browser capture unavailable or fails for a site

### Metrics captured
- Screenshot dimensions for desktop and mobile viewports
- Missing stylesheet signal
- Heading count, visible CTA count, section count, section order
- Text density estimates and duplicate text signals
- Horizontal/viewport overflow signals
- Broken image and broken link counts
- Asset load and console error summaries

---

## Phase 06 — Quality Gate

**File:** `packages/phases/phase_06_quality_gate.py`
**Entry:** `run_phase_06(run_id, workspace) -> dict`

### Inputs
| Source | Required |
|--------|----------|
| `runs/{run_id}/05_sites/{slug}/site/` | Yes (full site folder) |
| `runs/{run_id}/04_briefs/{slug}/FACTS.md` | Yes |
| `runs/{run_id}/05_sites/{slug}/build_status.json` | Yes |
| `runs/{run_id}/05_sites/{slug}/fact_usage_report.json` | Yes |
| `runs/{run_id}/05_sites/{slug}/screenshot_desktop.png` | Yes (existence check only) |
| `runs/{run_id}/05_sites/{slug}/screenshot_mobile.png` | Yes (missing mobile screenshot hard rejects) |

Phase 06 currently reads artifacts from `05_sites/{slug}/`. If Phase 05.5 has run, the screenshot files at that location are real browser captures. If Phase 05.5 has not run, legacy Phase 05 screenshot artifacts can still satisfy the current existence checks. Phase 06 does not yet read `render_capture.json`, `dom_metrics.json`, or `05_5_render_capture/result.json`.

### Outputs (per business)
| Path | Artifact |
|------|----------|
| `06_quality/{slug}/site_quality_report.json` | Full quality report |
| `06_quality/{slug}/credibility_score.json` | Score breakdown |

### Outputs (aggregate)
| Path | Artifact |
|------|----------|
| `06_quality/result.json` | ResultEnvelope |

### Hard reject checks
- Placeholder text (Lorem ipsum, TODO, TBD, etc.)
- Unresolved template slots
- Forbidden claims (award-winning, #1, licensed, certified, etc.)
- Missing required sections

### Known gaps (vs HANDOFF plan)
- Phase 05.5 exists and captures real screenshots/DOM metrics, but Phase 06 does not yet consume `render_capture.json` or `dom_metrics.json`
- No multi-axis visual/copy scoring from browser render metrics
- No duplicate-text detection across sections
- No body word count floor check
- Scoring is pass/fail, not 4-axis credibility score

---

## Phase 07 — Deployment

**File:** `packages/phases/phase_07_deployment.py`
**Entry:** `run_phase_07(run_id, workspace) -> dict`

### Inputs
| Source | Required |
|--------|----------|
| `runs/{run_id}/05_sites/{slug}/` | Yes |
| `runs/{run_id}/06_quality/{slug}/site_quality_report.json` | Yes |

### Outputs (per business)
| Path | Artifact |
|------|----------|
| `07_deployments/{slug}/deployment_record.json` | Deployment metadata |
| `07_deployments/{slug}/deployment_logs.txt` | Deploy log |

### Outputs (aggregate)
| Path | Artifact |
|------|----------|
| `07_deployments/deployments.json` | All deployments index |
| `07_deployments/result.json` | ResultEnvelope |

### Deployer
- `packages/deployers/local_only.py` — copies site to local deploy dir
- Takedown tracking: 30-day default, configurable
- Only deploys sites with `status=approved_for_deploy` in quality report

---

## Phase 08 — Outreach Generation

**File:** `packages/phases/phase_08_outreach_generation.py`
**Entry:** `run(run_id, workspace) -> dict`

### Inputs
| Source | Required |
|--------|----------|
| `runs/{run_id}/04_briefs/{slug}/FACTS.md` | Yes |
| `runs/{run_id}/04_briefs/{slug}/recipient_channel.json` | Yes |
| `runs/{run_id}/07_deployments/{slug}/deployment_record.json` | For preview_url |
| `runs/{run_id}/config/input_config.json` | For price_offer |

### Templates
| File | Channel |
|------|---------|
| `packages/templates/outreach/email.j2` | Email |
| `packages/templates/outreach/social_dm.j2 | Social DM |

### Outputs
| Path | Artifact |
|------|----------|
| `08_outreach/outreach_drafts.json` | All drafts |
| `08_outreach/result.json` | ResultEnvelope |

### Block conditions
- `recipient_channel = unknown` → draft blocked
- `draft_status != ready_for_review` → blocked
- Missing preview_url → blocked

---

## Phase 09 — Manual Approval Pack

**File:** `packages/phases/phase_09_manual_approval_pack.py`
**Entry:** `run_phase_09(run_id, workspace) -> dict`

### Inputs
| Source | Required |
|--------|----------|
| `runs/{run_id}/05_sites/{slug}/` | Screenshots, build_status |
| `runs/{run_id}/06_quality/{slug}/site_quality_report.json` | Quality data |
| `runs/{run_id}/07_deployments/{slug}/deployment_record.json` | Deploy data |
| `runs/{run_id}/08_outreach/outreach_drafts.json` | Drafts |
| `runs/{run_id}/03_scoring/leads_scored.json` | Lead scores |
| `runs/{run_id}/04_briefs/{slug}/recipient_channel.json` | Channel info |

### Outputs
| Path | Artifact |
|------|----------|
| `09_review/review_table.csv` | Operator review table |
| `09_review/review_pack.md` | Markdown summary |
| `09_review/screenshots_index.json` | Screenshot paths |
| `09_review/approval_decisions.json` | Approval state |
| `09_review/result.json` | ResultEnvelope |

---

## Phase 10 — Manual Sending

**File:** `packages/phases/phase_10_manual_sending.py`
**Entry:** `run_phase_10(run_id, workspace) -> dict`

### Inputs
| Source | Required |
|--------|----------|
| `runs/{run_id}/09_review/approval_decisions.json` | Approved sends |
| `runs/{run_id}/08_outreach/outreach_drafts.json` | Drafts |

### Outputs
| Path | Artifact |
|------|----------|
| `10_sent/send_queue.json` | Queue with mailto URLs |
| `10_sent/sent_log.json` | Manual confirmation log |
| `10_sent/result.json` | ResultEnvelope |

### Allowed sent channels
```
email, contact_form, phone, facebook_message, instagram_dm, whatsapp, line
```

### Block conditions
- `approval_status != send`
- `recipient_channel = unknown`
- Missing preview_url
- `draft_status != ready_for_review`

---

## Phase 11 — Monetization Tracking

**File:** `packages/phases/phase_11_monetization_tracking.py`
**Entry:** `run_phase_11(run_id, workspace) -> dict`

### Inputs
| Source | Required |
|--------|----------|
| `runs/{run_id}/10_sent/sent_log.json` | Yes |
| `runs/{run_id}/config/input_config.json` | For mvp_stop_threshold |

### Outputs
| Path | Artifact |
|------|----------|
| `11_results/mvp_results.md` | Markdown aggregate stats and decision summary |
| `11_results/objections_log.csv` | Objection events for manual review |
| `11_results/monetization_events.json` | Normalized manual monetization events |
| `11_results/monetization_segment_analytics.json` | Aggregates by niche, area, recipient channel, template family, and offer |
| `11_results/next_iteration_decision.md` | Human-readable next iteration recommendation |
| `11_results/result.json` | ResultEnvelope |

### Decision logic
```
zero replies after threshold → stop_or_pivot
any reply → continue_testing
```

---

## Data Flow Summary

```
Phase 01 ──→ config/input_config.json ──────────────────────────────→ Phase 03, 08, 11
  │
  └─→ 01_input/query_plan.json ────────────────────────────────────→ Phase 02

Phase 02 ──→ 02_discovery/leads_normalized.json ───────────────────→ Phase 02.1

Phase 02.1 → 02_1_website_filter/leads_no_website.json ────────────→ Phase 03

Phase 03 ──→ 03_scoring/selected_for_preview.json ─────────────────→ Phase 04, 09

Phase 04 ──→ 04_briefs/preview_ready_briefs.json ──────────────────→ Phase 04.5, 05
  │
  └─→ 04_briefs/{slug}/ ──────────────────────────────────────────→ Phase 05, 06, 08, 09

Phase 04.5 → 04_5_enrichment/{slug}/visual_profile.json ──────────→ Phase 05

Phase 05 ──→ 05_sites/{slug}/ ─────────────────────────────────────→ Phase 05.5, 06, 07, 09

Phase 05.5 → 05_sites/{slug}/screenshot_*.png ───────────────────→ Phase 06, 09
          ├→ 05_sites/{slug}/render_capture.json, dom_metrics.json,
          │  asset_load_log.json, console_log.json,
          │  layout_summary.json ─────────────────────────────────→ render audit / future Phase 06 scoring
          └→ 05_5_render_capture/result.json ─────────────────────→ run audit/status

Phase 06 ──→ 06_quality/{slug}/site_quality_report.json ──────────→ Phase 07, 09

Phase 07 ──→ 07_deployments/{slug}/deployment_record.json ────────→ Phase 08, 09

Phase 08 ──→ 08_outreach/outreach_drafts.json ─────────────────────→ Phase 09, 10

Phase 09 ──→ 09_review/approval_decisions.json ────────────────────→ Phase 10

Phase 10 ──→ 10_sent/sent_log.json ────────────────────────────────→ Phase 11
```

---

## Known Gaps vs HANDOFF Plan

| Gap | Priority | Impact |
|-----|----------|--------|
| Phase 03 scoring model too simple (no category_value, freshness, risk_penalty) | P1 | Lead quality |
| Phase 03 chain detection no word boundary | P1 | False rejects |
| Phase 03 website_status default too permissive | P1 | Bad leads pass |
| Phase 06 no 4-axis credibility scoring | P1 | Quality bar too low |
| Phase 06 does not consume Phase 05.5 render/DOM metrics for visual and copy scoring | P1 | Browser evidence is captured but not fully scored |
| Phase 06 no duplicate-text detection | P2 | Copy quality |
| Phase 06 no body word count floor | P2 | Thin pages pass |
| Phase 02.1 no HTTP verification in MVP | P2 | Website misclassification |
| Phase 04 CONTENT_PLAN still uses old format (not content_plan_v2) | P2 | Content quality |
| Phase 04 DESIGN.md still echoes config (not strategic) | P2 | Design quality |
| Phase 05 _build_generic_copy still active (not slot-based) | P1 | Copy quality |
| Phase 06 can still pass legacy Phase 05 screenshot artifacts by existence check if Phase 05.5 is not run | P1 | Screenshot provenance is not enforced by Phase 06 |
| Phase 01 config missing area_strategy, niche_cluster fields | P2 | Scouting |
| No iteration ledger | P3 | Ops |
| No approval checklist doc | P3 | Ops |

---

## Modular Template System (Runtime)

**Path:** `templates/modular/`

### Files
| File | Role |
|------|------|
| `parser.py` | TemplateParser — extracts sections from Stitch HTML by comment markers |
| `composer.py` | TemplateComposer — reassembles with mustache placeholder injection |
| `models.py` | BusinessData, ServiceItem, HoursSchedule dataclasses |
| `cli.py` | CLI: compose, parse, list, sample-data commands |

### Storage conventions
- Flat legacy: `{section}.html` + `{section}_mobile.html`
- V2: `desktop_v2/{section}.html` + `mobile_v2/{section}.html`
- `_load_section` in composer handles both

### 4 families x 7 sections x up to 4 variants
- clinical-trust, warm-editorial, industrial-reliable, fresh-utility
- Sections: header, hero, services, trust, location, cta, footer
- Variants: desktop, mobile, desktop_v2, mobile_v2

### Config per family
- `templates/modular/config/{family}.json` — palette, fonts, tone axes
