# AutoWebDelivery — Recovery Program Plan (R-Series)

**Status:** ACTIVE — single live source of truth for the hardening program
**Created:** 2026-02-09
**Supersedes:** finding narratives in [`docs/architecture/ARCHITECTURE_REFACTOR_PROPOSAL.md`](../architecture/ARCHITECTURE_REFACTOR_PROPOSAL.md) (retained as historical audit) and any external audit drafts.
**Applies to:** public repository `autowebdelivery-public`

---

## 0. Why this plan exists

Two external reviews proposed multi-sprint "productionization" programs. Every P0/P1 claim in those
reviews was re-verified against the code before being accepted here. Results:

- **Confirmed:** blind exception handling, path traversal via `business_slug`, the Vercel token in
  `argv`, missing SSRF guards, god modules, no idempotency, no persistent state, hardcoded quality
  thresholds, bare Playwright launch, plain-string secrets, no structured logging.
- **Rejected:** "no rate limiting on external APIs" (two `RateLimiter` classes already exist),
  "heavy mocking in E2E tests" (`tests/integration/` has zero mocks and runs phases 01→09 for real),
  and fabricated quality-gate constants (`MIN_WORD_COUNT`, `MAX_DUPLICATION_RATIO`,
  `QUALITY_THRESHOLD` do not appear anywhere in the codebase).
- **Already closed:** `run_id` second-granularity collision (S2: `make_run_id()`, verified live).

This plan keeps what verified, documents what was rejected so it is never reintroduced, and sizes
the work for the project's real development model: **a single maintainer working with AI agents,
shipping behind feature flags** — not a six-engineer enterprise program.

### Program goal

Keep AutoWebDelivery an honest **proof of concept** (the README status line stays), but make it a
**trustworthy** one:

1. A bad input or a network failure can never silently corrupt run artifacts.
2. Every failure is visible, classified, and recoverable; runs are resumable and re-runnable without
   duplication.
3. Outbound requests cannot be weaponized against internal networks.
4. Documentation reflects the live state of the code, not a snapshot from an older audit.

### Non-goals

- Becoming a commercial/production SaaS while PoC status holds (see README "Production gap").
- Rewriting the pipeline architecture — the phase/artifact model and all 14 feature flags stay.
- Async-everything: local file I/O stays synchronous (thread-offloaded where hot); only network I/O
  becomes async, behind a flag.

### Rejected findings (permanent record — do not resurface)

| Claim | Why rejected |
|---|---|
| "No rate limiting on external APIs" | `RateLimiter` already exists at `enrichment/social_scraper.py:164` and `discovery/overpass_fetcher.py:221`; `discovery/maps_fetcher.py` has daily caps + 429 handling. Real gap = two duplicate implementations → consolidated in R2. |
| "Heavy mocking in E2E tests" | `tests/integration/` contains zero `Mock`/`monkeypatch` across all 6 files; real E2E (`test_e2e_full_pipeline_09.py`) runs phases 01→09. Mocking is unit-level, which is correct. Real gap = contract drift → contract tests in R5. |
| `MIN_WORD_COUNT=50`, `MAX_DUPLICATION_RATIO=0.3`, `QUALITY_THRESHOLD=80` in the quality gate | Zero occurrences repo-wide. The real constants are listed in F-09. |
| `structlog`, `aiolimiter`, `respx` as required runtime deps | Project keeps a minimal dependency footprint (3 runtime deps). Where a tool is useful it is either stdlib (`sqlite3`), a dev-only tool (`pip-audit`), or an optional extra. |

## 1. Verified findings baseline

Every disposition cites code evidence. `ED` = engineer-days (maintainer + agent assistance).

