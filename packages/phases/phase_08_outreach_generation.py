"""Phase 08 — outreach draft generation.

Generate fact-safe outreach drafts for manual review.
"""

from __future__ import annotations

import argparse
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

PHASE_NAME = "phase_08_outreach_generation"
PHASE_SLUG = "08_outreach"
BLOCKED_REASON = "recipient_channel is unknown and no manual override exists"


def _parse_facts_md(path: Path) -> dict[str, str]:
    facts: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("- ") or ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        facts[key.strip()] = value.strip()
    return facts


def _load_template(name: str) -> str:
    template_path = Path(__file__).resolve().parents[1] / "templates" / "outreach" / name
    return template_path.read_text(encoding="utf-8")


def _render_template(template: str, context: dict[str, str]) -> str:
    """Render a template with the given context.

    Tries Jinja2 first ({{var}} syntax), falls back to str.format ({var} syntax)
    if Jinja2 is unavailable or the template uses str.format placeholders.
    """
    try:
        from jinja2 import Template
        jinja_template = Template(template)
        rendered = jinja_template.render(**context).strip()
        # If the rendered output still contains {var} patterns, try str.format
        import re
        if re.search(r"\{[a-zA-Z_]\w*\}", rendered):
            return template.format(**context).strip()
        return rendered
    except ImportError:
        return template.format(**context).strip()


def _preview_url_for(root: Path, run_id: str, business_slug: str) -> str:
    deployment_path = root / "runs" / run_id / "07_deployments" / business_slug / "deployment_record.json"
    if not deployment_path.exists():
        return ""
    deployment = read_json(str(deployment_path))
    return _safe_str(deployment.get("preview_url"))


def _build_personalization_reason(facts: dict[str, str]) -> str:
    category = _safe_str(facts.get("category"))
    rating = _safe_str(facts.get("rating"))
    review_count = _safe_str(facts.get("review_count"))

    if category and rating and review_count:
        return f"noticed {facts.get('business_name', 'your business')} has {rating} rating with {review_count} Google reviews and no clear website"
    if category:
        return f"noticed {facts.get('business_name', 'your business')} shows up for {category.lower()} searches without proper website"
    return "noticed your Google Maps listing does not appear to have proper website"


