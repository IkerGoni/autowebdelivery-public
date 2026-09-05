# AUTOWEBDELIVERY — Architecture Audit & Refactor Proposal

> ## ⚠️ SUPERSEDED — historical audit only
>
> This document is retained as a historical audit record. The **live** hardening program and
> findings tracker live in [`../plans/RECOVERY_PLAN.md`](../plans/RECOVERY_PLAN.md); its R-series
> sprint numbering supersedes the "Sprint 1–4" scheme used below. Facts cited here (e.g., test
> counts) are snapshots at time of writing and are stale — the live counts are in `AGENTS.md` and
> the recovery plan.
>
> **Date:** 2026-06-06 (historical)
> **Author:** RS Orchestrator analysis
> **Status:** Superseded

---

## 📍 Status Snapshot (live reference)

Cross-checked against `AGENTS.md` at top of repo. Update this section when sprint work lands.

| Sprint | State | Evidence |
|---|---|---|
| Sprint 1 (structural cleanup) | 🟡 In progress | Commits `4de5083`, `97702ec`, `8f9d3db`, `46a88ee`; shadow dirs not yet deleted |
| Sprint 2 (provider DI) | 🔴 Not started | Orphaned modules confirmed present, not wired |
| Sprint 3 (registry + config) | 🔴 Not started | `phase_05_unified.py` still has if/elif |
| Sprint 4 (phase splits) | 🔴 Not started | Monoliths intact |

> **Test count drift:** this proposal cites 505 passing. Live state per `AGENTS.md` is **1,623 passed, 0 failed** (ruff clean, 2026-09 R1 closeout). Update the snapshot below when this doc is re-read.

---

## 📊 Codebase Snapshot

- **27,229 LOC** across ~80 Python files (non-archive, non-runs)
- **9,858 LOC** test code, **505 tests passing** (⚠️ stale — live count is **1,623** per `AGENTS.md`), ruff clean
- **11-phase pipeline** (01→11) running end-to-end
- **118 markdown docs** in `docs/`

---

## 🚨 FINDING 1: Shadow Directory Chaos (P0)

4 top-level directories are stub re-exports duplicating real code in `packages/`:

| Dir | Stubs LOC | Real packages/ LOC |
|---|---|---|
| `phases/` | 39 | 8,561 |
| `pipeline/` | 18 | 769 |
| `discovery/` | 6 | ~1,100 |
| `deployers/` | 3 | ~300 |

Each stub file (e.g. `phases/phase_01_user_input.py`) is ~127 bytes: `from packages.phases.phase_01_user_input import *`

**Problems:**
- `packages/pipeline/__init__.py` has try/except fallback — codebase itself doesn't know canonical path
- Tests import via BOTH paths inconsistently
- Any edit to a stub = dead code
- New contributors confused about which is real

---

## 🚨 FINDING 2: No Provider Abstraction / Dependency Injection (P1)

Subsystems hardwired into phase code with if/elif chains:

**Discovery (Phase 02):**
```python
from packages.discovery.csv_loader import load_leads_from_csv
from packages.discovery.maps_fetcher import fetch_maps_leads
```
`overpass_fetcher.py` (404 LOC) exists but orphaned.

**Generation (Phase 05):**
```python
# phase_05_unified.py
if generation_mode in ("stitch", "auto"):
    ...run_stitch_phase_05(...)
elif generation_mode == "modular":
    ...run_modular_phase_05(...)
```

**Deployment (Phase 07):**
```python
if deploy_provider == "vercel":
    from packages.deployers.vercel import deploy_to_vercel
```

Adding a provider = edit phase code directly.

---

## 🚨 FINDING 3: 4 Orphaned Modules (P1)

Fully implemented, tested, disconnected from live pipeline:

| Module | File | LOC | Status |
|---|---|---|---|
| Overpass fetcher | `packages/discovery/overpass_fetcher.py` | 404 | Not wired to Phase 02 |
| Social scraper | `packages/enrichment/social_scraper.py` | 732 | Not wired to Phase 04.5 |
| Google Maps enricher | `packages/enrichment/google_maps_enricher.py` | 480 | Not wired to Phase 04.5 |
| Reviews extractor | `packages/enrichment/reviews_extractor.py` | 365 | Not wired to Phase 04.5 |