| ID | Finding | Evidence (file:line) | Disposition | Sprint |
|----|---------|----------------------|-------------|--------|
| F-01 | Pervasive blind `except Exception` | `pyproject.toml`: per-file `BLE001`/`S110` ignores for ~20 modules; policy comment marks allowlisted network/IO files as deliberate | OPEN (scoped — R0-04) | R0 |
| F-02 | Path traversal via `business_slug` | `phases/phase_05_preview_site_generation.py:86,123,432` (`root / "runs" / run_id / ... / business_slug`); same pattern in `pipeline/vnext_integration.py:110,149,209,298,...`; `slug.py` only *generates* slugs, never validates | OPEN | R0 |
| F-03 | Vercel token passed via CLI argv | `deployers/vercel.py:63` (`cmd.extend(["--token", token])`); env fallback already exists at line 61 | OPEN | R0 |
| F-04 | SSRF: untrusted URLs fetched without private-network blocking | `enrichment/social_scraper.py`, `enrichment/image_fallback.py` (private audit U-14) | OPEN | R0 |
| F-05 | Synchronous network I/O only | `discovery/maps_fetcher.py:132`, `discovery/overpass_fetcher.py`; no `asyncio` in `packages/` | OPEN | R2 |
| F-06 | God modules | `pipeline/vnext_integration.py` — 1,171 lines / 42,968 B; `phases/phase_04_5_enrichment.py` — 932 lines / 37,863 B | OPEN | R3 |
| F-07 | No idempotency | `pipeline/run_pipeline.py` re-runs every phase unconditionally; no resume/skip logic | OPEN | R1 |
| F-08 | Filesystem is the only state; no DB | zero `sqlite` references repo-wide | OPEN | R1 |
| F-09 | Hardcoded quality-gate thresholds | `phases/phase_06_strict_quality_gate.py:22-27`: `MIN_TEXT_DENSITY=0.001`, `MIN_SECTION_COUNT=3`, `MIN_CTA_COUNT=1`, `MAX_CONSOLE_ERRORS=3`, `MAX_BROKEN_IMAGES=0`, `MAX_BROKEN_LINKS=2` | OPEN | R3 |
| F-10 | Playwright launched without hardening flags | `phases/phase_05_5_browser_render_capture.py:142,276` (bare `chromium.launch()`) | OPEN | R4 |
| F-11 | Secrets are plain strings; no log redaction | `deployers/vercel.py` token handling; no `SecretStr` usage | OPEN | R4 |
| F-12 | No structured/JSON logging | deps are only `pydantic`, `httpx`, `jinja2`; stdlib `logging` + f-strings; `print()` in CLI summary | OPEN | R1 |
| F-13 | `run_id` second-granularity collision | `run_pipeline.py:47-55` | **CLOSED** (S2): `make_run_id()` → `run_<epoch>_<uuid4hex>` | — |
| F-14 | Duplicate rate-limit implementations | `social_scraper.py:164`, `overpass_fetcher.py:221` | RESCOPED → share one limiter | R2 |
| F-15 | Contract drift risk (not "heavy E2E mocking") | `tests/integration/` zero mocks; `docs/contracts/` drift risk | RESCOPED → contract tests | R5 |
| F-16 | Fabricated quality-gate constants | zero occurrences of the three names repo-wide | REJECTED (documented above) | — |
| F-17 | Stale documentation | `docs/architecture/ARCHITECTURE_REFACTOR_PROPOSAL.md` cited 505 tests vs 1,558 live (live count maintained in `AGENTS.md`) | CLOSED in R0 baseline; docs still swept each closeout | each closeout |

---
## 2. Sprints

### Sprint R0 — "STOP THE BLEEDING" (2 weeks, ~10 ED)
**Goal:** Close all proven security/correctness P0s. *"One bad input must never walk across the filesystem or the network."*

