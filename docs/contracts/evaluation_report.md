# Evaluation Report Contract — VNEXT-06

**Status:** Active  
**Schema Version:** 1.0.0  
**Feature Flag:** `use_structured_evaluation_report` (default OFF)  
**Origin:** VNEXT-06 Structured Evaluation Report

## Overview

The structured evaluation report evaluates a generated website against 12 quality
dimensions using deterministic, heuristic-based checks (no LLM). It produces an
`evaluation_report.json` that the existing quality gate can optionally consume.

This feature is **additive** — it does not modify the existing quality gate
(`phase_06_strict_quality_gate.py`) or premium scorecard (`premium_quality_scorecard.py`).

## Output Shape

```json
{
  "schema_version": "1.0.0",
  "run_id": "string — pipeline run identifier",
  "business_slug": "string — business slug",
  "generated_at": "ISO 8601 timestamp (deterministic from run_id + slug)",
  "dimensions": {
    "<dimension_name>": {
      "score": "integer 0–100",
      "status": "pass | warn | patchable | fail",
      "notes": "human-readable explanation"
    }
  },
  "overall_score": "float — simple average of all dimension scores",
  "verdict": "pass | patchable | fail",
  "hard_failures": ["list of hard-failure dimension names"],
  "patchable_failures": ["list of patchable dimension names"],
  "creative_spec_alignment": {
    "sections_present": ["list of detected section names"],
    "sections_missing": ["list of required but missing sections"],
    "cta_present": "boolean",
    "forbidden_claims_found": ["list of found forbidden claims"],
    "missing_data_handled_correctly": "boolean"
  },
  "missing_data": ["list of missing data field names from creative_spec"],
  "internal": {
    "flag": "use_structured_evaluation_report",
    "schema_origin": "VNEXT-06"
  }
}
```

## 12 Quality Dimensions

| Dimension | What It Checks | Category |
|---|---|---|
| `hierarchy` | H1/H2/H3 nesting, heading order | Structure |
| `branding` | CSS variables, consistent colors | Visual |
| `typography` | Font declarations, line-height, font-size | Visual |
| `spacing` | Padding, margin, gap, max-width | Visual |
| `imagery` | `<img>` tags, alt text, backgrounds, SVGs | Content |
| `trust` | Phone, email, address, schema.org markup | Content |
| `conversion` | CTA buttons, forms, action-oriented text | Content |
| `accessibility` | Lang attribute, alt text, ARIA, semantic HTML | **Hard** |
| `originality` | Custom classes, custom CSS, unique IDs, animations | Visual |
| `mobile_experience` | Viewport meta, media queries, responsive units | Structure |
| `factual_safety` | Forbidden claims detection | **Hard** |
| `local_relevance` | Business name, address, phone, local schema | Content |

### Scoring Rubric

Each dimension returns a score from 0–100. Point breakdowns per dimension:

**`hierarchy`** (H1 uniqueness: 40, H2 presence: 30, H3 presence: 15, heading order: 15)
- 1 H1 = 40pts; multiple H1 = 20pts; no H1 = 0pts
- ≥2 H2 = 30pts; 1 H2 = 15pts; no H2 = 0pts
- Any H3 = 15pts; H2 before H3 = 15pts order bonus

**`branding`** (CSS vars: 40, hex colors: 30, color reuse: 30)
- ≥4 CSS custom properties = 40pts; ≥2 = 25pts; any = 10pts
- ≥2 hex colors = 30pts; 1 = 15pts
- Repeated color = 30pts; no reuse = 10pts

**`typography`** (font-family: 35, line-height: 30, font-size: 20, font-weight: 15)
- ≥2 font-family decls = 35pts; 1 = 20pts
- Any line-height = 30pts
- ≥2 font-size decls = 20pts; 1 = 10pts
- Any font-weight = 15pts

**`spacing`** (padding: 35, margin: 35, gap: 15, max-width: 15)
- ≥4 padding decls = 35pts; ≥2 = 25pts; any = 10pts
- ≥4 margin decls = 35pts; ≥2 = 25pts; any = 10pts
- Any gap = 15pts (else 5pts); any max-width = 15pts (else 5pts)