Total: **~1,981 LOC** sitting idle.

---

## ⚠️ FINDING 4: Monolithic Phases (P2)

Top-heavy files mixing orchestration + business logic:

| File | LOC | Problem |
|---|---|---|
| `phase_04_5_enrichment.py` | 939 | Extraction + validation + I/O + config |
| `html_sanitizer.py` | 825 | Safety rules + HTML + reporting |
| `phase_05_5_browser_render_capture.py` | 730 | Playwright + screenshots + scoring |
| `stitch_adapter.py` | 584 | 3 clients + adapter + dataclasses |
| `phase_05_preview_site_generation.py` | 567 | Template + data bridge + output |

---

## ⚠️ FINDING 5: No Central Configuration (P2)

Configuration scattered across:
- CLI args (13 params in `run_full_pipeline()`)
- Hardcoded constants in `stitch_premium_adapter.py`
- Inline defaults throughout
- One JSON config file (`niche_scores.json`)

No settings class, no `.env` loading, no single source of truth.

---

## ⚠️ FINDING 6: Generation System Sprawl (P2)

```
packages/generation/
├── stitch_adapter.py        584 LOC  → 3 client classes
├── stitch_premium_adapter.py 485 LOC  → wraps adapter + design systems
├── stitch_prompt_builder.py  291 LOC  → prompt + safety rules
├── html_sanitizer.py         825 LOC  → 30+ rules + parsing
├── niche_copy.py             343 LOC  → copy generation
├── claim_policy.py           ???      → duplicate rules
```

- `McpStitchClient`, `McporterStitchClient` unused (dead code)
- Design presets as Python dataclasses instead of config

---

## ⚠️ FINDING 7: Import Style Inconsistency (P3)

Three conventions used simultaneously:
```python
# Style 1: Stub path
from pipeline.contracts import RunConfig

# Style 2: packages prefix
from packages.pipeline.json_io import read_json

# Style 3: Relative (templates only)
from .models import BusinessData
```

---

## ⚠️ FINDING 8: run_pipeline.py Procedural Bloat (P3)

328 LOC linear script with 12 identical error-handling blocks. No retry, no checkpoint, no resume.

---

## ✅ PROPOSED ARCHITECTURE: "Clean Packages + Protocol DI"

**Philosophy:** Surgical refactor. Preserve all working code. Fix structure. Unlock orphaned modules.

---

### A. Eliminate Shadow Directories

Delete `phases/`, `pipeline/`, `discovery/`, `deployers/` top-level stubs.
Update all imports to `packages.*` path.

---

### B. Provider Protocols

```python
# packages/providers/protocols.py

class DiscoveryProvider(Protocol):
    def fetch_leads(niche, area, country) -> list[RawPlace]: ...

class EnrichmentProvider(Protocol):
    def enrich(business_slug, facts_path) -> EnrichmentResult: ...

class SiteGenerator(Protocol):
    def generate(brief, output_dir) -> GenerationResult: ...

class Deployer(Protocol):
    def deploy(site_path, project_name) -> DeploymentResult: ...
```

Implementations: `CsvDiscovery`, `MapsDiscovery`, `OverpassDiscovery`, etc.

---

### C. Provider Registry

Replace if/elif with registry lookup:

```python
# packages/providers/registry.py
GENERATORS = {"stitch": StitchGenerator, "modular": ModularGenerator, "template": TemplateGenerator}
DEPLOYERS = {"local_only": LocalDeployer, "vercel": VercelDeployer}
```

---

### D. Central Settings

```python
# packages/config/settings.py
class PipelineSettings(BaseModel):
    niche: str
    area: str
    generation_mode: str = "stitch"
    deploy_provider: str = "local_only"
    # ... 12 parameters → 1 settings object
```

---

### E. Split Monoliths

- `phase_04_5_enrichment.py` (939 → 200 + 400)
- `html_sanitizer.py` (825 → 300 + 300 + 200)
- `stitch_adapter.py` (584 → 200 + 250)

---

### F. Prune Dead Code

- Delete `McpStitchClient`, `McporterStitchClient`
- Merge `claim_policy.py` into `stitch_prompt_builder.py`

