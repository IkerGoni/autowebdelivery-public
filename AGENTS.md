# AutoWebDelivery — Agent Bootstrap

## What this project is

A **proof-of-concept** pipeline (not a finished or commercial product) that discovers local businesses with weak web presence, scores opportunity value, generates custom preview websites using modular templates and AI generation (Google Stitch API), and manages the full outreach lifecycle with strict quality gates.

## Quick start

```bash
# Verify everything works
python3 -m pytest tests/ -q
ruff check packages/ tests/ templates/
```

## Pipeline architecture

```
Phase 01 → 02 → 02.1 → 03 → 04 → 04.5 → 05 → 05.5 → 06 → 07 → 08 → 09 → 10 → 11
 Input   Discov Filter Score Brief Enrich Gen   Render  QA  Deploy OutRch Appr  Send  Track
```

## Key technical decisions

- **Feature flags** (14 total, all default `False`) — every new capability is behind a flag, legacy pipeline always works
- **Factual safety** — generated sites never invent business facts; sanitizer + quality gates enforce this
- **Internal data isolation** — BI scores are translated to safe creative guidance before reaching prompts
- **Multi-path generation** — modular templates (4 design families), legacy template path, and AI generation (Stitch API, no fallback); `auto` tries Stitch first and falls back to the legacy template path
- **Browser evidence** — Playwright-based render capture provides real DOM metrics for quality scoring (non-blocking degradation without Playwright browsers installed)
- **Multi-agent development** — Researcher → Builder → Auditor → Security → Documenter pattern

## Validation

| Check | Command | Expected |
|-------|---------|----------|
| Tests | `python3 -m pytest tests/ -q` | 1,447 passed |
| Lint | `ruff check packages/ tests/ templates/` | All checks passed |

## Documentation

- `ARCHITECTURE.md` — technical deep dive: phases, generation paths, feature flags, invariants, trade-offs
- `docs/contracts/` — artifact contracts (I/O schemas for all phases)
- `docs/architecture/` — system architecture
- `docs/design/` — design system documentation
- `docs/agent_tasks/` — multi-agent prompt specifications
- `docs/gates/` — quality gate definitions

## Important rules

- Do NOT remove feature flags — they protect backward compatibility
- Do NOT refactor without running the full test suite
- Do NOT leak internal BI scores or risk flags into public HTML
- Do NOT deploy without human approval

## Development process

This project is built with an **AI-assisted engineering process**: independent agents research, implement, validate and audit each feature behind feature flags, with evidence-based accept/reject decisions per sprint. The operating protocols are deliberately kept out of this public repository (see `SECURITY.md`).

## Security expectations
- `04-validation/` — validation protocol and sprint closeout.
- `05-sprints/` — executable sprint definitions (currently S0, S1).
