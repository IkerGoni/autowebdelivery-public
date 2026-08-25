"""Services extractor for business enrichment - extracts verified service names from public sources."""

from __future__ import annotations

import re
from typing import Any

SERVICE_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "auto_detailing": [
        (r"ceramic\s*coating", "Ceramic Coating"),
        (r"ceramic\s*pro", "Ceramic Coating"),
        (r"paint\s*correction", "Paint Correction"),
        (r"paint\s*enhancement", "Paint Correction"),
        (r"exterior\s*detailing", "Exterior Detailing"),
        (r"interior\s*detailing", "Interior Detailing"),
        (r"interior\s*cleaning", "Interior Detailing"),
        (r"interior\s*steam\s*cleaning", "Interior Steam Cleaning"),
        (r"wheel\s*coating", "Wheel Coating"),
        (r"wheel\s*ceramic", "Wheel Ceramic Coating"),
        (r"paint\s*protection\s*film|ppf", "Paint Protection Film"),
        (r"headlight\s*restoration", "Headlight Restoration"),
        (r"engine\s*bay\s*cleaning", "Engine Bay Cleaning"),
        (r"claying", "Clay Service"),
        (r"buffing", "Buffing"),
    ],
    "plumbing": [
        (r"drain\s*(repair|cleaning|service)", "Drain Service"),
        (r"leak\s*detection", "Leak Detection"),
        (r"water\s*heater", "Water Heater Service"),
        (r"pipe\s*(replacement|repair)", "Pipe Service"),
        (r"faucet\s*repair", "Faucet Repair"),
        (r"toilet\s*repair", "Toilet Repair"),
        (r"sewer\s*line", "Sewer Line Service"),
        (r"emergency\s*plumbing", "Emergency Plumbing"),
        (r"plumbing\s*installation", "Installation"),
        (r"sump\s*pump", "Sump Pump Service"),
    ],
    "hvac": [
        (r"ac\s*repair|air\s*conditioning", "AC Repair"),
        (r"heating\s*repair|furnace\s*repair", "Heating Repair"),
        (r"duct\s*cleaning", "Duct Cleaning"),
        (r"air\s*duct", "Air Duct Service"),
        (r"heat\s*pump", "Heat Pump Service"),
        (r"thermostat\s*installation", "Thermostat Installation"),
        (r"indoor\s*air\s*quality", "Indoor Air Quality"),
        (r"ventilation", "Ventilation Service"),
        (r"maintenance", "Maintenance"),
    ],
    "cleaning": [
        (r"house\s*cleaning", "House Cleaning"),
        (r"office\s*cleaning", "Office Cleaning"),
        (r"deep\s*cleaning", "Deep Cleaning"),
        (r"move\s*out\s*cleaning", "Move-Out Cleaning"),
        (r"move\s*in\s*cleaning", "Move-In Cleaning"),
        (r"carpet\s*cleaning", "Carpet Cleaning"),
        (r"window\s*cleaning", "Window Cleaning"),
        (r"maid\s*service", "Maid Service"),
        (r"janitorial", "Janitorial Service"),
    ],
    "dental": [
        (r"teeth\s*cleaning", "Teeth Cleaning"),
        (r"root\s*canal", "Root Canal"),
        (r"crown", "Crown"),
        (r"filling", "Filling"),
        (r"implant", "Implant"),
        (r"extraction", "Extraction"),
        (r"checkup|exam", "Checkup"),
        (r"whitening", "Whitening"),
        (r"emergency", "Emergency Dental"),
    ],
    "hair_salon": [
        (r"haircut", "Haircut"),
        (r"hair\s*cut", "Haircut"),
        (r"color", "Hair Color"),
        (r"highlights", "Highlights"),
        (r"balayage", "Balayage"),
        (r"keratin", "Keratin Treatment"),
        (r"blowout", "Blowout"),
        (r"updo", "Updo"),
        (r"hair\s*mask|deep\s*condition", "Hair Treatment"),
    ],
    "electrical": [
        (r"outlet\s*repair", "Outlet Repair"),
        (r"light\s*installation", "Light Installation"),
        (r"wiring", "Wiring Service"),
        (r"panel\s*upgrade", "Panel Upgrade"),
        (r"breaker\s*box", "Breaker Service"),
        (r"ceiling\s*fan", "Ceiling Fan Installation"),
        (r"generator\s*installation", "Generator Service"),
    ],
}


def extract_services_from_html(html_text: str, category: str) -> list[dict[str, Any]]:
    """Extract verified service names from scraped HTML with confidence scoring."""
    services: list[dict[str, Any]] = []
    patterns = SERVICE_PATTERNS.get(category.lower(), [])
    seen: set[str] = set()

    for pattern, service_name in patterns:
        matches = re.findall(pattern, html_text, re.IGNORECASE)
        if matches and service_name.lower() not in seen:
            seen.add(service_name.lower())
            services.append(
                {
                    "service_name": service_name,
                    "source": "website_text",
                    "confidence": 0.9 if len(matches) > 1 else 0.7,
                }
            )

    return services


def extract_services_from_text(text: str, category: str) -> list[dict[str, Any]]:
    """Extract services from plain text (markdown, scraped content)."""
    return extract_services_from_html(text, category)


def services_to_markdown(services: list[dict[str, Any]]) -> str:
    """Convert services list to markdown format for FACTS.md."""
    if not services:
        return ""
    lines = ["- Services found:"]
    for s in services:
        lines.append(f"  - {s['service_name']}")
    return "\n".join(lines) + "\n"


def services_to_safe_field(services: list[dict[str, Any]]) -> dict[str, Any]:
    """Convert services to public-safe field format."""
    if not services:
        return {}
    names = [s["service_name"] for s in services if s.get("confidence", 0) >= 0.7]
    return {
        "field_name": "primary_services",
        "field_value": ", ".join(names),
        "safe_for_public_copy": True,
        "copy_slot_eligible": True,
    }


def merge_services_with_existing(existing: str = "", extracted: list[dict[str, Any]] | None = None) -> str:
    """Merge extracted services with existing FACTS.md services field.

    Args:
        existing: Current services string from FACTS.md (may be empty or generic)
        extracted: List of extracted service dicts

    Returns:
        Combined services string for public-safe use
    """
    extracted_names = []
    if extracted:
        extracted_names = [s["service_name"] for s in extracted if s.get("confidence", 0) >= 0.7]

    combined = list(set([existing] + extracted_names))
    return ", ".join(s for s in combined if s)