---

## 📋 DEV PLAN — 4 Sprints, 10 Days

### Sprint 1 (Day 1-2): Structural Cleanup — Foundation
- Delete 4 shadow directories
- Grep-replace `from pipeline.` → `from packages.pipeline.`
- Remove try/except fallback in `packages/pipeline/__init__.py`
- Remove sys.path hacks in `tests/conftest.py`
- Update pyproject.toml setuptools config
- Run full test suite → verify 505 passing

### Sprint 2 (Day 3-5): Provider Protocols + Discovery Wiring
- Create `packages/providers/protocols.py`, `registry.py`
- Define all 4 Protocols
- Wrap existing implementations as provider classes
- Connect `OverpassDiscovery` to Phase 02
- Wire `SocialScraper`, `GoogleMapsEnricher`, `ReviewExtractor` to Phase 04.5
- Add provider tests

### Sprint 3 (Day 6-8): Generation Registry + Central Config
- Create `packages/config/settings.py`
- Create `packages/config/design_systems.yaml`
- Wrap generators as `SiteGenerator` implementations
- Replace if/elif in `phase_05_unified.py` with registry
- Extract `HttpStitchClient` to own file
- Delete dead client classes
- Update CLI + `run_full_pipeline()` to use Settings

### Sprint 4 (Day 9-10): Phase Splits + Final Cleanup
- Split `phase_04_5_enrichment.py`
- Split `html_sanitizer.py`, `stitch_adapter.py`
- Wire all enrichment providers
- Final test suite → all passing
- Update AGENTS.md

---

## 🔄 Rollback Strategy (per sprint)

Each sprint is independently revertable. Apply in this order so a bad sprint never blocks the next one.

**Per-sprint safety contract:**
- Each sprint lands as a single commit (or small atomic chain) on a feature branch
- Revert command: `git revert <merge-sha>` then re-run full test suite
- Tests must pass *before* merging a sprint, not after
- Shadow directory delete (Sprint 1) is gated on `git grep "from pipeline\." tests/` returning zero matches

**Sprint 1 rollback:**
```bash
# If shadow-dir delete breaks imports
git revert --no-commit HEAD~N..HEAD
python3 -m pytest tests/ -q  # must hit 1042 passing
```

**Sprint 2 rollback (provider DI):**
- Old if/elif chains preserved in `phase_XX_legacy.py` until new registry path is proven
- Toggle via `USE_PROVIDER_REGISTRY=false` env var on first deploy
- Re-enable old path → no code change needed, just env flip

**Sprint 3+ rollback:**
- Settings object falls back to `**kwargs` on `PipelineSettings.__init__` if a key is missing → forwards to legacy defaults
- Generator registry returns the legacy function for any mode not yet migrated

**Hard stop conditions (any sprint):**
- Test count drops below 1042 → revert, do not patch forward
- ruff reports new violations → revert, do not patch forward
- E2E run (modular pipeline) fails → revert, do not patch forward

---

## ❌ WHAT NOT TO DO
- Don't rewrite from scratch — 505 tests + working E2E pipeline
- Don't add plugin system — YAGNI at current scale
- Don't touch `tools/` repo — separate concern
- Don't add async — pipeline is sequential by nature

---

## ⚠️ Anti-pattern Guidance (from AGENTS.md)

These are active constraints from the project's own guidance file. Violating them undermines the refactoring's value.

1. **Don't refactor discovery before monetization validation.** Current fixture/basic discovery works. Real discovery wiring (Sprint 2) happens *after* value is proven.
2. **Don't invent services/pricing in previews.** Must use real business data — sanitizer and quality gates block unsupported claims.
3. **Don't scale outbound automatically.** Outbound is manual by design — no automation of that step.
4. **Don't add new features until Phase 06 quality gate is validated with real Stitch sites.** This refactoring is structural, not feature work.

---

## 🔗 Related Documents

- [`AGENTS.md`](../../AGENTS.md) — agent bootstrap state, sprint commit log, vNext workstream status
- [`/docs/`](../) — 118 markdown docs, includes phase-specific design docs
- Pipeline entry point: `run_full_pipeline()` in root `run_pipeline.py`