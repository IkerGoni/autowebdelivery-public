# AutoWebDelivery — Agent Bootstrap

## What this project is

An AI-powered pipeline that discovers local businesses with weak web presence, scores opportunity value, generates custom preview websites using modular templates and AI generation (Google Stitch API), and manages the full outreach lifecycle with strict quality gates.

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

- **Feature flags** (13 total, all default `False`) — every new capability is behind a flag, legacy pipeline always works
- **Factual safety** — generated sites never invent business facts; sanitizer + quality gates enforce this
- **Internal data isolation** — BI scores are translated to safe creative guidance before reaching prompts
- **Multi-path generation** — modular template system (4 design families) + AI-generated (Stitch API) with auto-fallback
- **Browser evidence** — Playwright-based render capture provides real DOM metrics for quality scoring
- **Multi-agent development** — Researcher → Builder → Auditor → Security → Documenter pattern

## Validation

| Check | Command | Expected |
|-------|---------|----------|
| Tests | `python3 -m pytest tests/ -q` | 1,306+ passed |
| Lint | `ruff check packages/ tests/ templates/` | All checks passed |

## Documentation

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
