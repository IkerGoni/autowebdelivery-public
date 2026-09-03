"""Phase 06 Strict — Premium Quality Gate consuming Phase 05.5 artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from pipeline.json_io import write_json
    from pipeline.result_envelope import ResultEnvelope
except ModuleNotFoundError:  # pragma: no cover - CLI fallback
    from packages.pipeline.json_io import write_json
    from packages.pipeline.result_envelope import ResultEnvelope

from packages.phases.phase_06_quality_gate import run_quality_check

PHASE_NAME = "phase_06_strict_quality_gate"
PHASE_SLUG = "06_quality"

# Thresholds for strict mode
MIN_TEXT_DENSITY = 0.001        # visible_text_length / page_area
MIN_SECTION_COUNT = 3           # semantic HTML sections
MIN_CTA_COUNT = 1               # at least one CTA
MAX_CONSOLE_ERRORS = 3          # tolerate minor console noise
MAX_BROKEN_IMAGES = 0           # zero broken images allowed
MAX_BROKEN_LINKS = 2            # tolerate a few hash links

_CRITICAL_ASSET_EXTENSIONS = {".html", ".css"}


def _read_json_safe(path: Path) -> dict[str, Any] | None:
    """Read JSON file, return None on any failure."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _compute_visual_quality_score(dom_metrics: dict[str, Any], layout_summary: dict[str, Any] | None, console_log: dict[str, Any] | None, asset_load: dict[str, Any] | None) -> int:
    score = 100
    
    # Structure (40 pts)
    heading_count = dom_metrics.get("heading_count", 2)  # default to 2 if not present
    if heading_count < 2:
        score -= 15
        
    cta_count = dom_metrics.get("cta_count", 0)
    if cta_count < 1:
        score -= 25
        
    section_count = dom_metrics.get("section_count", 0)
    if section_count < 3:
        score -= 10
        
    body_word_count = dom_metrics.get("body_word_count", 100)  # default to 100
    if body_word_count < 80:
        score -= 15
        
    # Visual integrity (30 pts)
    broken_images = dom_metrics.get("broken_image_count", 0)
    if broken_images > 0:
        score -= 10 * min(broken_images, 3)
        
    broken_links = dom_metrics.get("broken_link_count", 0)
    if broken_links > 0:
        score -= 5 * min(broken_links, 3)
        
    if dom_metrics.get("missing_stylesheet", False) or dom_metrics.get("stylesheet_count", 1) < 1:
        score -= 30
        
    if dom_metrics.get("horizontal_overflow", False):
        score -= 15
        
    if layout_summary:
        mobile_summary = layout_summary.get("mobile", {})
        if mobile_summary.get("horizontal_overflow", False):
            score -= 15
            
    # Runtime health (15 pts)
    if console_log:
        errors = console_log.get("errors", [])
        if isinstance(errors, list) and len(errors) > 0:
            score -= 5 * min(len(errors), 3)
            
    # Content quality (15 pts)
    text_density = dom_metrics.get("visible_text_density_estimate", 0.1)
    if text_density < 0.05 or text_density > 0.80:
        score -= 10
        
    duplicate_text_signals = dom_metrics.get("duplicate_text_signals", 0)
    if duplicate_text_signals > 2:
        score -= 5
        
    return max(0, score)