def build_outreach_draft(
    run_id: str,
    business_slug: str,
    facts: dict[str, str],
    recipient: dict[str, Any],
    preview_url: str,
    price_offer: str,
    email_template: str,
    dm_template: str,
) -> dict[str, Any]:
    business_name = _safe_str(facts.get("business_name")) or business_slug.replace("-", " ").title()
    recipient_channel = _safe_str(recipient.get("recipient_channel", "unknown"))
    manual_override = bool(recipient.get("manual_override", False))
    subject = ""
    blocked_reason = ""

    if recipient_channel == "unknown" and not manual_override:
        return {
            "run_id": run_id,
            "record_id": f"out_{business_slug}",
            "business_slug": business_slug,
            "business_name": business_name,
            "niche": _safe_str(facts.get("niche") or facts.get("category")),
            "area": _safe_str(facts.get("area")),
            "country": _safe_str(facts.get("country")),
            "template_family": _safe_str(facts.get("template_family")),
            "template_variant": _safe_str(facts.get("template_variant")),
            "stitch_project_id": _safe_str(facts.get("stitch_project_id")),
            "offer_type": _safe_str(facts.get("offer_type", "setup_only")) or "setup_only",
            "offer_price": _safe_str(facts.get("offer_price")),
            "currency": _safe_str(facts.get("currency")),
            "pricing_market": _safe_str(facts.get("pricing_market")),
            "recipient_channel": recipient_channel,
            "recipient_value": _safe_str(recipient.get("recipient_value")),
            "subject": "",
            "body": "",
            "preview_url": preview_url,
            "price_offer": price_offer,
            "draft_status": "blocked",
            "blocked_reason": BLOCKED_REASON,
            "personalization_fields_used": ["business_name", "price_offer"],
        }

    if not preview_url:
        return {
            "run_id": run_id,
            "record_id": f"out_{business_slug}",
            "business_slug": business_slug,
            "business_name": business_name,
            "niche": _safe_str(facts.get("niche") or facts.get("category")),
            "area": _safe_str(facts.get("area")),
            "country": _safe_str(facts.get("country")),
            "template_family": _safe_str(facts.get("template_family")),
            "template_variant": _safe_str(facts.get("template_variant")),
            "stitch_project_id": _safe_str(facts.get("stitch_project_id")),
            "offer_type": _safe_str(facts.get("offer_type", "setup_only")) or "setup_only",
            "offer_price": _safe_str(facts.get("offer_price")),
            "currency": _safe_str(facts.get("currency")),
            "pricing_market": _safe_str(facts.get("pricing_market")),
            "recipient_channel": recipient_channel,
            "recipient_value": _safe_str(recipient.get("recipient_value")),
            "subject": "",
            "body": "",
            "preview_url": "",
            "price_offer": price_offer,
            "draft_status": "blocked",
            "blocked_reason": "preview_url missing",
            "personalization_fields_used": ["business_name", "price_offer"],
        }

    niche = _safe_str(facts.get("niche") or facts.get("category"))
    area = _safe_str(facts.get("area"))
    country = _safe_str(facts.get("country"))
    template_family = _safe_str(facts.get("template_family"))
    template_variant = _safe_str(facts.get("template_variant"))
    stitch_project_id = _safe_str(facts.get("stitch_project_id"))
    offer_type = _safe_str(facts.get("offer_type", "setup_only")) or "setup_only"
    offer_price = _safe_str(facts.get("offer_price"))
    currency = _safe_str(facts.get("currency"))
    pricing_market = _safe_str(facts.get("pricing_market"))

    context = {
        "business_name": business_name,
        "preview_url": preview_url,
        "price_offer": price_offer,
        "personalization_reason": _build_personalization_reason(facts),
        "recipient_channel": recipient_channel,
        "contact_name": _safe_str(facts.get("contact_name")),
        "category": _safe_str(facts.get("category")),
        "area": _safe_str(facts.get("area")),
        "tone": "professional",  # Default tone; can be overridden via config
        "sender_name": "",
        "sender_title": "",
        "update_details": "",
    }

    if recipient_channel == "email":
        subject = f"Quick website preview for {business_name}"
        body = _render_template(email_template, context)
    else:
        body = _render_template(dm_template, context)

    return {
        "run_id": run_id,
        "record_id": f"out_{business_slug}",
        "business_slug": business_slug,
        "business_name": business_name,
        "niche": niche,
        "area": area,
        "country": country,
        "template_family": template_family,
        "template_variant": template_variant,
        "stitch_project_id": stitch_project_id,
        "offer_type": offer_type,
        "offer_price": offer_price,
        "currency": currency,
        "pricing_market": pricing_market,
        "recipient_channel": recipient_channel,
        "recipient_value": _safe_str(recipient.get("recipient_value")),
        "subject": subject,
        "body": body,
        "preview_url": preview_url,
        "price_offer": price_offer,
        "draft_status": "ready_for_review",
        "blocked_reason": blocked_reason,
        "personalization_fields_used": ["business_name", "preview_url", "price_offer", "personalization_reason"],
    }


def generate_outreach_markdown(drafts: list[dict[str, Any]], output_path: Path) -> None:
    lines = ["# Outreach Drafts", ""]
    for draft in drafts:
        lines.extend([
            f"## {draft['business_name']} ({draft['business_slug']})",
            "",
            f"- Recipient Channel: {draft['recipient_channel']}",
            f"- Draft Status: {draft['draft_status']}",
            f"- Preview URL: {draft['preview_url'] or 'N/A'}",
            f"- Subject: {draft['subject'] or 'N/A'}",
            "",
            draft["body"] or draft["blocked_reason"],
            "",
        ])
    output_path.write_text("\n".join(lines), encoding="utf-8")


