"""Phase 02.1: Website Filter for Early Lead Screening.

Classifies leads by website status per pipeline_data_contract.md.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pipeline.contracts import WebsiteClassification
from pipeline.json_io import read_json, write_json
from pipeline.result_envelope import ResultEnvelope


PHASE_NAME = "phase_02_1_website_filter"

# Social media domains that indicate social_only status
SOCIAL_DOMAINS = {
    "facebook.com", "fb.com", "instagram.com", "messenger.com",
    "twitter.com", "x.com", "linkedin.com", "line.me", "lin.ee",
    "tiktok.com", "youtube.com", "youtu.be", "pinterest.com",
}

# Shortlink domains that require verification
SHORTLINK_DOMAINS = {
    "bit.ly", "tinyurl.com", "goo.gl", "ow.ly", "buff.ly",
    "polr.me", "shorte.st", "adcrun.ch", "cutt.ly", "is.gd",
}

# Google Maps pattern
MAPS_PATTERN = re.compile(r"maps\.google\.com|google\..*maps", re.I)


def classify_website(website_raw: str) -> tuple[str, str, list[str]]:
    """Classify website URL into website_status, domain_type, and reason_codes.

    Returns:
        Tuple of (website_status, domain_type, reason_codes)
    """
    if not website_raw or not website_raw.strip():
        return "no_website", "empty", ["empty_website_field"]

    url = website_raw.strip()

    # Normalize URL
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Remove www. prefix
        if domain.startswith("www."):
            domain = domain[4:]
    except Exception:
        return "invalid_url", "malformed", ["malformed_url"]

    # Check for Google Maps URL
    if MAPS_PATTERN.search(url):
        return "uncertain", "maps", ["maps_url_no_website"]

    # Check for social media domains
    for social_domain in SOCIAL_DOMAINS:
        if domain.endswith(social_domain) or social_domain in domain:
            return "social_only", "social", ["social_profile_url"]

    # Check for shortlinks
    for short_domain in SHORTLINK_DOMAINS:
        if domain == short_domain or domain.endswith("." + short_domain):
            return "uncertain", "unknown", ["shortlink_url"]

    # Check for bio-link services
    bio_link_patterns = ["linktr.ee", "beacons.ai", "bio.link", "linkin.bio", "carrd.co"]
    for pattern in bio_link_patterns:
        if domain.endswith(pattern) or pattern in domain:
            return "uncertain", "unknown", ["bio_link_url"]

    # Check for clearly invalid domains
    if "." not in domain or len(domain) < 3:
        return "invalid_url", "malformed", ["invalid_domain_format"]

    # Looks like a business domain
    return "has_website", "business_domain", ["business_domain_detected"]


def make_website_classification(
    run_id: str,
    record_id: str,
    business_slug: str,
    website_raw: str,
) -> WebsiteClassification:
    """Create WebsiteClassification from input data."""
    website_status, domain_type, reason_codes = classify_website(website_raw)

    # Determine decision based on status
    if website_status in ("no_website", "social_only"):
        decision = "keep"
    elif website_status == "has_website":
        decision = "skip"
    else:
        # uncertain or invalid_url -> manual_review or skip per contract
        decision = "manual_review"

    # Normalize URL for output
    website_normalized = website_raw.strip() if website_raw else ""
    if website_normalized and not website_normalized.startswith(("http://", "https://")):
        website_normalized = "https://" + website_normalized

    # Extract registered domain
    registered_domain = ""
    if website_raw:
        try:
            parsed = urlparse(website_raw if website_raw.startswith("http") else "https://" + website_raw)
            registered_domain = parsed.netloc.lower()
            if registered_domain.startswith("www."):
                registered_domain = registered_domain[4:]
        except Exception:
            registered_domain = ""

    # Confidence based on certainty of classification
    confidence = 0.9 if website_status in ("no_website", "has_website", "social_only") else 0.5

    return WebsiteClassification(
        run_id=run_id,
        record_id=record_id,
        business_slug=business_slug,
        website_raw=website_raw or "",
        website_normalized=website_normalized,
        registered_domain=registered_domain,
        domain_type=domain_type,
        website_status=website_status,
        confidence=confidence,
        decision=decision,
        reason_codes=reason_codes,
        http_checked=False,
        http_status=None,
        final_url=None,
        redirect_chain=[],
        checked_redirect=False,
        website_resolution_status="not_checked",
        notes=[],
    )


def run(
    run_id: str,
    workspace: str,
    input_leads: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute Phase 02.1 and return result envelope.

    Args:
        run_id: Run identifier
        workspace: Base workspace directory
        input_leads: List of normalized place dicts. If None, reads from fixture path.

    Returns:
        Result envelope dict
    """
    workspace_path = Path(workspace)

    # Check for required Phase 02 outputs
    phase_dir = workspace_path / "runs" / run_id / "02_discovery"
    if not phase_dir.exists():
        return ResultEnvelope.blocked(
            phase=PHASE_NAME,
            run_id=run_id,
            missing_fields=["leads_normalized"],
            inputs_used=[],
            errors=["Phase 02 must complete before Phase 02.1"],
        ).to_dict()

    # Load input
    if input_leads is None:
        # First try workspace path for inter-phase consistency
        workspace_input = workspace_path / "runs" / run_id / "02_discovery" / "leads_normalized.json"
        if workspace_input.exists():
            input_leads = read_json(str(workspace_input))
        else:
            # Fall back to fixture path
            input_path = workspace_path / "tests" / "fixtures" / PHASE_NAME / "input" / "leads_normalized_edge_cases.json"
            if not input_path.exists():
                return ResultEnvelope.blocked(
                    phase=PHASE_NAME,
                    run_id=run_id,
                    missing_fields=["leads_normalized"],
                    inputs_used=[],
                ).to_dict()
            input_leads = read_json(str(input_path))

    # Create output directory
    output_dir = workspace_path / "runs" / run_id / "02_1_website_filter"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Process leads
    classifications: list[dict[str, Any]] = []
    leads_no_website: list[dict[str, Any]] = []
    skipped_has_website: list[dict[str, Any]] = []
    manual_review: list[dict[str, Any]] = []

    for lead in input_leads:
        record_id = lead.get("record_id", "")
        business_slug = lead.get("business_slug", "")
        website_raw = lead.get("website_raw", "")

        # Skip records without record_id or business_name
        if not record_id or not lead.get("business_name"):
            continue

        classification = make_website_classification(
            run_id=run_id,
            record_id=record_id,
            business_slug=business_slug,
            website_raw=website_raw,
        )
        classifications.append(classification.model_dump())

        # Route to appropriate output
        if classification.decision == "keep":
            leads_no_website.append(lead)
        elif classification.decision == "skip":
            skipped_has_website.append(lead)
        else:
            manual_review.append(lead)

    # Write outputs
    leads_no_website_path = output_dir / "leads_no_website.json"
    skipped_path = output_dir / "skipped_has_website.json"
    manual_path = output_dir / "manual_review_website.json"
    report_path = output_dir / "website_filter_report.json"
    resolution_path = output_dir / "website_resolution_checks.json"
    result_path = output_dir / "result.json"

    write_json(str(leads_no_website_path), leads_no_website)
    write_json(str(skipped_path), skipped_has_website)
    write_json(str(manual_path), manual_review)

    # Create website filter report
    report = {
        "run_id": run_id,
        "phase": "02_1_website_filter",
        "records_processed": len(input_leads),
        "leads_no_website_count": len(leads_no_website),
        "skipped_has_website_count": len(skipped_has_website),
        "manual_review_count": len(manual_review),
        "classifications": [
            {
                "record_id": c["record_id"],
                "website_status": c["website_status"],
                "decision": c["decision"],
                "reason_codes": c["reason_codes"],
            }
            for c in classifications
        ],
        "status": "complete",
    }
    write_json(str(report_path), report)

    # Write website resolution checks (empty for MVP - no HTTP checks)
    resolution_checks = {
        "run_id": run_id,
        "checks_performed": 0,
        "checks": [],
    }
    write_json(str(resolution_path), resolution_checks)

    # Determine status
    if len(input_leads) == 0:
        status = "blocked"
    elif len(manual_review) > 0:
        status = "done"  # Non-empty manual review is valid output
    else:
        status = "done"

    result = ResultEnvelope(
        phase=PHASE_NAME,
        status=status,
        run_id=run_id,
        inputs_used=["leads_normalized"],
        outputs_created=[
            "02_1_website_filter/leads_no_website.json",
            "02_1_website_filter/skipped_has_website.json",
            "02_1_website_filter/manual_review_website.json",
            "02_1_website_filter/website_filter_report.json",
            "02_1_website_filter/website_resolution_checks.json",
            "02_1_website_filter/result.json",
        ],
        records_processed=len(input_leads),
        records_created=len(classifications),
        records_skipped=0,
        decisions=[
            f"Classified {len(input_leads)} leads",
            f"{len(leads_no_website)} leads with no_website or social_only kept",
            f"{len(skipped_has_website)} leads with has_website skipped",
            f"{len(manual_review)} leads routed to manual review",
        ],
    ).model_dump(exclude_none=True, by_alias=True)

    write_json(str(result_path), result)

    return result


if __name__ == "__main__":
    import sys
    workspace = sys.argv[1] if len(sys.argv) > 1 else "."
    run_id = sys.argv[2] if len(sys.argv) > 2 else "test_run"
    result = run(workspace, run_id)
    print(f"Phase 02.1 complete: {result['status']}")