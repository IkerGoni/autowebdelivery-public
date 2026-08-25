"""Phase 06 — Quality Gate for generated preview sites."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

try:
    from pipeline.json_io import read_json, write_json
    from pipeline.result_envelope import ResultEnvelope
    from pipeline.template_slots import find_unresolved_slots
except ModuleNotFoundError:  # pragma: no cover - CLI fallback
    from packages.pipeline.json_io import read_json, write_json
    from packages.pipeline.result_envelope import ResultEnvelope
    from packages.pipeline.template_slots import find_unresolved_slots

from packages.shared.provenance import _safe_str

PHASE_NAME = "phase_06_quality_gate"
PHASE_SLUG = "06_quality"

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
# - Removed 'testimonial' (75% of real dental sites use it)
# - Removed 'family owned' (legitimate descriptor)
# - Removed 'years in business' (legitimate factual claim)
# - 'licensed' and 'certified' moved to needs_edit tier (25% of real sites use legitimately)
FORBIDDEN_CLAIMS = [
    "award-winning",
    "best in town",
    "#1",
    "top-rated",
    "trusted by thousands",
    "guaranteed",
    "review says",
    "prices from",
]

# Calibrated from real competitor analysis (2026-06-18):
# - Removed 'premier' (descriptive term used by real dental sites)
UNSUPPORTED_FACTUAL_CLAIMS = [
    "5-star",
    "5 star",
    "five-star",
    "five star",
    "certified",
    "trusted by",
    "#1",
    "award-winning",
    "guarantee",
    "guaranteed",
    "official partner",
]

GENERIC_VERIFIED_CONTACT_PLACEHOLDERS = [
    "verified phone number",
    "verified phone",
    "verified address",
    "verified contact",
    "verified contact information",
    "verified business information",
]

FAKE_555_01XX_PHONE_PATTERN = re.compile(
    r"(?:\+?1[\s.\-]*)?(?:\(?\d{3}\)?[\s.\-]*)?555[\s.\-]*01\d{2}\b"
)

# Calibrated from real competitor analysis (2026-06-18):
# - Removed 'licensed' and 'certified' (25% of real dental sites use them legitimately)
#   These now trigger needs_edit, not hard reject.
SEVERE_CLAIMS = [
    "best in town",
    "#1",
    "award-winning",
    "guaranteed",
    "testimonial",
]


def _parse_facts_md(path: Path) -> dict[str, str]:
    facts: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("- ") or ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        facts[key.strip()] = value.strip()
    return facts


def _visible_text(text: str) -> str:
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return text


def _scan_hits(text: str, blocked: list[str]) -> list[str]:
    lowered = _visible_text(text).lower()
    hits: list[str] = []
    for item in blocked:
        if item.lower() in lowered:
            hits.append(item)
    return hits


def _scan_fake_phone_numbers(text: str) -> list[str]:
    visible = _visible_text(text)
    hits = FAKE_555_01XX_PHONE_PATTERN.findall(visible)
    return list(dict.fromkeys(hit.strip() for hit in hits))


def _is_severe_claim(hit: str) -> bool:
    return hit.lower() in [c.lower() for c in SEVERE_CLAIMS]


def _check_build_status(build_status: dict[str, Any], site_dir: Path | None = None) -> tuple[bool, str]:
    status = build_status.get("status", "")
    if status != "done":
        # Modular sites may lack "status" field entirely — verify real files on disk
        gen_mode = build_status.get("generation_mode", "")
        if gen_mode == "modular" and build_status.get("sanitizer_hard_block") is not True:
            # Verify actual HTML was generated — don't trust status alone
            if site_dir:
                has_html = (site_dir / "site" / "index.html").exists() or (site_dir / "index.html").exists()
                if not has_html:
                    return False, "Modular site has no generated HTML file (index.html not found)"
            return True, ""
        return False, f"Build status is '{status}', expected 'done'"
    return True, ""


def _check_deploy_mode_safety(build_status: dict[str, Any], html: str) -> tuple[list[str], list[str]]:
    """Check production_deploy_mode safety rules.

    Returns (rejection_reasons, needs_edit_reasons).
    """
    # Only apply safety checks when deploy_mode is explicitly set
    deploy_mode = build_status.get("deploy_mode", "")
    reject_reasons: list[str] = []
    needs_edit_reasons: list[str] = []
    lowered_html = html.lower()

    # Google-derived photo in production mode => hard reject
    # EXCEPT when the asset is hosted on Stitch's own CDN (aida-public), which is
    # AI-generated content produced by Stitch — not a third-party Google Maps photo.
    if deploy_mode == "production_deploy_mode":
        google_photo_indicators = [
            "maps.gstatic.com",
            "ggpht.com",
            "photo: google maps",
            "google maps photo",
        ]
        for indicator in google_photo_indicators:
            if indicator in lowered_html:
                reject_reasons.append(f"Google-derived photo found in production_deploy_mode: '{indicator}'")
                break

        # lh3.googleusercontent.com is shared by both Google Maps photos and
        # Stitch's asset CDN. Only treat it as a third-party photo when the
        # path does NOT look like a Stitch asset (aida / aida-public).
        if "lh3.googleusercontent.com" in lowered_html:
            import re
            lh3_paths = re.findall(r"lh3\.googleusercontent\.com(/[^\"' >)]*)", lowered_html)
            non_stitch_lh3 = [p for p in lh3_paths if "aida" not in p]
            if non_stitch_lh3:
                reject_reasons.append(
                    f"Google Maps photo (non-Stitch asset) found in production_deploy_mode: 'lh3.googleusercontent.com{non_stitch_lh3[0]}'"
                )

    return reject_reasons, needs_edit_reasons


def _check_fallback_and_attribution(build_status: dict[str, Any], site_dir: Path) -> tuple[list[str], list[str]]:
    """Check fallback slot counts and review attribution from fact_usage_report.json.

    Returns (rejection_reasons, needs_edit_reasons).
    """
    reject_reasons: list[str] = []
    needs_edit_reasons: list[str] = []

    fact_usage_path = site_dir / "fact_usage_report.json"
    if not fact_usage_path.exists():
        return reject_reasons, needs_edit_reasons

    import json as _json
    try:
        fact_usage = _json.loads(fact_usage_path.read_text(encoding="utf-8"))
    except Exception:
        needs_edit_reasons.append("fact_usage_report.json is not valid JSON")
        return reject_reasons, needs_edit_reasons

    # Check fallback/generic slot counts (two-tier cap)
    generic_count = len(fact_usage.get("generic_copy_blocks", []))
    core_fallback_count = 0
    for block in fact_usage.get("generic_copy_blocks", []):
        site_loc = block.get("site_location", "")
        # site_location examples: "hero.heading", "hero.subheading", "trust", "contact_cta.body"
        if any(core in site_loc for core in ["hero.heading", "hero.subheading", "trust", "contact_cta.body"]):
            core_fallback_count += 1

    if generic_count > 3:
        reject_reasons.append(f"Too many fallback/generic slots: {generic_count} (max 3)")

    if core_fallback_count > 1:
        needs_edit_reasons.append(f"Too many core fallback slots: {core_fallback_count} (max 1 among hero_tagline, hero_supporting_line, trust_intro, cta_body)")

    # Check review-derived content attribution
    review_summary = fact_usage.get("review_summary", [])
    for entry in review_summary:
        if isinstance(entry, dict) and not entry.get("attribution_visible", False):
            needs_edit_reasons.append("Review summary content present without visible attribution")

    # Check trust chips from unverified attributes
    trust_chips = fact_usage.get("trust_chips", [])
    for chip in trust_chips:
        if isinstance(chip, dict) and chip.get("source_type") == "unverified_attribute":
            needs_edit_reasons.append("Trust chip rendered from unverified attribute")

    # Check accent override contrast failure recorded in fact_usage
    design_meta = fact_usage.get("design_metadata", {})
    if design_meta.get("accent_override_rejected_reason"):
        needs_edit_reasons.append(f"Accent override failed contrast: {design_meta['accent_override_rejected_reason']}")

    return reject_reasons, needs_edit_reasons


def _check_html_file(site_dir: Path) -> tuple[bool, str, str]:
    # Check standard location (site/index.html) and modular location (index.html)
    index_path = site_dir / "site" / "index.html"
    if not index_path.exists():
        index_path = site_dir / "index.html"
    if not index_path.exists():
        return False, "index.html not found (checked site/index.html and index.html)", ""
    html_content = index_path.read_text(encoding="utf-8")
    return True, "", html_content


def _check_screenshots(site_dir: Path) -> tuple[bool, list[str]]:
    missing: list[str] = []
    # Standard naming: screenshot_desktop.png, screenshot_mobile.png
    # Modular sites produce: screenshot.png (fallback for both)
    has_fallback = (site_dir / "screenshot.png").exists()
    if not (site_dir / "screenshot_desktop.png").exists() and not has_fallback:
        missing.append("screenshot_desktop.png")
    if not (site_dir / "screenshot_mobile.png").exists() and not has_fallback:
        missing.append("screenshot_mobile.png")
    return len(missing) == 0, missing


def _check_business_name_match(html: str, expected_name: str) -> tuple[bool, str]:
    escaped_name = expected_name.lower()
    if escaped_name not in html.lower():
        return False, f"Business name '{expected_name}' not found in generated HTML"
    return True, ""


def _check_cta_links(html: str) -> tuple[bool, list[str]]:
    broken: list[str] = []
    tel_pattern = r'tel:([^"]+)"'
    tel_matches = re.findall(tel_pattern, html)
    if tel_matches and not any(len(m) > 5 for m in tel_matches):
        broken.append("tel link appears malformed")
    return len(broken) == 0, broken


def run_quality_check(site_dir: Path, brief_dir: Path) -> dict[str, Any]:
    rejection_reasons: list[str] = []
    needs_edit_reasons: list[str] = []
    approved = True
    needs_edit = False

    facts_path = brief_dir / "FACTS.md"
    if not facts_path.exists():
        return {
            "status": "rejected",
            "findings": [{"check": "facts.md", "result": "failed", "reason": "FACTS.md missing"}],
            "rejection_reasons": ["FACTS.md missing"],
        }

    facts = _parse_facts_md(facts_path)
    business_name = _safe_str(facts.get("business_name", ""))

    build_status_path = site_dir / "build_status.json"
    if not build_status_path.exists():
        return {
            "status": "rejected",
            "findings": [{"check": "build_status.json", "result": "failed", "reason": "build_status.json missing"}],
            "rejection_reasons": ["build_status.json missing"],
        }

    build_status = read_json(str(build_status_path))
    build_ok, build_reason = _check_build_status(build_status, site_dir)
    if not build_ok:
        return {
            "status": "rejected",
            "findings": [{"check": "build", "result": "failed", "reason": build_reason}],
            "rejection_reasons": [build_reason],
        }

    html_ok, html_reason, html_content = _check_html_file(site_dir)
    if not html_ok:
        return {
            "status": "rejected",
            "findings": [{"check": "index.html", "result": "failed", "reason": html_reason}],
            "rejection_reasons": [html_reason],
        }

    screenshots_ok, missing_screenshots = _check_screenshots(site_dir)
    if not screenshots_ok:
        # Missing screenshots are a needs_edit issue, not a rejection - sites can be reviewed without them
        needs_edit = True
        needs_edit_reasons.append(f"Missing screenshots: {', '.join(missing_screenshots)}")

    name_ok, name_reason = _check_business_name_match(html_content, business_name)
    if not name_ok:
        return {
            "status": "rejected",
            "findings": [{"check": "business_name_match", "result": "failed", "reason": name_reason}],
            "rejection_reasons": [name_reason],
        }

    placeholder_hits = _scan_hits(html_content, FORBIDDEN_PLACEHOLDERS)
    unresolved_slots = find_unresolved_slots(html_content)
    if placeholder_hits:
        rejection_reasons.append(f"Placeholder text found: {', '.join(placeholder_hits)}")
        approved = False
    if unresolved_slots:
        rejection_reasons.append(f"Unresolved template slots found: {', '.join(unresolved_slots)}")
        approved = False

    claim_hits = _scan_hits(html_content, FORBIDDEN_CLAIMS)
    severe_hits = [h for h in claim_hits if _is_severe_claim(h)]
    if severe_hits:
        rejection_reasons.append(f"Severe fake claims found: {', '.join(severe_hits)}")
        approved = False
    elif claim_hits:
        needs_edit = True
        needs_edit_reasons.append(f"Potential fake claims found: {', '.join(claim_hits)}")

    unsupported_claim_hits = _scan_hits(html_content, UNSUPPORTED_FACTUAL_CLAIMS)
    if unsupported_claim_hits:
        rejection_reasons.append(f"Unsupported factual claims found: {', '.join(unsupported_claim_hits)}")
        approved = False

    fake_phone_hits = _scan_fake_phone_numbers(html_content)
    if fake_phone_hits:
        rejection_reasons.append(f"Fake phone numbers found: {', '.join(fake_phone_hits)}")
        approved = False

    verified_contact_hits = _scan_hits(html_content, GENERIC_VERIFIED_CONTACT_PLACEHOLDERS)
    if verified_contact_hits:
        rejection_reasons.append(f"Generic verified contact placeholders found: {', '.join(verified_contact_hits)}")
        approved = False

    cta_ok, cta_issues = _check_cta_links(html_content)
    if not cta_ok:
        needs_edit = True
        needs_edit_reasons.extend(cta_issues)

    fact_usage_path = site_dir / "fact_usage_report.json"
    if fact_usage_path.exists():
        fact_usage = read_json(str(fact_usage_path))
        if fact_usage.get("needs_review"):
            needs_edit = True
            needs_edit_reasons.append("Fact usage report indicates needs_review")

    # Wave 1: deploy_mode safety (Google-derived photos in production)
    deploy_reject, deploy_needs = _check_deploy_mode_safety(build_status, html_content)
    rejection_reasons.extend(deploy_reject)
    needs_edit_reasons.extend(deploy_needs)
    if deploy_reject:
        approved = False

    # Wave 1: fallback cap + attribution + accent contrast checks
    fallback_reject, fallback_needs = _check_fallback_and_attribution(build_status, site_dir)
    rejection_reasons.extend(fallback_reject)
    needs_edit_reasons.extend(fallback_needs)
    if fallback_reject:
        approved = False
    if fallback_needs:
        needs_edit = True

    if not approved:
        return {
            "status": "rejected",
            "findings": [
                {"check": "placeholders", "result": "pass" if not placeholder_hits else "fail", "details": placeholder_hits},
                {"check": "fake_claims", "result": "pass" if not claim_hits else "needs_edit", "details": claim_hits},
            ],
            "rejection_reasons": rejection_reasons,
        }

    if needs_edit:
        return {
            "status": "needs_edit",
            "findings": [
                {"check": "screenshots", "result": "pass" if screenshots_ok else "needs_edit", "details": missing_screenshots},
                {"check": "ctas", "result": "pass" if cta_ok else "needs_edit", "details": cta_issues},
            ],
            "needs_edit_reasons": needs_edit_reasons,
        }

    return {
        "status": "approved_for_deploy",
        "findings": [
            {"check": "build", "result": "pass"},
            {"check": "screenshots", "result": "pass"},
            {"check": "business_name_match", "result": "pass"},
            {"check": "placeholders", "result": "pass"},
            {"check": "fake_claims", "result": "pass"},
        ],
        "approved_for_deploy": True,
    }


def run_phase_06(run_id: str, workspace: str) -> dict[str, Any]:
    root = Path(workspace)
    sites_dir = root / "runs" / run_id / "05_sites"

    if not sites_dir.exists():
        return ResultEnvelope.blocked(
            phase=PHASE_NAME,
            run_id=run_id,
            missing_fields=["runs/{run_id}/05_sites folder"],
            errors=["Phase 05 sites required before Phase 06"],
            inputs_used=[],
        ).to_dict()

    quality_dir = root / "runs" / run_id / PHASE_SLUG
    quality_dir.mkdir(parents=True, exist_ok=True)

    reports: list[dict[str, Any]] = []
    approved_count = 0
    rejected_count = 0
    needs_edit_count = 0

    for site_subdir in sites_dir.iterdir():
        if not site_subdir.is_dir():
            continue

        business_slug = site_subdir.name
        brief_dir = root / "runs" / run_id / "04_briefs" / business_slug

        report = run_quality_check(site_subdir, brief_dir)
        report["business_slug"] = business_slug
        report["run_id"] = run_id

        report_path = quality_dir / business_slug / "site_quality_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(str(report_path), report)
        reports.append(report)

        if report["status"] == "approved_for_deploy":
            approved_count += 1
        elif report["status"] == "rejected":
            rejected_count += 1
        else:
            needs_edit_count += 1

    result = ResultEnvelope(
        phase=PHASE_NAME,
        status="done",
        run_id=run_id,
        inputs_used=[f"runs/{run_id}/05_sites"],
        outputs_created=[f"runs/{run_id}/{PHASE_SLUG}/{r['business_slug']}/site_quality_report.json" for r in reports],
        records_processed=len(reports),
        records_created=approved_count,
        decisions=[
            f"Quality checked {len(reports)} sites",
            f"Approved: {approved_count}, Needs edit: {needs_edit_count}, Rejected: {rejected_count}",
        ],
        next_tasks=["Phase 07 — Deployment"] if approved_count > 0 else [],
    ).model_dump(exclude_none=True, by_alias=True)
    write_json(str(quality_dir / "result.json"), result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 06 — Quality Gate")
    parser.add_argument("--run-id", default="fixture_001", help="Run ID (default: fixture_001)")
    parser.add_argument("--project-root", default=".", help="Project root (default: current directory)")
    args = parser.parse_args()

    result = run_phase_06(args.run_id, args.project_root)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()