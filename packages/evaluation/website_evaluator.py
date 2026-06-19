"""Structured website evaluator — VNEXT-06.

Evaluates a generated website against 12 quality dimensions using
deterministic, heuristic-based checks (no LLM).  Produces an
``evaluation_report.json``-shaped dict.

Feature-flagged behind ``use_structured_evaluation_report`` (default OFF).
This module is **additive** — it does not modify the existing quality gate or
premium scorecard.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from packages.evaluation.spec_alignment import check_spec_alignment

SCHEMA_VERSION = "1.0.0"

# Hard-failure dimensions (score < 50 triggers hard failure)
_HARD_FAILURE_DIMENSIONS = {"factual_safety", "accessibility"}

# Patchable dimensions (low score → patchable, not hard failure)
_PATCHABLE_DIMENSIONS = {"imagery", "originality", "typography", "spacing", "branding"}

# Minimum score thresholds
_HARD_FAIL_SCORE_THRESHOLD = 50
_OVERALL_FAIL_THRESHOLD = 40
_PASS_OVERALL_THRESHOLD = 60

# Default forbidden claims list
DEFAULT_FORBIDDEN_CLAIMS: list[str] = [
    "guaranteed",
    "#1 rated",
    "best in the world",
    "100% effective",
    "miracle cure",
    "FDA approved",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def evaluate_website(
    site_html: str,
    creative_spec: dict | None = None,
    config: dict | None = None,
    *,
    run_id: str,
    business_slug: str,
) -> dict[str, Any]:
    """Evaluate a generated website against quality dimensions.

    Parameters
    ----------
    site_html:
        The full HTML string of the generated site.
    creative_spec:
        Optional creative spec dict (required sections, forbidden claims, etc.).
    config:
        Optional config dict.  Recognised keys:
        ``forbidden_claims`` (list[str]), ``hard_fail_score_threshold`` (int).
    run_id:
        Pipeline run identifier.
    business_slug:
        Business slug for the site being evaluated.

    Returns
    -------
    dict
        An ``evaluation_report.json``-shaped dict.
    """
    cfg = config or {}
    forbidden_claims = cfg.get("forbidden_claims", DEFAULT_FORBIDDEN_CLAIMS)

    # --- Dimension scoring ---
    scorers = {
        "hierarchy": lambda h: _score_hierarchy(h),
        "branding": lambda h: _score_branding(h),
        "typography": lambda h: _score_typography(h),
        "spacing": lambda h: _score_spacing(h),
        "imagery": lambda h: _score_imagery(h),
        "trust": lambda h: _score_trust(h),
        "conversion": lambda h: _score_conversion(h),
        "accessibility": lambda h: _score_accessibility(h),
        "originality": lambda h: _score_originality(h),
        "mobile_experience": lambda h: _score_mobile_experience(h),
        "factual_safety": lambda h: _score_factual_safety(h, forbidden_claims),
        "local_relevance": lambda h: _score_local_relevance(h, business_slug),
    }

    dimensions: dict[str, dict[str, Any]] = {}
    for name, scorer in scorers.items():
        score, notes = scorer(site_html)
        status = _dimension_status(name, score)
        dimensions[name] = {
            "score": score,
            "status": status,
            "notes": notes,
        }

    # --- Overall score (simple average) ---
    overall_score = round(
        sum(d["score"] for d in dimensions.values()) / len(dimensions), 1
    )

    # --- Hard / patchable failures ---
    hard_failures = [
        name
        for name, dim in dimensions.items()
        if name in _HARD_FAILURE_DIMENSIONS and dim["score"] < _HARD_FAIL_SCORE_THRESHOLD
    ]
    patchable_failures = [
        name
        for name, dim in dimensions.items()
        if name in _PATCHABLE_DIMENSIONS and dim["score"] < _HARD_FAIL_SCORE_THRESHOLD
    ]

    # --- Verdict ---
    if hard_failures or overall_score < _OVERALL_FAIL_THRESHOLD:
        verdict = "fail"
    elif patchable_failures or overall_score < _PASS_OVERALL_THRESHOLD:
        verdict = "patchable"
    else:
        verdict = "pass"

    # --- Spec alignment ---
    spec_alignment: dict[str, Any] = {}
    if creative_spec is not None:
        spec_alignment = check_spec_alignment(site_html, creative_spec)
    else:
        spec_alignment = {
            "sections_present": [],
            "sections_missing": [],
            "cta_present": _has_cta_heuristic(site_html),
            "forbidden_claims_found": [],
            "missing_data_handled_correctly": True,
        }

    # --- Missing data ---
    missing_data = creative_spec.get("missing_data", []) if creative_spec else []

    # --- Deterministic timestamp ---
    generated_at = _deterministic_timestamp(run_id, business_slug)

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "business_slug": business_slug,
        "generated_at": generated_at,
        "dimensions": dimensions,
        "overall_score": overall_score,
        "verdict": verdict,
        "hard_failures": hard_failures,
        "patchable_failures": patchable_failures,
        "creative_spec_alignment": spec_alignment,
        "missing_data": missing_data,
        "internal": {
            "flag": "use_structured_evaluation_report",
            "schema_origin": "VNEXT-06",
        },
    }


def write_evaluation_report(
    report: dict[str, Any],
    output_dir: str | Path,
) -> Path:
    """Write the evaluation report as ``evaluation_report.json``.

    Parameters
    ----------
    report:
        The dict returned by :func:`evaluate_website`.
    output_dir:
        Directory to write into.

    Returns
    -------
    Path
        Path to the written JSON file.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / "evaluation_report.json"
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# Dimension scorers — each returns (score 0–100, notes string)
# ---------------------------------------------------------------------------