def run_phase_08(run_id: str, workspace: str) -> dict[str, Any]:
    root = Path(workspace)
    preview_ready_path = root / "runs" / run_id / "04_briefs" / "preview_ready_briefs.json"
    briefs_dir = root / "runs" / run_id / "04_briefs"
    config_path = root / "runs" / run_id / "config" / "input_config.json"

    missing_fields: list[str] = []
    for path, label in (
        (preview_ready_path, "preview_ready_briefs.json"),
        (briefs_dir, "04_briefs"),
        (config_path, "RunConfig"),
    ):
        if not path.exists():
            missing_fields.append(label)

    if missing_fields:
        return ResultEnvelope.blocked(
            phase=PHASE_NAME,
            run_id=run_id,
            missing_fields=missing_fields,
            inputs_used=[],
            errors=["Phase 04 outputs and Phase 01 config required before Phase 08"],
        ).to_dict()

    preview_ready = read_json(str(preview_ready_path))
    config = read_json(str(config_path))
    output_dir = root / "runs" / run_id / PHASE_SLUG
    output_dir.mkdir(parents=True, exist_ok=True)

    email_template = _load_template("email.j2")
    dm_template = _load_template("social_dm.j2")
    price_offer = _safe_str(config.get("price_offer"))

    drafts: list[dict[str, Any]] = []
    for row in preview_ready:
        business_slug = _safe_str(row.get("business_slug"))
        brief_dir = briefs_dir / business_slug
        facts = _parse_facts_md(brief_dir / "FACTS.md")
        recipient = read_json(str(brief_dir / "recipient_channel.json"))
        preview_url = _preview_url_for(root, run_id, business_slug)
        draft = build_outreach_draft(
            run_id,
            business_slug,
            facts,
            recipient,
            preview_url,
            price_offer,
            email_template,
            dm_template,
        )
        drafts.append(draft)

    blocked_path = briefs_dir / "blocked_no_recipient_channel.json"
    if blocked_path.exists():
        for row in read_json(str(blocked_path)):
            business_slug = _safe_str(row.get("business_slug"))
            brief_dir = briefs_dir / business_slug
            facts = _parse_facts_md(brief_dir / "FACTS.md")
            recipient_path = brief_dir / "recipient_channel.json"
            recipient = read_json(str(recipient_path)) if recipient_path.exists() else {"recipient_channel": "unknown"}
            drafts.append(build_outreach_draft(
                run_id,
                business_slug,
                facts,
                recipient,
                "",
                price_offer,
                email_template,
                dm_template,
            ))

    drafts_path = output_dir / "outreach_drafts.json"
    md_path = output_dir / "outreach_drafts.md"
    result_path = output_dir / "result.json"
    write_json(str(drafts_path), drafts)
    generate_outreach_markdown(drafts, md_path)

    blocked_count = len([draft for draft in drafts if draft["draft_status"] == "blocked"])
    result = ResultEnvelope(
        phase=PHASE_NAME,
        status="done",
        run_id=run_id,
        inputs_used=[
            f"runs/{run_id}/04_briefs/preview_ready_briefs.json",
            f"runs/{run_id}/config/input_config.json",
        ],
        outputs_created=[
            f"runs/{run_id}/{PHASE_SLUG}/outreach_drafts.json",
            f"runs/{run_id}/{PHASE_SLUG}/outreach_drafts.md",
            f"runs/{run_id}/{PHASE_SLUG}/result.json",
        ],
        records_processed=len(drafts),
        records_created=len(drafts),
        records_skipped=blocked_count,
        decisions=[
            f"Generated {len(drafts) - blocked_count} outreach drafts ready for review",
            f"Marked {blocked_count} outreach drafts as blocked",
        ],
        next_tasks=["Phase 09 — Manual Approval Pack"],
    ).model_dump(exclude_none=True, by_alias=True)
    write_json(str(result_path), result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 08 — Outreach Draft Generation")
    parser.add_argument("--run-id", default="fixture_001", help="Run ID (default: fixture_001)")
    parser.add_argument("--project-root", default=".", help="Project root (default: current directory)")
    args = parser.parse_args()

    result = run_phase_08(args.run_id, args.project_root)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
