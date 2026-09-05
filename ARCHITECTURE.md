# Architecture

> **Status: proof of concept.** This document describes the architecture as implemented for demonstration purposes; it is not the specification of a finished or commercial product.

This document is the technical deep dive for AutoWebDelivery. The [README](README.md) covers what the project is and how to run it; this page covers how it works: phases, generation paths, feature flags, safety mechanisms, artifacts, and invariants.

## Pipeline overview

```text
Phase 01 → 02 → 02.1 → 03 → 04 → 04.5 → 05 → 05.5 → 06 → 07 → 08 → 09 → 10 → 11
 Input   Discov Filter Score Brief Enrich Gen*  Render  QA  Deploy OutRch Appr  Send  Track
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
               modular templates    template mode     Stitch AI gen
               (4 design families)  (legacy path)     (no fallback)
```

Each phase reads the persisted artifacts of its predecessors from `runs/<run_id>/` and writes its own outputs there — there is no shared in-memory state between phases, which is what allows any phase to be tested or re-run in isolation (see [`docs/testing/standalone_phase_testing.md`](docs/testing/standalone_phase_testing.md)).

## Phase map

| Phase | Name | Output |
|-------|------|--------|
| 01 | User Input | Resolved `RunConfig` (niche, area, offer, language, thresholds) |
| 02 | Lead Discovery | Normalized leads from fixture / CSV / Overpass OSM / Google Maps |
| 02.1 | Website Filter | Candidates split by web-presence status |
| 03 | Lead Scoring | Deterministic BI scorecard per lead |
| 04 | Business Brief | Facts-only brief (pydantic-validated) |
| 04.5 | Enrichment | Maps data, social profiles, reviews, image fallback |
| 05 | Site Generation | Preview HTML via modular/template/Stitch path |
| 05.5 | Render Capture | Playwright DOM metrics as quality evidence |
| 06 | Quality Gate | Sanitizer + factual-claims checker + premium scorecard |
| 07 | Deployment | Local-first; optional Vercel/nginx providers |
| 08 | Outreach Generation | Personalized drafts from verified data |
| 09 | Approval Pack | Human-reviewable bundle per candidate |
| 10 | Manual Sending | Human-approved outbound only |
| 11 | Monetization Tracking | Replies, meetings, conversions, segment analytics |

## Generation paths

Phase 05 dispatches on `generation_mode` (see `packages/phases/phase_05_unified.py`):

| Mode | Behavior |
|------|----------|
| `modular` | Production-quality modular templates across 4 design families, with contact forms. Supports a production mode that removes watermark/test markers (`--production`). |
| `template` | Legacy basic template path. |
| `stitch` | AI-generated sites via the Google Stitch API. Exclusive path by policy — **no** template fallback (`--stitch-api-key` required). |
| `auto` | Attempts Stitch first; if no site was produced for every processed lead, falls back to the legacy `template` path. |

The modular path composes per-section templates defined under `packages/templates/modular/` (sections, composer, parser) driven by JSON config per design family.

### Design systems

| Family | Target verticals |
|--------|-----------------|
| `clinical-trust` | Healthcare, dental, professional services |
| `warm-editorial` | Restaurants, boutiques, artisan businesses |
| `industrial-reliable` | Auto services, construction, trades |
| `fresh-utility` | Modern general-purpose layouts |

Family definitions live in `packages/templates/modular/config/*.json` (and as `DesignSystemConfig`s in `packages/generation/stitch_premium_adapter.py`).

## Run artifact layout

Every run persists one directory tree under `runs/<run_id>/`, one folder per phase:

```text
runs/run_<timestamp>/
├── config/input_config.json            # resolved run configuration
├── 01_input/query_plan.json
├── 02_discovery/leads_normalized.json · discovery_report.json
├── 02_1_website_filter/leads_no_website.json · website_filter_report.json
├── 03_scoring/qualified_leads.json · selected_for_preview.json · leads_scored.csv
├── 04_briefs/<lead-slug>/BUSINESS_BRIEF.md · FACTS.md · DESIGN.md · ...
├── 04_5_enrichment/<lead-slug>/enriched_facts.json
├── 05_sites/<lead-slug>/index.html (+ screenshots)
├── 05_5_render_capture/result.json     # browser render evidence
├── 06_quality/<lead-slug>/site_quality_report.json
└── 07_deployments/ · 08_outreach/ · 09_review/ · 10_sent/ · 11_results/
```

Phase result manifests (`result.json`) record status, inputs used, outputs created, decisions, risks, and errors per phase — including non-fatal degradations such as render capture running without Playwright browsers installed.

## Run state DB (resume & idempotency)

Behind the `run_state_db` flag (default `False`; enable via `vnext_flags` or `RUN_STATE_DB=1`), the orchestrator mirrors run state into `<workspace>/runs/state.db` (stdlib SQLite, R1-02 store). Before each phase dispatch it consults `phase_executions`: a successful prior execution (status `done`, or `needs_review` for phases 02/02.1) is skipped and its recorded result reused; a failed/partial one has its run directory deleted (via `safe_path`) before a clean re-run. Each execution is written back with status, result envelope, `result.json` artifact path and duration; run start/finish are recorded on all exit paths, including unhandled exceptions. Selected leads are fingerprinted (sha256 of normalized name/address/place_id) into `lead_fingerprints` so repeat leads across runs are skipped at the orchestrator level (phase modules still read their own on-disk artifacts). With the flag off, no DB is created and the legacy path is untouched.