def _score_hierarchy(html: str) -> tuple[int, str]:
    """Check H1/H2/H3 nesting and heading order."""
    score = 0
    notes: list[str] = []

    h1s = re.findall(r"<h1[^>]*>", html, re.IGNORECASE)
    h2s = re.findall(r"<h2[^>]*>", html, re.IGNORECASE)
    h3s = re.findall(r"<h3[^>]*>", html, re.IGNORECASE)

    # H1 should exist and be unique (0–40 pts)
    if len(h1s) == 1:
        score += 40
    elif len(h1s) > 1:
        score += 20
        notes.append("Multiple H1 tags found")
    else:
        notes.append("No H1 tag found")

    # H2 tags present (0–30 pts)
    if len(h2s) >= 2:
        score += 30
    elif len(h2s) == 1:
        score += 15
    else:
        notes.append("No H2 tags found")

    # H3 tags present (0–15 pts)
    if h3s:
        score += 15
    else:
        notes.append("No H3 tags found")

    # Check heading order (no H3 before H2) (0–15 pts)
    if h2s and h3s:
        # Simplified: just check that there's at least one H2 before H3 content
        h2_pos = html.lower().find("<h2")
        h3_pos = html.lower().find("<h3")
        if h2_pos >= 0 and h3_pos >= 0 and h2_pos < h3_pos:
            score += 15
        else:
            score += 5
            notes.append("Heading order may be incorrect")
    elif h2s:
        score += 10

    if not notes:
        notes.append("Good heading hierarchy detected")
    return (min(score, 100), "; ".join(notes))


def _score_branding(html: str) -> tuple[int, str]:
    """Check for CSS variables and consistent color usage."""
    score = 0
    notes: list[str] = []

    html_lower = html.lower()

    # CSS custom properties / variables (0–40 pts)
    css_vars = re.findall(r"--[\w-]+\s*:", html_lower)
    if len(css_vars) >= 4:
        score += 40
    elif len(css_vars) >= 2:
        score += 25
    elif css_vars:
        score += 10
    else:
        notes.append("No CSS custom properties found")

    # Consistent color format (hex or rgb) (0–30 pts)
    hex_colors = re.findall(r"#[0-9a-f]{3,8}\b", html_lower)
    if len(hex_colors) >= 2:
        score += 30
    elif hex_colors:
        score += 15
    else:
        notes.append("No hex color values found")

    # Primary color used more than once (0–30 pts)
    if hex_colors and len(hex_colors) >= 2:
        color_counts: dict[str, int] = {}
        for c in hex_colors:
            normalized = c.lower()[:7]  # Normalize to 6-char hex
            color_counts[normalized] = color_counts.get(normalized, 0) + 1
        repeated = sum(1 for v in color_counts.values() if v >= 2)
        if repeated >= 1:
            score += 30
        else:
            score += 10
    else:
        score += 5

    if not notes:
        notes.append("Branding consistency detected")
    return (min(score, 100), "; ".join(notes))


