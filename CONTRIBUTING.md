# Contributing

Thanks for your interest in AutoWebDelivery. This is a **proof-of-concept** project, so
please keep contributions aligned with the existing architecture and its invariants.

## Ground rules

1. **Never fabricate business facts.** The pipeline's core promise is that no generated
   site may contain a business fact (name, address, phone, rating, review count, hours,
   service, price, certification, guarantee, award, testimonial, schedule) that does not
   come from the verified brief. Code, templates and prompts must stay facts-only.
2. **Feature flags protect backward compatibility.** New capabilities go behind a flag
   (default `False`); legacy paths are never removed without full replacement coverage.
3. **Do not weaken tests.** If a test asserts current behavior, update it only with an
   explicit rationale; better yet, add a test that asserts the *desired* behavior.
4. **No secrets, no local state.** Never commit secrets, `config/run_config.json`,
   `.kilo/`/agent state, or internal process documentation (see `SECURITY.md`).

## Architecture at a glance

```text
Phase 01 → 02 → 02.1 → 03 → 04 → 04.5 → 05 → 05.5 → 06 → 07 → 08 → 09 → 10 → 11
 Input    Discov Filter Score Brief Enrich Gen   Render  QA  Deploy OutRch Appr  Send  Track
```

Each phase reads persisted artifacts under `runs/<run_id>/` and writes its own outputs;
there is no shared in-memory state between phases. Key source of truth documents:

- `ARCHITECTURE.md` — technical deep dive (phases, generation paths, feature flags).
- `docs/contracts/` — artifact I/O schemas for all phases.
- `docs/gates/` — quality gate definitions.

## Local setup

```bash
# Requires Python 3.10+ and git. Dependencies are pinned in uv.lock.
uv sync                     # install locked deps
uv run python -m pytest tests/ -q          # full suite (~25 s)
uv run ruff check packages/ tests/ templates/
uv run ruff format --check packages/ tests/ templates/
```

> Note: CI installs the latest ruff, so local checks should also pass with
> `uvx ruff@latest check packages/ tests/ templates/`.

Without Playwright browsers installed, browser-evidence phases degrade non-blocking
(tests still pass). External integrations (Stitch AI, Google Maps, Vercel) are not
required for the test suite.

## Making changes

1. Fork the repo and create a branch.
2. Follow existing conventions: conventional commit messages (`fix:`, `feat:`, `test:`,
   `docs:`, `ci:`), atomic commits, explicit `git add <paths>` (never `git add -A`).
3. Add or update tests covering the change — especially for any failure-semantics or
   factual-safety behavior (fail-closed: missing mandatory evidence must never PASS).
4. Run the full validation battery before pushing:

```bash
uv run python -m pytest tests/ -q
uv run ruff check packages/ tests/ templates/
uvx ruff@latest check packages/ tests/ templates/
```

5. Open a pull request describing what changed, why, and what you verified.

## Author

Built and architected by [Iker Goñi](https://github.com/IkerGoni). Security issues:
see [SECURITY.md](SECURITY.md).