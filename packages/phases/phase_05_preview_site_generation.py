"""Phase 05 — deterministic preview site generation.

Generate one-page static preview sites from Phase 04 preview-ready briefs.
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import re
import struct
import zlib
from pathlib import Path
from typing import Any

from packages.shared.provenance import _safe_str

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "preview_site"

try:
    from pipeline.json_io import read_json, write_json
    from pipeline.result_envelope import ResultEnvelope
    from pipeline.slug import safe_path
    from pipeline.template_slots import find_unresolved_slots
except ModuleNotFoundError:  # pragma: no cover - CLI fallback
    from packages.pipeline.json_io import read_json, write_json
    from packages.pipeline.result_envelope import ResultEnvelope
    from packages.pipeline.slug import safe_path
    from packages.pipeline.template_slots import find_unresolved_slots

try:
    from generation.html_sanitizer import sanitize_html, write_sanitized_html, write_sanitizer_report
    from generation.niche_copy import copy_slots_to_dict, generate_copy_from_facts
except ModuleNotFoundError:  # pragma: no cover
    from packages.generation.html_sanitizer import sanitize_html, write_sanitized_html, write_sanitizer_report
    from packages.generation.niche_copy import copy_slots_to_dict, generate_copy_from_facts

PHASE_NAME = "phase_05_preview_site_generation"
PHASE_SLUG = "05_sites"
PHASE_04_5_SLUG = "04_5_enrichment"
FORBIDDEN_PLACEHOLDERS = [
    "Lorem ipsum",
    "TODO",
    "TBD",
    "INSERT",
    "PLACEHOLDER",
    "[BUSINESS_NAME]",
    "[PHONE]",
    "[ADDRESS]",
    "[HOURS]",
    "Your business",
    "Example business",
    "Sample text",
]
# Calibrated from real competitor analysis (2026-06-18):
# - Removed 'testimonial/s' (75% of real dental sites use them)
# - Removed 'family-owned' (legitimate descriptor)
# Remaining terms still flagged for human review but not hard-rejected.
FORBIDDEN_CLAIMS = [
    "best",
    "top-rated",
    "#1",
    "trusted by thousands",
    "award-winning",
    "licensed",
    "certified",
    "guarantee",
    "guarantees",
    "before/after",
]


def _parse_facts_md(path: Path) -> dict[str, str]:
    facts: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("- ") or ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        facts[key.strip()] = value.strip()
    return facts


def _slug_to_brief_dir(root: Path, run_id: str, business_slug: str) -> Path:
    return safe_path(root, "runs", run_id, "04_briefs", business_slug)


def _build_generic_copy(category: str, business_name: str) -> dict[str, str]:
    category_label = category or "Local business"
    return {
        "overview": (
            f"{business_name} offers {category_label.lower()} information in clean, mobile-first format "
            "to help visitors understand location, hours, and contact options quickly."
        ),
        "cta": "View location details, check listed hours, and use available contact options to reach business.",
        "footer": f"Preview website prepared for {business_name}.",
    }


def _slot_value(copy_inputs: dict[str, Any], slot_name: str) -> str:
    slots = copy_inputs.get("slots", {}) if isinstance(copy_inputs, dict) else {}
    return _safe_str(slots.get(slot_name))


def _load_template(name: str) -> str:
    return (TEMPLATE_DIR / name).read_text(encoding="utf-8")


def _render_template(template: str, slots: dict[str, str]) -> str:
    result = template
    for key, value in slots.items():
        result = result.replace("{{" + key + "}}", value)
    return result


def _html_document(content: dict[str, str]) -> str:
    template = _load_template("base.html")
    return _render_template(template, content)


def _load_phase_04_5_context(root: Path, run_id: str, business_slug: str) -> tuple[dict[str, Any], dict[str, Any]]:
    enrich_dir = safe_path(root, "runs", run_id, PHASE_04_5_SLUG, business_slug)
    visual_profile_path = enrich_dir / "visual_profile.json"
    copy_inputs_path = enrich_dir / "copy_inputs.json"
    visual_profile = read_json(str(visual_profile_path)) if visual_profile_path.exists() else {}
    copy_inputs = read_json(str(copy_inputs_path)) if copy_inputs_path.exists() else {}
    return visual_profile, copy_inputs


def _load_run_config(root: Path, run_id: str) -> dict[str, Any]:
    config_dir = safe_path(root, "runs", run_id, "config")
    config_path = config_dir / "run_config.json"
    if config_path.exists():
        return read_json(str(config_path))
    input_config_path = config_dir / "input_config.json"
    if input_config_path.exists():
        return read_json(str(input_config_path))
    return {}


def _valid_hex_color(value: str) -> bool:
    return bool(re.fullmatch(r"#[0-9a-fA-F]{6}", value or ""))


def _render_stylesheet(visual_profile: dict[str, Any]) -> str:
    css = _load_template("styles.css")
    accent = _safe_str(visual_profile.get("accent_color_candidate"))
    if _valid_hex_color(accent):
        css = css.replace("--accent: #2c7be5;", f"--accent: {accent};")
    return css


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def write_screenshot_png(path: Path, width: int, height: int, business_name: str) -> None:
    base = sum(ord(char) for char in business_name) % 256
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            red = (base + x * 3 + y) % 256
            green = (120 + base + y * 2) % 256
            blue = (200 + base + x) % 256
            rows.extend((red, green, blue))
    raw = bytes(rows)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", zlib.compress(raw, 9)) + _png_chunk(b"IEND", b"")
    path.write_bytes(png)


def _screenshot_entry(path: str, width: int, height: int) -> dict[str, Any]:
    return {"path": path, "width": width, "height": height}


def capture_screenshots(
    site_dir: Path,
    output_dir: Path,
    business_name: str,
    browser_available: bool | None = None,
) -> dict[str, Any]:
    """Capture browser screenshots when Playwright is available, else deterministic PNGs."""
    desktop = _screenshot_entry("screenshot_desktop.png", 1280, 800)
    mobile = _screenshot_entry("screenshot_mobile.png", 390, 844)
    metadata: dict[str, Any] = {
        "desktop": desktop,
        "mobile": mobile,
        "source_url": (site_dir / "index.html").resolve().as_uri(),
    }

    fallback_reason = "browser capture disabled"
    if browser_available is not False:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": desktop["width"], "height": desktop["height"]})
                page.goto(metadata["source_url"], wait_until="networkidle")
                page.screenshot(path=str(output_dir / desktop["path"]), full_page=True)
                page.set_viewport_size({"width": mobile["width"], "height": mobile["height"]})
                page.screenshot(path=str(output_dir / mobile["path"]), full_page=True)
                browser.close()
            metadata.update({"capture_mode": "browser", "browser": "playwright-chromium"})
            return metadata
        except Exception as exc:  # pragma: no cover - depends on local browser install
            fallback_reason = f"browser capture unavailable: {exc.__class__.__name__}"

    write_screenshot_png(output_dir / desktop["path"], desktop["width"], desktop["height"], business_name)
    write_screenshot_png(output_dir / mobile["path"], mobile["width"], mobile["height"], business_name)
    metadata.update({
        "capture_mode": "deterministic_fallback",
        "browser": "unavailable",
        "fallback_reason": fallback_reason,
    })
    return metadata


def _scan_hits(text: str, blocked: list[str]) -> list[str]:
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    lowered = text.lower()
    hits: list[str] = []
    for item in blocked:
        if item.lower() in lowered:
            hits.append(item)
    return hits


def build_site_record(root: Path, run_id: str, brief_row: dict[str, Any]) -> dict[str, Any]:
    business_slug = _safe_str(brief_row.get("business_slug"))
    brief_dir = _slug_to_brief_dir(root, run_id, business_slug)
    facts = _parse_facts_md(brief_dir / "FACTS.md")
    visual_profile, copy_inputs = _load_phase_04_5_context(root, run_id, business_slug)
    run_config = _load_run_config(root, run_id)
    deploy_mode = _safe_str(run_config.get("deploy_mode")) or "production_deploy_mode"

    # --- Modular template renderer has been ARCHIVED ---
    # See archive/templates/modular/ — removed from active pipeline.
    # Stitch AI generation is now the primary path for sellable quality.
    html_text = None
    modular_mode = False

    business_name = _safe_str(facts.get("business_name"))
    category = _safe_str(facts.get("category"))
    rating = _safe_str(facts.get("rating"))
    review_count = _safe_str(facts.get("review_count"))
    address = _safe_str(facts.get("address"))
    phone = _safe_str(facts.get("phone"))
    hours = _safe_str(facts.get("hours"))
    maps_url = _safe_str(facts.get("maps_url"))
    record_id = _safe_str(facts.get("record_id")) or _safe_str(brief_row.get("record_id"))

    if not modular_mode:
        generic = _build_generic_copy(category, business_name)
        niche_slots = generate_copy_from_facts(facts, niche=_load_run_config(root, run_id).get("niche", ""))
        niche_dict = copy_slots_to_dict(niche_slots)
        _trust_text = f"Rated {rating} from {review_count} Google reviews" if rating and review_count else "Google rating information not available in source data"
        hours_text = hours or "Hours not listed in source data"
        _address_text = address or "Address not listed in source data"
        maps_block = (
            f'<a class="btn secondary" href="{html.escape(maps_url, quote=True)}">Open Google Maps</a>'
            if maps_url
            else "<p>Map link not listed in source data.</p>"
        )

        cta_links: list[str] = []
        if phone:
            cta_links.append(f'<a class="btn" href="tel:{html.escape(phone, quote=True)}">Call {html.escape(phone)}</a>')
        if maps_url:
            cta_links.append(f'<a class="btn secondary" href="{html.escape(maps_url, quote=True)}">Get directions</a>')
        if not cta_links:
            cta_links.append('<span class="btn secondary">Contact details limited in source data</span>')

        # Use niche copy first, then copy_inputs slots, then generic fallback
        hero_tagline = _slot_value(copy_inputs, "hero_tagline") or niche_dict["hero_tagline"]
        hero_supporting_line = _slot_value(copy_inputs, "hero_supporting_line") or niche_dict["hero_supporting_line"]
        overview_intro = _slot_value(copy_inputs, "overview_intro") or niche_dict["overview_intro"]
        trust_intro = _slot_value(copy_inputs, "trust_intro") or niche_dict["trust_intro"]
        location_intro = _slot_value(copy_inputs, "location_intro") or niche_dict["location_intro"]
        cta_body = _slot_value(copy_inputs, "cta_body") or niche_dict["cta_body"]
        footer_note = _slot_value(copy_inputs, "footer_note") or niche_dict["footer_note"]

        preview_banner = ""
        if deploy_mode == "preview_demo_mode":
            preview_banner = "This is a preview site — not the final production version."

        eyebrow = "Preview website"
        if deploy_mode != "preview_demo_mode":
            eyebrow = ""

        # Compute SEO variables for the fallback template
        page_title = html.escape(f"{business_name} | {category}" if category else business_name)
        meta_description = html.escape(overview_intro or generic["overview"])
        website_url = html.escape(facts.get("website", ""))

        # Parse address into components for JSON-LD
        address_parts = address.split(",") if address else ["", "", ""]
        street_address = address_parts[0].strip() if len(address_parts) > 0 else address
        locality = address_parts[1].strip() if len(address_parts) > 1 else ""
        state_zip = address_parts[2].strip() if len(address_parts) > 2 else ""
        state_parts = state_zip.split()
        region = state_parts[0] if state_parts else ""
        postal_code = state_parts[1] if len(state_parts) > 1 else ""

        content = {
            "title": html.escape(business_name),
            "business_name": html.escape(hero_tagline),
            "category": html.escape(hero_supporting_line),
            "overview_heading": html.escape(category or "Business overview"),
            "overview": html.escape(overview_intro),
            "trust_text": html.escape(trust_intro),
            "address": html.escape(location_intro),
            "hours": html.escape(hours_text),
            "maps_block": maps_block,
            "cta_body": html.escape(cta_body),
            "cta_links": "".join(cta_links),
            "footer_text": html.escape(footer_note),
            "preview_banner": preview_banner,
            "eyebrow": eyebrow,
            # SEO variables
            "page_title": page_title,
            "meta_description": meta_description,
            "og_title": page_title,
            "og_description": meta_description,
            "og_url": website_url,
            "twitter_title": page_title,
            "twitter_description": meta_description,
            "phone": html.escape(phone),
            "street_address": html.escape(street_address),
            "locality": html.escape(locality),
            "region": html.escape(region),
            "postal_code": html.escape(postal_code),
            "rating_value": html.escape(rating),
            "review_count_value": html.escape(review_count),
        }
        html_text = _html_document(content)
    unresolved_slots = find_unresolved_slots(html_text) if not modular_mode else []

    fact_usage = {
        "run_id": run_id,
        "record_id": record_id,
        "business_slug": business_slug,
        "deploy_mode": deploy_mode,
        "visual_profile": {
            "preset_id": _safe_str(visual_profile.get("preset_id")),
            "hero_mode": _safe_str(visual_profile.get("hero_mode")),
            "photo_policy": _safe_str(visual_profile.get("photo_policy")),
            "accent_color_candidate": _safe_str(visual_profile.get("accent_color_candidate")),
        },
        "facts_used": [
            {"field": "business_name", "value": business_name, "source": "FACTS.md", "site_location": "hero.heading"},
            {"field": "business_name", "value": business_name, "source": "FACTS.md", "site_location": "footer"},
            {"field": "category", "value": category, "source": "FACTS.md", "site_location": "hero.subheading"},
            {"field": "category", "value": category, "source": "FACTS.md", "site_location": "overview.heading"},
        ],
        "facts_omitted": [],
        "generic_copy_blocks": [],
        "forbidden_claim_hits": [],
        "placeholder_hits": unresolved_slots,
        "needs_review": bool(unresolved_slots),
        "notes": [],
    }

    if rating and review_count:
        fact_usage["facts_used"].append({"field": "rating", "value": rating, "source": "FACTS.md", "site_location": "trust"})
        fact_usage["facts_used"].append({"field": "review_count", "value": review_count, "source": "FACTS.md", "site_location": "trust"})
    else:
        fact_usage["facts_omitted"].append({"field": "rating", "reason": "missing_pair_for_trust_copy"})
        fact_usage["facts_omitted"].append({"field": "review_count", "reason": "missing_pair_for_trust_copy"})
        fact_usage["needs_review"] = True

    if address:
        fact_usage["facts_used"].append({"field": "address", "value": address, "source": "FACTS.md", "site_location": "location_and_hours.address"})
    else:
        fact_usage["facts_omitted"].append({"field": "address", "reason": "missing"})
        fact_usage["needs_review"] = True
        fact_usage["notes"].append("Address missing; neutral fallback used.")

    if hours:
        fact_usage["facts_used"].append({"field": "hours", "value": hours, "source": "FACTS.md", "site_location": "location_and_hours.hours"})
    else:
        fact_usage["facts_omitted"].append({"field": "hours", "reason": "missing_neutral_fallback_used"})
        fact_usage["notes"].append("Hours missing; required neutral text used.")

    if maps_url:
        fact_usage["facts_used"].append({"field": "maps_url", "value": maps_url, "source": "FACTS.md", "site_location": "map_or_maps_link"})
    else:
        fact_usage["facts_omitted"].append({"field": "maps_url", "reason": "missing"})
        fact_usage["needs_review"] = True
        fact_usage["notes"].append("Map link missing; map CTA omitted.")

    if phone:
        fact_usage["facts_used"].append({"field": "phone", "value": phone, "source": "FACTS.md", "site_location": "contact_cta.phone_button"})
    else:
        fact_usage["facts_omitted"].append({"field": "phone", "reason": "missing"})
        fact_usage["notes"].append("Phone missing; phone CTA omitted.")

    # Track generic copy blocks — only when old _build_generic_copy text is used.
    # Niche copy (from niche_copy.py) is persuasive and niche-specific, not generic.
    if not modular_mode:
        if not _slot_value(copy_inputs, "overview_intro") and not niche_dict.get("overview_intro"):
            fact_usage["generic_copy_blocks"].append({
                "site_location": "overview.body",
                "text": generic["overview"],
                "rationale": "generic category-level copy; no business-specific claim",
            })
        if not _slot_value(copy_inputs, "cta_body") and not niche_dict.get("cta_body"):
            fact_usage["generic_copy_blocks"].append({
                "site_location": "contact_cta.body",
                "text": generic["cta"],
                "rationale": "neutral call to action; no unsupported claim",
            })
        if not _slot_value(copy_inputs, "footer_note") and not niche_dict.get("footer_note"):
            fact_usage["generic_copy_blocks"].append({
                "site_location": "footer.note",
                "text": generic["footer"],
                "rationale": "neutral footer fallback",
            })

    fact_usage["forbidden_claim_hits"] = _scan_hits(html_text, FORBIDDEN_CLAIMS)
    fact_usage["placeholder_hits"] = _scan_hits(html_text, FORBIDDEN_PLACEHOLDERS)
    if fact_usage["forbidden_claim_hits"]:
        fact_usage["needs_review"] = True
        fact_usage["notes"].append("Forbidden claim hit found in generated HTML.")
    if fact_usage["placeholder_hits"]:
        fact_usage["needs_review"] = True
        fact_usage["notes"].append("Placeholder hit found in generated HTML.")

    site_dir = safe_path(root, "runs", run_id, PHASE_SLUG, business_slug, "site")
    site_dir.mkdir(parents=True, exist_ok=True)
    output_dir = site_dir.parent
    if not modular_mode:
        (site_dir / "index.html").write_text(html_text, encoding="utf-8")
        (site_dir / "styles.css").write_text(_render_stylesheet(visual_profile), encoding="utf-8")

    # --- sanitize template-generated HTML ---
    verified_facts = dict(facts)
    san_result = sanitize_html(html_text, verified_facts=verified_facts)
    if san_result.findings:
        write_sanitizer_report(san_result, output_dir)
        write_sanitized_html(san_result, site_dir / "index.html")
        html_text = san_result.sanitized_html

    write_json(str(output_dir / "fact_usage_report.json"), fact_usage)
    screenshot_metadata = capture_screenshots(site_dir, output_dir, business_name)

    build_status = {
        "run_id": run_id,
        "record_id": record_id,
        "business_slug": business_slug,
        "status": "done",
        "deploy_mode": deploy_mode,
        "visual_profile": {
            "preset_id": _safe_str(visual_profile.get("preset_id")),
            "hero_mode": _safe_str(visual_profile.get("hero_mode")),
            "photo_policy": _safe_str(visual_profile.get("photo_policy")),
        },
        "site_path": f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/site",
        "screenshots": {
            **screenshot_metadata,
            "desktop": {
                **screenshot_metadata["desktop"],
                "path": f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/screenshot_desktop.png",
            },
            "mobile": {
                **screenshot_metadata["mobile"],
                "path": f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/screenshot_mobile.png",
            },
        },
        "notes": fact_usage["notes"],
    }
    write_json(str(output_dir / "build_status.json"), build_status)
    return build_status


def run_phase_05(run_id: str, workspace: str) -> dict[str, Any]:
    root = Path(workspace)
    preview_ready_path = safe_path(root, "runs", run_id, "04_briefs") / "preview_ready_briefs.json"
    blocked_path = safe_path(root, "runs", run_id, "04_briefs") / "blocked_no_recipient_channel.json"

    missing_fields: list[str] = []
    if not preview_ready_path.exists():
        missing_fields.append("preview_ready_briefs.json")
    if missing_fields:
        return ResultEnvelope.blocked(
            phase=PHASE_NAME,
            run_id=run_id,
            missing_fields=missing_fields,
            errors=["Phase 04 preview-ready briefs required before Phase 05"],
            inputs_used=[],
        ).to_dict()

    preview_ready = read_json(str(preview_ready_path))
    blocked = read_json(str(blocked_path)) if blocked_path.exists() else []
    blocked_lookup = {row.get("business_slug"): row for row in blocked}

    output_root = safe_path(root, "runs", run_id, PHASE_SLUG)
    output_root.mkdir(parents=True, exist_ok=True)

    build_statuses: list[dict[str, Any]] = []
    skipped_blocked = 0
    for row in preview_ready:
        business_slug = _safe_str(row.get("business_slug"))
        if business_slug in blocked_lookup and not bool(row.get("manual_override", False)):
            skipped_blocked += 1
            continue
        build_statuses.append(build_site_record(root, run_id, row))

    fallback_count = sum(
        1 for row in build_statuses if row.get("screenshots", {}).get("capture_mode") == "deterministic_fallback"
    )
    browser_count = sum(1 for row in build_statuses if row.get("screenshots", {}).get("capture_mode") == "browser")

    result = ResultEnvelope(
        phase=PHASE_NAME,
        status="done",
        run_id=run_id,
        inputs_used=[
            f"runs/{run_id}/04_briefs/preview_ready_briefs.json",
            f"runs/{run_id}/04_briefs/blocked_no_recipient_channel.json",
        ],
        outputs_created=[
            *[f"runs/{run_id}/{PHASE_SLUG}/{row['business_slug']}/site" for row in build_statuses],
            *[f"runs/{run_id}/{PHASE_SLUG}/{row['business_slug']}/site/styles.css" for row in build_statuses],
            *[f"runs/{run_id}/{PHASE_SLUG}/{row['business_slug']}/build_status.json" for row in build_statuses],
            *[f"runs/{run_id}/{PHASE_SLUG}/{row['business_slug']}/fact_usage_report.json" for row in build_statuses],
            *[f"runs/{run_id}/{PHASE_SLUG}/{row['business_slug']}/screenshot_desktop.png" for row in build_statuses],
            *[f"runs/{run_id}/{PHASE_SLUG}/{row['business_slug']}/screenshot_mobile.png" for row in build_statuses],
            f"runs/{run_id}/{PHASE_SLUG}/result.json",
        ],
        records_processed=len(preview_ready),
        records_created=len(build_statuses),
        records_skipped=skipped_blocked,
        decisions=[
            f"Generated {len(build_statuses)} deterministic preview sites",
            "Used fixed HTML structure from packages/templates/preview_site/base.html",
            f"Captured {browser_count} screenshot set(s) with Playwright browser",
            f"Generated {fallback_count} deterministic fallback screenshot set(s)",
        ],
        risks=(
            ["Some screenshots are deterministic artifact renders, not browser captures"]
            if fallback_count
            else []
        ),
        errors=[],
        next_tasks=["Phase 06 — Quality Gate"],
    ).model_dump(exclude_none=True, by_alias=True)
    write_json(str(output_root / "result.json"), result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 05 — Preview Site Generation")
    parser.add_argument("--run-id", default="fixture_001", help="Run ID (default: fixture_001)")
    parser.add_argument("--project-root", default=".", help="Project root (default: current directory)")
    args = parser.parse_args()

    result = run_phase_05(args.run_id, args.project_root)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