| ID | Story | Scope | Acceptance criteria | Flag | ED |
|----|-------|-------|---------------------|------|----|
| R0-01 | Vercel token out of argv | **Delete `vercel.py:63`** (`cmd.extend(["--token", ...])`); keep the existing env-var path (line 61); add regression test asserting token never appears in `cmd` | `DeployCommandTest.test_token_only_from_env`; grep `--token` in `deployers/` = 0 | none (bugfix) | 0.5 |
| R0-02 | `validate_slug` + `safe_path` | **Extend existing `packages/pipeline/slug.py`** (not a new module): add `validate_slug()` (raise, no `assert`) and `safe_path(root, *parts)`; apply to every site where `business_slug`/`run_id` touch paths (phase_05, vnext_integration, artifact_paths) | Negative tests: `../`, `%2e`, `.`/`..`, backslashes, null bytes, unicode homographs all rejected; allowed `[a-z0-9_-]{1,73}` — the `{1,73}` bound, not `{1,64}`, because `make_uuid_slug()` appends `-<8 hex>` to a base already truncated to 64 (= 73 max); compatibility baseline: every output of `make_slug`/`make_uuid_slug` must validate; full suite green | none (bugfix) | 2 |
| R0-03 | SSRF validator | New `packages/shared/ssrf_validator.py`: scheme allowlist (http/https only), block private/loopback/link-local/multicast IPv4+IPv6, literal IPs, DNS resolve-then-check of **all** A/AAAA records before the request (best-effort against rebinding — a re-resolution between check and connect is a residual TOCTOU, documented as such, not claimed as solved); wire into `social_scraper`, `image_fallback` | Unit tests for 10.x/172.16-31/192.168/169.254/127/::1/fc00::/7, `file://`, redirects; docs reference U-14 | `ENRICH_SSRF_GUARD` (default on — deliberate exception to the all-False convention: this is a security invariant, not a new capability; flags exist to protect backward compatibility, and an off-by-default guard protects nothing. Override: `ENRICH_SSRF_GUARD=0`) | 2 |
| R0-04 | Blind exceptions — scoped | Keep the documented allowlist policy for network/IO resilience modules (per `pyproject.toml` comment); remove ignores from files that catch-and-silence needlessly; require the specific exceptions those modules already discriminate | Terminal allowlist is an explicit file list in the `pyproject.toml` policy comment (network/IO resilience modules only — the terminal set, not a moving count); every file removed from the list has zero `BLE001` findings and ≥1 failure-path test proving no silent swallow; `ruff check` clean | — | 3 |
| R0-05 | Docs baseline | Create this plan; banner `ARCHITECTURE_REFACTOR_PROPOSAL.md` as superseded; fix its stale "505 tests" line; link plan from `ARCHITECTURE.md`, `README.md`, `AGENTS.md` | No other doc claims a plan status; full doc pointer audit | — | 1 |

**R0 DoD:** R0-01..R0-05 done; full suite + `ruff` green (live test count maintained in `AGENTS.md` Validation table — never hard-coded here); F-01..F-04, F-17 closed in tracker below.

**R0 closeout checklist:**
- [x] F-01 (scoped), F-02, F-03, F-04, F-17 marked closed in tracker §6
- [x] `pytest tests/ -q` green (`1558 passed in 24.72s`); `ruff check packages/ tests/ templates/` green
- [x] `git grep --token packages/` = no output

---
### Sprint R1 — "OBSERVABILITY & RESILIENCE BONES" (2 weeks, ~12 ED)
**Goal:** Every failure is visible and classified; runs are resumable and idempotent. *"If a run is interrupted, we resume it without duplication; if a phase fails, we know why, where, and with what data."*

**Key decision:** SQLite state comes **first**, idempotency is built **on top** — no throwaway file-based idempotency. Uses stdlib `sqlite3` (already in Python 3.10+); no new dependency.

| ID | Story | Scope | Acceptance criteria | Flag | ED |
|----|-------|-------|---------------------|------|----|
| R1-01 | Structured logging | Stdlib `logging` + JSON formatter in `packages/shared/logging_config.py` (zero new top-level deps); every pipeline log carries `run_id`, `phase`, `ts`; keep human-readable console output | Sample run produces valid JSON logs with the three fields; `structlog` noted as optional extra in docs, not required | none (additive) | 2 |
| R1-02 | `state_db.py` | `packages/pipeline/state_db.py` (stdlib sqlite3, auto-create, `schema_version` migration table): `runs`, `phase_executions`, `artifacts`, `dead_letters`, `lead_fingerprints`. **Write-through** mode: DB mirrors existing filesystem artifacts so legacy consumers keep working | DB survives process restart; artifact paths unchanged for phases that don't opt in; migration path documented | none (new capability, additive) | 3.5 |
| R1-03 | Idempotency + resume | `run_pipeline.py` consults `phase_executions` before each phase: skip completed (return existing result), clean partial artifacts, resume from last `done`; lead-fingerprint dedupe via `lead_fingerprints` | Re-run of a completed run returns immediately; interrupted run resumes; duplicate leads skipped; zero duplicate site writes | gated per phase via `RUN_STATE_DB` | 3 |
| R1-04 | Failure classification extension | Extend existing `failure_semantics.py` (taxonomy already present) with `FailureContext` (phase, artifact, error, retryable, category); ensure every phase writes it to `result.json` + logs | Each phase's `result.json` failure block has full context; no unclassified failure path | none | 1.5 |
| R1-05 | Dead-letter queue | Failed records written to `dead_letters` table with full context + artifact refs | DLQ survives restart; per-record (not per-phase) | `RUN_STATE_DB` | 1 |
| R1-06 | Phase metrics | `PhaseMetrics` dataclass (duration, counts, failures) persisted per execution | Metrics row per phase in `phase_executions`; exposed in run summary | `RUN_STATE_DB` | 1 |

