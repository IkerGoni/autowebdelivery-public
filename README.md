# AutoWebDelivery

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/IkerGoni/autowebdelivery-public/actions/workflows/ci.yml/badge.svg)](https://github.com/IkerGoni/autowebdelivery-public/actions/workflows/ci.yml)

**A proof-of-concept pipeline that finds local businesses with weak web presence, scores them by opportunity value, and generates factually-safe preview websites — with human approval gating every outbound action.**

```text
discovery ──▶ scoring ──▶ brief ──▶ generation ──▶ QA gate ──▶ deploy ──▶ outreach ──▶ tracking
   01/02       03          04       05 (4 modes)     06         07        08–10        11
```

Python 3.10+ · Pydantic v2 · httpx · Jinja2 · Playwright · **1,307 tests passing** · MIT

> **⚠️ Status: proof of concept — not a finished or commercial product.** AutoWebDelivery demonstrates an end-to-end architecture and is under active development. It runs on synthetic demo data by default, external integrations (Stitch AI, Google Maps, Vercel) are not production-hardened, and it has not been security-reviewed, load-tested, or operated long-term. Known limitations and trade-offs: [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Why this project exists

Local businesses (restaurants, clinics, gyms) lose customers to competitors that simply look better online. AutoWebDelivery operationalizes the full sales motion for that gap:

1. **Discover** businesses via fixtures, CSV, OpenStreetMap/Overpass, or Google Maps.
2. **Score** them deterministically on opportunity value — then translate internal scores into *safe creative guidance* before anything reaches a generation prompt.
3. **Generate** a custom preview site through four interchangeable generation modes (modular templates, legacy template, AI-generated via Google Stitch, or auto).
4. **Gate** every artifact: HTML sanitizer, factual-claims checker, premium visual scorecard, real browser render evidence.
5. **Deploy locally first**, draft personalized outreach, and require **explicit human approval** before any outbound communication.

The design constraint that shapes everything: **the pipeline may never invent a business fact.** No fabricated services, pricing, staff, certifications, awards, or testimonials — enforced in code, not by convention.

## What this project demonstrates

Every claim below maps to code and tests in this repository:

- **End-to-end automation** — an E2E test drives all 11 phases against synthetic data (`tests/e2e/test_full_pipeline_01_to_11.py`)
- **Multi-source research & enrichment** — five discovery sources plus Maps/social/review/image enrichment modules
- **Deterministic + probabilistic system design** — LLM generation where reasoning matters; deterministic scoring, validation, contracts, and provenance everywhere correctness matters
- **Structured data contracts** — every phase exchanges pydantic-validated artifacts ([`docs/contracts/`](docs/contracts/))
- **Browser-level validation** — generated HTML is rendered in a real browser (Playwright) and evaluated from actual DOM metrics
- **Automated quality gates** — sanitizer, factual-claims checker, and premium scorecard decide approve/edit/reject per site
- **Factual safety controls** — output is scanned for fabricated services, pricing, staff, awards, or testimonials before approval
- **Human-in-the-loop workflow** — outreach is drafted automatically but nothing is sent without explicit approval (phases 09–10)
- **Feature-flagged architecture evolution** — 14 next-generation modules ship disabled by default; legacy behavior is always preserved
- **Regression protection** — unit + integration tests, golden-fixture regression suites, and a regenerable fixture toolchain (`scripts/regenerate_fixtures.py`)

## Demo

<!-- TODO: add a project demo screenshot/GIF — an ideal demo is a terminal recording of a fixture run next to the generated preview site under runs/<run_id>/05_sites/ -->

## Quickstart

```bash
git clone https://github.com/IkerGoni/autowebdelivery-public.git
cd autowebdelivery-public

python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,browser]"       # installs pytest/ruff + Playwright
playwright install chromium           # enables Phase 05.5 browser-render evidence

# Reproducible alternative (uses uv.lock, no editable install needed):
uv sync --extra dev,browser && uv run playwright install chromium

# Run your first pipeline (~seconds, zero API keys needed):
python -m packages.cli.run \
    --niche "restaurant" --area "Dallas, TX" \
    --generation-mode modular --deploy-provider local_only \
    --max-sites 2 --dry-run
```

> **About the bundled demo fixture:** the default `--discovery-source fixture` loads synthetic businesses from `tests/fixtures/phase_02_basic_lead_discovery/input/raw_places_with_websites.json`. Those records are **always dentists, regardless of what you pass in `--niche`** — the niche changes the run configuration, not the fixture contents. Use `csv_file`, `overpass`, `maps_api`, or `maps_search` for real discovery.

> Without Playwright browsers installed, runs still complete end-to-end; Phase 05.5 then records no render evidence (non-blocking).

## What a run produces

Artifacts land under `runs/<run_id>/` — one folder per phase, one subfolder per lead:

```text
runs/run_<timestamp>/
├── config/input_config.json            # resolved run configuration
├── 01_input/query_plan.json
├── 02_discovery/leads_normalized.json
├── 02_1_website_filter/leads_no_website.json
├── 03_scoring/qualified_leads.json · selected_for_preview.json
├── 04_briefs/<lead-slug>/BUSINESS_BRIEF.md
├── 04_5_enrichment/<lead-slug>/enriched_facts.json
├── 05_sites/<lead-slug>/index.html     # generated preview site (+ screenshots)
├── 05_5_render_capture/result.json     # browser render evidence (needs Playwright)
├── 06_quality/<lead-slug>/site_quality_report.json
└── 07_deployments/ · 08_outreach/ · 09_review/ · 10_sent/ · 11_results/
```

## How it works

Phase 05 dispatches across four generation modes: `modular` (production templates across 4 design families), `template` (legacy path), `stitch` (Google Stitch AI — exclusive path, no template fallback), and `auto` (Stitch first, legacy-template fallback if nothing is produced).

The complete phase map, generation-path semantics, feature-flag catalog, and quality-gate chain live in [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Selected engineering decisions

| Decision | Rationale |
|----------|-----------|
| **AI where reasoning matters, deterministic logic where correctness matters** | Generation is the only probabilistic step. Scoring, validation, contracts, provenance, and state are deterministic and testable. |
| **Real browser validation instead of trusting generated HTML** | Phase 05.5 renders every site in Playwright and feeds actual DOM metrics into quality scoring. |
| **Internal intelligence is isolated from public-facing generation** | BI scores and risk flags are translated into safe creative guidance before any generation prompt — raw scores never leak into public HTML. |
| **Human approval remains the outbound boundary** | Phases 08–10: drafts and approval packs are automated; sending is manual by design. |
| **vNext capabilities are feature-flagged** | All 14 flags default to `False`; the legacy pipeline always works and new capabilities opt in per run. |

The resulting safety chain — verified facts → generation → claim validation → HTML sanitization → real browser rendering → premium scorecard → human approval — is specified in [`docs/gates/quality_gates.md`](docs/gates/quality_gates.md).

## CLI reference

```bash
python -m packages.cli.run [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--niche` *(required)* | — | Business category, e.g. `"auto detailing"` |
| `--area` *(required)* | — | Target city/area |
| `--country` | `US` | ISO country code |
| `--generation-mode` | `stitch` | `stitch` \| `modular` \| `template` \| `auto` |
| `--discovery-source` | `fixture` | `fixture` \| `overpass` \| `csv_file` \| `maps_api` \| `maps_search` |
| `--deploy-provider` | `local_only` | `local_only` \| `vercel` \| `nginx_local` |
| `--max-sites` | `5` | Max preview sites per run |
| `--price-offer` | `$499 one-time` | Offer price to pitch in outreach |
| `--production` | off | Removes watermark/test markers (modular mode) |
| `--stitch-api-key` | `$STITCH_API_KEY` | Only needed for the Stitch AI path |
| `--stitch-model` | `GEMINI_3_1_PRO` | Stitch generation model |
| `--dry-run` | off | Skips deployment and outreach steps |
| `--verbose` | off | Debug logging |

Example — real discovery with OSM data, deterministic templates, local deploy:

```bash
python -m packages.cli.run --niche "dentist" --area "Austin, TX" \
    --generation-mode modular --discovery-source overpass \
    --deploy-provider local_only --max-sites 3 --verbose
```

## Testing & quality

```bash
python -m pytest tests/ -q            # full suite: 1,307 passed in ~15s
ruff check packages/ tests/ templates/
```

The suite combines unit tests per phase/module, integration tests between phases, golden-fixture regression tests (regenerable via `scripts/regenerate_fixtures.py`), and an E2E chain covering all 11 phases against synthetic data (`tests/e2e/test_full_pipeline_01_to_11.py`).

## Project structure

```text
packages/
├── cli/              # CLI entry points
├── config/           # Runtime configuration loading
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
├── pipeline/         # Orchestrator, contracts, feature flags
├── sales/            # Sales package generation
├── shared/           # Provenance & shared utilities
└── templates/        # Jinja2 templates (sites, outreach, prompts)

tests/                # unit · integration · e2e · golden fixtures
docs/                 # architecture · contracts · gates · testing
scripts/              # fixture regeneration & maintenance tooling
config/               # run_config.example.json — copy & adjust per run
```

## Documentation

| Doc | Contents |
|-----|----------|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Complete phase map, generation paths, feature flags, invariants |
| [`docs/architecture/`](docs/architecture/) | Architecture analysis & refactor proposal |
| [`docs/contracts/`](docs/contracts/) | Artifact I/O schemas between phases |
| [`docs/gates/quality_gates.md`](docs/gates/quality_gates.md) | Quality gate specification |
| [`docs/testing/standalone_phase_testing.md`](docs/testing/standalone_phase_testing.md) | Testing phases in isolation |
| [`AGENTS.md`](AGENTS.md) | Repository bootstrap for AI-assisted contribution |

## Author

Built and architected by [Iker Goñi](https://github.com/IkerGoni).

## License

MIT — see [LICENSE](LICENSE).
