"""Spec alignment checks — verify generated HTML against creative_spec directives.

Part of VNEXT-06 Structured Evaluation Report.
Feature-flagged behind ``use_structured_evaluation_report`` (default OFF).
"""

from __future__ import annotations

import re


def check_spec_alignment(html: str, creative_spec: dict) -> dict:
    """Check if the generated site aligns with *creative_spec* directives.

    Returns a dict matching the ``creative_spec_alignment`` shape in
    ``evaluation_report.json``::

        {
            "sections_present": [...],
            "sections_missing": [...],
            "cta_present": bool,
            "forbidden_claims_found": [...],
            "missing_data_handled_correctly": bool,
        }
    """
    required_sections = creative_spec.get("required_sections", [])
    forbidden = creative_spec.get("forbidden_claims", [])
    missing = creative_spec.get("missing_data", [])

    sections_result = _check_sections(html, required_sections)
    cta_present = _check_cta(html)
    forbidden_found = _check_forbidden_claims(html, forbidden)
    missing_ok = _check_missing_data_handling(html, missing)

    return {
        "sections_present": sections_result["present"],
        "sections_missing": sections_result["missing"],
        "cta_present": cta_present,
        "forbidden_claims_found": forbidden_found,
        "missing_data_handled_correctly": missing_ok,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Maps canonical section names to regex patterns we search for in the HTML.
_SECTION_PATTERNS: dict[str, list[str]] = {
    "hero": [r"id=['\"]hero['\"]", r"class=['\"][^'\"]*hero[^'\"]*['\"]"],
    "services": [r"id=['\"]services['\"]", r"class=['\"][^'\"]*services[^'\"]*['\"]"],
    "about": [r"id=['\"]about['\"]", r"class=['\"][^'\"]*about[^'\"]*['\"]"],
    "contact": [r"id=['\"]contact['\"]", r"class=['\"][^'\"]*contact[^'\"]*['\"]"],
    "cta": [r"id=['\"]cta['\"]", r"class=['\"][^'\"]*cta[^'\"]*['\"]"],
    "testimonials": [r"id=['\"]testimonials['\"]", r"class=['\"][^'\"]*testimonial[^'\"]*['\"]"],
    "gallery": [r"id=['\"]gallery['\"]", r"class=['\"][^'\"]*gallery[^'\"]*['\"]"],
    "pricing": [r"id=['\"]pricing['\"]", r"class=['\"][^'\"]*pricing[^'\"]*['\"]"],
    "faq": [r"id=['\"]faq['\"]", r"class=['\"][^'\"]*faq[^'\"]*['\"]"],
    "footer": [r"<footer", r"id=['\"]footer['\"]", r"class=['\"][^'\"]*footer[^'\"]*['\"]"],
    "header": [r"<header", r"id=['\"]header['\"]", r"class=['\"][^'\"]*header[^'\"]*['\"]"],
    "navigation": [r"<nav", r"id=['\"]nav['\"]", r"class=['\"][^'\"]*nav[^'\"]*['\"]"],
}


def _check_sections(html: str, required_sections: list[str]) -> dict:
    """Return ``{present: [...], missing: [...]}`` for *required_sections*."""
    html_lower = html.lower()
    present: list[str] = []
    missing: list[str] = []

    for section in required_sections:
        section_lower = section.lower()
        patterns = _SECTION_PATTERNS.get(section_lower, [
            re.escape(section_lower),
        ])
        found = any(re.search(p, html_lower) for p in patterns)
        if found:
            present.append(section)
        else:
            missing.append(section)

    return {"present": present, "missing": missing}


def _check_cta(html: str) -> bool:
    """Return *True* if at least one CTA element is detected."""
    html_lower = html.lower()
    # Check for common CTA patterns: buttons with action text, form submit buttons
    cta_patterns = [
        r"<button[^>]*>.*?(?:get\s+started|contact\s+us|book\s+now|call\s+now|schedule|free\s+estimate|request\s+a?\s*quote|sign\s+up|learn\s+more|get\s+a?\s*quote|hire\s+us|order\s+now|subscribe|buy\s+now|request\s+consultation).*?</button>",
        r"<a[^>]*class=['\"][^'\"]*(?:btn|button|cta)[^'\"]*['\"][^>]*>",
        r"<input[^>]*type=['\"]submit['\"][^>]*>",
        r"<button[^>]*class=['\"][^'\"]*(?:btn|button|cta)[^'\"]*['\"][^>]*>",
        r"class=['\"][^'\"]*cta[^'\"]*['\"]",
    ]
    return any(re.search(p, html_lower, re.DOTALL) for p in cta_patterns)


def _check_forbidden_claims(html: str, forbidden: list[str]) -> list[str]:
    """Return list of forbidden claim strings found in the HTML text."""
    if not forbidden:
        return []
    # Strip tags for text matching
    text = re.sub(r"<[^>]+>", " ", html).lower()
    found: list[str] = []
    for claim in forbidden:
        if claim.lower() in text:
            found.append(claim)
    return found


def _check_missing_data_handling(html: str, missing: list[str]) -> bool:
    """Return *True* if missing data fields are handled correctly.

    A field is "handled" if the HTML does NOT contain raw placeholder markers
    like ``{{field}}`` or ``[field]`` or ``__MISSING_field__``.
    """
    if not missing:
        return True
    html_lower = html.lower()
    for field in missing:
        field_lower = field.lower()
        # Check for unhandled placeholder patterns
        bad_patterns = [
            "{{" + field_lower + "}}",
            "[[" + field_lower + "]]",
            "__missing_" + field_lower + "__",
            "[" + field_lower + "]",
        ]
        for pattern in bad_patterns:
            if pattern in html_lower:
                return False
    return True
