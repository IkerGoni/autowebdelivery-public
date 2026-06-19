# VNEXT-07 — Patch Plan Contract

**Feature flag:** `use_patch_phase` (default OFF)
**Schema origin:** VNEXT-07
**Schema version:** 1.0.0

## Purpose

The patch plan phase sits between evaluation (VNEXT-06) and deployment.
It analyses the evaluation report and produces a list of safe, deterministic
patches for localised failures — without invoking an LLM.

Hard-reject sites (verdict `"fail"`) are **never** patched. They receive an
empty patch list and should be regenerated instead.

## Artifact

**File:** `{output_dir}/{business_slug}/patch_plan.json`

### Shape

```json
{
  "schema_version": "1.0.0",
  "run_id": "...",
  "business_slug": "...",
  "generated_at": "<ISO timestamp, hash-offset from UTC now>",
  "verdict": "patchable",
  "original_verdict": "patchable",
  "patches": [
    {
      "id": "patch_001",
      "category": "missing_final_cta",
      "description": "Add final CTA section before closing body tag",
      "target": "html",
      "selector": "</body>",
      "action": "insert_before",
      "content": "<section class='cta'>...</section>",
      "safety": "approved"
    }
  ],
  "skipped_reasons": [],
  "internal": {
    "flag": "use_patch_phase",
    "schema_origin": "VNEXT-07"
  }
}
```

## Approved Patch Categories

**Only these five categories may be emitted.** Any other category is silently
skipped.

| Category | Target | Action | Description |
|---|---|---|---|
| `missing_final_cta` | html | insert_before | Insert a CTA section before `</body>` |
| `forbidden_claim_removal` | html | replace | Replace forbidden claim text with neutral fallback |
| `mobile_overflow_css_fix` | css | insert_css | Add `overflow-x:hidden` to body/main |
| `spacing_adjustment` | css | insert_css | Add consistent section padding |
| `cta_link_correction` | html | replace | Fix CTA links with bare `#` href |

## Trigger Rules

| Category | Trigger Condition |
|---|---|
| `missing_final_cta` | conversion score < 50, or no action text/buttons/forms found |
| `forbidden_claim_removal` | Forbidden claim text found in HTML (from creative_spec content_policy or evaluation_report) |
| `mobile_overflow_css_fix` | mobile_experience score < 50, or in patchable_failures |
| `spacing_adjustment` | spacing score < 50, or in patchable_failures |
| `cta_link_correction` | CTA link with `href="#"` found in HTML |

## Safety Rules

1. **Hard-reject = no patches.** Sites with verdict `"fail"` get empty patch list.
2. **Only approved categories.** Unknown categories are silently skipped.
3. **Idempotent application.** Applying the same patch twice is a no-op.
4. **Deterministic IDs.** Patch IDs follow `patch_{NNN}` format, assigned sequentially.
5. **Pseudo-deterministic timestamps.** `generated_at` uses current UTC time with a second offset derived from SHA-256(run_id:slug), stable within a run but not fully reproducible across invocations.

## Upstream Dependencies

- `evaluation_report.json` (VNEXT-06) — verdict, dimensions, patchable_failures
- `creative_spec.json` (VNEXT-04) — content_policy.forbidden_claims (optional)

## Downstream Consumers

- HTML patch engine (`packages/patching/html_patch_engine.py`)
- CSS patch engine (`packages/patching/css_patch_engine.py`)
- Pipeline integration via `use_patch_phase` feature flag

## Module Layout

```
packages/patching/
├── __init__.py
├── patch_plan.py          # build_patch_plan(), write_patch_plan()
├── html_patch_engine.py   # apply_html_patches()
└── css_patch_engine.py    # apply_css_patches()

tests/patching/
├── __init__.py
├── test_patch_plan.py
├── test_html_patch_engine.py
└── test_css_patch_engine.py
```

## Key Functions

### `patch_plan.py`

```python
def build_patch_plan(
    evaluation_report: dict,
    creative_spec: dict | None = None,
    *,
    run_id: str,
    business_slug: str,
) -> dict

def write_patch_plan(plan: dict, output_dir: str | Path, business_slug: str) -> str
```

### `html_patch_engine.py`

```python
def apply_html_patches(html: str, patches: list[dict]) -> str
```

### `css_patch_engine.py`

```python
def apply_css_patches(html: str, patches: list[dict]) -> str
```

## Edge Cases

| Scenario | Behavior |
|---|---|
| Empty or missing `_site_html` | Patch planners skip HTML-dependent checks; only dimension scores trigger patches |
| No `</body>` tag | `missing_final_cta` patch silently skipped |
| `overflow-x:hidden` already present | `mobile_overflow_css_fix` patch skipped (idempotency check) |
| Multiple forbidden claims | Each claim generates a separate patch with unique ID |
| Verdict `"pass"` with no patches | Returns original verdict, empty patch list |
| No `<style>` block for CSS patches | Engine injects new `<style>` before `</head>` or `</body>` |

## Troubleshooting

**Patches not being applied?**
1. Verify feature flag: `use_patch_phase` must be enabled
2. Check verdict: hard-reject (`"fail"`) returns empty patch list by design
3. Inspect `_site_html`: patch planners require raw HTML for accurate detection
4. Verify dimension scores: patches trigger on score < 50 or patchable_failures list

**Forbidden claims not detected?**
1. Check `creative_spec.content_policy.forbidden_claims` is populated
2. Fallback: check `evaluation_report.dimensions.factual_safety.notes` contains "forbidden claims found:"
3. Verify HTML contains claim text (case-insensitive match)

**Timestamp appears different on re-run?**
Expected — timestamp uses current UTC time with hash-derived offset, not fully deterministic across invocations.
