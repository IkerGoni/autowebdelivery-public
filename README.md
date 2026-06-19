# AutoWebDelivery

**AI-powered website generation pipeline for local businesses.**

An end-to-end automated system that discovers local businesses with weak or no web presence, scores them by opportunity value, generates custom high-quality preview websites, and manages the full outreach lifecycle — all with strict quality gates and factual safety constraints.

## Key Metrics

| Metric | Value |
|--------|-------|
| Pipeline phases | 11 + 16 vNext modules |
| Test suite | 1,306 tests passing |
| Source code | ~24,600 lines (Python) |
| Test code | ~21,500 lines |
| Feature flags | 13 (all backward-compatible) |
| Template families | 4 design systems |

## Architecture

```
Phase 01 → 02 → 02.1 → 03 → 04 → 04.5 → 05 → 05.5 → 06 → 07 → 08 → 09 → 10 → 11
 Input   Discov Filter Score Brief Enrich Gen   Render  QA  Deploy OutRch Appr  Send  Track
```

### Phase Map

| Phase | Name | Description |
|-------|------|-------------|
| 01 | User Input | Configure run by niche, area, offer, language, and thresholds |
| 02 | Lead Discovery | Multi-source business discovery (fixtures, CSV, Google Maps API, Overpass OSM) |
| 02.1 | Website Filter | Filter candidates by web presence status |
| 03 | Lead Scoring | Business intelligence scoring with deterministic signal combination |
| 04 | Business Brief | Generate safe business briefs from verified facts only |
| 04.5 | Enrichment | Deep enrichment: Google Maps, social profiles, visual context, reviews |
| 05 | Preview Site Generation | Multi-path: modular templates + AI-generated (Google Stitch API) |
| 05.5 | Browser Render Capture | Playwright-based real browser rendering with performance metrics |
| 06 | Quality Gate | Strict quality gates: sanitizer, factual claims checker, premium scorecard |
| 07 | Deployment | Local-first with optional Vercel public deployment |
| 08 | Outreach Generation | Personalized outreach drafts from verified business data |
| 09 | Manual Approval Pack | Human-reviewable approval packages for each candidate |
| 10 | Manual Sending | Human-approved outbound only |
| 11 | Monetization Tracking | Track replies, interest, meetings, conversions, objections, segment analytics |

### vNext Architecture (Feature-Flagged)

16 additional modules behind feature flags, providing next-generation capabilities:

| Module | Capability |
|--------|-----------|
| Business Profile Contract | Structured business identity model |
| Market Profile Contract | Market/competitor landscape model |
| Brand Reconstruction | AI-driven brand voice extraction |
| Creative Specification | Design intent specification |
| Stitch Compiler | Google Stitch API integration for AI-generated sites |
| Structured Evaluation | Multi-dimensional quality evaluation reports |
| Deterministic Patch Planner | Automated HTML fix planning |
| Sales Package | Client-ready sales artifact generation |
| Learning Record | Feedback loop from outcomes to scoring |
| Competitor Intelligence | Benchmark matching and gap analysis |
| Pipeline Integration + E2E | Full end-to-end orchestrator |
| Overpass Enrichment | OpenStreetMap data for business context |
| Google Maps Enrichment | Places API data extraction |
| Social Scraper | Facebook/Instagram public profile data |
| High-Density Synthesis | Multi-source business profile fusion |

## Technical Highlights

### Multi-Agent Orchestration

The pipeline uses a **Researcher → Builder → Auditor → Security → Documenter** multi-agent pattern for development, testing, and quality assurance. Each agent has specialized prompts (see `docs/agent_tasks/`).

### Quality-First Generation

- **Factual safety**: Generated sites must not invent services, pricing, staff, certifications, guarantees, awards, or testimonials
- **HTML sanitizer**: Automated scanning for unsupported/fake claims
- **Premium scorecard**: Visual quality scoring out of 100 with critical structure thresholds
- **Browser render evidence**: Real DOM/render metrics from Playwright capture
- **Internal data isolation**: Business intelligence scores are translated into safe creative guidance before reaching generation prompts — raw scores, risk flags, and internal hints never leak into public HTML

### Modular Template System

4 design families with production-mode support:

- **Clinical Trust** — healthcare, dental, professional services
- **Warm Editorial** — restaurants, boutiques, artisan businesses
- **Industrial Reliable** — auto services, construction, trades
- **Fresh Utility** — modern general-purpose layouts

### Business Intelligence Scoring

Deterministic lead scoring combining:

- Category value signals
- Website need assessment
- Public demand indicators
- Contact friction analysis
- Enrichment depth metrics

### Enrichment Pipeline

Multi-source data enrichment:

- **Google Maps API** — business details, hours, categories, ratings
- **Overpass/OSM** — geographic and neighborhood context
- **Social Scraper** — public Facebook/Instagram profile data
- **Review Extraction** — verified customer sentiment signals
- **Image Fallback** — visual context when photos unavailable

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.10+ |
| Data Models | Pydantic v2 |
| HTTP Client | httpx |
| Templating | Jinja2 |
| Browser Automation | Playwright |
| Linting | Ruff |
| Testing | pytest + pytest-xdist |
| AI Generation | Google Stitch API |
| Deployment | Vercel CLI (optional) |
| Orchestrator | Multi-agent (custom) |

## Project Structure

```
packages/
├── cli/              # CLI entry points
├── config/           # Runtime configuration
├── creative/         # Creative specification & brand reconstruction
├── deployers/        # Local + Vercel deployment
├── discovery/        # Multi-source lead discovery (CSV, Maps API, Overpass)
├── enrichment/       # Business data enrichment (Maps, social, reviews, images)
├── evaluation/       # Structured quality evaluation
├── generation/       # Site generation (modular templates + Stitch adapter)
├── intelligence/     # Competitor intelligence & benchmarking
├── learning/         # Outcome feedback loop
├── patching/         # Deterministic HTML fix planner
├── phases/           # Phase implementations (01–11)
├── pipeline/         # Orchestrator, feature flags, vNext integration
├── sales/            # Sales package generation
├── shared/           # Shared utilities (provenance, helpers)
└── templates/        # Jinja2 templates (modular, outreach, stitch prompts)

tests/
├── unit/             # Unit tests per phase/module
├── e2e/              # End-to-end pipeline chain tests
├── enrichment/       # Enrichment module tests
├── fixtures/         # Test fixtures for all phases
└── conftest.py       # Shared test configuration

docs/
├── contracts/        # Artifact contracts (I/O schemas)
├── architecture/     # Architecture documentation
├── design/           # Design system documentation
├── agent_tasks/      # Multi-agent prompt specifications
├── gates/            # Quality gate documentation
├── prompts/          # Generation prompt templates
├── templates/        # Documentation templates
└── testing/          # Testing documentation
```

## Getting Started

```bash
# Install dependencies
pip install -e ".[dev,browser]"

# Run tests
python -m pytest tests/ -q

# Lint
ruff check packages/ tests/ templates/

# Run the pipeline (dry-run)
python -m packages.cli.run --dry-run --niche "restaurant" --area "Dallas, TX"
```

## Quality & Safety

- Human approval required before any outbound communication
- Preview generation cannot invent business facts
- Sanitizer and quality gates scan for unsupported claims
- Browser render capture provides real DOM evidence
- Internal BI data is isolated from public-facing content
- Feature flags ensure backward compatibility for all new capabilities

## License

Private — not for redistribution.
