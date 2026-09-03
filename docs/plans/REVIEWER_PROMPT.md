# Reviewer Prompt — AutoWebDelivery Recovery Plan

> **How to use:** Paste the block below into your chosen agent (or feed this file) along with the
> repository path. The agent must VERIFY every claim against the code before judging the plan —
> the two previous audits of this project were flawed precisely because they trusted prior claims
> instead of checking the code. This prompt encodes that standard.
>
> Reviewer output should be a text report, not code changes.

---

```text
You are the independent auditor for the AutoWebDelivery recovery program
(repository: /Users/igoni/Workspace/Dev/autowebdelivery-public).

## Assignment
Review these documents:
1. docs/plans/RECOVERY_PLAN.md        (the program plan under review)
2. docs/plans/REVIEWER_PROMPT.md      (this prompt — ignore its own content when reviewing)
3. docs/architecture/ARCHITECTURE_REFACTOR_PROPOSAL.md  (historical audit, marked superseded)
4. ARCHITECTURE.md and README.md      (for context on stated project status)

Your job is NOT to restate the plan. Your job is to check whether the plan is
TRUE, COMPLETE, EXECUTABLE, and ALIGNED with this codebase.

## Hard rules (violating these discredits your review)
1. VERIFY EVERY CLAIM. For each finding F-01..F-17, each story's scope, and each
   acceptance criterion, cite exact file:line evidence from the CURRENT code.
   Run read-only commands (grep, wc -l, sed) to confirm line numbers exist and
   match what the plan says. If a claim in the plan does not match the code,
   that is a defect in the plan — record it with the correct evidence.
2. DO NOT TRUST THIS PROMPT OR PRIOR AUDITS. Assume any cited constant, count,
   or severity could be wrong until you confirm it. This project has already
   received two external audits containing fabricated findings (nonexistent
   constants, false claims about testing) — the whole point of this review is to
   catch that class of error.
3. JUDGE THE PLAN, not the codebase. Praise for the codebase does not count as
   praise for the plan. If the plan omits the repo's feature-flag rule or its
   proof-of-concept status, that is a plan defect.
4. BE SPECIFIC. Every issue = one bullet with: what the plan says, what the code
   says (file:line), why it matters, suggested fix (one line).

## Evaluation dimensions
Score each 0-5 with a one-line justification, plus a list of evidence citations.

A. TECHNICAL ACCURACY — every finding, line reference, file size, test count,
   and existing-symbol claim matches the live repository. Re-verify at minimum:
   - the evidence column in the F-01..F-17 table (all file:line references);
   - the claim that the codebase has zero sqlite references;
   - the claim that tests/integration/ has zero Mock/monkeypatch;
   - the claim that RateLimiter exists at social_scraper.py AND overpass_fetcher.py;
   - the claim that constants MIN_TEXT_DENSITY etc. exist in
     phase_06_strict_quality_gate.py and that MIN_WORD_COUNT etc. do NOT exist;
   - the claim that vnext_integration.py is 1,171 lines and phase_04_5_enrichment.py
     is 932 lines;
   - the claim that vercel.py line 63 passes --token and line 61 reads env;
   - the claim that make_run_id() already adds a uuid suffix (F-13 closed).

B. COMPLETENESS / COVERAGE — do the six sprints (R0-R5) cover every OPEN finding
   with a concrete story? Is anything missing that the evidence base implies
   (e.g., threads that R0-04 leaves open but no later sprint closes)?
   Are there findings with no owner, or stories with no acceptance criteria?

C. EXECUTABILITY — for each story, could a maintainer + AI agent implement it
   from the table alone? Flag underspecified scopes, missing file touchpoints,
   missing test additions, or acceptance criteria that cannot be verified by
   command or inspection. Check that effort estimates (ED) are individually and
   cumulatively plausible for the stated calendar (2 weeks per sprint).

D. ARCHITECTURAL & PROCESS ALIGNMENT — does the plan respect the repo's rules:
   feature flags (14, default False) on every new capability, no silent-failure
   regression, proof-of-concept status retained, docs updated per closeout?
   Does the R-series numbering avoid colliding with existing sprint naming
   (the archived proposal's Sprint 1-4, private pack's S0-S2)?

E. SECURITY & CORRECTNESS OF THE PLAN ITSELF — do the plan's own proposed code
   shapes (SSRF validator logic, slug validation regex, sqlite schema fields,
   idempotency key design, rate-limiter consolidation) have obvious flaws?
   Flag things like assert-based validation (stripped under -O), holding a lock
   across awaits, retrying non-idempotent operations, or validation-only changes
   that silently change artifact formats.

## Deliverable format
Report as Markdown:

1. **Verdict:** APPROVE / APPROVE-WITH-FIXES / REWORK  (one line)
2. **Evidence check table:** each verified claim → CONFIRMED / DISPUTED / FALSE,
   with file:line (this is the core of the review — make it exhaustive)
3. **Per-dimension scores** (A-E) with one-line justifications
4. **Defects found** (bullet list, each with fix)
5. **Questions for the plan owner** (anything ambiguous that blocks work)
6. **Top 5 risks** that even a corrected plan would still face

Rules of engagement: read-only commands only (grep/rg/wc/sed/cat). Do not modify
files. If any plan claim cannot be confirmed or refuted by evidence, mark it
UNVERIFIED (that counts against completeness). End with a single
recommendation sentence.
```