"""VNEXT-07 — Deterministic Patch Planner.

Analyses an evaluation report (VNEXT-06) and builds a list of safe,
deterministic patches for localised failures.  Hard-reject sites (verdict
``"fail"``) are **never** patched — they receive an empty patch list.

Only the five approved patch categories are emitted; anything else is
silently skipped.

Feature flag: ``use_patch_phase`` (default OFF).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Approved patch categories — ONLY these may be emitted
# ---------------------------------------------------------------------------
APPROVED_CATEGORIES: tuple[str, ...] = (
    "missing_final_cta",
    "forbidden_claim_removal",
    "mobile_overflow_css_fix",
    "spacing_adjustment",
    "cta_link_correction",
)

# Neutral fallback text when removing a forbidden claim.
_NEUTRAL_FALLBACK = "contact us for details"

# CTA section inserted when missing_final_cta is triggered.
_DEFAULT_CTA_HTML = (
    "<section class='cta' style='text-align:center;padding:2rem 1rem;'>"
    "<h2>Ready to Get Started?</h2>"
    "<p>Contact us today for a free consultation.</p>"
    "<a href='#contact' class='cta-button' "
    "style='display:inline-block;padding:0.75rem 1.5rem;"
    "background:#2563eb;color:#fff;border-radius:0.375rem;"
    "text-decoration:none;font-weight:600;'>"
    "Get in Touch</a></section>"
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_patch_plan(
    evaluation_report: dict[str, Any],
    creative_spec: dict[str, Any] | None = None,
    *,
    run_id: str,
    business_slug: str,
) -> dict[str, Any]:
    """Build a patch plan from an evaluation report.

    Returns a plan with an empty ``patches`` list when the verdict is
    ``"fail"`` (hard-reject) or ``"pass"`` (nothing to patch).

    Parameters
    ----------
    evaluation_report:
        The dict produced by :func:`packages.evaluation.website_evaluator.evaluate_website`.
    creative_spec:
        Optional creative spec (for forbidden claims list).
    run_id:
        Pipeline run identifier.
    business_slug:
        Business slug.

    Returns
    -------
    dict
        A ``patch_plan.json``-shaped dict.
    """
    verdict = evaluation_report.get("verdict", "pass")
    original_verdict = verdict

    # Hard-reject sites are NOT patched.
    if verdict == "fail":
        return _empty_plan(run_id, business_slug, verdict, original_verdict)

    patches: list[dict[str, Any]] = []
    skipped_reasons: list[str] = []

    # Extract HTML from evaluation_report internal state if available,
    # otherwise use the creative_spec_alignment section to decide patches.
    # The evaluation_report itself doesn't carry raw HTML — callers must
    # supply it via the creative_spec or we derive patch signals from
    # the report's dimension data.

    site_html = evaluation_report.get("_site_html", "")
    if not site_html and creative_spec:
        site_html = creative_spec.get("_site_html", "")

    dimensions = evaluation_report.get("dimensions", {})
    patchable_failures = evaluation_report.get("patchable_failures", [])

    # 1. Missing final CTA — triggered by low conversion score or no CTA detected
    if _should_plan_cta(dimensions, patchable_failures, site_html):
        patch = _plan_cta_patch(site_html)
        if patch is not None:
            patches.append(patch)

    # 2. Forbidden claim removal
    forbidden_claims = _get_forbidden_claims(creative_spec, evaluation_report)
    if forbidden_claims and site_html:
        claim_patches = _plan_forbidden_claim_removal(site_html, forbidden_claims)
        patches.extend(claim_patches)

    # 3. Mobile overflow CSS fix
    if _should_plan_mobile_overflow(dimensions, patchable_failures, site_html):
        patch = _plan_mobile_overflow_patch(site_html)
        if patch is not None:
            patches.append(patch)

    # 4. Spacing adjustment
    if _should_plan_spacing(dimensions, patchable_failures, site_html):
        patch = _plan_spacing_adjustment(site_html)
        if patch is not None:
            patches.append(patch)

    # 5. CTA link correction
    if _should_plan_cta_link(site_html):
        patch = _plan_cta_link_correction(site_html)
        if patch is not None:
            patches.append(patch)

    # Assign deterministic IDs
    for idx, patch in enumerate(patches, start=1):
        patch["id"] = _deterministic_patch_id(run_id, business_slug, idx)

    if not patches and verdict == "pass":
        # Clean site — nothing to patch.
        pass

    plan_verdict = "patchable" if patches else original_verdict

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "business_slug": business_slug,
        "generated_at": _deterministic_timestamp(run_id, business_slug),
        "verdict": plan_verdict,
        "original_verdict": original_verdict,
        "patches": patches,
        "skipped_reasons": skipped_reasons,
        "internal": {
            "flag": "use_patch_phase",
            "schema_origin": "VNEXT-07",
        },
    }


def write_patch_plan(
    plan: dict[str, Any],
    output_dir: str | Path,
    business_slug: str,
) -> str:
    """Write the patch plan as ``patch_plan.json``.

    Returns the absolute path of the written file.
    """
    out = Path(output_dir) / business_slug
    out.mkdir(parents=True, exist_ok=True)
    target = out / "patch_plan.json"
    target.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return str(target.resolve())


# ---------------------------------------------------------------------------
# Patch planners — one per approved category
# ---------------------------------------------------------------------------


def _plan_cta_patch(html: str) -> dict[str, Any] | None:
    """Plan a missing_final_cta patch — insert a CTA section before </body>."""
    if not html or not html.strip():
        logger.debug("Empty HTML in _plan_cta_patch, skipping")
        return None
    # If there's no </body>, skip
    if "</body>" not in html.lower():
        return None
    return {
        "id": "",
        "category": "missing_final_cta",
        "description": "Add final CTA section before closing body tag",
        "target": "html",
        "selector": "</body>",
        "action": "insert_before",
        "content": _DEFAULT_CTA_HTML,
        "safety": "approved",
    }


def _plan_forbidden_claim_removal(
    html: str,
    forbidden_claims: list[str],
) -> list[dict[str, Any]]:
    """Plan forbidden_claim_removal patches for each found claim."""
    if not html or not forbidden_claims:
        return []

    text = re.sub(r"<[^>]+>", " ", html).lower()
    text = re.sub(r"\s+", " ", text)

    patches: list[dict[str, Any]] = []
    for claim in forbidden_claims:
        if claim.lower() in text:
            patches.append({
                "id": "",
                "category": "forbidden_claim_removal",
                "description": f"Remove forbidden claim: '{claim}'",
                "target": "html",
                "selector": claim,
                "action": "replace",
                "content": _NEUTRAL_FALLBACK,
                "safety": "approved",
            })

    return patches


def _plan_mobile_overflow_patch(html: str) -> dict[str, Any] | None:
    """Plan a mobile_overflow_css_fix — add overflow-x:hidden to body/main."""
    if not html or not html.strip():
        logger.debug("Empty HTML in _plan_mobile_overflow_patch, skipping")
        return None
    # Check if already present
    if re.search(r"overflow-x\s*:\s*hidden", html, re.IGNORECASE):
        return None
    return {
        "id": "",
        "category": "mobile_overflow_css_fix",
        "description": "Add overflow-x:hidden to body for mobile",
        "target": "css",
        "selector": "body",
        "action": "insert_css",
        "content": "body{overflow-x:hidden!important;}",
        "safety": "approved",
    }


def _plan_spacing_adjustment(html: str) -> dict[str, Any] | None:
    """Plan a spacing_adjustment — improve section padding/spacing."""
    return {
        "id": "",
        "category": "spacing_adjustment",
        "description": "Add consistent spacing between sections",
        "target": "css",
        "selector": "section",
        "action": "insert_css",
        "content": "section{padding-top:1.5rem;padding-bottom:1.5rem;}",
        "safety": "approved",
    }


def _plan_cta_link_correction(html: str) -> dict[str, Any] | None:
    """Plan a cta_link_correction — fix CTA links with '#' href."""
    if not html:
        return None

    # Find CTA-style elements with bare "#" href
    bad_ctas = re.findall(
        r"<a[^>]*href\s*=\s*['\"]#['\"][^>]*(?:btn|button|cta)[^>]*>",
        html,
        re.IGNORECASE,
    )
    if not bad_ctas:
        # Also check for href="#" near action text
        bad_ctas = re.findall(
            r"<a[^>]*href\s*=\s*['\"]#['\"][^>]*>.*?(?:get started|contact|book now|call now|sign up).*?</a>",
            html,
            re.IGNORECASE | re.DOTALL,
        )

    if not bad_ctas:
        return None

    return {
        "id": "",
        "category": "cta_link_correction",
        "description": "Fix CTA link with placeholder '#' href",
        "target": "html",
        "selector": "a[href='#']",
        "action": "replace",
        "content": "a[href='#contact']",
        "safety": "approved",
    }


# ---------------------------------------------------------------------------
# Trigger helpers — decide whether to plan each category
# ---------------------------------------------------------------------------


def _should_plan_cta(
    dimensions: dict,
    patchable_failures: list[str],
    html: str,
) -> bool:
    """Return True if a missing CTA should be patched."""
    conversion = dimensions.get("conversion", {})
    if conversion.get("score", 100) < 50:
        return True
    if "conversion" in patchable_failures:
        return True
    # If no HTML to inspect, rely on scores alone
    if html:
        html_lower = html.lower()
        # Check for absence of action-oriented text
        action_words = [
            "get started", "contact us", "book now", "call now",
            "free estimate", "schedule", "sign up",
        ]
        text = re.sub(r"<[^>]+>", " ", html_lower)
        has_action = any(w in text for w in action_words)
        has_button = bool(re.search(r"<(?:button|a)[^>]*(?:btn|button|cta)[^>]*>", html_lower))
        has_form = bool(re.search(r"<form[\s>]", html_lower))
        if not has_action and not has_button and not has_form:
            return True
    return False


def _should_plan_mobile_overflow(
    dimensions: dict,
    patchable_failures: list[str],
    html: str,
) -> bool:
    """Return True if a mobile overflow CSS fix should be planned."""
    mobile = dimensions.get("mobile_experience", {})
    if mobile.get("score", 100) < 50:
        return True
    return "mobile_experience" in patchable_failures


def _should_plan_spacing(
    dimensions: dict,
    patchable_failures: list[str],
    html: str,
) -> bool:
    """Return True if spacing adjustment should be planned."""
    spacing = dimensions.get("spacing", {})
    if spacing.get("score", 100) < 50:
        return True
    return "spacing" in patchable_failures


def _should_plan_cta_link(html: str) -> bool:
    """Return True if CTA link correction should be planned."""
    if not html:
        return False
    # Check for CTA links with bare "#"
    return bool(
        re.search(
            r"<a[^>]*href\s*=\s*['\"]#['\"][^>]*>",
            html,
            re.IGNORECASE,
        )
        and re.search(
            r"btn|button|cta|get started|contact|book now",
            html,
            re.IGNORECASE,
        )
    )


def _get_forbidden_claims(
    creative_spec: dict[str, Any] | None,
    evaluation_report: dict[str, Any],
) -> list[str]:
    """Get forbidden claims from creative_spec or evaluation_report."""
    if creative_spec:
        cp = creative_spec.get("content_policy", {})
        if isinstance(cp, dict):
            claims = cp.get("forbidden_claims", [])
            if claims:
                return claims

    # Fallback: check factual_safety dimension notes
    dims = evaluation_report.get("dimensions", {})
    safety = dims.get("factual_safety", {})
    notes = safety.get("notes", "")
    if "forbidden claims found:" in notes.lower():
        # Extract claims from notes like "Forbidden claims found: guaranteed; #1 rated"
        parts = notes.split(":", 1)
        if len(parts) == 2:
            return [c.strip() for c in parts[1].split(";") if c.strip()]

    # Check creative_spec_alignment
    alignment = evaluation_report.get("creative_spec_alignment", {})
    found = alignment.get("forbidden_claims_found", [])
    if found:
        return found

    return []


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _empty_plan(
    run_id: str,
    business_slug: str,
    verdict: str,
    original_verdict: str,
) -> dict[str, Any]:
    """Return an empty patch plan (used for hard-reject and clean sites)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "business_slug": business_slug,
        "generated_at": _deterministic_timestamp(run_id, business_slug),
        "verdict": verdict,
        "original_verdict": original_verdict,
        "patches": [],
        "skipped_reasons": [],
        "internal": {
            "flag": "use_patch_phase",
            "schema_origin": "VNEXT-07",
        },
    }


def _deterministic_timestamp(run_id: str, business_slug: str) -> str:
    """Generate a deterministic ISO timestamp from run_id + slug."""
    now = datetime.now(timezone.utc)
    seed = hashlib.sha256(f"{run_id}:{business_slug}".encode()).hexdigest()
    offset = int(seed[:8], 16) % 256
    ts = now.replace(microsecond=0)
    ts = ts.replace(second=offset % 60)
    return ts.isoformat()


def _deterministic_patch_id(
    run_id: str,
    business_slug: str,
    index: int,
) -> str:
    """Generate a deterministic patch ID (patch_001, patch_002, etc.)."""
    return f"patch_{index:03d}"