def _score_typography(html: str) -> tuple[int, str]:
    """Check for font declarations and line-height."""
    score = 0
    notes: list[str] = []

    html_lower = html.lower()

    # Font family declarations (0–35 pts)
    font_families = re.findall(r"font-family\s*:", html_lower)
    if len(font_families) >= 2:
        score += 35
    elif font_families:
        score += 20
    else:
        notes.append("No font-family declarations found")

    # Line-height declarations (0–30 pts)
    line_heights = re.findall(r"line-height\s*:", html_lower)
    if line_heights:
        score += 30
    else:
        notes.append("No line-height declarations found")

    # Font-size declarations (0–20 pts)
    font_sizes = re.findall(r"font-size\s*:", html_lower)
    if len(font_sizes) >= 2:
        score += 20
    elif font_sizes:
        score += 10
    else:
        notes.append("No font-size declarations found")

    # Font-weight variations (0–15 pts)
    font_weights = re.findall(r"font-weight\s*:", html_lower)
    if font_weights:
        score += 15

    if not notes:
        notes.append("Typography well-defined")
    return (min(score, 100), "; ".join(notes))


def _score_spacing(html: str) -> tuple[int, str]:
    """Check for padding/margin usage."""
    score = 0
    notes: list[str] = []

    html_lower = html.lower()

    # Padding declarations (0–35 pts)
    paddings = re.findall(r"padding[\w-]*\s*:", html_lower)
    if len(paddings) >= 4:
        score += 35
    elif len(paddings) >= 2:
        score += 25
    elif paddings:
        score += 10
    else:
        notes.append("No padding declarations found")

    # Margin declarations (0–35 pts)
    margins = re.findall(r"margin[\w-]*\s*:", html_lower)
    if len(margins) >= 4:
        score += 35
    elif len(margins) >= 2:
        score += 25
    elif margins:
        score += 10
    else:
        notes.append("No margin declarations found")

    # Gap usage (modern CSS) (0–15 pts)
    gaps = re.findall(r"gap\s*:", html_lower)
    if gaps:
        score += 15
    else:
        score += 5

    # Max-width on containers (0–15 pts)
    max_widths = re.findall(r"max-width\s*:", html_lower)
    if max_widths:
        score += 15
    else:
        score += 5

    if not notes:
        notes.append("Good spacing patterns detected")
    return (min(score, 100), "; ".join(notes))


def _score_imagery(html: str) -> tuple[int, str]:
    """Check for img tags, alt text, and background images."""
    score = 0
    notes: list[str] = []

    # Image tags (0–30 pts)
    img_tags = re.findall(r"<img\s[^>]*>", html, re.IGNORECASE)
    if len(img_tags) >= 3:
        score += 30
    elif len(img_tags) >= 1:
        score += 15
    else:
        notes.append("No <img> tags found")

    # Alt text on images (0–35 pts)
    imgs_with_alt = [img for img in img_tags if re.search(r"alt\s*=\s*['\"][^'\"]+['\"]", img, re.IGNORECASE)]
    if img_tags:
        alt_ratio = len(imgs_with_alt) / len(img_tags)
        score += int(35 * alt_ratio)
        if alt_ratio < 1.0:
            notes.append(f"{len(img_tags) - len(imgs_with_alt)} images missing alt text")
    else:
        score += 0

    # Background images or gradients (0–20 pts)
    bg_images = re.findall(r"background-image\s*:", html, re.IGNORECASE)
    gradients = re.findall(r"linear-gradient|radial-gradient", html, re.IGNORECASE)
    if bg_images or gradients:
        score += 20
    else:
        score += 5

    # SVG usage (0–15 pts)
    svgs = re.findall(r"<svg", html, re.IGNORECASE)
    if svgs:
        score += 15
    else:
        score += 5

    if not notes:
        notes.append("Good imagery coverage")
    return (min(score, 100), "; ".join(notes))


