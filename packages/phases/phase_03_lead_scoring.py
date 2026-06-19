"""Phase 03: Lead Scoring for qualified lead selection.

Scores leads from Phase 02.1 output and filters to qualified leads.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any
from pipeline.json_io import read_json, write_json
from pipeline.result_envelope import ResultEnvelope
from packages.phases.business_intelligence_scorecard import (
    safe_float,
    safe_int,
    score_business_intelligence,
)

PHASE_NAME = "phase_03_lead_scoring"

# VNEXT-02: feature flag removed. market_profile.json logic moved to phase_04
# to align with 04_briefs output directory requirement.
USE_MARKET_PROFILE_CONTRACT_FLAG = "use_market_profile_contract"


def calculate_rating_score(rating: float, threshold: float) -> float:
    """Calculate rating component score (0-100)."""
    if rating <= 0:
        return 0.0
    if rating >= threshold:
        return 100.0
    # Linear scale from 0 to threshold
    return max(0.0, (rating / threshold) * 100)


def calculate_review_score(review_count: int, threshold: int) -> float:
    """Calculate review count component score (0-100)."""
    if review_count <= 0:
        return 0.0
    if review_count >= threshold:
        return 100.0
    # Logarithmic scaling - diminishing returns after threshold
    import math
    if threshold <= 0:
        return 100.0
    # Scale from 0 to threshold with logarithmic curve
    if review_count > 0:
        return min(100.0, (math.log10(review_count + 1) / math.log10(threshold + 1)) * 100)
    return 0.0


def calculate_contactability_score(
    phone: str,
    website_raw: str,
    website_status: str,
    maps_url: str,
) -> float:
    """Calculate contactability component score (0-100).

    Missing contact data is penalized but does not reject.
    """
    score = 0.0
    reasons = []

    if phone and phone.strip():
        score += 40
    else:
        reasons.append("no_phone")

    if website_raw and website_raw.strip():
        if website_status == "no_website":
            score += 20  # Social or no website is still a lead signal
        elif website_status == "social_only":
            score += 30  # Social profile for outreach
        else:
            score += 40  # Has website
    else:
        reasons.append("no_website_field")

    if maps_url and maps_url.strip():
        score += 20
    else:
        reasons.append("no_maps_url")

    return score, reasons


def check_chain_franchise(business_name: str, category: str) -> bool:
    """Check for chain/franchise signals in business name or category."""
    chain_keywords = [
        "mcdonald", "starbucks", "subway", "kfc", "burger king",
        "walmart", "target", "costco", "best buy", " franchise",
        "franchise", "corp", "corporation", "inc.", "llc",
        "location", "store #", "branch", "chain",
    ]
    name_lower = business_name.lower()
    cat_lower = category.lower()

    for keyword in chain_keywords:
        if keyword in name_lower or keyword in cat_lower:
            return True
    return False


def score_lead(
    lead: dict[str, Any],
    config: dict[str, Any],
    run_id: str = "",
) -> dict[str, Any]:
    """Score a single lead and return scored lead with components."""
    record_id = lead.get("record_id", "")
    business_slug = lead.get("business_slug", "")
    business_name = lead.get("business_name", "")
    rating = safe_float(lead.get("rating"), 0.0)
    review_count = safe_int(lead.get("review_count"), 0)
    phone = lead.get("phone", "") or ""
    website_raw = lead.get("website_raw", "") or ""
    website_status = lead.get("website_status", "no_website")
    maps_url = lead.get("maps_url", "") or ""
    business_status = lead.get("business_status", "unknown")
    category = lead.get("category", "") or ""
    lead_run_id = lead.get("run_id", run_id) or run_id

    # Get thresholds from config
    min_rating = config.get("minimum_rating", 4.3)
    min_reviews = config.get("minimum_reviews", 40)

    # Calculate component scores
    rating_score = calculate_rating_score(rating, min_rating)
    review_score = calculate_review_score(review_count, min_reviews)
    contact_score, contact_reasons = calculate_contactability_score(
        phone, website_raw, website_status, maps_url
    )

    # Check hard rejection criteria
    rejection_reasons = []
    hard_reject = False

    if business_status == "closed":
        rejection_reasons.append("business_closed")
        hard_reject = True

    if rating < min_rating:
        rejection_reasons.append("rating_below_threshold")
        hard_reject = True

    if review_count < min_reviews:
        rejection_reasons.append("review_count_below_threshold")
        hard_reject = True

    if check_chain_franchise(business_name, category):
        rejection_reasons.append("chain_franchise_signal")
        hard_reject = True

    # Overall lead score (weighted average)
    lead_score = (rating_score * 0.4 + review_score * 0.3 + contact_score * 0.3)

    # Determine qualification status
    if hard_reject:
        qualification_status = "rejected"
    elif lead_score >= 50:
        qualification_status = "qualified"
    elif lead_score >= 30:
        qualification_status = "needs_review"
    else:
        qualification_status = "rejected"
        if not rejection_reasons:
            rejection_reasons.append("score_below_threshold")

    # Build scored lead
    business_intelligence = score_business_intelligence(lead, config)
    scored_lead = {
        "run_id": lead_run_id,
        "record_id": record_id,
        "business_slug": business_slug,
        "business_name": business_name,
        "category": category,
        "rating": rating,
        "review_count": review_count,
        "address": lead.get("address", "") or "",
        "hours": lead.get("hours", "") or "",
        "business_status": business_status,
        "website_status": website_status,
        "phone": phone,
        "website_raw": website_raw,
        "maps_url": maps_url,
        "scoring": {
            "rating_score": round(rating_score, 2),
            "review_score": round(review_score, 2),
            "contactability_score": round(contact_score, 2),
            "lead_score": round(lead_score, 2),
        },
        "business_intelligence": business_intelligence,
        "qualification_status": qualification_status,
        "rejection_reasons": rejection_reasons,
        "scoring_notes": {
            "contactability_issues": contact_reasons,
        },
    }

    return scored_lead


def run(
    run_id: str,
    workspace: str,
    config: dict[str, Any] | None = None,
    input_leads: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute Phase 03 lead scoring and return result envelope.

    Args:
        run_id: Run identifier
        workspace: Base workspace directory
        config: RunConfig with thresholds. If None, reads from workspace.
        input_leads: List of leads from Phase 02.1. If None, reads from fixture path.

    Returns:
        Result envelope dict
    """
    workspace_path = Path(workspace)

    # Check for required Phase 02.1 output
    phase_dir = workspace_path / "runs" / run_id / "02_1_website_filter"
    if not phase_dir.exists():
        return ResultEnvelope.blocked(
            phase=PHASE_NAME,
            run_id=run_id,
            missing_fields=["leads_no_website"],
            inputs_used=[],
            errors=["Phase 02.1 must complete before Phase 03"],
        ).to_dict()

    # Load config if not provided
    if config is None:
        config_path = workspace_path / "runs" / run_id / "config" / "run_config.json"
        if config_path.exists():
            config = read_json(str(config_path))
        else:
            config = {
                "minimum_rating": 4.3,
                "minimum_reviews": 40,
                "max_preview_sites": 5,
            }

    # Load input leads
    if input_leads is None:
        workspace_input = workspace_path / "runs" / run_id / "02_1_website_filter" / "leads_no_website.json"
        fixture_input = workspace_path / "tests" / "fixtures" / PHASE_NAME / "input" / "qualified_high_rating_many_reviews.json"

        if workspace_input.exists():
            input_leads = read_json(str(workspace_input))
        elif fixture_input.exists():
            input_leads = read_json(str(fixture_input))
        else:
            return ResultEnvelope.blocked(
                phase=PHASE_NAME,
                run_id=run_id,
                missing_fields=["leads_no_website"],
                inputs_used=[],
            ).to_dict()

    # Create output directory
    output_dir = workspace_path / "runs" / run_id / "03_scoring"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Score all leads
    scored_leads = []
    for lead in input_leads:
        if not lead.get("record_id"):
            continue
        scored_lead = score_lead(lead, config, run_id=run_id)
        scored_leads.append(scored_lead)

    # Partition by qualification status
    qualified_leads = [lead for lead in scored_leads if lead["qualification_status"] == "qualified"]
    needs_review = [lead for lead in scored_leads if lead["qualification_status"] == "needs_review"]
    rejected = [lead for lead in scored_leads if lead["qualification_status"] == "rejected"]

    # Select for preview (top qualified up to max_preview_sites)
    max_preview = config.get("max_preview_sites", 5)
    selected_for_preview = sorted(
        qualified_leads,
        key=lambda x: (
            x.get("business_intelligence", {}).get("overall_score", 0),
            x["scoring"]["lead_score"],
        ),
        reverse=True,
    )[:max_preview]

    # Write outputs
    leads_scored_path = output_dir / "leads_scored.json"
    leads_scored_csv_path = output_dir / "leads_scored.csv"
    qualified_path = output_dir / "qualified_leads.json"
    selected_path = output_dir / "selected_for_preview.json"
    result_path = output_dir / "result.json"

    write_json(str(leads_scored_path), scored_leads)
    write_json(str(qualified_path), qualified_leads)
    write_json(str(selected_path), selected_for_preview)

    # Write CSV
    with open(leads_scored_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "record_id", "business_name", "rating", "review_count",
            "lead_score", "rating_score", "review_score", "contactability_score",
            "qualification_status", "rejection_reasons",
        ])
        for lead in scored_leads:
            writer.writerow([
                lead["record_id"],
                lead["business_name"],
                lead["rating"],
                lead["review_count"],
                lead["scoring"]["lead_score"],
                lead["scoring"]["rating_score"],
                lead["scoring"]["review_score"],
                lead["scoring"]["contactability_score"],
                lead["qualification_status"],
                ";".join(lead["rejection_reasons"]) if lead["rejection_reasons"] else "",
            ])

    # Determine status
    if len(input_leads) == 0:
        status = "blocked"
    elif len(scored_leads) == 0:
        status = "blocked"
    else:
        status = "done"

    result = ResultEnvelope(
        phase=PHASE_NAME,
        status=status,
        run_id=run_id,
        inputs_used=["leads_no_website", "run_config"],
        outputs_created=[
            "03_scoring/leads_scored.json",
            "03_scoring/leads_scored.csv",
            "03_scoring/qualified_leads.json",
            "03_scoring/selected_for_preview.json",
            "03_scoring/result.json",
        ],
        records_processed=len(input_leads),
        records_created=len(scored_leads),
        records_skipped=len(rejected),
        decisions=[
            f"Scored {len(scored_leads)} leads",
            f"{len(qualified_leads)} qualified leads",
            f"{len(needs_review)} leads need review",
            f"{len(rejected)} rejected leads",
            f"{len(selected_for_preview)} selected for preview",
        ],
    ).model_dump(exclude_none=True, by_alias=True)

    write_json(str(result_path), result)

    return result


if __name__ == "__main__":
    import sys
    workspace = sys.argv[1] if len(sys.argv) > 1 else "."
    run_id = sys.argv[2] if len(sys.argv) > 2 else "test_run"
    result = run(workspace, run_id)
    print(f"Phase 03 complete: {result['status']}")