Failure reporting (R1-04/05/06): every phase failure is classified into a `FailureContext` (canonical `FailureClass` taxonomy) that is logged, stored in the run summary under `failures` and — when the flag is on — serialized into the recorded result payload, with a per-record (or per-phase) dead letter written to `dead_letters` (readable via `StateDB.list_dead_letters`). Each recorded payload also carries a `counts` block; `StateDB.phase_metrics(run_id)` returns one row per phase (status, duration, counts) and the run summary exposes it as `phase_metrics` when the flag is on.

## Factual safety model

| Layer | Mechanism |
|-------|-----------|
| Input | Briefs built from **verified facts only** (phase 04 contract) |
| Isolation | BI scores/risk flags translated to safe creative guidance before any prompt |
| Generation | Templates cannot emit claims outside the brief's fact set |
| Verification | HTML sanitizer scans output for unsupported/fake claims |
| Scoring | Premium scorecard (0–100) with critical structural thresholds |
| Evidence | Real browser render metrics (Playwright), not screenshots-only |
| Human gate | Phases 09–10: nothing leaves the machine without explicit approval |

Full specification: [`docs/gates/quality_gates.md`](docs/gates/quality_gates.md).

## vNext modules (feature-flagged)

14 next-generation modules ship disabled by default — legacy behavior is always preserved. Flags are defined in `_VNEXT_FLAG_DEFAULTS` in `packages/pipeline/vnext_integration.py` and set per-run under `vnext_flags` in the run config:

| Flag | Capability |
|------|-----------|
| `use_business_profile_contract` | Structured business identity model |
| `use_market_profile_contract` | Market/competitor landscape model |
| `use_brand_reconstruction_contract` | AI-driven brand voice extraction |
| `use_creative_spec` | Design intent specification |
| `use_stitch_compiler` | Google Stitch compilation path |
| `use_structured_evaluation_report` | Multi-dimensional quality reports |
| `use_sales_package_contract` | Client-ready sales artifacts |
| `use_learning_record_contract` | Outcome feedback into scoring |
| `use_competitor_intelligence` | Benchmark matching & gap analysis |
| `use_patch_phase` | Deterministic HTML fix planner |
| `use_overpass_enrichment` | OSM context enrichment |
| `use_gmaps_enrichment` | Google Places enrichment |
| `use_social_enrichment` | Public FB/IG profile data |
| `use_image_fallback` | Visual fallback when photos are missing |

The corresponding data contracts (business profile, market profile, creative spec, evaluation report, learning record, patch plan, competitor profile, brand profile) are specified in [`docs/contracts/`](docs/contracts/).

## Module layout

```text
packages/
├── cli/              # CLI entry points (arg parsing, run bootstrap)
├── config/           # Runtime configuration loading (incl. niche_scores.json)
├── creative/         # Creative specification & brand reconstruction
├── deployers/        # local_only / vercel / nginx_local
├── discovery/        # fixture, CSV, Google Maps, Overpass fetchers
├── enrichment/       # Maps, social, reviews, image fallback
├── evaluation/       # Structured quality evaluation
├── generation/       # Modular templates + Stitch adapter
├── intelligence/     # Competitor intelligence & benchmarking
├── learning/         # Outcome feedback loop
├── patching/         # Deterministic HTML fix planner
├── phases/           # Phase implementations (01–11)
├── pipeline/         # Orchestrator, contracts, feature flags (run_pipeline.py, vnext_integration.py)
├── sales/            # Sales package generation
├── shared/           # Provenance & shared utilities
└── templates/        # Jinja2 templates (modular sections, outreach, stitch prompts)

tests/                # unit · integration · e2e · golden fixtures
docs/                 # architecture · contracts · gates · testing
scripts/              # fixture regeneration & maintenance tooling
config/               # run_config.example.json — copy & adjust per run
```

## Invariants & constraints

These are load-bearing constraints — changes that violate them require a full test-suite pass and explicit review (see [`AGENTS.md`](AGENTS.md)):

1. **Feature flags are never removed** — they protect backward compatibility of the legacy pipeline.
2. **Internal BI data never leaks into public HTML** — scores and risk flags must pass through safe-creative-guidance translation before reaching any generation prompt.
3. **No outbound communication without human approval** — phases 09–10 exist precisely to keep sending manual.
4. **Generated content stays inside the brief's fact set** — sanitizer and factual-claims checker reject fabricated services, pricing, staff, certifications, guarantees, awards, or testimonials.
5. **Phases communicate only through persisted artifacts** — enables isolated testing, re-runs, and auditability of every decision.

## Trade-offs & known limitations

- The Stitch path depends on an external API (key required); deterministic paths exist so the pipeline is fully usable offline.
- Browser render capture requires Playwright browser binaries; without them the phase records a non-blocking degradation instead of failing the run.
- The bundled demo fixture is static synthetic data (always dental-clinic records), which keeps the E2E path hermetic but means fixture runs do not exercise real discovery sources.

The **active hardening program** for these trade-offs (idempotency, persistence, SSRF, secret handling, rate-limit consolidation, per-threshold configuration) lives in [`docs/plans/RECOVERY_PLAN.md`](docs/plans/RECOVERY_PLAN.md) with its live findings tracker. Earlier analysis is retained as a historical audit in [`docs/architecture/ARCHITECTURE_REFACTOR_PROPOSAL.md`](docs/architecture/ARCHITECTURE_REFACTOR_PROPOSAL.md) (marked superseded).
