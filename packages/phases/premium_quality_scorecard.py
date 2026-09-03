"""Premium Quality Scorecard — multi-dimensional quality scoring for generated sites."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from pipeline.json_io import write_json
    from pipeline.result_envelope import ResultEnvelope
except ModuleNotFoundError:  # pragma: no cover - CLI fallback
    from packages.pipeline.json_io import write_json
    from packages.pipeline.result_envelope import ResultEnvelope

from packages.pipeline.failure_semantics import classify_scorecard_verdict

PHASE_NAME = "premium_quality_scorecard"
PHASE_SLUG = "06_quality"

PASS_THRESHOLD = 0.70
REJECT_THRESHOLD = 0.40

# Placeholder strings from legacy Phase 06
_FORBIDDEN_PLACEHOLDERS = [
    "lorem ipsum",
    "todo",
    "tbd",
    "insert",
    "placeholder",
    "[business_name]",
    "[phone]",
    "[address]",
    "[hours]",
    "your business",
    "example business",
    "sample text",
]

# Unsupported factual claims from legacy Phase 06
_UNSUPPORTED_CLAIMS = [
    "award-winning",
    "best in town",
    "#1",
    "top-rated",
    "trusted by thousands",
    "guaranteed",
    "testimonial",
]


@dataclass
class QualityDimension:
    name: str
    score: float        # 0.0 - 1.0
    weight: float       # relative weight for composite
    verdict: str        # "pass", "needs_edit", "reject"
    findings: list[str] = field(default_factory=list)


@dataclass
class PremiumQualityScore:
    business_slug: str
    run_id: str
    overall_verdict: str     # "PASS", "NEEDS_EDIT", "REJECT"
    overall_score: float     # weighted composite 0.0-1.0
    dimensions: list[QualityDimension]
    pass_threshold: float
    reject_threshold: float
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_json_safe(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _read_html(site_dir: Path) -> str:
    index_path = site_dir / "site" / "index.html"
    if index_path.exists():
        return index_path.read_text(encoding="utf-8", errors="replace")
    return ""


def _visible_text(html: str) -> str:
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return text


def _body_prefix(html: str, chars: int = 2000) -> str:
    """Return first *chars* characters after <body...>."""
    m = re.search(r"<body[^>]*>", html, re.IGNORECASE)
    if not m:
        return html[:chars]
    start = m.end()
    return html[start : start + chars]


# ---------------------------------------------------------------------------
# Dimension scorers
# ---------------------------------------------------------------------------

def _score_factual_safety(site_dir: Path, _html: str) -> QualityDimension:
    weight = 0.25
    findings: list[str] = []

    sanitizer = _read_json_safe(site_dir / "sanitizer_report.json")
    if sanitizer is None:
        # U-06 fail-closed: missing OR malformed sanitizer evidence means
        # factual_safety is NOT_VERIFIED — never PASS. We distinguish the two
        # in the finding text for humans, but both degrade identically.
        missing_asset = site_dir / "sanitizer_report.json"
        if missing_asset.exists():
            findings.append("sanitizer_report.json present but malformed/not JSON")
        else:
            findings.append("sanitizer_report.json missing — factual safety not verified")
        return QualityDimension("factual_safety", 0.0, weight, "not_verified", findings)

    if sanitizer.get("hard_block") is True:
        findings.append("sanitizer hard_block")
        return QualityDimension("factual_safety", 0.0, weight, "reject", findings)

    sf_findings = sanitizer.get("findings", [])
    count = len(sf_findings) if isinstance(sf_findings, list) else 0
    score = max(0.0, 1.0 - count * 0.1)
    findings.append(f"{count} sanitizer findings")
    verdict = "reject" if score < REJECT_THRESHOLD else "pass"
    return QualityDimension("factual_safety", score, weight, verdict, findings)


def _score_visual_completeness(site_dir: Path, _html: str) -> QualityDimension:
    weight = 0.15
    findings: list[str] = []

    dom = _read_json_safe(site_dir / "dom_metrics.json")
    if dom is None:
        findings.append("dom_metrics.json missing")
        return QualityDimension("visual_completeness", 0.0, weight, "reject", findings)

    score = 0.0
    section_count = dom.get("section_count", 0)
    heading_count = dom.get("heading_count", 0)
    image_count = dom.get("image_count", 0)

    # section scoring
    if section_count >= 5:
        score += 0.4
    elif section_count >= 3:
        score += 0.25
    else:
        score += 0.1

    # heading scoring
    if heading_count >= 4:
        score += 0.3
    elif heading_count >= 2:
        score += 0.15

    # image bonus
    if image_count >= 1:
        score += 0.15

    # screenshots
    has_desktop = (site_dir / "screenshot_desktop.png").exists()
    has_mobile = (site_dir / "screenshot_mobile.png").exists()
    if has_desktop and has_mobile:
        score += 0.15
    elif has_desktop or has_mobile:
        score += 0.05

    score = min(1.0, score)
    findings.append(f"sections={section_count} headings={heading_count} images={image_count}")

    verdict = "reject" if score < 0.4 else "pass"
    return QualityDimension("visual_completeness", score, weight, verdict, findings)


def _score_mobile_quality(site_dir: Path, _html: str) -> QualityDimension:
    weight = 0.15
    findings: list[str] = []

    dom = _read_json_safe(site_dir / "dom_metrics.json")
    if dom is None:
        findings.append("dom_metrics.json missing")
        return QualityDimension("mobile_quality", 0.0, weight, "reject", findings)

    if dom.get("horizontal_overflow") is True:
        findings.append("horizontal overflow in dom_metrics")
        return QualityDimension("mobile_quality", 0.0, weight, "reject", findings)

    score = 1.0
    findings.append("no horizontal overflow")

    # Check layout_summary for mobile overflow
    layout = _read_json_safe(site_dir / "layout_summary.json")
    if layout is not None:
        mobile_overflow = layout.get("mobile", {}).get("horizontal_overflow", False)
        if mobile_overflow:
            findings.append("horizontal overflow in layout_summary mobile")
            return QualityDimension("mobile_quality", 0.0, weight, "reject", findings)

    # Check render_capture for mobile screenshot
    render = _read_json_safe(site_dir / "render_capture.json")
    if render is not None and render.get("capture_status") == "done":
        findings.append("render_capture mobile confirmed")

    return QualityDimension("mobile_quality", score, weight, "pass", findings)


def _score_cta_clarity(site_dir: Path, html: str) -> QualityDimension:
    weight = 0.15
    findings: list[str] = []

    dom = _read_json_safe(site_dir / "dom_metrics.json")
    if dom is None:
        findings.append("dom_metrics.json missing")
        return QualityDimension("cta_clarity", 0.0, weight, "reject", findings)

    cta_count = dom.get("cta_count", 0)

    if cta_count >= 2:
        score = 1.0
    elif cta_count == 1:
        score = 0.7
    else:
        score = 0.0
        findings.append("cta_count=0")
        return QualityDimension("cta_clarity", 0.0, weight, "reject", findings)

    findings.append(f"cta_count={cta_count}")

    # Above-fold CTA check
    above_fold = _body_prefix(html, 2000).lower()
    cta_signals = ["tel:", "contact", "call", "book"]
    has_above_fold = any(sig in above_fold for sig in cta_signals)
    if has_above_fold:
        score = min(1.0, score + 0.0)  # already good, keep at max
        findings.append("above-fold CTA signal found")
    else:
        findings.append("no above-fold CTA signal")

    verdict = "pass"
    return QualityDimension("cta_clarity", score, weight, verdict, findings)


def _score_local_relevance(site_dir: Path, html: str, brief_dir: Path) -> QualityDimension:
    weight = 0.10
    findings: list[str] = []
    checks = 0
    passed = 0

    lower_html = html.lower()

    # Business name
    facts_path = brief_dir / "FACTS.md"
    business_name = ""
    if facts_path.exists():
        for line in facts_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("- business_name:") and ":" in line[2:]:
                business_name = line.split(":", 1)[1].strip()
                break

    checks += 1
    if business_name and business_name.lower() in lower_html:
        passed += 1
        findings.append(f"business name '{business_name}' found")
    else:
        findings.append("business name not found in HTML")

    # Address or service area
    checks += 1
    location_signals = ["address", "service area", "serving", "located at", "serving the"]
    if any(sig in lower_html for sig in location_signals):
        passed += 1
        findings.append("address/service area found")
    else:
        findings.append("no address/service area found")

    # Phone number
    checks += 1
    phone_pattern = re.compile(r"tel:[^\s\"']+")
    if phone_pattern.search(html):
        passed += 1
        findings.append("phone number (tel:) found")
    elif re.search(r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}", html):
        passed += 1
        findings.append("phone number pattern found")
    else:
        findings.append("no phone number found")

    # Location/service area section in section_order
    checks += 1
    dom = _read_json_safe(site_dir / "dom_metrics.json")
    section_order = []
    if dom is not None:
        section_order = [s.lower() for s in dom.get("section_order", [])]
    location_sections = [s for s in section_order if any(kw in s for kw in ["location", "area", "service", "contact", "about"])]
    if location_sections:
        passed += 1
        findings.append(f"location section found: {location_sections[0]}")
    else:
        findings.append("no location/service section in section_order")

    if checks == 0:
        score = 0.0
    else:
        score = passed / checks

    verdict = "pass"
    return QualityDimension("local_relevance", score, weight, verdict, findings)


def _score_copy_specificity(site_dir: Path, _html: str) -> QualityDimension:
    weight = 0.10
    findings: list[str] = []

    dom = _read_json_safe(site_dir / "dom_metrics.json")
    if dom is None:
        findings.append("dom_metrics.json missing")
        return QualityDimension("copy_specificity", 0.0, weight, "pass", findings)

    word_count = dom.get("body_word_count", 0)
    if word_count >= 200:
        score = 1.0
    elif word_count >= 100:
        score = 0.5
    elif word_count >= 50:
        score = 0.2
    else:
        score = 0.1

    findings.append(f"body_word_count={word_count}")

    # Text density penalty
    density = dom.get("visible_text_density_estimate", 0)
    if density < 0.001 and word_count < 100:
        score *= 0.5
        findings.append("low text density")

    # Duplicate signals penalty
    dup_count = dom.get("duplicate_text_signals", 0)
    if dup_count > 0:
        score = max(0.0, score - dup_count * 0.1)
        findings.append(f"duplicate_text_signals={dup_count}")

    # Placeholder text check in visible text
    html = _read_html(site_dir)
    visible = _visible_text(html).lower()
    placeholder_hits = [p for p in _FORBIDDEN_PLACEHOLDERS if p in visible]
    if placeholder_hits:
        score = max(0.0, score - 0.2 * len(placeholder_hits))
        findings.append(f"placeholder text: {', '.join(placeholder_hits[:3])}")

    verdict = "pass"
    return QualityDimension("copy_specificity", score, weight, verdict, findings)


def _score_premium_feel(site_dir: Path, _html: str) -> QualityDimension:
    weight = 0.05
    findings: list[str] = []

    dom = _read_json_safe(site_dir / "dom_metrics.json")
    if dom is None:
        findings.append("dom_metrics.json missing")
        return QualityDimension("premium_feel", 0.0, weight, "pass", findings)

    score = 0.5  # baseline
    heading_count = dom.get("heading_count", 0)
    section_count = dom.get("section_count", 0)

    if heading_count >= 4:
        score += 0.15
        findings.append("headings >= 4")
    else:
        findings.append(f"heading_count={heading_count}")

    if section_count >= 5:
        score += 0.15
        findings.append("sections >= 5")
    else:
        findings.append(f"section_count={section_count}")

    # Stylesheet present
    missing_ss = dom.get("missing_stylesheet", False)
    ss_count = dom.get("stylesheet_count", 0)
    if not missing_ss and ss_count >= 1:
        score += 0.1
        findings.append("stylesheet present")
    else:
        score -= 0.2
        findings.append("missing stylesheet")

    # No console errors
    console = _read_json_safe(site_dir / "console_log.json")
    if console is not None:
        errors = console.get("errors", [])
        err_count = len(errors) if isinstance(errors, list) else 0
        if err_count == 0:
            score += 0.05
        else:
            score -= 0.05 * min(err_count, 3)
        findings.append(f"console_errors={err_count}")
    else:
        score += 0.05
        findings.append("no console_log.json")

    # Broken images
    broken = dom.get("broken_image_count", 0)
    if broken == 0:
        score += 0.05
    else:
        score -= 0.1 * broken
    findings.append(f"broken_images={broken}")

    score = max(0.0, min(1.0, score))
    return QualityDimension("premium_feel", score, weight, "pass", findings)


def _score_template_smell_penalty(site_dir: Path, _html: str) -> QualityDimension:
    """Inverted dimension: high template smell = low score."""
    weight = 0.05
    findings: list[str] = []
    penalty = 0.0

    dom = _read_json_safe(site_dir / "dom_metrics.json")
    if dom is None:
        findings.append("dom_metrics.json missing")
        return QualityDimension("template_smell_penalty", 0.0, weight, "pass", findings)

    # Duplicate text signals
    dup_count = dom.get("duplicate_text_signals", 0)
    if dup_count > 2:
        penalty += 0.3
        findings.append(f"high duplicate_text_signals={dup_count}")
    elif dup_count > 0:
        penalty += dup_count * 0.05
        findings.append(f"duplicate_text_signals={dup_count}")

    # Generic copy blocks in fact_usage_report
    fact_usage = _read_json_safe(site_dir / "fact_usage_report.json")
    if fact_usage is not None:
        generic_blocks = fact_usage.get("generic_copy_blocks", [])
        generic_count = len(generic_blocks) if isinstance(generic_blocks, list) else 0
        if generic_count > 3:
            penalty += 0.4
            findings.append(f"too many generic_copy_blocks={generic_count}")
        elif generic_count > 0:
            penalty += generic_count * 0.05
            findings.append(f"generic_copy_blocks={generic_count}")

    # Very low word count
    word_count = dom.get("body_word_count", 0)
    if word_count < 50:
        penalty += 0.3
        findings.append(f"very low word_count={word_count}")

    score = max(0.0, 1.0 - penalty)
    verdict = "pass"
    return QualityDimension("template_smell_penalty", score, weight, verdict, findings)


# ---------------------------------------------------------------------------
# Main scorer
# ---------------------------------------------------------------------------

def score_site(
    site_dir: Path,
    brief_dir: Path,
    *,
    pass_threshold: float = PASS_THRESHOLD,
    reject_threshold: float = REJECT_THRESHOLD,
) -> PremiumQualityScore:
    """Score a single site across all quality dimensions."""
    html = _read_html(site_dir)
    run_id = site_dir.parent.parent.name  # runs/{run_id}/05_sites/{slug}
    business_slug = site_dir.name

    dimensions: list[QualityDimension] = [
        _score_factual_safety(site_dir, html),
        _score_visual_completeness(site_dir, html),
        _score_mobile_quality(site_dir, html),
        _score_cta_clarity(site_dir, html),
        _score_local_relevance(site_dir, html, brief_dir),
        _score_copy_specificity(site_dir, html),
        _score_premium_feel(site_dir, html),
        _score_template_smell_penalty(site_dir, html),
    ]

    # Weighted composite
    overall_score = sum(d.score * d.weight for d in dimensions)

    # Verdict precedence (U-06): a missing-evidence dimension (not_verified)
    # makes the whole site NOT_VERIFIED — never PASS — and takes priority over
    # REJECT and the score thresholds. The scorecard is fail-closed in every
    # mode; the production/preview distinction is only at the batch level.
    any_not_verified = any(d.verdict == "not_verified" for d in dimensions)
    any_reject = any(d.verdict == "reject" for d in dimensions)

    if any_not_verified:
        overall_verdict = "NOT_VERIFIED"
    elif any_reject:
        overall_verdict = "REJECT"
    elif overall_score >= pass_threshold:
        overall_verdict = "PASS"
    elif overall_score >= reject_threshold:
        overall_verdict = "NEEDS_EDIT"
    else:
        overall_verdict = "REJECT"

    return PremiumQualityScore(
        business_slug=business_slug,
        run_id=run_id,
        overall_verdict=overall_verdict,
        overall_score=round(overall_score, 4),
        dimensions=dimensions,
        pass_threshold=pass_threshold,
        reject_threshold=reject_threshold,
        metadata={
            "scorer_version": "premium_v2",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------

def run_premium_scorecard(
    run_id: str,
    workspace: str,
    *,
    pass_threshold: float = PASS_THRESHOLD,
    reject_threshold: float = REJECT_THRESHOLD,
    mode: str = "production",
) -> dict[str, Any]:
    """Score all sites and write premium_quality_score.json for each.

    Args:
        mode: ``"production"`` (fail-closed: any NOT_VERIFIED site blocks the
            run as a missing-evidence failure) or ``"preview"`` (non-production:
            NOT_VERIFIED sites are recorded but the phase completes). A
            NOT_VERIFIED verdict always means "never PASS" in both modes.
    """
    if mode not in ("production", "preview"):
        raise ValueError(f"unknown scorecard mode {mode!r} (expected 'production' or 'preview')")
    root = Path(workspace)
    sites_dir = root / "runs" / run_id / "05_sites"

    if not sites_dir.exists():
        return ResultEnvelope.blocked(
            phase=PHASE_NAME,
            run_id=run_id,
            missing_fields=[f"runs/{run_id}/05_sites folder"],
            errors=["Phase 05 sites required before premium scorecard"],
            inputs_used=[],
        ).to_dict()

    quality_dir = root / "runs" / run_id / PHASE_SLUG
    quality_dir.mkdir(parents=True, exist_ok=True)

    outputs: list[str] = []
    scores_data: list[dict[str, Any]] = []
    pass_count = 0
    needs_edit_count = 0
    reject_count = 0
    not_verified_count = 0
    not_verified_slugs: list[str] = []

    for site_subdir in sorted(sites_dir.iterdir()):
        if not site_subdir.is_dir():
            continue

        business_slug = site_subdir.name
        brief_dir = root / "runs" / run_id / "04_briefs" / business_slug

        result = score_site(
            site_subdir,
            brief_dir,
            pass_threshold=pass_threshold,
            reject_threshold=reject_threshold,
        )
        result.run_id = run_id

        # Serialize to dict
        score_dict = {
            "business_slug": result.business_slug,
            "run_id": result.run_id,
            "overall_verdict": result.overall_verdict,
            "overall_score": result.overall_score,
            "dimensions": [asdict(d) for d in result.dimensions],
            "pass_threshold": result.pass_threshold,
            "reject_threshold": result.reject_threshold,
            "metadata": result.metadata,
        }

        out_path = quality_dir / business_slug / "premium_quality_score.json"
        write_json(str(out_path), score_dict)

        rel = f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/premium_quality_score.json"
        outputs.append(rel)
        scores_data.append(score_dict)

        if result.overall_verdict == "PASS":
            pass_count += 1
        elif result.overall_verdict == "NEEDS_EDIT":
            needs_edit_count += 1
        elif result.overall_verdict == "NOT_VERIFIED":
            not_verified_count += 1
            not_verified_slugs.append(business_slug)
        else:
            reject_count += 1

    # U-06 fail-closed (production): mandatory evidence missing/malformed ->
    # NOT_VERIFIED -> the run is blocked before any deployment path reads it.
    not_verified_semantics = classify_scorecard_verdict(
        "NOT_VERIFIED", production=(mode == "production")
    )
    not_verified_blocked = bool(not_verified_slugs) and not_verified_semantics.blocks_deployment

    skipped_count = reject_count + not_verified_count
    shared_decisions = [
        f"Premium scorecard evaluated {len(scores_data)} sites",
        (
            f"PASS: {pass_count}, NEEDS_EDIT: {needs_edit_count}, "
            f"REJECT: {reject_count}, NOT_VERIFIED: {not_verified_count}"
        ),
    ]
    risks = [f"{needs_edit_count} sites need edits"] if needs_edit_count else []
    if not_verified_count:
        risks.append(f"{not_verified_count} site(s) NOT_VERIFIED: mandatory evidence missing")

    if not_verified_blocked:
        envelope = ResultEnvelope(
            phase=PHASE_NAME,
            status="blocked",
            run_id=run_id,
            inputs_used=[f"runs/{run_id}/05_sites"],
            outputs_created=outputs,
            records_processed=len(scores_data),
            records_created=pass_count,
            records_skipped=skipped_count,
            missing_fields=[
                f"runs/{run_id}/05_sites/{slug}/sanitizer_report.json"
                for slug in not_verified_slugs
            ],
            decisions=shared_decisions,
            risks=risks,
            errors=[
                (
                    f"{not_verified_count} site(s) NOT_VERIFIED: mandatory sanitizer "
                    "evidence missing/malformed (fail-closed, U-06)"
                )
            ],
        ).model_dump(exclude_none=True, by_alias=True)
    else:
        envelope = ResultEnvelope(
            phase=PHASE_NAME,
            status="done",
            run_id=run_id,
            inputs_used=[f"runs/{run_id}/05_sites"],
            outputs_created=outputs,
            records_processed=len(scores_data),
            records_created=pass_count,
            records_skipped=skipped_count,
            decisions=shared_decisions,
            risks=risks,
            next_tasks=["Phase 07 — Deployment"] if pass_count > 0 else [],
        ).model_dump(exclude_none=True, by_alias=True)

    write_json(str(quality_dir / "premium_scorecard_result.json"), envelope)
    return envelope
