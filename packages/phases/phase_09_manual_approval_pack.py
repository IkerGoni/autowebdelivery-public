"""Phase 09 — Manual Approval Pack for operator review.

Build the operator review pack from approved preview sites and outreach drafts.

Inputs:
  - runs/{run_id}/05_sites/{business_slug}/ (screenshots, build_status.json)
  - runs/{run_id}/06_quality/{business_slug}/site_quality_report.json
  - runs/{run_id}/07_deployments/{business_slug}/deployment_record.json
  - runs/{run_id}/08_outreach/outreach_drafts.json
  - runs/{run_id}/03_scoring/leads_scored.json
  - runs/{run_id}/04_briefs/{business_slug}/recipient_channel.json

Outputs:
  - runs/{run_id}/09_review/review_table.csv
  - runs/{run_id}/09_review/review_pack.md
  - runs/{run_id}/09_review/screenshots_index.json
  - runs/{run_id}/09_review/approval_decisions.json
  - runs/{run_id}/09_review/result.json
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from pipeline.json_io import read_json, write_json
    from pipeline.result_envelope import ResultEnvelope
except ModuleNotFoundError:  # pragma: no cover - CLI fallback
    from packages.pipeline.json_io import read_json, write_json
    from packages.pipeline.result_envelope import ResultEnvelope

from packages.shared.provenance import _safe_str

PHASE_NAME = "phase_09_manual_approval_pack"
PHASE_SLUG = "09_review"

SEND_APPROVAL_CHECKLIST_FIELDS = [
    "identity_truthful_confirmed",
    "subject_truthful_confirmed",
    "no_fake_relationship_confirmed",
    "no_fake_urgency_confirmed",
    "preview_disclosure_confirmed",
    "verified_facts_only_confirmed",
    "opt_out_path_confirmed",
    "sender_contact_confirmed",
    "public_preview_reviewed",
    "takedown_policy_reviewed",
]

SEND_APPROVAL_CHECKLIST_DEFAULTS = {
    **{field: False for field in SEND_APPROVAL_CHECKLIST_FIELDS},
    "reviewer_name": "",
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return default


def build_review_record(
    lead_score: dict[str, Any],
    recipient_channel: dict[str, Any],
    deployment: dict[str, Any],
    outreach: dict[str, Any] | None,
    site_info: dict[str, Any],
) -> dict[str, Any]:
    """Build a single review record for the table."""
    business_slug = _safe_str(lead_score.get("business_slug", ""))
    lead_score_val = _safe_float(lead_score.get("lead_score", 0))

    return {
        "business_slug": business_slug,
        "business_name": _safe_str(lead_score.get("business_name", "")),
        "lead_score": lead_score_val,
        "qualification_status": _safe_str(lead_score.get("qualification_status", "")),
        "recipient_channel": _safe_str(recipient_channel.get("recipient_channel", "unknown")),
        "recipient_value": _safe_str(recipient_channel.get("recipient_value", "")),
        "preview_url": _safe_str(deployment.get("preview_url", "")),
        "preview_url_type": _safe_str(deployment.get("preview_url_type", "")),
        "outward_send_allowed": bool(deployment.get("outward_send_allowed", False)),
        "deployment_status": _safe_str(deployment.get("deployment_status", "")),
        "site_status": site_info.get("status", "unknown"),
        "screenshot_desktop_path": site_info.get("screenshot_desktop_path", ""),
        "screenshot_mobile_path": site_info.get("screenshot_mobile_path", ""),
        "draft_status": _safe_str(outreach.get("draft_status", "missing")) if outreach else "missing",
        "outreach_subject": _safe_str(outreach.get("subject", "")) if outreach else "",
        "approval_status": "pending",
        "site_review_status": "approved" if site_info.get("status") == "approved_for_deploy" else "needs_review",
        "outreach_review_status": "approved" if outreach and outreach.get("draft_status") == "ready_for_review" else "needs_edit",
        **SEND_APPROVAL_CHECKLIST_DEFAULTS,
    }


def generate_review_table_csv(records: list[dict[str, Any]], output_path: Path) -> None:
    """Generate CSV review table for operator."""
    headers = [
        "business_slug", "business_name", "lead_score", "qualification_status",
        "recipient_channel", "preview_url", "preview_url_type", "outward_send_allowed", "site_status", "draft_status",
        "approval_status", "site_review_status", "outreach_review_status",
        *SEND_APPROVAL_CHECKLIST_FIELDS, "reviewer_name",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def generate_review_pack_md(records: list[dict[str, Any]], output_path: Path) -> None:
    """Generate markdown review pack for operator review."""
    lines = ["# Manual Approval Pack", "", f"Generated: {datetime.now(timezone.utc).isoformat()}", ""]

    for rec in records:
        lines.extend([
            f"## {rec['business_name']} ({rec['business_slug']})",
            "",
            f"- **Lead Score**: {rec['lead_score']}",
            f"- **Recipient Channel**: {rec['recipient_channel']}",
            f"- **Preview URL**: {rec['preview_url'] or 'N/A'}",
            f"- **Preview URL Type**: {rec.get('preview_url_type') or 'N/A'}",
            f"- **Outward Send Allowed**: {rec.get('outward_send_allowed', False)}",
            f"- **Site Status**: {rec['site_status']}",
            f"- **Draft Status**: {rec['draft_status']}",
            "",
            "### Send Approval Checklist",
            "",
            "- [ ] Identity truthful confirmed",
            "- [ ] Subject truthful confirmed",
            "- [ ] No fake relationship confirmed",
            "- [ ] No fake urgency confirmed",
            "- [ ] Preview disclosure confirmed",
            "- [ ] Verified facts only confirmed",
            "- [ ] Opt-out path confirmed",
            "- [ ] Sender contact confirmed",
            "- [ ] Public preview reviewed",
            "- [ ] Takedown policy reviewed",
            "- Reviewer name: ",
            "",
        ])

    output_path.write_text("\n".join(lines), encoding="utf-8")


def generate_screenshots_index(records: list[dict[str, Any]], output_path: Path) -> None:
    """Generate screenshots index JSON."""
    index = [
        {
            "business_slug": rec["business_slug"],
            "screenshot_desktop_path": rec["screenshot_desktop_path"],
            "screenshot_mobile_path": rec["screenshot_mobile_path"],
        }
        for rec in records
        if rec["screenshot_desktop_path"] and rec["screenshot_mobile_path"]
    ]
    write_json(str(output_path), index)


def generate_approval_decisions(records: list[dict[str, Any]], output_path: Path, run_id: str = "") -> None:
    """Generate approval decisions JSON with default pending status."""
    decisions = []
    for rec in records:
        decision = {
            "run_id": run_id or rec.get("run_id", ""),
            "record_id": rec.get("record_id", ""),
            "business_slug": rec["business_slug"],
            "approval_status": "pending",
            "site_review_status": rec["site_review_status"],
            "outreach_review_status": rec["outreach_review_status"],
            "preview_url_type": rec.get("preview_url_type", ""),
            "outward_send_allowed": rec.get("outward_send_allowed", False),
            "screenshot_path": "",
            "screenshot_desktop_path": rec["screenshot_desktop_path"],
            "screenshot_mobile_path": rec["screenshot_mobile_path"],
            "reviewer_notes": "",
            "approved_at": "",
            **SEND_APPROVAL_CHECKLIST_DEFAULTS,
        }
        decisions.append(decision)

    write_json(str(output_path), decisions)


def run_phase_09(run_id: str, workspace: str, *, skip_missing_stubs: bool = False) -> dict[str, Any]:
    root = Path(workspace)


    missing_fields: list[str] = []
    stub_07 = False
    stub_08 = False

    if not (root / "runs" / run_id / "07_deployments").exists():
        if skip_missing_stubs:
            stub_07 = True
        else:
            missing_fields.append(str(root / "runs" / run_id / "07_deployments"))

    if not (root / "runs" / run_id / "08_outreach" / "outreach_drafts.json").exists():
        if skip_missing_stubs:
            stub_08 = True
        else:
            missing_fields.append(str(root / "runs" / run_id / "08_outreach" / "outreach_drafts.json"))

    other_required = [
        root / "runs" / run_id / "05_sites",
        root / "runs" / run_id / "06_quality",
        root / "runs" / run_id / "03_scoring" / "leads_scored.json",
        root / "runs" / run_id / "04_briefs",
    ]
    for path in other_required:
        if not path.exists():
            missing_fields.append(str(path))

    if missing_fields:
        return ResultEnvelope.blocked(
            phase=PHASE_NAME,
            run_id=run_id,
            missing_fields=missing_fields,
            inputs_used=[],
            errors=[
                "Phase 05, 06, 03, and 04 outputs required before Phase 09. "
                "Phase 07/08 can be stubbed with skip_missing_stubs=True."
            ],
        ).to_dict()

    # Stub Phase 07/08 if requested and missing
    if stub_07:
        deploy_dir = root / "runs" / run_id / "07_deployments"
        deploy_dir.mkdir(parents=True, exist_ok=True)
        write_json(str(deploy_dir / "deployments.json"), [])

    if stub_08:
        outreach_dir = root / "runs" / run_id / "08_outreach"
        outreach_dir.mkdir(parents=True, exist_ok=True)
        write_json(str(outreach_dir / "outreach_drafts.json"), [])

    # Load data
    outreach_drafts = read_json(str(root / "runs" / run_id / "08_outreach" / "outreach_drafts.json"))
    leads_scored = read_json(str(root / "runs" / run_id / "03_scoring" / "leads_scored.json"))

    # Build lookup maps
    outreach_by_slug = {d.get("business_slug"): d for d in outreach_drafts}
    lead_score_by_slug = {s.get("business_slug"): s for s in leads_scored}

    # Process each deployed site
    records: list[dict[str, Any]] = []
    sites_dir = root / "runs" / run_id / "05_sites"

    # If stubbed, create per-business deployment records so the loop finds them
    if stub_07:
        for site_subdir in sites_dir.iterdir():
            if site_subdir.is_dir():
                biz_stub = deploy_dir / site_subdir.name / "deployment_record.json"
                biz_stub.parent.mkdir(parents=True, exist_ok=True)
                write_json(str(biz_stub), {
                    "business_slug": site_subdir.name,
                    "preview_url": f"https://{site_subdir.name}.example.com",
                    "preview_url_type": "https",
                    "outward_send_allowed": False,
                    "deployment_status": "stubbed",
                })

    for site_subdir in sites_dir.iterdir():
        if not site_subdir.is_dir():
            continue

        business_slug = site_subdir.name

        # Check both screenshots exist
        screenshot_desktop = site_subdir / "screenshot_desktop.png"
        screenshot_mobile = site_subdir / "screenshot_mobile.png"

        if not screenshot_desktop.exists() or not screenshot_mobile.exists():
            continue  # Skip sites missing required screenshots

        # Load quality report
        quality_path = root / "runs" / run_id / "06_quality" / business_slug / "site_quality_report.json"
        if not quality_path.exists():
            continue

        quality_report = read_json(str(quality_path))
        site_status = quality_report.get("status", "unknown")

        # Load deployment record
        deploy_path = root / "runs" / run_id / "07_deployments" / business_slug / "deployment_record.json"
        if not deploy_path.exists():
            continue

        deployment = read_json(str(deploy_path))

        # Load recipient channel
        recipient_path = root / "runs" / run_id / "04_briefs" / business_slug / "recipient_channel.json"
        if not recipient_path.exists():
            continue

        recipient_channel = read_json(str(recipient_path))

        # Get lead score
        lead_score = lead_score_by_slug.get(business_slug, {})

        # Get outreach draft
        outreach = outreach_by_slug.get(business_slug)

        # Build review record
        record = build_review_record(
            lead_score=lead_score,
            recipient_channel=recipient_channel,
            deployment=deployment,
            outreach=outreach,
            site_info={
                "status": site_status,
                "screenshot_desktop_path": str(screenshot_desktop),
                "screenshot_mobile_path": str(screenshot_mobile),
            },
        )
        records.append(record)

    # Create output directory
    output_dir = root / "runs" / run_id / PHASE_SLUG
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate outputs
    generate_review_table_csv(records, output_dir / "review_table.csv")
    generate_review_pack_md(records, output_dir / "review_pack.md")
    generate_screenshots_index(records, output_dir / "screenshots_index.json")
    generate_approval_decisions(records, output_dir / "approval_decisions.json", run_id=run_id)

    result = ResultEnvelope(
        phase=PHASE_NAME,
        status="done",
        run_id=run_id,
        inputs_used=[
            f"runs/{run_id}/05_sites",
            f"runs/{run_id}/06_quality",
            f"runs/{run_id}/07_deployments",
            f"runs/{run_id}/08_outreach/outreach_drafts.json",
            f"runs/{run_id}/03_scoring/leads_scored.json",
            f"runs/{run_id}/04_briefs",
        ],
        outputs_created=[
            f"runs/{run_id}/{PHASE_SLUG}/review_table.csv",
            f"runs/{run_id}/{PHASE_SLUG}/review_pack.md",
            f"runs/{run_id}/{PHASE_SLUG}/screenshots_index.json",
            f"runs/{run_id}/{PHASE_SLUG}/approval_decisions.json",
            f"runs/{run_id}/{PHASE_SLUG}/result.json",
        ],
        records_processed=len(records),
        records_created=len(records),
        decisions=[
            f"Generated review pack for {len(records)} businesses",
        ],
        next_tasks=["Phase 10 — Manual Sending"] if len(records) > 0 else [],
    ).model_dump(exclude_none=True, by_alias=True)

    write_json(str(output_dir / "result.json"), result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 09 — Manual Approval Pack")
    parser.add_argument("--run-id", default="fixture_001", help="Run ID (default: fixture_001)")
    parser.add_argument("--project-root", default=".", help="Project root (default: current directory)")
    args = parser.parse_args()

    result = run_phase_09(args.run_id, args.project_root)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()