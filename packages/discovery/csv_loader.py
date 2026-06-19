"""CSV-based lead loader for Phase 02.

Loads leads from CSV files and converts them to Phase 02 raw place format.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default CSV column mapping to RawPlace fields
DEFAULT_COLUMN_MAP = {
    "business_name": "business_name",
    "area": "area",
    "source_url": "source_url",
    "website_url": "website",
    "website_weakness": "website_weakness",
    "visible_contact_channel": "contact_channel",
    "why_likely_buys": "why_likely_buys",
    "preview_angle": "preview_angle",
    "confidence": "confidence",
    "rating": "rating",
    "review_count": "review_count",
    "phone": "phone",
    "address": "address",
    "maps_url": "maps_url",
}


def load_leads_from_csv(
    csv_path: str | Path,
    *,
    column_map: dict[str, str] | None = None,
    max_results: int | None = None,
) -> list[dict[str, Any]]:
    """Load leads from a CSV file.

    Args:
        csv_path: Path to CSV file
        column_map: Optional mapping from CSV column names to RawPlace field names.
                    Defaults to DEFAULT_COLUMN_MAP.
        max_results: Optional limit on number of leads to return.

    Returns:
        List of raw place dicts matching Phase 02 input contract.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        logger.warning("CSV file not found: %s", csv_path)
        return []

    mapping = column_map or DEFAULT_COLUMN_MAP
    leads: list[dict[str, Any]] = []

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            if max_results and idx >= max_results:
                break
            lead = _map_csv_row(row, mapping, idx)
            leads.append(lead)

    logger.info("Loaded %d leads from %s", len(leads), csv_path)
    return leads


def _map_csv_row(
    row: dict[str, str],
    mapping: dict[str, str],
    index: int,
) -> dict[str, Any]:
    """Map a CSV row to a raw place dict."""
    result: dict[str, Any] = {}

    for csv_col, raw_field in mapping.items():
        value = row.get(csv_col, "").strip()
        if value:
            result[raw_field] = value

    # Ensure required fields have defaults
    result.setdefault("business_name", f"Business {index + 1}")
    result.setdefault("category", "")
    result.setdefault("rating", 0.0)
    result.setdefault("review_count", 0)
    result.setdefault("address", "")
    result.setdefault("phone", "")
    result.setdefault("website", "")
    result.setdefault("maps_url", "")
    result.setdefault("source_url", "")

    # Convert numeric fields
    try:
        result["rating"] = float(result.get("rating", 0.0))
    except (ValueError, TypeError):
        result["rating"] = 0.0

    try:
        result["review_count"] = int(result.get("review_count", 0))
    except (ValueError, TypeError):
        result["review_count"] = 0

    return result
