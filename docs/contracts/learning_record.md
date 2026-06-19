# Learning Record Contract (v1.0.0)

> **Status:** VNEXT-09 — feature-flagged (default OFF).
> **Schema version:** `1.0.0`
> **Owner:** Learning Record module (`packages/learning/`)
> **Consumers (planned):** Analytics pipelines, outcome tracking, A/B testing, conversion optimization.

## Purpose

`learning_record.json` is the **append-only learning record** artifact for a
single lead. It connects lead features, generation features, evaluation
results, sales package data, and outcome into a single structured record that
supports downstream analytics.

Goals:

1. **Store one learning record per lead** connecting all pipeline stages.
2. Support **append-only outcome tracking** — events are never deleted.
3. Enable **analytics grouping** by niche, score band, creative strategy,
   channel, and outcome category.
4. Maintain **provenance and confidence** on every extracted value.
5. Work with **partial data** — the record can be created before all upstream
   artifacts are available.

## Feature flag

This module is gated behind `use_learning_record_contract` (default OFF).
When the flag is off, no learning record is generated. The module is
**additive** — it does not modify existing pipeline output.

## Schema version

The artifact always carries a top-level `schema_version` string in SemVer
form. The current value is `"1.0.0"`. Breaking changes to field names, types,
or semantics require a major-version bump; additive fields are allowed under
minor versions.

## Top-level shape

```json
{
  "schema_version": "1.0.0",
  "run_id": "run_001",
  "business_slug": "north-dallas-mobile-detailing",
  "generated_at": "2025-04-15T12:34:56+00:00",
  "lead_features": { ... },
  "generation_features": { ... },
  "evaluation_summary": { ... },
  "sales_package_ref": { ... },
  "outcome": {
    "status": "pending",
    "events": [],
    "last_updated": null
  },
  "analytics_keys": {
    "niche": "auto_detailing",
    "score_band": "high",
    "creative_strategy": "missing_website_upgrade",
    "channel": "phone",
    "outcome_category": "pending"
  },
  "missing_data": [],
  "internal": {
    "flag": "use_learning_record_contract",
    "schema_origin": "VNEXT-09"
  }
}
```

### lead_features

Lead-level features extracted from `business_profile.json` and
`market_profile.json`. Each field carries a provenance envelope
(`value`, `source`, `confidence`).

Example provenance envelope:

```json
{
  "value": "Auto Detailing Service",
  "source": "selected_for_preview.json",
  "confidence": "verified"
}
```

| Field | Source | Confidence |
|---|---|---|
| `category` | `selected_for_preview.json` (fallback: `market_profile.json`) | verified |
| `area` | `selected_for_preview.json` (fallback: `business_profile` address → `market_profile`) | verified |
| `rating` | `business_profile.json` | verified |
| `review_count` | `business_profile.json` | verified |
| `website_status` | `market_profile.json` | verified |

**Extraction notes:**
- `category` is first looked up in `business_profile.verified_facts.category`, then falls back to `market_profile.category`.
- `area` tries `business_profile.verified_facts.area` → `business_profile.verified_facts.address` → `market_profile.area`.
- Fields are only included when a non-empty value is found; absent fields are omitted from the record entirely.

### generation_features

Generation-level features from `creative_spec.json` and
`stitch_prompt_contract.json`.

| Field | Source | Confidence |
|---|---|---|
| `template_family` | `creative_spec.json` | inferred |
| `sections` | `creative_spec.json` | inferred |
| `prompt_hash` | `stitch_prompt_contract.json` | verified |
| `compiler_version` | `stitch_prompt_contract.json` | verified |

### evaluation_summary

Summary fields from `evaluation_report.json`.

| Field | Source | Confidence |
|---|---|---|
| `overall_score` | `evaluation_report.json` | verified |
| `verdict` | `evaluation_report.json` | verified |
| `factual_safety` | `evaluation_report.json` | verified |
| `hard_failures` | `evaluation_report.json` | verified |

### sales_package_ref

Reference to the sales package.

| Field | Type | Notes |
|---|---|---|
| `has_sales_package` | bool | `True` when a non-empty `sales_package` dict was provided to `build_learning_record` |
| `offer_price` | provenance | Price from `sales_package.offer.price`. Omitted if no sales package or no price. |

### outcome

Append-only outcome tracking. Events are never deleted.

```json
{
 "status": "preview_sent",
 "events": [
   {"event_type": "created", "timestamp": "2026-04-15T10:00:00+00:00"},
   {"event_type": "preview_sent", "timestamp": "2026-04-15T11:00:00+00:00"}
 ],
 "last_updated": "2026-04-15T11:00:00+00:00"
}
```

Events with details:

```json
{
 "event_type": "owner_responded",
 "timestamp": "2026-04-15T12:00:00+00:00",
 "details": {"response": "interested", "channel": "email"}
}
```

**Valid event types:**

| Event | Description |
|---|---|
| `created` | Learning record created |
| `preview_sent` | Preview sent to owner |
| `owner_viewed` | Owner viewed the preview |
| `owner_responded` | Owner responded |
| `sale_completed` | Sale completed |
| `sale_declined` | Owner declined |
| `follow_up_scheduled` | Follow-up scheduled |
| `expired` | Opportunity expired |

**Outcome categories (derived from latest event):**

| Category | Condition |
|---|---|
| `pending` | No events |
| `in_progress` | Any non-terminal event |
| `converted` | Latest event is `sale_completed` |
| `lost` | Latest event is `sale_declined` or `expired` |