**`imagery`** (img tags: 30, alt coverage: 35, bg/gradients: 20, SVG: 15)
- ≥3 img tags = 30pts; ≥1 = 15pts
- Alt text ratio × 35pts
- Background-image or gradient = 20pts (else 5pts)
- Any SVG = 15pts (else 5pts)

**`trust`** (phone: 25, email: 25, address: 25, org markup: 25)
- Phone pattern match = 25pts
- Email pattern match = 25pts
- Address keyword match = 25pts
- schema.org / LocalBusiness markup = 25pts (0pts if absent — no partial credit)

**`conversion`** (CTA buttons: 30, forms: 25, inputs: 20, action text: 25)
- ≥2 CTA-style buttons = 30pts; 1 = 20pts
- Any `<form>` = 25pts
- Any `<input>` = 20pts (else 5pts)
- ≥2 action phrases = 25pts; 1 = 15pts

**`accessibility`** (lang: 10, alt: 20, ARIA: 20, semantic: 30, role: 10, tabindex: 10)
- `lang` on `<html>` = 10pts
- All imgs have alt = 20pts; some = 10pts; no images = 10pts
- Any aria-label/aria-labelledby = 20pts
- ≥4 semantic tags = 30pts; ≥2 = 20pts; any = 10pts
- Any role = 10pts (else 3pts); any tabindex = 10pts (else 3pts)

**`originality`** (custom classes: 25, custom CSS: 25, unique IDs: 25, animations: 25)
- ≥5 non-framework classes = 25pts; ≥2 = 15pts; any = 5pts
- ≥10 CSS rule blocks = 25pts; ≥5 = 15pts; any = 5pts
- ≥3 unique IDs = 25pts; ≥1 = 15pts
- @keyframes or animation = 25pts (else 5pts)

**`mobile_experience`** (viewport: 30, media queries: 30, responsive units: 20, flex/grid: 20)
- Viewport with device-width = 30pts; viewport without = 15pts
- ≥2 @media queries = 30pts; 1 = 20pts
- ≥3 responsive units (rem/em/vw/vh) = 20pts; any = 10pts
- display:flex or display:grid = 20pts (else 5pts)

**`factual_safety`** (100 − 30× per forbidden claim found)
- Starts at 100; each found claim deducts 30pts (floor 0)

**`local_relevance`** (slug: 30, address: 30, phone: 20, schema: 20)
- Business slug parts in text = 30pts
- City/State/ZIP pattern = 30pts; address keyword = 20pts
- Phone pattern = 20pts (else 5pts)
- LocalBusiness schema = 20pts (else 5pts)

## Verdict Logic

| Verdict | Condition |
|---|---|
| `pass` | No hard failures AND overall_score >= 60 |
| `patchable` | Has patchable failures but no hard failures, OR 40 <= overall < 60 |
| `fail` | Has hard failures (factual_safety < 50 or accessibility < 50) OR overall < 40 |

### Hard-Failure Dimensions
- `factual_safety` — score < 50 triggers hard failure
- `accessibility` — score < 50 triggers hard failure

### Patchable Dimensions
- `imagery`, `originality`, `typography`, `spacing`, `branding` — score < 50 triggers patchable

## Public API

### `evaluate_website(site_html, creative_spec, config, *, run_id, business_slug) -> dict`

Evaluates a website and returns the full report dict.

**Parameters:**
- `site_html` (str): Full HTML of the generated site
- `creative_spec` (dict | None): Optional spec with `required_sections`, `forbidden_claims`, `missing_data`
- `config` (dict | None): Optional config. Recognized keys:
  - `forbidden_claims` (list[str]): Overrides the default forbidden claims list
  - `hard_fail_score_threshold` (int): Overrides the default hard-failure threshold (50)
- `run_id` (str, keyword-only): Pipeline run identifier
- `business_slug` (str, keyword-only): Business slug

### `write_evaluation_report(report, output_dir) -> Path`

Writes the report dict as `evaluation_report.json` in the given directory.

## Spec Alignment Module