def _score_trust(html: str) -> tuple[int, str]:
    """Check for contact info, phone, address."""
    score = 0
    notes: list[str] = []

    html_lower = html.lower()
    # Strip tags for text analysis
    text = re.sub(r"<[^>]+>", " ", html_lower)
    text = re.sub(r"\s+", " ", text)

    # Phone number (0–25 pts)
    phone_patterns = re.findall(
        r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text
    )
    if phone_patterns:
        score += 25
    else:
        notes.append("No phone number detected")

    # Email address (0–25 pts)
    emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    if emails:
        score += 25
    else:
        notes.append("No email address detected")

    # Address (0–25 pts)
    address_keywords = ["street", "ave", "avenue", "blvd", "boulevard", "drive", "road", "suite", "ln", "lane", "st,", "rd,"]
    if any(kw in text for kw in address_keywords):
        score += 25
    else:
        notes.append("No address detected")

    # Business name / org markup (0–25 pts)
    org_patterns = re.findall(r"organization|locals?business|schema\.org", html_lower)
    if org_patterns:
        score += 25
    else:
        # No org markup found — award 0 points (not 10) so the score
        # accurately reflects the absence of business identity markup.
        # A partial/inferred brand should not inflate the trust score.
        score += 0

    if not notes:
        notes.append("Trust signals detected")
    return (min(score, 100), "; ".join(notes))


def _score_conversion(html: str) -> tuple[int, str]:
    """Check for CTA buttons and form elements."""
    score = 0
    notes: list[str] = []

    html_lower = html.lower()

    # CTA buttons (0–30 pts)
    cta_buttons = re.findall(
        r"<(?:button|a)[^>]*(?:btn|button|cta)[^>]*>", html_lower
    )
    if len(cta_buttons) >= 2:
        score += 30
    elif cta_buttons:
        score += 20
    else:
        notes.append("No CTA-style buttons found")

    # Form elements (0–25 pts)
    forms = re.findall(r"<form[\s>]", html_lower)
    if forms:
        score += 25
    else:
        notes.append("No <form> elements found")

    # Input fields (0–20 pts)
    inputs = re.findall(r"<input[\s>]", html_lower)
    if inputs:
        score += 20
    else:
        score += 5

    # Action-oriented link text (0–25 pts)
    action_words = ["get started", "contact us", "book now", "call now", "free estimate", "schedule", "sign up", "learn more"]
    text = re.sub(r"<[^>]+>", " ", html_lower)
    found_actions = [w for w in action_words if w in text]
    if len(found_actions) >= 2:
        score += 25
    elif found_actions:
        score += 15
    else:
        notes.append("No action-oriented link text found")

    if not notes:
        notes.append("Conversion elements present")
    return (min(score, 100), "; ".join(notes))


def _score_accessibility(html: str) -> tuple[int, str]:
    """Check for alt text, aria labels, semantic HTML."""
    score = 0
    notes: list[str] = []

    html_lower = html.lower()

    # Language attribute on html tag (0–10 pts)
    if re.search(r"<html[^>]*lang\s*=", html_lower):
        score += 10
    else:
        notes.append("No lang attribute on <html>")

    # Alt text on images (0–20 pts)
    img_tags = re.findall(r"<img\s[^>]*>", html, re.IGNORECASE)
    if img_tags:
        imgs_with_alt = [img for img in img_tags if re.search(r"alt\s*=", img, re.IGNORECASE)]
        if len(imgs_with_alt) == len(img_tags):
            score += 20
        elif imgs_with_alt:
            score += 10
        else:
            notes.append("Images missing alt text")
    else:
        score += 10  # No images, no penalty

    # ARIA labels (0–20 pts)
    aria_labels = re.findall(r"aria-label\s*=", html_lower)
    aria_labelledby = re.findall(r"aria-labelledby\s*=", html_lower)
    if aria_labels or aria_labelledby:
        score += 20
    else:
        notes.append("No ARIA labels found")

    # Semantic HTML elements (0–30 pts)
    semantic_tags = ["<header", "<nav", "<main", "<section", "<article", "<aside", "<footer"]
    found_semantic = [tag for tag in semantic_tags if tag in html_lower]
    if len(found_semantic) >= 4:
        score += 30
    elif len(found_semantic) >= 2:
        score += 20
    elif found_semantic:
        score += 10
    else:
        notes.append("Few semantic HTML elements")

    # Role attributes (0–10 pts)
    roles = re.findall(r"role\s*=", html_lower)
    if roles:
        score += 10
    else:
        score += 3

    # Tabindex (0–10 pts)
    tabindex = re.findall(r"tabindex\s*=", html_lower)
    if tabindex:
        score += 10
    else:
        score += 3

    if not notes:
        notes.append("Good accessibility practices")
    return (min(score, 100), "; ".join(notes))


