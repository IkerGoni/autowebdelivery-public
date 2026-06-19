"""Phase 11 — local-only monetization tracking.

Track manual outreach outcomes without CRM, billing, or remote integrations.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

try:
    from pipeline.json_io import read_json, write_json
    from pipeline.result_envelope import ResultEnvelope
except ModuleNotFoundError:  # pragma: no cover - CLI fallback
    from packages.pipeline.json_io import read_json, write_json
    from packages.pipeline.result_envelope import ResultEnvelope

from packages.shared.provenance import _safe_str

PHASE_NAME = "phase_11_monetization_tracking"
PHASE_SLUG = "11_results"
DEFAULT_MVP_STOP_THRESHOLD = 20
ZERO_DEMAND_DECISION = "stop_or_pivot"
PROCEED_DECISION = "continue_testing"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_sent_log(path: Path) -> list[dict[str, Any]]:
    data = read_json(str(path))
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def _load_manual_updates(path: Path) -> list[dict[str, Any]]:
    data = read_json(str(path))
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def _is_sent_record(row: dict[str, Any]) -> bool:
    """Return True for delivered sent records. Missing status is legacy sent."""
    status = _safe_str(row.get("sent_status"))
    return status == "" or status == "sent"


def _lead_key(row: dict[str, Any]) -> str:
    return (
        _safe_str(row.get("business_slug"))
        or _safe_str(row.get("lead_slug"))
        or _safe_str(row.get("sent_record_id"))
        or _safe_str(row.get("record_id"))
        or "unknown"
    )


def _unique_sent_records(sent_log: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sent_records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(sent_log, start=1):
        if not _is_sent_record(row):
            continue
        key = _lead_key(row) or f"sent_index_{index}"
        if key in seen:
            continue
        seen.add(key)
        sent_records.append(row)
    return sent_records


def _normalize_event(run_id: str, row: dict[str, Any], index: int) -> dict[str, Any]:
    business_slug = _safe_str(row.get("business_slug", row.get("lead_slug", "unknown"))) or "unknown"
    event_type = _safe_str(row.get("event_type", "note")) or "note"
    objection = _safe_str(row.get("objection", row.get("objection_category", "")))
    serious_interest = bool(row.get("serious_interest", False))
    paid_conversion = bool(row.get("paid_conversion", False))
    reply_received = bool(row.get("reply_received", False))
    meeting_booked = bool(row.get("meeting_booked", False))

    if event_type == "reply":
        reply_received = True
    if event_type == "meeting":
        meeting_booked = True
        reply_received = True
    if event_type == "serious_interest":
        serious_interest = True
        reply_received = True
    if event_type == "paid_conversion":
        paid_conversion = True
        serious_interest = True
        reply_received = True

    lifecycle_effect = event_type if event_type in {"opt_out", "removal_requested", "removed"} else ""

    return {
        "run_id": run_id,
        "event_id": _safe_str(row.get("event_id", f"evt_{index:03d}")),
        "business_slug": business_slug,
        "business_name": _safe_str(row.get("business_name")),
        "niche": _safe_str(row.get("niche")),
        "area": _safe_str(row.get("area")),
        "country": _safe_str(row.get("country")),
        "recipient_channel": _safe_str(row.get("recipient_channel")),
        "template_family": _safe_str(row.get("template_family")),
        "template_variant": _safe_str(row.get("template_variant")),
        "stitch_project_id": _safe_str(row.get("stitch_project_id")),
        "offer_type": _safe_str(row.get("offer_type")),
        "offer_price": _safe_str(row.get("offer_price")),
        "currency": _safe_str(row.get("currency")),
        "pricing_market": _safe_str(row.get("pricing_market")),
        "sent_record_id": _safe_str(row.get("sent_record_id", row.get("record_id", ""))),
        "event_type": event_type,
        "reply_received": reply_received,
        "serious_interest": serious_interest,
        "meeting_booked": meeting_booked,
        "paid_conversion": paid_conversion,
        "lifecycle_effect": lifecycle_effect,
        "objection": objection,
        "notes": _safe_str(row.get("notes", "")),
        "occurred_at": _safe_str(row.get("occurred_at", row.get("updated_at", ""))),
    }


def _offer_key(row: dict[str, Any]) -> str:
    return "|".join([
        _safe_str(row.get("offer_type")) or "unknown",
        _safe_str(row.get("offer_price")) or "unknown",
        _safe_str(row.get("currency")) or "unknown",
        _safe_str(row.get("pricing_market")) or "unknown",
    ])


def _empty_segment_metrics() -> dict[str, Any]:
    return {
        "total_sent": 0,
        "reply_count": 0,
        "serious_interest_count": 0,
        "meeting_count": 0,
        "paid_conversion_count": 0,
        "objection_count": 0,
        "reply_rate": 0.0,
        "paid_conversion_rate": 0.0,
    }


def _build_segment_analytics(sent_log: list[dict[str, Any]], events: list[dict[str, Any]]) -> dict[str, Any]:
    sent_by_record_id = {_safe_str(row.get("record_id")): row for row in sent_log if _safe_str(row.get("record_id"))}
    sent_by_business_slug = {_safe_str(row.get("business_slug")): row for row in sent_log if _safe_str(row.get("business_slug"))}
    dimensions = {
        "by_niche": "niche",
        "by_area": "area",
        "by_recipient_channel": "recipient_channel",
        "by_template_family": "template_family",
        "by_offer": "offer",
    }
    analytics: dict[str, dict[str, dict[str, Any]]] = {name: {} for name in dimensions}

    def segment_key(row: dict[str, Any], field: str) -> str:
        if field == "offer":
            return _offer_key(row)
        return _safe_str(row.get(field)) or "unknown"

    for sent in sent_log:
        for dimension_name, field in dimensions.items():
            key = segment_key(sent, field)
            metrics = analytics[dimension_name].setdefault(key, _empty_segment_metrics())
            metrics["total_sent"] += 1

    for event in events:
        sent = sent_by_record_id.get(_safe_str(event.get("sent_record_id"))) or sent_by_business_slug.get(_safe_str(event.get("business_slug")))
        if not sent:
            continue
        merged = {**sent, **{key: value for key, value in event.items() if _safe_str(value)}}
        for dimension_name, field in dimensions.items():
            key = segment_key(merged, field)
            metrics = analytics[dimension_name].setdefault(key, _empty_segment_metrics())
            if event["reply_received"]:
                metrics["reply_count"] += 1
            if event["serious_interest"]:
                metrics["serious_interest_count"] += 1
            if event["meeting_booked"]:
                metrics["meeting_count"] += 1
            if event["paid_conversion"]:
                metrics["paid_conversion_count"] += 1
            if event["objection"]:
                metrics["objection_count"] += 1

    for dimension in analytics.values():
        for metrics in dimension.values():
            total_sent = metrics["total_sent"]
            if total_sent:
                metrics["reply_rate"] = round(metrics["reply_count"] / total_sent, 4)
                metrics["paid_conversion_rate"] = round(metrics["paid_conversion_count"] / total_sent, 4)

    return analytics


def build_lead_status_ledger(sent_log: list[dict[str, Any]], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sent_records = _unique_sent_records(sent_log)
    ledger: dict[str, dict[str, Any]] = {}
    ledger_key_by_record_id: dict[str, str] = {}
    for sent in sent_records:
        key = _lead_key(sent)
        record_id = _safe_str(sent.get("record_id"))
        if record_id:
            ledger_key_by_record_id[record_id] = key
        ledger[key] = {
            "business_slug": _safe_str(sent.get("business_slug", sent.get("lead_slug", key))) or key,
            "business_name": _safe_str(sent.get("business_name")),
            "preview_url": _safe_str(sent.get("preview_url")),
            "recipient_channel": _safe_str(sent.get("recipient_channel") or sent.get("sent_channel") or sent.get("source_recipient_channel")),
            "sent_record_id": _safe_str(sent.get("record_id")),
            "sent_status": _safe_str(sent.get("sent_status")) or "sent",
            "sent_at": _safe_str(sent.get("sent_at")),
            "sender_account": _safe_str(sent.get("sender_account")),
            "lead_status": "sent",
            "reply_status": "none",
            "reply_received": False,
            "serious_interest": False,
            "meeting_booked": False,
            "paid_conversion": False,
            "opted_out": False,
            "do_not_contact": False,
            "removal_requested": False,
            "removed": False,
            "takedown_status": "not_requested",
            "latest_event_type": "",
            "latest_event_at": "",
            "objection": "",
            "next_action": "",
            "next_action_due_at": "",
            "notes": "",
            "niche": _safe_str(sent.get("niche")),
            "area": _safe_str(sent.get("area")),
            "country": _safe_str(sent.get("country")),
            "template_family": _safe_str(sent.get("template_family")),
            "template_variant": _safe_str(sent.get("template_variant")),
            "offer_type": _safe_str(sent.get("offer_type")),
            "offer_price": _safe_str(sent.get("offer_price")),
            "currency": _safe_str(sent.get("currency")),
            "pricing_market": _safe_str(sent.get("pricing_market")),
        }

    for event in events:
        key = _safe_str(event.get("business_slug")) or ledger_key_by_record_id.get(_safe_str(event.get("sent_record_id"))) or _lead_key(event)
        if key not in ledger:
            continue
        row = ledger[key]
        for field in ["business_name", "niche", "area", "country", "recipient_channel", "template_family", "template_variant", "offer_type", "offer_price", "currency", "pricing_market"]:
            value = _safe_str(event.get(field))
            if value:
                row[field] = value
        row["reply_received"] = bool(row["reply_received"] or event.get("reply_received"))
        row["serious_interest"] = bool(row["serious_interest"] or event.get("serious_interest"))
        row["meeting_booked"] = bool(row["meeting_booked"] or event.get("meeting_booked"))
        row["paid_conversion"] = bool(row["paid_conversion"] or event.get("paid_conversion"))
        event_type = _safe_str(event.get("event_type"))
        if event_type == "opt_out":
            row["opted_out"] = True
            row["do_not_contact"] = True
            row["lead_status"] = "opted_out"
        elif event_type == "removal_requested":
            row["removal_requested"] = True
            row["takedown_status"] = "removal_requested"
            row["lead_status"] = "removal_requested"
        elif event_type == "removed":
            row["removed"] = True
            row["takedown_status"] = "removed"
            row["lead_status"] = "removed"
        elif row["paid_conversion"]:
            row["lead_status"] = "paid_conversion"
        elif row["meeting_booked"]:
            row["lead_status"] = "meeting_booked"
        elif row["serious_interest"]:
            row["lead_status"] = "serious_interest"
        elif row["reply_received"]:
            row["lead_status"] = "replied"
        row["reply_status"] = "replied" if row["reply_received"] else row["reply_status"]
        row["latest_event_type"] = event_type
        row["latest_event_at"] = _safe_str(event.get("occurred_at"))
        row["objection"] = _safe_str(event.get("objection"))
        row["next_action"] = _safe_str(event.get("next_action"))
        row["next_action_due_at"] = _safe_str(event.get("next_action_due_at"))
        row["notes"] = _safe_str(event.get("notes"))
    return list(ledger.values())


def write_lead_status_ledger_csv(ledger: list[dict[str, Any]], output_path: Path) -> None:
    headers = [
        "business_slug", "business_name", "preview_url", "recipient_channel", "sent_status",
        "sent_at", "sender_account", "reply_status", "latest_event_type", "objection",
        "next_action", "next_action_due_at", "do_not_contact", "removal_requested",
        "takedown_status", "notes", "sent_record_id", "lead_status",
        "reply_received", "serious_interest", "meeting_booked", "paid_conversion",
        "opted_out", "removed", "latest_event_at",
        "niche", "area", "country", "template_family",
        "template_variant", "offer_type", "offer_price", "currency", "pricing_market",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(ledger)


def summarize_monetization(
    sent_log: list[dict[str, Any]],
    manual_updates: list[dict[str, Any]],
    *,
    mvp_stop_threshold: int = DEFAULT_MVP_STOP_THRESHOLD,
) -> dict[str, Any]:
    normalized_events = [
        _normalize_event(_safe_str(row.get("run_id", "")), row, index)
        for index, row in enumerate(manual_updates, start=1)
    ]

    sent_records = _unique_sent_records(sent_log)
    total_sent = len(sent_records)
    replies = sum(1 for row in normalized_events if row["reply_received"])
    serious_interest = sum(1 for row in normalized_events if row["serious_interest"])
    meetings = sum(1 for row in normalized_events if row["meeting_booked"])
    paid_conversions = sum(1 for row in normalized_events if row["paid_conversion"])
    objections = [row for row in normalized_events if row["objection"]]
    segment_analytics = _build_segment_analytics(sent_records, normalized_events)
    lead_status_ledger = build_lead_status_ledger(sent_records, normalized_events)

    threshold_reached = total_sent >= mvp_stop_threshold
    zero_reply_or_interest = replies == 0 and serious_interest == 0
    should_stop_or_pivot = threshold_reached and zero_reply_or_interest
    decision = ZERO_DEMAND_DECISION if should_stop_or_pivot else PROCEED_DECISION

    return {
        "total_sent": total_sent,
        "reply_count": replies,
        "serious_interest_count": serious_interest,
        "meeting_count": meetings,
        "paid_conversion_count": paid_conversions,
        "objection_count": len(objections),
        "threshold_reached": threshold_reached,
        "zero_reply_or_interest": zero_reply_or_interest,
        "should_stop_or_pivot": should_stop_or_pivot,
        "decision": decision,
        "events": normalized_events,
        "objections": objections,
        "segment_analytics": segment_analytics,
        "lead_status_ledger": lead_status_ledger,
        "mvp_stop_threshold": mvp_stop_threshold,
    }


def write_objections_log(objections: list[dict[str, Any]], output_path: Path) -> None:
    headers = [
        "run_id",
        "event_id",
        "business_slug",
        "sent_record_id",
        "event_type",
        "objection",
        "notes",
        "occurred_at",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(objections)


def write_mvp_results_md(run_id: str, summary: dict[str, Any], output_path: Path) -> None:
    lines = [
        "# MVP Monetization Results",
        "",
        f"- Run ID: {run_id}",
        f"- Total Sent: {summary['total_sent']}",
        f"- Replies: {summary['reply_count']}",
        f"- Serious Interest: {summary['serious_interest_count']}",
        f"- Meetings: {summary['meeting_count']}",
        f"- Paid Conversions: {summary['paid_conversion_count']}",
        f"- Objections Logged: {summary['objection_count']}",
        f"- MVP Stop Threshold: {summary['mvp_stop_threshold']}",
        f"- Threshold Reached: {summary['threshold_reached']}",
        f"- Zero Reply/Interest: {summary['zero_reply_or_interest']}",
        f"- Decision: {summary['decision']}",
        "",
        "## Decision Summary",
        "",
    ]

    if summary["should_stop_or_pivot"]:
        lines.extend([
            "Stop or pivot recommended.",
            "",
            "Reason: threshold reached with zero replies and zero serious-interest events.",
        ])
    else:
        lines.extend([
            "Continue testing recommended.",
            "",
            "Reason: demand signal exists or threshold not yet reached.",
        ])

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_next_iteration_decision_md(summary: dict[str, Any], output_path: Path) -> None:
    lines = [
        "# Next Iteration Decision",
        "",
        f"Decision: {summary['decision']}",
        "",
    ]
    if summary["should_stop_or_pivot"]:
        lines.extend([
            "## Recommendation",
            "",
            "Pause scaling. Review offer, targeting, and outreach message before more sends.",
        ])
    else:
        lines.extend([
            "## Recommendation",
            "",
            "Keep manual testing. Collect more replies, objections, meetings, and closes.",
        ])
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_phase_11(run_id: str, workspace: str) -> dict[str, Any]:
    root = Path(workspace)
    sent_log_path = root / "runs" / run_id / "10_sent" / "sent_log.json"
    updates_path = root / "runs" / run_id / PHASE_SLUG / "manual_updates.json"
    config_path = root / "runs" / run_id / "config" / "input_config.json"

    missing_fields: list[str] = []
    if not sent_log_path.exists():
        missing_fields.append("sent_log.json")
    if not config_path.exists():
        missing_fields.append("RunConfig")
    if missing_fields:
        return ResultEnvelope.blocked(
            phase=PHASE_NAME,
            run_id=run_id,
            missing_fields=missing_fields,
            inputs_used=[],
            errors=["Phase 10 sent log and Phase 01 config required before Phase 11"],
        ).to_dict()

    sent_log = _load_sent_log(sent_log_path)
    manual_updates = _load_manual_updates(updates_path) if updates_path.exists() else []
    config = read_json(str(config_path))
    mvp_stop_threshold = _safe_int(config.get("mvp_stop_threshold"), DEFAULT_MVP_STOP_THRESHOLD)

    summary = summarize_monetization(
        sent_log,
        manual_updates,
        mvp_stop_threshold=mvp_stop_threshold,
    )
    summary["run_id"] = run_id

    output_dir = root / "runs" / run_id / PHASE_SLUG
    output_dir.mkdir(parents=True, exist_ok=True)
    mvp_results_path = output_dir / "mvp_results.md"
    objections_path = output_dir / "objections_log.csv"
    events_path = output_dir / "monetization_events.json"
    segment_analytics_path = output_dir / "monetization_segment_analytics.json"
    lead_status_ledger_json_path = output_dir / "lead_status_ledger.json"
    lead_status_ledger_csv_path = output_dir / "lead_status_ledger.csv"
    next_decision_path = output_dir / "next_iteration_decision.md"
    result_path = output_dir / "result.json"

    write_mvp_results_md(run_id, summary, mvp_results_path)
    write_objections_log(summary["objections"], objections_path)
    write_json(str(events_path), summary["events"])
    write_json(str(segment_analytics_path), summary["segment_analytics"])
    write_json(str(lead_status_ledger_json_path), summary["lead_status_ledger"])
    write_lead_status_ledger_csv(summary["lead_status_ledger"], lead_status_ledger_csv_path)
    write_next_iteration_decision_md(summary, next_decision_path)

    result = ResultEnvelope(
        phase=PHASE_NAME,
        status="done",
        run_id=run_id,
        inputs_used=[
            f"runs/{run_id}/10_sent/sent_log.json",
            f"runs/{run_id}/config/input_config.json",
            f"runs/{run_id}/11_results/manual_updates.json" if updates_path.exists() else "manual_updates omitted",
        ],
        outputs_created=[
            f"runs/{run_id}/{PHASE_SLUG}/mvp_results.md",
            f"runs/{run_id}/{PHASE_SLUG}/objections_log.csv",
            f"runs/{run_id}/{PHASE_SLUG}/monetization_events.json",
            f"runs/{run_id}/{PHASE_SLUG}/monetization_segment_analytics.json",
            f"runs/{run_id}/{PHASE_SLUG}/lead_status_ledger.json",
            f"runs/{run_id}/{PHASE_SLUG}/lead_status_ledger.csv",
            f"runs/{run_id}/{PHASE_SLUG}/next_iteration_decision.md",
            f"runs/{run_id}/{PHASE_SLUG}/result.json",
        ],
        records_processed=summary["total_sent"],
        records_created=len(summary["events"]),
        records_skipped=0,
        decisions=[
            f"Decision: {summary['decision']}",
            f"Replies: {summary['reply_count']}",
            f"Serious interest: {summary['serious_interest_count']}",
            f"Paid conversions: {summary['paid_conversion_count']}",
        ],
        risks=[
            "Do not scale automation until measurable demand exists",
        ] if summary["should_stop_or_pivot"] else [],
        next_tasks=["Review objections and refine offer"] if summary["should_stop_or_pivot"] else ["Continue manual outreach tracking"],
    ).model_dump(exclude_none=True, by_alias=True)
    write_json(str(result_path), result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 11 — Monetization Tracking")
    parser.add_argument("--run-id", default="fixture_001", help="Run ID")
    parser.add_argument("--project-root", default=".", help="Project root")
    args = parser.parse_args()

    result = run_phase_11(args.run_id, args.project_root)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
