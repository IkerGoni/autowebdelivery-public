"""Phase 10 — manual sending log.

No automated sending. Build local-only helper artifacts and sent log from
operator approvals plus manual confirmations.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

try:
    from pipeline.json_io import read_json, write_json
    from pipeline.result_envelope import ResultEnvelope
except ModuleNotFoundError:  # pragma: no cover - CLI fallback
    from packages.pipeline.json_io import read_json, write_json
    from packages.pipeline.result_envelope import ResultEnvelope

from packages.shared.provenance import _safe_str

PHASE_NAME = "phase_10_manual_sending"
PHASE_SLUG = "10_sent"
ALLOWED_SENT_CHANNELS = {
    "email",
    "contact_form",
    "phone",
    "facebook_message",
    "instagram_dm",
    "whatsapp",
    "line",
}
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


def _build_mailto_url(recipient_value: str, subject: str, body: str) -> str:
    recipient = quote(recipient_value, safe="@")
    query = f"subject={quote(subject)}&body={quote(body)}"
    return f"mailto:{recipient}?{query}"


def _is_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def build_send_queue_record(
    approval: dict[str, Any],
    draft: dict[str, Any],
) -> dict[str, Any]:
    recipient_channel = _safe_str(draft.get("recipient_channel", "unknown"))
    recipient_value = _safe_str(draft.get("recipient_value"))
    subject = _safe_str(draft.get("subject"))
    body = _safe_str(draft.get("body"))
    preview_url = _safe_str(draft.get("preview_url"))
    blocked_reasons: list[str] = []

    if approval.get("approval_status") != "send":
        blocked_reasons.append("approval_status is not send")
    if recipient_channel not in ALLOWED_SENT_CHANNELS:
        blocked_reasons.append(f"recipient_channel is not known: {recipient_channel or 'missing'}")
    if not preview_url:
        blocked_reasons.append("preview_url is missing")
    elif not _is_https_url(preview_url):
        blocked_reasons.append("preview_url is not https")
    if _safe_str(draft.get("draft_status")) != "ready_for_review":
        blocked_reasons.append("draft_status is not ready_for_review")
    if "outward_send_allowed" in approval:
        outward_send_allowed = _is_true(approval.get("outward_send_allowed"))
    elif "outward_send_allowed" in draft:
        outward_send_allowed = _is_true(draft.get("outward_send_allowed"))
    else:
        outward_send_allowed = False
    if not outward_send_allowed:
        blocked_reasons.append("outward_send_allowed is not true")
    for field in SEND_APPROVAL_CHECKLIST_FIELDS:
        if not _is_true(approval.get(field)):
            blocked_reasons.append(f"{field} is not true")

    return {
        "run_id": _safe_str(approval.get("run_id") or draft.get("run_id")),
        "record_id": _safe_str(approval.get("record_id") or draft.get("record_id")),
        "business_slug": _safe_str(approval.get("business_slug") or draft.get("business_slug")),
        "business_name": _safe_str(draft.get("business_name")),
        "niche": _safe_str(draft.get("niche")),
        "area": _safe_str(draft.get("area")),
        "country": _safe_str(draft.get("country")),
        "template_family": _safe_str(draft.get("template_family")),
        "template_variant": _safe_str(draft.get("template_variant")),
        "stitch_project_id": _safe_str(draft.get("stitch_project_id")),
        "offer_type": _safe_str(draft.get("offer_type")),
        "offer_price": _safe_str(draft.get("offer_price")),
        "currency": _safe_str(draft.get("currency")),
        "pricing_market": _safe_str(draft.get("pricing_market")),
        "approval_status": _safe_str(approval.get("approval_status")),
        "automation_mode": "manual_required",
        "recipient_channel": recipient_channel,
        "recipient_value": recipient_value,
        "subject": subject,
        "body": body,
        "preview_url": preview_url,
        "draft_status": _safe_str(draft.get("draft_status")),
        "send_ready": len(blocked_reasons) == 0,
        "blocked_reasons": blocked_reasons,
        "mailto_url": _build_mailto_url(recipient_value, subject, body) if recipient_channel == "email" and recipient_value else "",
    }


def build_sent_log_record(
    run_id: str,
    approval: dict[str, Any],
    draft: dict[str, Any],
    confirmation: dict[str, Any] | None,
) -> dict[str, Any]:
    sent_channel = _safe_str((confirmation or {}).get("sent_channel"))
    sent_status = _safe_str((confirmation or {}).get("sent_status")) or "not_sent"
    errors: list[str] = []

    if sent_channel and sent_channel not in ALLOWED_SENT_CHANNELS:
        errors.append(f"invalid sent_channel: {sent_channel}")
    if sent_status not in {"sent", "not_sent", "failed"}:
        errors.append(f"invalid sent_status: {sent_status}")
    if sent_status == "sent":
        for field in ("sent_channel", "sent_at", "sender_account", "message_ref"):
            if not _safe_str((confirmation or {}).get(field)):
                errors.append(f"sent_status=sent requires {field}")

    normalized_sent_status = sent_status if sent_status in {"sent", "not_sent", "failed"} else "failed"
    if errors:
        normalized_sent_status = "failed"

    return {
        "run_id": run_id,
        "record_id": _safe_str(approval.get("record_id") or draft.get("record_id")),
        "business_slug": _safe_str(approval.get("business_slug") or draft.get("business_slug")),
        "business_name": _safe_str(draft.get("business_name")),
        "niche": _safe_str(draft.get("niche")),
        "area": _safe_str(draft.get("area")),
        "country": _safe_str(draft.get("country")),
        "template_family": _safe_str(draft.get("template_family")),
        "template_variant": _safe_str(draft.get("template_variant")),
        "stitch_project_id": _safe_str(draft.get("stitch_project_id")),
        "offer_type": _safe_str(draft.get("offer_type")),
        "offer_price": _safe_str(draft.get("offer_price")),
        "currency": _safe_str(draft.get("currency")),
        "pricing_market": _safe_str(draft.get("pricing_market")),
        "automation_mode": "manual_required",
        "sent_status": normalized_sent_status,
        "sent_channel": sent_channel,
        "sent_at": _safe_str((confirmation or {}).get("sent_at")),
        "sender_account": _safe_str((confirmation or {}).get("sender_account")),
        "message_ref": _safe_str((confirmation or {}).get("message_ref")),
        "notes": _safe_str((confirmation or {}).get("notes")),
        "source_recipient_channel": _safe_str(draft.get("recipient_channel")),
        "source_recipient_value": _safe_str(draft.get("recipient_value")),
        "preview_url": _safe_str(draft.get("preview_url")),
        "errors": errors,
    }


def write_sent_log_csv(records: list[dict[str, Any]], output_path: Path) -> None:
    headers = [
        "run_id",
        "record_id",
        "business_slug",
        "sent_status",
        "sent_channel",
        "sent_at",
        "sender_account",
        "message_ref",
        "notes",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def write_manual_send_checklist(records: list[dict[str, Any]], output_path: Path) -> None:
    lines = [
        "# Manual Send Checklist",
        "",
        "No automated sending in MVP.",
        "",
    ]
    for record in records:
        lines.extend([
            f"## {record['business_slug']}",
            "",
            f"- Send Ready: {'yes' if record['send_ready'] else 'no'}",
            f"- Recipient Channel: {record['recipient_channel']}",
            f"- Recipient Value: {record['recipient_value'] or 'N/A'}",
            f"- Preview URL: {record['preview_url'] or 'N/A'}",
            f"- Subject: {record['subject'] or 'N/A'}",
            f"- Mailto URL: {record['mailto_url'] or 'N/A'}",
            f"- Blocked Reasons: {', '.join(record['blocked_reasons']) if record['blocked_reasons'] else 'none'}",
            "",
        ])
    output_path.write_text("\n".join(lines), encoding="utf-8")


def run_phase_10(run_id: str, workspace: str) -> dict[str, Any]:
    root = Path(workspace)
    review_dir = root / "runs" / run_id / "09_review"
    phase_dir = root / "runs" / run_id / PHASE_SLUG
    approvals_path = review_dir / "approval_decisions.json"
    drafts_path = root / "runs" / run_id / "08_outreach" / "outreach_drafts.json"
    confirmations_path = phase_dir / "manual_confirmation.json"

    missing_fields: list[str] = []
    for path in (approvals_path, drafts_path):
        if not path.exists():
            missing_fields.append(str(path))

    if missing_fields:
        return ResultEnvelope.blocked(
            phase=PHASE_NAME,
            run_id=run_id,
            missing_fields=missing_fields,
            inputs_used=[],
            errors=["Phase 09 approvals and Phase 08 outreach drafts required before Phase 10"],
        ).to_dict()

    approvals = read_json(str(approvals_path))
    drafts = read_json(str(drafts_path))
    approved_records = [row for row in approvals if _safe_str(row.get("approval_status")) == "send"]
    if not approved_records:
        return ResultEnvelope.blocked(
            phase=PHASE_NAME,
            run_id=run_id,
            missing_fields=["approval_decisions.json with approval_status=send"],
            inputs_used=[
                f"runs/{run_id}/09_review/approval_decisions.json",
                f"runs/{run_id}/08_outreach/outreach_drafts.json",
            ],
            errors=["no approved records"],
        ).to_dict()

    drafts_by_slug = {_safe_str(row.get("business_slug")): row for row in drafts}
    send_queue = [
        build_send_queue_record(approval, drafts_by_slug.get(_safe_str(approval.get("business_slug")), {}))
        for approval in approved_records
    ]
    send_ready_records = [row for row in send_queue if row["send_ready"]]
    if not send_ready_records:
        return ResultEnvelope.blocked(
            phase=PHASE_NAME,
            run_id=run_id,
            missing_fields=["send-ready approved outreach records"],
            inputs_used=[
                f"runs/{run_id}/09_review/approval_decisions.json",
                f"runs/{run_id}/08_outreach/outreach_drafts.json",
            ],
            errors=["no approved records are send-ready"],
        ).to_dict()

    phase_dir.mkdir(parents=True, exist_ok=True)
    write_json(str(phase_dir / "approved_send_records.json"), send_ready_records)
    write_json(str(phase_dir / "no_approved_records.json"), [] if approved_records else approvals)
    write_json(str(phase_dir / "manual_send_queue.json"), send_queue)
    write_manual_send_checklist(send_queue, phase_dir / "manual_send_checklist.md")

    if not confirmations_path.exists():
        write_json(str(phase_dir / "manual_confirmation_missing.json"), {"missing": True, "path": str(confirmations_path)})
        return ResultEnvelope.blocked(
            phase=PHASE_NAME,
            run_id=run_id,
            missing_fields=[str(confirmations_path)],
            inputs_used=[
                f"runs/{run_id}/09_review/approval_decisions.json",
                f"runs/{run_id}/08_outreach/outreach_drafts.json",
                f"runs/{run_id}/{PHASE_SLUG}/manual_send_queue.json",
            ],
            errors=["manual sent confirmation missing"],
        ).to_dict()

    confirmations = read_json(str(confirmations_path))
    confirmations_by_slug = {_safe_str(row.get("business_slug")): row for row in confirmations}
    sent_log = [
        build_sent_log_record(run_id, approval, drafts_by_slug.get(_safe_str(approval.get("business_slug")), {}), confirmations_by_slug.get(_safe_str(approval.get("business_slug"))))
        for approval in approved_records
    ]

    write_json(str(phase_dir / "manual_confirmation_present.json"), {"missing": False, "count": len(confirmations)})
    write_json(str(phase_dir / "sent_log.json"), sent_log)
    write_sent_log_csv(sent_log, phase_dir / "sent_log.csv")

    sent_count = len([row for row in sent_log if row["sent_status"] == "sent"])
    not_sent_count = len([row for row in sent_log if row["sent_status"] == "not_sent"])
    failed_count = len([row for row in sent_log if row["sent_status"] == "failed"])

    result = ResultEnvelope(
        phase=PHASE_NAME,
        status="done",
        run_id=run_id,
        inputs_used=[
            f"runs/{run_id}/09_review/approval_decisions.json",
            f"runs/{run_id}/08_outreach/outreach_drafts.json",
            f"runs/{run_id}/{PHASE_SLUG}/manual_confirmation.json",
        ],
        outputs_created=[
            f"runs/{run_id}/{PHASE_SLUG}/approved_send_records.json",
            f"runs/{run_id}/{PHASE_SLUG}/manual_send_queue.json",
            f"runs/{run_id}/{PHASE_SLUG}/manual_send_checklist.md",
            f"runs/{run_id}/{PHASE_SLUG}/manual_confirmation_present.json",
            f"runs/{run_id}/{PHASE_SLUG}/sent_log.json",
            f"runs/{run_id}/{PHASE_SLUG}/sent_log.csv",
            f"runs/{run_id}/{PHASE_SLUG}/result.json",
        ],
        records_processed=len(approved_records),
        records_created=len(sent_log),
        records_skipped=not_sent_count + failed_count,
        decisions=[
            f"Prepared {len(send_ready_records)} send-ready manual outreach records",
            f"Logged {sent_count} sent, {not_sent_count} not_sent, {failed_count} failed manual outreach records",
        ],
        next_tasks=["Phase 11 — Monetization Tracking"] if sent_count > 0 else [],
    ).model_dump(exclude_none=True, by_alias=True)
    write_json(str(phase_dir / "result.json"), result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 10 — Manual Sending")
    parser.add_argument("--run-id", default="fixture_001", help="Run ID (default: fixture_001)")
    parser.add_argument("--project-root", default=".", help="Project root (default: current directory)")
    args = parser.parse_args()

    result = run_phase_10(args.run_id, args.project_root)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
