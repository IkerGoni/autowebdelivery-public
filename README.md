# AutoWebDelivery

> **An AI-assisted engineering case study in building reliable automation around probabilistic AI components.**

AutoWebDelivery is a phase-based pipeline that discovers local businesses with weak web presence, evaluates opportunity, generates custom website previews, validates the resulting artifacts, and prepares a human-reviewed outreach workflow.

The project is deliberately built around a simple engineering principle:

> **Use AI where interpretation and generation create value; use deterministic software where correctness, safety, state, and accountability matter.**

```text
Input
  ↓
Discovery → Website filtering → Deterministic scoring
  ↓
Facts-only brief → Enrichment
  ↓
Site generation
  ↓
Render capture → Quality gate
  ↓
Deployment → Outreach draft → Human approval → Manual send → Tracking
```

**Python 3.10+ · Pydantic v2 · httpx · Jinja2 · Playwright · pytest · Ruff · GitHub Actions**

[![CI](https://github.com/IkerGoni/autowebdelivery-public/actions/workflows/ci.yml/badge.svg)](https://github.com/IkerGoni/autowebdelivery-public/actions)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

> **Status: proof of concept / portfolio engineering project.** The repository demonstrates architecture, reliability patterns, validation, quality gates, and AI-assisted development. It is not presented as a production-hardened or commercial system.

---

## Why this project exists

A website-generation demo is easy to build:

```text
prompt → LLM → HTML
```

The harder engineering problem is building a workflow in which generated output can be **inspected, constrained, tested, rejected, reproduced, and safely moved toward real-world action**.

AutoWebDelivery explores that problem through a complete workflow:

```text
real-world inputs
      ↓
structured contracts
      ↓
deterministic business logic
      ↓
AI-assisted generation
      ↓
factual validation
      ↓
HTML / content quality checks
      ↓
browser rendering evidence
      ↓
quality decision
      ↓
human approval
      ↓
action
```

The application domain is local-business web delivery. The engineering subject is broader:

- AI systems engineering
- LLM application architecture
- workflow orchestration
- deterministic/probabilistic system design
- data contracts and provenance
- generated-output validation
- browser automation
- regression engineering
- human-in-the-loop automation
- product-oriented software engineering

---

## Engineering highlights

| Area | What the repository demonstrates |
|---|---|
| Phase-based orchestration | 11 numbered business stages with persisted artifacts between stages |
| Typed contracts | Pydantic-validated artifacts define phase boundaries |
| Deterministic scoring | Lead qualification is implemented as explicit business logic |
| AI generation | Google Stitch integration plus modular and legacy generation paths |
| Factual safety | Generated output is checked against the verified fact set |
| HTML/content validation | Sanitization and quality rules can reject unsafe or weak output |
| Browser evidence | Playwright render capture produces DOM/render evidence when browsers are available |
| Quality gates | Phase 06 evaluates safety, data utilization, copy quality, and visual credibility |
| Human approval | Outbound sending is blocked unless the required review state is approved |
| Feature flags | 14 vNext capabilities are opt-in and disabled by default |
| Regression protection | Unit, integration, golden-fixture, and full-pipeline E2E coverage |
| CI/security | Ruff, pytest on Python 3.10/3.12, Gitleaks, and pip-audit run in GitHub Actions |

---

## Architecture

The pipeline is intentionally decomposed into phases with persisted artifacts.

```text
01 Input
   ↓
02 Discovery
   ↓
02.1 Website Filter
   ↓
03 Deterministic Lead Scoring
   ↓
04 Facts-only Business Brief
   ↓
04.5 Enrichment
   ↓
05 Site Generation
   ├── modular templates
   ├── legacy template
   └── Google Stitch AI
   ↓
05.5 Browser Render Capture
   ↓
06 Multi-axis Quality Gate
   ↓
07 Deployment
   ↓
08 Outreach Generation
   ↓
09 Approval Pack
   ↓
10 Manual Sending
   ↓
11 Monetization / Outcome Tracking
```

A key implementation property is that phases exchange persisted artifacts under `runs/<run_id>/` rather than relying on shared in-memory state. This makes individual phases easier to test and rerun in isolation.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full phase map and invariants.

---

## The AI trust boundary

AI-generated output is treated as **untrusted generated material**, not as the system of record.

The current factual-safety design is:

```text
verified facts
     ↓
creative guidance
     ↓
generation
     ↓
claim / content checks
     ↓
HTML sanitization
     ↓
quality evaluation
     ↓
human approval
```

The system explicitly protects against unsupported business claims such as fabricated:

- services
- pricing
- staff
- certifications
- awards
- testimonials
- other unsupported credibility claims

Internal business intelligence is also separated from public-facing generation: scoring and risk information is translated into safe creative guidance rather than exposed directly in generated HTML.

The detailed rules live in [`docs/gates/quality_gates.md`](docs/gates/quality_gates.md).

---

## Quality gates

Phase 06 is more than a simple "does the page exist?" check.

It evaluates four axes:

| Axis | Weight | Examples |
|---|---:|---|
| Safety | 25 | unsupported claims, placeholders, required sections |
| Data utilization | 25 | use of available business facts and enrichment |
| Copy quality | 25 | word count, duplication, CTA quality, fallback content |
| Visual credibility | 25 | layout/preset, screenshot presence, density, overflow, links |

```text
                    ┌──────────────┐
                    │    Safety    │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ Data usage   │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ Copy quality │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │Visual cred.  │
                    └──────┬───────┘
                           │
                           ▼
                  0–100 credibility score
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
       APPROVED       NEEDS_REVIEW      NEEDS_EDIT
        ≥ 90            70–89             50–69
                           │
                           ▼
                       REJECTED
                         < 50
```

Hard-reject conditions include unsupported claims, missing required sections, placeholders, missing screenshots, failed rendering, insufficient body content, duplicated core copy, and other explicitly defined violations.

One important current-state detail: **Phase 05.5 produces Playwright browser evidence, but Phase 06 does not yet consume that evidence as a strict scoring input.** The current quality gate checks screenshot existence; deeper Phase 05.5 provenance/DOM-metric integration is documented as future work. This distinction is intentional and avoids overstating the current implementation.

---

## Generation paths

Phase 05 supports four modes:

| Mode | Current behavior |
|---|---|
| `modular` | Modular templates across four design families |
| `template` | Legacy template path |
| `stitch` | Google Stitch AI generation; no template fallback |
| `auto` | Stitch first; falls back to the legacy template path if no site is produced |

The modular design families currently include:

- `clinical-trust`
- `warm-editorial`
- `industrial-reliable`
- `fresh-utility`

---

## Feature-flagged architecture evolution

The repository contains **14 vNext capabilities**, disabled by default.

Examples include:

- structured business profiles
- market/competitor profiles
- brand reconstruction
- creative specifications
- Stitch compilation
- structured evaluation reports
- sales-package contracts
- learning records
- competitor intelligence
- deterministic HTML patch planning
- Overpass enrichment
- Google Maps enrichment
- social enrichment
- image fallback

The migration strategy is deliberately conservative:

```text
existing behavior
      +
new capability behind a flag
      +
explicit contract
      +
regression coverage
```

This allows architectural evolution without requiring a single high-risk rewrite.

---

## What a run produces

Every run persists its intermediate state under:

```text
runs/<run_id>/
```

Example:

```text
runs/run_<timestamp>/
├── config/input_config.json
├── 01_input/query_plan.json
├── 02_discovery/
├── 02_1_website_filter/
├── 03_scoring/
├── 04_briefs/<lead-slug>/
├── 04_5_enrichment/<lead-slug>/
├── 05_sites/<lead-slug>/
├── 05_5_render_capture/
├── 06_quality/<lead-slug>/
├── 07_deployments/
├── 08_outreach/
├── 09_review/
├── 10_sent/
└── 11_results/
```

Phase result manifests record status, inputs, outputs, decisions, risks, and errors. The artifact-oriented approach makes intermediate decisions inspectable instead of hiding the whole workflow behind one opaque agent call.

---

## Quickstart

The default demonstration path uses synthetic data and does not require external API credentials.

```bash
git clone https://github.com/IkerGoni/autowebdelivery-public.git
cd autowebdelivery-public

python3 -m venv .venv
source .venv/bin/activate

pip install -e ".[dev,browser]"
playwright install chromium

python -m packages.cli.run     --niche "restaurant"     --area "Dallas, TX"     --generation-mode modular     --deploy-provider local_only     --max-sites 2     --dry-run
```

Or with the locked environment:

```bash
uv sync --extra dev,browser
uv run playwright install chromium
```

The default fixture is synthetic. The bundled fixture records are dentists regardless of the `--niche` value; the niche changes the run configuration, not the fixture contents.

For real discovery, the repository supports:

```text
fixture
csv_file
overpass
maps_api
maps_search
```

---

## Testing and validation

The current repository reports **1,558 passing tests** (R0 closeout, 2026-02).

The number is deliberately a supporting metric rather than the main project claim. The important part is the coverage model:

```text
unit tests
    ↓
integration tests
    ↓
golden-fixture regression
    ↓
full 11-phase E2E
    ↓
browser/render evidence where available
```

Run locally:

```bash
python -m pytest tests/ -q
ruff check packages/ tests/ templates/
```

The full CI pipeline currently runs:

- Ruff
- pytest on Python 3.10
- pytest on Python 3.12
- Gitleaks secret scanning
- pip-audit dependency auditing

See [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

---

## AI-assisted development

This repository was developed using an **AI-assisted engineering process**.

The project documentation describes a multi-agent development pattern in which independent agents can research, implement, validate, audit, and document work.

The important engineering point is not that AI was used. It is **how AI-generated work is constrained and verified**:

```text
AI-assisted implementation
          ↓
explicit architecture
          ↓
typed contracts
          ↓
tests / fixtures
          ↓
lint + CI
          ↓
security / dependency checks
          ↓
runtime validation
          ↓
human engineering judgment
```

AI tools are therefore treated as implementation leverage, not as a substitute for engineering responsibility.

The public repository intentionally does not contain the private agent operating protocols and internal orchestration material used during development.

---

## Selected engineering decisions

| Decision | Why |
|---|---|
| AI for generation; deterministic logic for correctness | Keeps critical state, validation, scoring, and contracts testable |
| Persisted phase artifacts | Makes phases inspectable, testable, and independently rerunnable |
| Pydantic contracts | Makes phase boundaries explicit and machine-validatable |
| Human approval before outbound sending | Prevents autonomous external communication |
| Feature flags for vNext | Enables incremental migration while preserving the legacy path |
| Golden fixtures | Protects behavior while the architecture evolves |
| Real browser render capture | Adds runtime/browser evidence beyond static HTML inspection |
| Internal BI isolation | Prevents internal scores and risk signals from leaking into public output |

---

## Failure handling

The pipeline defines explicit `done`, `blocked`, `failed`, `needs_review`, and `skipped` states.

Examples of explicit blocking/failure criteria include:

- missing required discovery inputs;
- unavailable discovery sources;
- invalid or missing lead identity;
- unsupported claims in business briefs;
- missing required generation inputs;
- generated placeholder content;
- missing required site sections;
- insufficient quality score;
- failed deployment;
- missing approval before outbound sending.

See [`docs/gates/quality_gates.md`](docs/gates/quality_gates.md) for the phase-by-phase kill criteria.

---

## Production gap

This repository is intentionally a **portfolio / engineering prototype**, not a claim of production readiness.

It has not been presented as:

- security-reviewed;
- load-tested;
- operated long-term;
- a production SaaS;
- a distributed job-processing platform.

A production evolution would likely require:

- durable job orchestration;
- retry/backoff and idempotency;
- persistent artifact storage;
- structured observability;
- per-phase metrics and cost tracking;
- worker pools and rate limiting;
- stronger browser sandboxing;
- SSRF/outbound-domain protections;
- managed secrets;
- stronger operational alerting.

Documenting these gaps is part of the engineering case study rather than something to hide.

The **active, evidence-verified hardening program** (idempotency, persistence, SSRF protection,
secret handling, rate-limit consolidation, resumable runs, and doc consolidation) is tracked in
[`docs/plans/RECOVERY_PLAN.md`](docs/plans/RECOVERY_PLAN.md), with a findings baseline and live
sprint tracker.

---

## Project structure

```text
packages/
├── cli/              # CLI entry points
├── config/           # Runtime configuration
├── creative/         # Creative specification / brand reconstruction
├── deployers/        # local_only / vercel / nginx_local
├── discovery/        # fixture, CSV, Google Maps, Overpass
├── enrichment/       # Maps, social, reviews, image fallback
├── evaluation/       # Structured quality evaluation
├── generation/       # Modular templates + Stitch adapters
├── intelligence/     # Competitor intelligence
├── learning/         # Outcome feedback
├── patching/         # Deterministic HTML repair planning
├── phases/           # Pipeline phase implementations
├── pipeline/         # Orchestration, contracts, feature flags
├── sales/            # Sales-package generation
├── shared/            # Provenance and shared utilities
└── templates/        # Sites, outreach, prompts

tests/                # unit / integration / E2E / golden fixtures
docs/                 # architecture / contracts / design / gates / testing
scripts/              # fixture regeneration and maintenance
config/               # example runtime configuration
```

---

## Documentation

| Document | Purpose |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Phase map, generation paths, artifacts, feature flags, invariants |
| [`docs/plans/RECOVERY_PLAN.md`](docs/plans/RECOVERY_PLAN.md) | LIVE hardening program: verified findings baseline, R0–R5 sprint plan, findings tracker |
| [`docs/contracts/`](docs/contracts/) | Artifact I/O schemas |
| [`docs/gates/quality_gates.md`](docs/gates/quality_gates.md) | Quality gates and kill criteria |
| [`docs/architecture/`](docs/architecture/) | Architecture analysis and evolution |
| [`docs/design/`](docs/design/) | Design-system documentation |
| [`docs/testing/`](docs/testing/) | Standalone phase testing |
| [`AGENTS.md`](AGENTS.md) | Public engineering/agent bootstrap and validation rules |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Development and contribution guidance |
| [`SECURITY.md`](SECURITY.md) | Security policy and repository boundaries |

---

## Limitations

This public repository intentionally excludes private agent operating protocols, local tool state, run-specific configuration, secrets, and generated local artifacts.

External integrations require credentials and additional operational hardening.

The repository should be evaluated as a **technical portfolio and engineering prototype**, not as a commercial product.

---

## Author

**Iker Goñi**

Software engineer working across AI systems, automation, full-stack engineering, and product execution.

[LinkedIn](https://www.linkedin.com/in/iker-goni/)

---

## License

MIT — see [`LICENSE`](LICENSE).