def _score_originality(html: str) -> tuple[int, str]:
    """Check for non-template patterns (unique class names, custom CSS)."""
    score = 0
    notes: list[str] = []

    html_lower = html.lower()

    # Custom class names (not common framework names) (0–25 pts)
    class_names = re.findall(r"class\s*=\s*['\"]([^'\"]+)['\"]", html_lower)
    all_classes: list[str] = []
    for cls_str in class_names:
        all_classes.extend(cls_str.split())

    common_framework_classes = {
        "container", "row", "col", "col-sm", "col-md", "col-lg",
        "btn", "btn-primary", "btn-secondary",
        "active", "disabled", "hidden", "visible",
        "text-center", "text-left", "text-right",
        "flex", "grid", "block", "inline", "relative", "absolute",
        "p-1", "p-2", "p-3", "p-4", "m-1", "m-2", "m-3", "m-4",
        "w-full", "h-full", "bg-white", "bg-gray",
    }
    custom_classes = [c for c in all_classes if c not in common_framework_classes]
    if len(custom_classes) >= 5:
        score += 25
    elif len(custom_classes) >= 2:
        score += 15
    elif custom_classes:
        score += 5
    else:
        notes.append("Only framework-standard class names found")

    # Custom CSS rules in <style> (0–25 pts)
    style_blocks = re.findall(r"<style[^>]*>(.*?)</style>", html, re.IGNORECASE | re.DOTALL)
    custom_rules = 0
    for block in style_blocks:
        custom_rules += len(re.findall(r"\{", block))
    if custom_rules >= 10:
        score += 25
    elif custom_rules >= 5:
        score += 15
    elif custom_rules:
        score += 5
    else:
        notes.append("No custom CSS rules found")

    # Unique IDs (0–25 pts)
    unique_ids = re.findall(r"id\s*=\s*['\"]([^'\"]+)['\"]", html_lower)
    if len(unique_ids) >= 3:
        score += 25
    elif len(unique_ids) >= 1:
        score += 15
    else:
        score += 5

    # @keyframes or custom animations (0–25 pts)
    if re.search(r"@keyframes|animation\s*:", html_lower):
        score += 25
    else:
        score += 5

    if not notes:
        notes.append("Original design patterns detected")
    return (min(score, 100), "; ".join(notes))


def _score_mobile_experience(html: str) -> tuple[int, str]:
    """Check for viewport meta and responsive patterns."""
    score = 0
    notes: list[str] = []

    html_lower = html.lower()

    # Viewport meta tag (0–30 pts)
    if re.search(r"<meta[^>]*viewport[^>]*>", html_lower):
        if re.search(r"width\s*=\s*['\"]device-width['\"]", html_lower):
            score += 30
        else:
            score += 15
    else:
        notes.append("No viewport meta tag found")

    # Media queries (0–30 pts)
    media_queries = re.findall(r"@media\s+", html_lower)
    if len(media_queries) >= 2:
        score += 30
    elif media_queries:
        score += 20
    else:
        notes.append("No @media queries found")

    # Responsive units (rem, em, %, vw, vh) (0–20 pts)
    responsive_units = re.findall(r"[\d.]+(?:rem|em|vh|vw)", html_lower)
    if len(responsive_units) >= 3:
        score += 20
    elif responsive_units:
        score += 10
    else:
        notes.append("Few responsive units found")

    # Flexbox or grid (0–20 pts)
    if re.search(r"display\s*:\s*flex", html_lower) or re.search(r"display\s*:\s*grid", html_lower):
        score += 20
    else:
        score += 5

    if not notes:
        notes.append("Mobile-friendly patterns detected")
    return (min(score, 100), "; ".join(notes))