### analytics_keys

Pre-computed grouping keys for analytics queries.

| Key | Values | Source |
|---|---|---|
| `niche` | Lowercase, underscored category | `lead_features.category` |
| `score_band` | `low` / `medium` / `high` / `premium` / `unknown` | `evaluation_summary.overall_score` |
| `creative_strategy` | `missing_website_upgrade` / `website_redesign` / `unknown` | `lead_features.website_status` |
| `channel` | `phone` (default) | `sales_package` |
| `outcome_category` | `pending` / `in_progress` / `converted` / `lost` | latest outcome event |

**Score band thresholds:**

| Band | Score range |
|---|---|
| `low` | < 50 |
| `medium` | 50 ≤ score < 70 |
| `high` | 70 ≤ score < 85 |
| `premium` | ≥ 85 |
| `unknown` | score is None |

### missing_data

A list of top-level section names that contain no meaningful data. This
enables downstream consumers to identify records with incomplete information.

**Checked sections:** `lead_features`, `generation_features`, `evaluation_summary`,
`sales_package_ref`.

A section is listed as missing when:
- `lead_features`, `generation_features`, `evaluation_summary`: the dict is empty or all field values are empty/null.
- `sales_package_ref`: `has_sales_package` is `False` (i.e. an empty dict was passed).

## Troubleshooting

### Record has empty `lead_features`
- Verify `business_profile.verified_facts` contains `category`, `area`, `rating`, `review_count` with non-empty `value` keys.
- If using `market_profile`, ensure `category` and `area` have `value` keys.
- The extractor silently skips fields with empty/None values — it does not raise.

### `append_outcome_event` raises `ValueError`
- Check that `event_type` is one of the 8 valid types (see table above). Common typo: `sale_complete` → should be `sale_completed`.

### `outcome_category` stays `in_progress` after terminal event
- `get_outcome_category` derives state from the **latest** event only. If a `follow_up_scheduled` event was appended after `sale_completed`, the category becomes `in_progress`. Events are append-only — you cannot remove or reorder them. Ensure terminal events (`sale_completed`, `sale_declined`, `expired`) are always appended last.

### `generated_at` changes between runs
- This should not happen. `generated_at` is deterministic from `run_id + business_slug` (SHA-256 based). If it changes, one of those two inputs changed.

### `score_band` shows `unknown` despite a score being present
- `overall_score` must be a numeric value inside a provenance envelope (e.g. `{"value": 82, "source": "...", "confidence": "..."}`). A bare number or a missing `value` key will result in `unknown`.

### internal

Metadata about the contract itself:

```json
{
  "flag": "use_learning_record_contract",
  "schema_origin": "VNEXT-09"
}
```

## Public API

### `learning_record.py`

```python
def build_learning_record(
    business_profile: dict | None = None,
    market_profile: dict | None = None,
    creative_spec: dict | None = None,
    evaluation_report: dict | None = None,
    sales_package: dict | None = None,
    prompt_contract: dict | None = None,
    config: dict | None = None,
    *,
    run_id: str,
    business_slug: str,
) -> dict:
    """Build a learning record from upstream artifacts."""

def write_learning_record(
    record: dict,
    output_dir: str | Path,
    business_slug: str,
) -> str:
    """Write to <output_dir>/<business_slug>/learning_record.json."""
```

### `outcome_events.py`

```python
def append_outcome_event(
    record: dict,
    event_type: str,
    details: dict | None = None,
) -> dict:
    """Append an outcome event (append-only). Raises ValueError for invalid types.

    The record is mutated in-place and returned. Each call updates
    ``outcome.status``, ``outcome.last_updated``, and
    ``analytics_keys.outcome_category``.

    Parameters
    ----------
    record:
        The learning record dict (mutated and returned).
    event_type:
        One of: ``created``, ``preview_sent``, ``owner_viewed``,
        ``owner_responded``, ``sale_completed``, ``sale_declined``,
        ``follow_up_scheduled``, ``expired``.
    details:
        Optional dict of event-specific metadata (e.g. ``{"response": "interested"}``
        for ``owner_responded``). Stored as the ``details`` key on the event.

    Raises
    ------
    ValueError:
        If *event_type* is not a valid event type.
    """

def get_outcome_category(record: dict) -> str:
    """Derive outcome_category from the latest event."""
```

## Design decisions

1. **Append-only events:** Events are never deleted or modified after appending.
2. **All upstream artifacts optional:** The record can be created with just
   `run_id` and `business_slug`.
3. **No prompt text stored:** Only `prompt_hash` and `compiler_version` — no
   raw prompt content.
4. **Deterministic timestamp:** `generated_at` is deterministic from
   `run_id + business_slug`.
5. **Forbidden claims:** The `_FORBIDDEN_PUBLIC_CLAIMS` blocklist is enforced
   — none of these categories appear in the record.
6. **Feature-flagged:** Gated behind `use_learning_record_contract` (default
   OFF). Additive — does not affect existing pipeline behavior.

## File layout

```
packages/learning/
├── __init__.py
├── learning_record.py      # Build + write learning records
└── outcome_events.py        # Append-only outcome tracking

tests/learning/
├── __init__.py
├── test_learning_record.py  # ≥25 tests for record building
└── test_outcome_events.py   # Tests for outcome tracking

docs/contracts/
└── learning_record.md       # This file
```