**R1 DoD:** Resume/idempotency demo on a real interrupted run; full suite + ruff green; F-07, F-08, F-12 closed in tracker.

---
### Sprint R2 — "CONCURRENCY & RATE-LIMIT CONSOLIDATION" (2 weeks, ~11 ED)
**Goal:** Network I/O concurrent (flag-gated) and rate limiting centralized — *without* rebuilding what already works.

| ID | Story | Scope | Acceptance criteria | Flag | ED |
|----|-------|-------|---------------------|------|----|
| R2-01 | Async HTTP client | New `packages/shared/http_client.py`: single `httpx.AsyncClient` (pooling, timeouts, SSRF validator hook); convert fetchers/enrichers; legacy sync path remains | 100-lead enrichment via async path matches sync results; no regression with flag off; pool-reuse metrics | `RUN_ASYNC_HTTP` (opt-in) | 4 |
| R2-02 | Consolidate rate limiter | **Delete duplicate implementations** in `social_scraper.py:164` and `overpass_fetcher.py:221`; move one token-bucket limiter into `packages/shared/rate_limiter.py`; domain-keyed option (per-host bucket) so N concurrent modules cannot multiply effective RPM; keep per-module limits configurable. Note: `maps_fetcher.py` daily caps are in-memory only (TODO at `maps_fetcher.py:236` — lost on restart); decide here whether persistent daily-cap state lands in this story or is explicitly deferred | Both modules import the shared limiter; existing rate-limiter tests pass against the shared class; default pacing unchanged or more conservative | none (refactor, keep behavior) | 2.5 |
| R2-03 | Browser pool | `BrowserPool` (max N from config) around the existing `chromium.launch()` call sites (`phase_05_5_browser_render_capture.py:142,276`); reuse contexts | Pool of ≤5, sequential runs unaffected; render capture still degrades gracefully without Playwright binaries | `RUN_BROWSER_POOL` (opt-in) | 2.5 |
| R2-04 | Performance baseline | `tests/performance/test_benchmarks.py` in fixture-only mode | Baselines committed; CI fails on >30% regression vs baseline (no absolute thresholds) | — | 2 |

**R2 DoD:** F-05 resolved via flag path; F-14 consolidated (two `RateLimiter` classes gone); suite green.

---

### Sprint R3 — "ARCHITECTURE & CONFIG" (2 weeks, ~11 ED)
**Goal:** Modules under 500 lines, single responsibility, thresholds configurable. *"No magic number without a name and a purpose."*

| ID | Story | Scope | Acceptance criteria | Flag | ED |
|----|-------|-------|---------------------|------|----|
| R3-01 | Split `vnext_integration.py` (1,171 lines) | By feature-flag domain (market_profile, brand, enrichment, evaluation, sales, learning) + shared helpers; no behavior change | No file >500 lines; gates only by calling code, flag semantics preserved; all tests green with flags on and off | none (structural) | 4 |
| R3-02 | Split `phase_04_5_enrichment.py` (932 lines) | Enrichment orchestrator + per-source modules (maps, social, reviews, image fallback) | No file >500 lines; phase wiring unchanged | none (structural) | 3 |
| R3-03 | Status enums | `PhaseStatus`/`DeploymentStatus` enums as internal types; **keep string serialization** in artifacts (contracts are the wire format) | Type checker passes; no behavior change in `result.json` statuses | none | 1 |
| R3-04 | Extend `RunConfig` | Thresholds/config merged into the existing `RunConfig` (`pipeline/contracts.py:13`) — no parallel `PipelineConfig` module | All magic-number consumers read config; validation enforced | none | 1 |
| R3-05 | Extract real magic numbers | Move the **actual** constants (F-09 list) into `RunConfig` with documented purpose per threshold | `phase_06_strict_quality_gate.py` reads zero hardcoded thresholds; identical behavior under defaults; `docs/gates/quality_gates.md` documents each threshold | none | 2 |

**R3 DoD:** F-06, F-09 closed; largest file <500 lines; suite green.