def run_strict_quality_check(
    site_dir: Path,
    brief_dir: Path,
    *,
    strict: bool = True,
) -> dict[str, Any]:
    """Run strict premium quality check consuming Phase 05.5 artifacts.

    Returns same shape as existing Phase 06:
    {
        "status": "approved_for_deploy" | "needs_edit" | "rejected",
        "findings": [...],
        "rejection_reasons": [...],
        "needs_edit_reasons": [...],
        "business_slug": ...,
        "run_id": ...,
    }
    """
    # ------------------------------------------------------------------
    # 1. BASE CHECKS — run legacy Phase 06 first
    # ------------------------------------------------------------------
    legacy = run_quality_check(site_dir, brief_dir)

    if not strict:
        # Non-strict mode: return legacy result unchanged
        legacy["visual_quality_score"] = None
        return legacy

    # If legacy rejected, propagate immediately
    if legacy["status"] == "rejected":
        return legacy

    # Collect legacy needs_edit reasons; continue with strict checks
    rejection_reasons: list[str] = list(legacy.get("rejection_reasons", []))
    needs_edit_reasons: list[str] = list(legacy.get("needs_edit_reasons", []))
    findings: list[dict[str, Any]] = list(legacy.get("findings", []))

    # ------------------------------------------------------------------
    # 2. RENDER CAPTURE
    # ------------------------------------------------------------------
    render_capture_path = site_dir / "render_capture.json"
    render_capture = _read_json_safe(render_capture_path)

    if render_capture is None:
        rejection_reasons.append("render_capture.json missing")
        findings.append({"check": "render_capture", "result": "failed", "reason": "missing"})
        return {
            "status": "rejected",
            "findings": findings,
            "rejection_reasons": rejection_reasons,
            "needs_edit_reasons": needs_edit_reasons,
        }

    if render_capture.get("capture_status") != "done":
        rejection_reasons.append(
            f"render_capture capture_status is '{render_capture.get('capture_status')}', expected 'done'"
        )
        findings.append({"check": "render_capture", "result": "failed", "reason": "capture_status not done"})
        return {
            "status": "rejected",
            "findings": findings,
            "rejection_reasons": rejection_reasons,
            "needs_edit_reasons": needs_edit_reasons,
        }

    if render_capture.get("capture_mode") != "browser":
        rejection_reasons.append(
            f"render_capture capture_mode is '{render_capture.get('capture_mode')}', expected 'browser'"
        )
        findings.append({"check": "render_capture", "result": "failed", "reason": "capture_mode not browser"})
        return {
            "status": "rejected",
            "findings": findings,
            "rejection_reasons": rejection_reasons,
            "needs_edit_reasons": needs_edit_reasons,
        }

    findings.append({"check": "render_capture", "result": "pass"})

    # ------------------------------------------------------------------
    # 3. DOM METRICS
    # ------------------------------------------------------------------
    dom_metrics_path = site_dir / "dom_metrics.json"
    dom_metrics = _read_json_safe(dom_metrics_path)

    if dom_metrics is None:
        rejection_reasons.append("dom_metrics.json missing")
        findings.append({"check": "dom_metrics", "result": "failed", "reason": "missing"})
        return {
            "status": "rejected",
            "findings": findings,
            "rejection_reasons": rejection_reasons,
            "needs_edit_reasons": needs_edit_reasons,
        }

    _dom_rejected = False

    if dom_metrics.get("horizontal_overflow") is True:
        rejection_reasons.append("Horizontal overflow detected in DOM metrics")
        findings.append({"check": "horizontal_overflow", "result": "failed"})
        _dom_rejected = True

    missing_stylesheet = dom_metrics.get("missing_stylesheet", False)
    stylesheet_count = dom_metrics.get("stylesheet_count", 0)
    if missing_stylesheet or stylesheet_count < 1:
        rejection_reasons.append("Missing stylesheet detected in DOM metrics")
        findings.append({"check": "missing_stylesheet", "result": "failed"})
        _dom_rejected = True

    broken_images = dom_metrics.get("broken_image_count", 0)
    if broken_images > MAX_BROKEN_IMAGES:
        rejection_reasons.append(f"Too many broken images: {broken_images} (max {MAX_BROKEN_IMAGES})")
        findings.append({"check": "broken_images", "result": "failed", "count": broken_images})
        _dom_rejected = True

    broken_links = dom_metrics.get("broken_link_count", 0)
    if broken_links > MAX_BROKEN_LINKS:
        rejection_reasons.append(f"Too many broken links: {broken_links} (max {MAX_BROKEN_LINKS})")
        findings.append({"check": "broken_links", "result": "failed", "count": broken_links})
        _dom_rejected = True

    text_density = dom_metrics.get("visible_text_density_estimate", 0)
    if text_density < MIN_TEXT_DENSITY:
        rejection_reasons.append(
            f"Text density too low: {text_density} (min {MIN_TEXT_DENSITY})"
        )
        findings.append({"check": "text_density", "result": "failed", "value": text_density})
        _dom_rejected = True

    section_count = dom_metrics.get("section_count", 0)
    if section_count < MIN_SECTION_COUNT:
        rejection_reasons.append(
            f"Insufficient sections: {section_count} (min {MIN_SECTION_COUNT})"
        )
        findings.append({"check": "section_count", "result": "failed", "value": section_count})
        _dom_rejected = True

    cta_count = dom_metrics.get("cta_count", 0)
    if cta_count < MIN_CTA_COUNT:
        rejection_reasons.append(
            f"No CTA found: cta_count={cta_count} (min {MIN_CTA_COUNT})"
        )
        findings.append({"check": "cta_count", "result": "failed", "value": cta_count})
        _dom_rejected = True

    if _dom_rejected:
        return {
            "status": "rejected",
            "findings": findings,
            "rejection_reasons": rejection_reasons,
            "needs_edit_reasons": needs_edit_reasons,
        }

    findings.append({"check": "dom_metrics", "result": "pass"})

    # ------------------------------------------------------------------
    # 4. CONSOLE LOG
    # ------------------------------------------------------------------
    console_log_path = site_dir / "console_log.json"
    console_log = _read_json_safe(console_log_path)

    if console_log is not None:
        errors = console_log.get("errors", [])
        if not isinstance(errors, list):
            errors = []
        if len(errors) > MAX_CONSOLE_ERRORS:
            needs_edit_reasons.append(
                f"Too many console errors: {len(errors)} (max {MAX_CONSOLE_ERRORS})"
            )
            findings.append({"check": "console_errors", "result": "needs_edit", "count": len(errors)})
        else:
            findings.append({"check": "console_errors", "result": "pass", "count": len(errors)})
    else:
        # No console log file is acceptable — might not have been captured
        findings.append({"check": "console_errors", "result": "pass", "note": "no console_log.json"})

    # ------------------------------------------------------------------
    # 5. ASSET LOAD
    # ------------------------------------------------------------------
    asset_load_path = site_dir / "asset_load_log.json"
    asset_load = _read_json_safe(asset_load_path)

    if asset_load is not None:
        failed_requests = asset_load.get("failed_requests", [])
        if not isinstance(failed_requests, list):
            failed_requests = []

        critical_failures: list[str] = []
        non_critical_failures: list[str] = []

        for req in failed_requests:
            if not isinstance(req, dict):
                continue
            url = req.get("url", "")
            if any(url.endswith(ext) or f".{ext}?" in url for ext in _CRITICAL_ASSET_EXTENSIONS):
                critical_failures.append(url)
            else:
                non_critical_failures.append(url)

        if critical_failures:
            rejection_reasons.append(
                f"Critical asset load failures: {critical_failures}"
            )
            findings.append({"check": "asset_load", "result": "failed", "critical_failures": critical_failures})
        elif non_critical_failures:
            needs_edit_reasons.append(
                f"Non-critical asset load failures: {non_critical_failures}"
            )
            findings.append({"check": "asset_load", "result": "needs_edit", "non_critical_failures": non_critical_failures})
        else:
            findings.append({"check": "asset_load", "result": "pass"})
    else:
        findings.append({"check": "asset_load", "result": "pass", "note": "no asset_load_log.json"})

    # Check if critical asset failures caused rejection
    if any("Critical asset load failures" in r for r in rejection_reasons):
        return {
            "status": "rejected",
            "findings": findings,
            "rejection_reasons": rejection_reasons,
            "needs_edit_reasons": needs_edit_reasons,
        }

    # ------------------------------------------------------------------
    # 6. SANITIZER
    # ------------------------------------------------------------------
    sanitizer_path = site_dir / "sanitizer_report.json"
    sanitizer = _read_json_safe(sanitizer_path)

    if sanitizer is not None:
        if sanitizer.get("hard_block") is True:
            rejection_reasons.append("Sanitizer hard_block is true")
            findings.append({"check": "sanitizer", "result": "failed", "reason": "hard_block"})
            return {
                "status": "rejected",
                "findings": findings,
                "rejection_reasons": rejection_reasons,
                "needs_edit_reasons": needs_edit_reasons,
            }
        findings.append({"check": "sanitizer", "result": "pass"})
    else:
        # No sanitizer report is acceptable — might not have been generated
        findings.append({"check": "sanitizer", "result": "pass", "note": "no sanitizer_report.json"})

    # ------------------------------------------------------------------
    # Final determination
    # ------------------------------------------------------------------
    layout_summary_path = site_dir / "layout_summary.json"
    layout_summary = _read_json_safe(layout_summary_path)

    visual_score = _compute_visual_quality_score(dom_metrics, layout_summary, console_log, asset_load)

    # Convert DOM and layout checks into format expected by Slice 3:
    # Adding heading_count check to findings
    heading_count = dom_metrics.get("heading_count", 2)
    findings.append({"check": "heading_count", "result": "pass" if heading_count >= 2 else "fail", "value": heading_count})

    if rejection_reasons:
        return {
            "status": "rejected",
            "findings": findings,
            "rejection_reasons": rejection_reasons,
            "needs_edit_reasons": needs_edit_reasons,
            "visual_quality_score": visual_score,
        }

    if needs_edit_reasons:
        return {
            "status": "needs_edit",
            "findings": findings,
            "needs_edit_reasons": needs_edit_reasons,
            "visual_quality_score": visual_score,
        }

    return {
        "status": "approved_for_deploy",
        "findings": findings,
        "approved_for_deploy": True,
        "visual_quality_score": visual_score,
    }


def run_strict_phase_06(
    run_id: str,
    workspace: str,
    *,
    strict: bool = True,
) -> dict[str, Any]:
    """Run strict Phase 06 over all sites, same interface as run_phase_06."""
    root = Path(workspace)
    sites_dir = root / "runs" / run_id / "05_sites"

    if not sites_dir.exists():
        return ResultEnvelope.blocked(
            phase=PHASE_NAME,
            run_id=run_id,
            missing_fields=[f"runs/{run_id}/05_sites folder"],
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

        report = run_strict_quality_check(site_subdir, brief_dir, strict=strict)
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
            f"Strict quality checked {len(reports)} sites",
            f"Approved: {approved_count}, Needs edit: {needs_edit_count}, Rejected: {rejected_count}",
        ],
        next_tasks=["Phase 07 — Deployment"] if approved_count > 0 else [],
    ).model_dump(exclude_none=True, by_alias=True)
    write_json(str(quality_dir / "result.json"), result)
    return result