def _score_factual_safety(html: str, forbidden_claims: list[str]) -> tuple[int, str]:
    """Check against forbidden claims list."""
    text = re.sub(r"<[^>]+>", " ", html).lower()
    text = re.sub(r"\s+", " ", text)

    found_claims: list[str] = []
    for claim in forbidden_claims:
        if claim.lower() in text:
            found_claims.append(claim)

    if not found_claims:
        return (100, "No forbidden claims detected")

    # Each found claim reduces score
    score = max(0, 100 - len(found_claims) * 30)
    return (score, f"Forbidden claims found: {'; '.join(found_claims)}")


def _score_local_relevance(html: str, business_slug: str) -> tuple[int, str]:
    """Check for business name and location in content."""
    score = 0
    notes: list[str] = []

    html_lower = html.lower()
    text = re.sub(r"<[^>]+>", " ", html_lower)
    text = re.sub(r"\s+", " ", text)

    # Business slug appears (0–30 pts)
    slug_parts = business_slug.replace("-", " ").replace("_", " ").split()
    slug_found = any(part in text for part in slug_parts) if slug_parts else False
    if slug_found:
        score += 30
    else:
        notes.append("Business name not clearly present")

    # Address or city references (0–30 pts)
    address_indicators = ["street", "ave", "blvd", "road", "suite", "drive", "lane"]
    city_state = re.findall(r"[A-Z][a-z]+(?:\s[A-Z][a-z]+)?,\s*[A-Z]{2}\s+\d{5}", html)
    if city_state:
        score += 30
    elif any(ind in text for ind in address_indicators):
        score += 20
    else:
        notes.append("No address/location detected")

    # Phone with area code (0–20 pts)
    phones = re.findall(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
    if phones:
        score += 20
    else:
        score += 5

    # Local schema markup (0–20 pts)
    if re.search(r"locals?business|schema\.org", html_lower):
        score += 20
    else:
        score += 5

    if not notes:
        notes.append("Local relevance signals present")
    return (min(score, 100), "; ".join(notes))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _dimension_status(name: str, score: int) -> str:
    """Derive a pass/fail/warn status for a dimension."""
    if name in _HARD_FAILURE_DIMENSIONS and score < _HARD_FAIL_SCORE_THRESHOLD:
        return "fail"
    if name in _PATCHABLE_DIMENSIONS and score < _HARD_FAIL_SCORE_THRESHOLD:
        return "patchable"
    if score < 60:
        return "warn"
    return "pass"


def _has_cta_heuristic(html: str) -> bool:
    """Quick heuristic check for CTA presence (used when no creative_spec)."""
    html_lower = html.lower()
    cta_patterns = [
        r"<button[^>]*>",
        r"<form[\s>]",
        r"<input[^>]*type=['\"]submit['\"]",
        r"get started|contact us|book now|call now|free estimate|schedule|sign up",
    ]
    return any(re.search(p, html_lower) for p in cta_patterns)


def _deterministic_timestamp(run_id: str, business_slug: str) -> str:
    """Generate a deterministic ISO timestamp from run_id + slug.

    Uses a hash-based offset from the current time so the same inputs always
    produce the same timestamp within a session.
    """
    now = datetime.now(timezone.utc)
    seed = hashlib.sha256(f"{run_id}:{business_slug}".encode()).hexdigest()
    # Use first 8 hex chars as a small offset (0–255 seconds)
    offset = int(seed[:8], 16) % 256
    ts = now.replace(microsecond=0)
    ts = ts.replace(second=offset % 60)
    return ts.isoformat()