---
### Sprint R4 — "SECURITY HARDENING" (2 weeks, ~10 ED)
**Goal:** Defense in depth on what remains. *"Every secret protected, every external request sandboxed, every input validated."*

| ID | Story | Scope | Acceptance criteria | Flag | ED |
|----|-------|-------|---------------------|------|----|
| R4-01 | Playwright launch hardening | Add launch args: `--disable-dev-shm-usage`, `--disable-extensions`, `--disable-gpu`, isolated temp profile. `--no-sandbox` ONLY behind explicit `AWD_CI_INSECURE=1` and documented as a trade-off (it disables Chromium's sandbox — never listed as hardening) | `launch()` args verified by test; local requests still constrained to approved root (existing logic at `phase_05_5_browser_render_capture.py:95-96`) | `RUN_BROWSER_POOL` | 2 |
| R4-02 | Input validation framework | Pydantic validators for all external input landing in `RunConfig`/`RawPlace`/enrichment; strip dangerous characters for HTML/slug contexts | Attack corpus (traversal, JS, template strings) rejected or sanitized; valid data still accepted | none | 3 |
| R4-03 | Secret management | `SecretStr` for API keys/token; env-only; **log-redaction filter** wired into the R1 logging config | Secrets never appear in formatted logs (grep test); no secret in argv (re-verify R0-01) | none | 2 |
| R4-04 | Security test suite | Negative tests (traversal, SSRF, XSS, secret leaks) wired into CI | CI runs security tests; any failure fails the job | — | 2 |
| R4-05 | Dependency scanning | `pip-audit` step in CI (dev-only tool, not a runtime dep) | CI job green on current `uv.lock` | — | 1 |

**R4 DoD:** F-10, F-11 closed; security suite in CI; no secrets in logs or argv.

---

### Sprint R5 — "TESTING, CONTRACTS & DOCS CONSOLIDATION" (2 weeks, ~10 ED)
**Goal:** Confidence through real integration + document consistency. Replaces the rejected "reduce heavy mocking" premise with the verified gap: contract drift.

| ID | Story | Scope | Acceptance criteria | ED |
|----|-------|-------|---------------------|----|
| R5-01 | Negative security tests (consolidate) | Parameterized attack corpus across all validators built in R0/R4 | 100% attack cases rejected | 2 |
| R5-02 | Failure-mode tests | Timeout/429/lock/partial-failure behavior against R1–R2 machinery. No full Docker: `httpx.MockTransport` at unit level, fixture-based integration | Each R1–R2 resilience path has ≥1 failure-mode test | 2 |
| R5-03 | **Contract tests (the real gap)** | Schema tests per phase I/O against `docs/contracts/` + `contracts.py`; run over artifact fixtures | Every phase artifact validates against its documented contract; drift fails CI | 3 |
| R5-04 | E2E no-stubs, all paths | Extend existing real E2E to cover the modular-template path (fixture-driven). Phases 10–11 are covered by **fixture-level validation only** (their functions run against artifact fixtures; no live deploy, no live sending — repo rule: no deploy/send without human approval). Wiring phases 10–11 into `run_pipeline.py` is **out of scope** unless separately approved | Both generation paths run E2E; keep zero mocks in `tests/integration/`; phases 10–11 each have a fixture-driven test that never invokes a real deploy/send | 2 |
| R5-05 | Final doc consolidation | Sweep ALL docs (`README`, `ARCHITECTURE`, `docs/**`, `AGENTS.md`) for stale facts (test counts, sprint numbers, closed findings); unify sprint naming; finalize tracker | No doc cites an out-of-date count/sprint; every finding has a terminal disposition; `AGENTS.md` links this plan | 1 |

**R5 DoD:** F-15, F-17 closed; all program stories done; tracker finalized.

---
## 3. Program-level definition of done

- [ ] All findings F-01…F-17 have a terminal disposition in the tracker below (closed / rejected / rescoped).
- [ ] Full suite (live count per `AGENTS.md` Validation table — grows every sprint) + `ruff check packages/ tests/ templates/` green at every sprint closeout.
- [ ] Silent-capture audit: `except Exception` without classification = 0 outside the documented resilience allowlist (§1 F-01).
- [ ] Traversal / SSRF / secret-leak negative suite green.
- [ ] Resumable run and duplicate-lead dedupe demonstrated end-to-end.
- [ ] Feature-flag policy held: every new capability is behind a flag; legacy pipeline works with all flags off.
- [ ] Documentation consolidated and live — no stale status in README/ARCHITECTURE/docs.
- [ ] PoC status statement retained in README/ARCHITECTURE (honest positioning preserved).

## 4. Documentation consolidation (workstream across all sprints)

| Document | Action | Owned by |
|---|---|---|
| **`docs/plans/RECOVERY_PLAN.md`** | This file — plan + live tracker (§6); updated at every sprint closeout | Each closeout |
| `docs/architecture/ARCHITECTURE_REFACTOR_PROPOSAL.md` | Superseded banner → points here; fix stale "505 tests" snapshot; keep as historical audit | R0-05 |
| `ARCHITECTURE.md` | Pointer in "Trade-offs & known limitations" section → this plan | R0-05 |
| `README.md` | Pointer in "Production gap" + Documentation table → this plan | R0-05 |
| `AGENTS.md` | Add to Documentation list; note "live program status lives here" | R0-05 |
| `docs/contracts/`, `docs/gates/`, etc. | Any doc made stale by a sprint update (R3-05 updates `docs/gates/quality_gates.md`) | Each closeout |

Rule: **every sprint closeout includes a documentation pass.** No story lands without its docs being
reconciled.

## 5. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Refactor regresses the full test suite (~1,454 tests, growing) | Every story's acceptance includes full suite + ruff; structural refactors (R3) preserve flag semantics and behavior |
| "Production-grade" scope creep | Non-goals section is explicit; PoC status retained; new work must map to a finding |
| SQLite adoption friction in a filesystem-isolated test environment | Write-through mode keeps filesystem as source of truth; state DB is opt-in per phase |
| False findings resurface in future audits | "Rejected findings" section is permanent; future reviews verify, not trust, prior claims |
| Feature-flag proliferation | Flags are the repo's #1 convention; each new capability names its flag gate explicitly in the story table |

## 6. Live findings & sprint tracker

Update every disposition here at sprint closeout (evidence-gated, like the rest of the project).

> Process note: this plan and the R0-05 doc-pointer edits (README/AGENTS/ARCHITECTURE/proposal
> banner) landed in the working tree first and are committed by the owner at R0 closeout — the
> tracker below reflects implementation state, not git state.

| Sprint | Status | Evidence (commit / run) | Closed findings |
|---|---|---|---|
| R0 | ✅ CLOSED | `1558 passed` (2026-02 R0 closeout) | F-01, F-02, F-03, F-04, F-17 |
| R1 | ✅ CLOSED | `1623 passed`, ruff clean (2026-09 R1 closeout); resume demo: re-run of completed run skips all phases (`test_rerun_same_run_id_skips_completed_phases` logs) | F-07, F-08, F-12 |
| R2 | ⬜ Not started | — | — |
| R3 | ⬜ Not started | — | — |
| R4 | ⬜ Not started | — | — |
| R5 | ⬜ Not started | — | — |

| Finding | Disposition | Sprint | Closed when |
|---|---|---|---|
| F-01 | CLOSED | R0 | typed 7 files, terminal allowlist 20→13 |
| F-02 | CLOSED | R0 | safe_path + validate_slug + origin normalization |
| F-03 | CLOSED | R0 | token via env only |
| F-04 | CLOSED | R0 | ssrf_validator.py + wire into social/image |
| F-05 | OPEN | R2 | |
| F-06 | OPEN | R3 | |
| F-07 | CLOSED | R1 | phase_executions-backed skip/resume in run_pipeline; RUN_STATE_DB flag; stale-artifact cleanup |
| F-08 | CLOSED | R1 | state_db.py (sqlite3, write-through, WAL, schema_version migration) |
| F-09 | OPEN | R3 | |
| F-10 | OPEN | R4 | |
| F-11 | OPEN | R4 | |
| F-12 | CLOSED | R1 | logging_config.py JSON formatter + contextvars; CLI --json-logs; FailureContext on every failure path |
| F-13 | CLOSED (S2, pre-program) | — | already shipped |
| F-14 | RESCOPED | R2 | |
| F-15 | RESCOPED | R5 | |
| F-16 | REJECTED | — | already rejected |
| F-17 | CLOSED | R0 | README/AGENTS/proposal counts updated; plan linked from README/ARCHITECTURE/AGENTS |     
---