### `check_spec_alignment(html, creative_spec) -> dict`

Checks alignment between generated HTML and creative_spec directives.

**Detected sections:** hero, services, about, contact, cta, testimonials, gallery, pricing, faq, footer, header, navigation

**Forbidden claims checking:** Strips HTML tags, performs case-insensitive text search.

**Missing data handling:** Detects unhandled placeholders (`{{field}}`, `[[field]]`, `[field]`, `__missing_field__`).

## Default Forbidden Claims

When no `forbidden_claims` list is provided via `config` or `creative_spec`, the following defaults are used:

```python
DEFAULT_FORBIDDEN_CLAIMS = [
    "guaranteed",
    "#1 rated",
    "best in the world",
    "100% effective",
    "miracle cure",
    "FDA approved",
]
```

## Dimension Status

Each dimension also carries a per-dimension `status` field (separate from the overall verdict):

| Status | Condition |
|---|---|
| `fail` | Hard-failure dimension (accessibility, factual_safety) with score < 50 |
| `patchable` | Patchable dimension (imagery, originality, typography, spacing, branding) with score < 50 |
| `warn` | Score < 60 but not in a hard/patchable dimension |
| `pass` | Score >= 60 |

## Deterministic Timestamp

The `generated_at` field is derived deterministically from `run_id + business_slug` using SHA-256. The first 8 hex characters of the hash produce a 0–255 second offset applied to the current UTC time. The same inputs always produce the same timestamp within a session.

## Feature Flag

The structured evaluation report is gated behind the `use_structured_evaluation_report` flag, which defaults to OFF. When OFF, the existing quality gate and premium scorecard operate unchanged. To enable:

```python
# In pipeline config
config["use_structured_evaluation_report"] = True
```

## File Locations

| File | Purpose |
|---|---|
| `packages/evaluation/__init__.py` | Package marker |
| `packages/evaluation/website_evaluator.py` | Main evaluator with 12 dimension scorers |
| `packages/evaluation/spec_alignment.py` | Creative spec alignment checks |
| `tests/evaluation/__init__.py` | Test package marker |
| `tests/evaluation/test_website_evaluator.py` | Evaluator tests |
| `tests/evaluation/test_spec_alignment.py` | Spec alignment tests |
| `docs/contracts/evaluation_report.md` | This document |

## Troubleshooting

### Common Low-Score Patterns

| Symptom | Likely Cause | Fix |
|---|---|---|
| `hierarchy` = 0 | Missing H1 or all headings | Ensure template outputs exactly one `<h1>` and multiple `<h2>` |
| `branding` < 30 | No CSS custom properties | Add CSS variables (`--primary-color: #xxx`) to `<style>` block |
| `accessibility` < 20 | No `lang` attribute, no ARIA | Add `lang="en"` to `<html>`, add `aria-label` to nav/forms |
| `factual_safety` < 50 | Forbidden claims in generated text | Check prompt templates for absolute claims; add to blocklist |
| `local_relevance` = 0 | Business name not in HTML | Pass correct `business_slug`; ensure it appears in page text |
| `mobile_experience` < 30 | No viewport meta or media queries | Add `<meta name="viewport" content="width=device-width">` |
| `trust` ≤ 25 | Missing schema.org markup | Add `itemtype="https://schema.org/LocalBusiness"` to container |
| `originality` < 20 | Only framework classes used | Add project-specific class names (e.g., `class="acme-hero"`) |

### Debugging a Failing Report

1. Read `evaluation_report.json` → check `hard_failures` list
2. For each failed dimension, check `dimensions.<name>.notes` for specific failure reasons
3. Check `creative_spec_alignment.sections_missing` for required sections not found
4. Check `creative_spec_alignment.forbidden_safety_found` for blocked claims
5. If `missing_data_handled_correctly` is `false`, search HTML for raw `{{placeholder}}` markers

## Backward Compatibility

- No existing files are modified
- No changes to `phase_06_strict_quality_gate.py`
- No changes to `premium_quality_scorecard.py`
- Feature flag defaults to OFF — zero impact unless explicitly enabled
