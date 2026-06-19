"""Hours extractor for business enrichment - parses structured hours from various formats."""

from __future__ import annotations

import re
from typing import Any


DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_MAP = {d.lower(): d for d in DAYS}
DAY_ABBREV_MAP = {
    "mon": "Monday",
    "tue": "Tuesday",
    "wed": "Wednesday",
    "thu": "Thursday",
    "fri": "Friday",
    "sat": "Saturday",
    "sun": "Sunday",
}


def parse_hours_text(hours_text: str) -> dict[str, str]:
    """Parse hours from various formats into structured dict.

    Accepts formats like:
    - "Mon-Fri: 9am-5pm"
    - "Monday: 9:00 AM - 5:00 PM"
    - "9am-5pm Mon-Fri"
    """
    result: dict[str, str] = {}

    def normalize_day(day_str: str) -> str:
        """Normalize day abbreviation to full name."""
        day_lower = day_str.lower()[:3]
        return DAY_ABBREV_MAP.get(day_lower, day_str.title())

    # Pattern 1: Day range with times (Mon-Fri: 9am-5pm)
    day_range_pattern = r"(\w+)(?:-(\w+))?:\s*([\d:]+)\s*(?:am|pm)\s*[-–]\s*([\d:]+)\s*(?:am|pm)"

    for match in re.finditer(day_range_pattern, hours_text, re.IGNORECASE):
        start_day = match.group(1)
        end_day = match.group(2) if match.group(2) else start_day
        start_time = match.group(3)
        end_time = match.group(4)

        start_norm = normalize_day(start_day)
        end_norm = normalize_day(end_day)

        # Find all days in range
        try:
            start_idx = DAYS.index(start_norm)
            end_idx = DAYS.index(end_norm)
            for idx in range(start_idx, end_idx + 1):
                result[DAYS[idx]] = f"{start_time}-{end_time}"
        except ValueError:
            # Fallback if day not found
            result[start_norm] = f"{start_time}-{end_time}"
            result[end_norm] = f"{start_time}-{end_time}"

    # Pattern 2: Individual days (Monday 9am-5pm, Tuesday 9am-5pm)
    if not result:
        individual_pattern = r"(\w+):\s*([\d:]+)\s*(?:am|pm)\s*[-–]\s*([\d:]+)\s*(?:am|pm)"
        for match in re.finditer(individual_pattern, hours_text, re.IGNORECASE):
            day = DAY_MAP.get(match.group(1).lower(), match.group(1).title())
            result[day] = f"{match.group(2)}-{match.group(3)}"

    # Pattern 3: Closed detection
    closed_pattern = r"(\w+):\s*(?:closed)"
    for match in re.finditer(closed_pattern, hours_text, re.IGNORECASE):
        day = DAY_MAP.get(match.group(1).lower(), match.group(1).title())
        result[day] = "Closed"

    return result


def format_hours_display(hours_dict: dict[str, str]) -> str:
    """Convert structured hours to human-readable display format."""
    if not hours_dict:
        return "Hours not listed in source data"

    lines = []
    for day in DAYS:
        if day in hours_dict:
            lines.append(f"{day}: {hours_dict[day]}")

    return "\n".join(lines)


def hours_to_safe_field(hours_dict: dict[str, str]) -> dict[str, Any]:
    """Convert hours to public-safe field format."""
    if not hours_dict:
        return {}

    return {
        "field_name": "hours_structured",
        "field_value": format_hours_display(hours_dict),
        "safe_for_public_copy": True,
        "copy_slot_eligible": True,
    }


def extract_hours_from_html(html_text: str) -> dict[str, str]:
    """Extract hours section from HTML and parse."""
    # Look for hours section markers
    hours_patterns = [
        r"Hours:\s*(.+?)(?:<|$)",
        r"Opening\s*Hours:\s*(.+?)(?:<|$)",
    ]

    for pattern in hours_patterns:
        match = re.search(pattern, html_text, re.IGNORECASE | re.DOTALL)
        if match:
            hours_text = match.group(1)
            parsed = parse_hours_text(hours_text)
            if parsed:
                return parsed

    return {}


def merge_hours(raw_hours: str, parsed_hours: dict[str, str]) -> dict[str, Any]:
    """Merge raw hours string with parsed structured hours.

    Returns dict with:
    - raw: original hours string
    - parsed_structured: structured dict if parsing succeeded
    - confidence: 1.0 if parsed, 0.5 if raw only
    """
    result: dict[str, Any] = {"raw": raw_hours}

    if parsed_hours:
        result["parsed_structured"] = parsed_hours
        result["confidence"] = 1.0
    else:
        result["parsed_structured"] = {}
        result["confidence"] = 0.5 if raw_hours else 0.0

    return result