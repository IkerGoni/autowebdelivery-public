"""Tests for Phase 05 premium Stitch site generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.phases.phase_05_stitch_site_generation import (
    PHASE_NAME,
    PHASE_SLUG,
    build_stitch_site_record,
    run_stitch_phase_05,
)
from packages.pipeline.json_io import read_json, write_json

# ---------------------------------------------------------------------------
# Fixtures & Fakes
# ---------------------------------------------------------------------------

SAMPLE_FACTS_MD = """\
- business_name: Frisco Mobile Detailing
- category: Mobile auto detailing
- phone: (972) 555-1234
- address: 123 Main St, Frisco TX
- rating: 4.8
- review_count: 127
"""

SAMPLE_HTML = (
    "<!DOCTYPE html>\n"
    "<html>\n"
    "<head><title>Frisco Mobile Detailing</title></head>\n"
    "<body>\n"
    "<h1>Frisco Mobile Detailing</h1>\n"
    "<p>Mobile auto detailing in Frisco TX</p>\n"
    '<a href="tel:(972) 555-1234">Call Now</a>\n'
    "<div>" + ("x" * 2500) + "</div>\n"
    "</body>\n"
    "</html>\n"
)

HARD_BLOCK_HTML = """\
<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>
<script>alert("xss")</script>
<script>alert("xss2")</script>
<h1>Frisco Mobile Detailing</h1>
</body>
</html>
"""


@dataclass
class FakeStitchClient:
    """Minimal StitchClient implementation for testing."""

    html_content: str = SAMPLE_HTML
    should_fail: bool = False
    last_prompt: str = ""

    def __post_init__(self) -> None:
        self._generated: bool = False

    def create_project(self, *, title: str) -> dict[str, Any]:
        return {"name": "projects/fake-project-id", "project_id": "fake-project-id"}

    def generate_screen_from_text(
        self,
        *,
        project_id: str,
        prompt: str,
        design_system: str | None = None,
        device_type: str = "DESKTOP",
        model_id: str | None = None,
    ) -> dict[str, Any]:
        self.last_prompt = prompt
        if self.should_fail:
            raise RuntimeError("Stitch generation failed (test)")
        self._generated = True
        # Return full response — screen lives in outputComponents
        return {
            "structuredContent": {
                "outputComponents": [{
                    "design": {
                        "screens": [{
                            "name": "projects/fake-project-id/screens/fake-screen-id",
                            "htmlCode": {"downloadUrl": "https://example.com/screen.html"},
                            "screenshot": {"downloadUrl": "https://example.com/screenshot.png"},
                        }]
                    }
                }]
            }
        }

    def list_screens(self, *, project_id: str) -> dict[str, Any]:
        if not self._generated:
            return {"screens": []}
        return {"screens": [{"name": "projects/fake-project-id/screens/fake-screen-id"}]}

    def get_project(self, *, project_id: str) -> dict[str, Any]:
        return {"name": f"projects/{project_id}"}

    def get_screen(self, *, project_id: str, screen_id: str) -> dict[str, Any]:
        return {
            "name": f"projects/{project_id}/screens/{screen_id}",
            "htmlCode": {"downloadUrl": "https://example.com/screen.html"},
            "screenshot": {"downloadUrl": "https://example.com/screenshot.png"},
        }

    def download_assets(self, *, project_id: str, output_dir: Path | str, html_url: str | None = None) -> dict[str, Any]:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.html").write_text(self.html_content, encoding="utf-8")
        return {"status": "ok", "output_dir": str(out)}


def _write_fixtures(
    root: Path,
    run_id: str,
    slug: str = "frisco-mobile-detailing",
    *,
    facts_md: str = SAMPLE_FACTS_MD,
    business_intelligence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write minimal fixture files for a single brief. Returns brief_row."""
    # FACTS.md
    brief_dir = root / "runs" / run_id / "04_briefs" / slug
    brief_dir.mkdir(parents=True, exist_ok=True)
    (brief_dir / "FACTS.md").write_text(facts_md, encoding="utf-8")

    # enrichment (visual_profile, copy_inputs)
    enrich_dir = root / "runs" / run_id / "04_5_enrichment" / slug
    enrich_dir.mkdir(parents=True, exist_ok=True)
    write_json(str(enrich_dir / "visual_profile.json"), {
        "preset_id": "auto_detailing_01",
        "hero_mode": "gradient",
        "photo_policy": "no_external",
        "accent_color_candidate": "#2c7be5",
    })
    write_json(str(enrich_dir / "copy_inputs.json"), {"slots": {}})

    if business_intelligence is not None:
        scoring_dir = root / "runs" / run_id / "03_scoring"
        scoring_dir.mkdir(parents=True, exist_ok=True)
        write_json(str(scoring_dir / "leads_scored.json"), [{
            "business_slug": slug,
            "business_intelligence": business_intelligence,
        }])

    return {
        "business_slug": slug,
        "record_id": f"rec_{slug}",
        "business_name": "Frisco Mobile Detailing",
    }


def _write_preview_ready(root: Path, run_id: str, briefs: list[dict[str, Any]]) -> None:
    briefs_dir = root / "runs" / run_id / "04_briefs"
    briefs_dir.mkdir(parents=True, exist_ok=True)
    write_json(str(briefs_dir / "preview_ready_briefs.json"), briefs)


# ---------------------------------------------------------------------------
# Tests: build_stitch_site_record
# ---------------------------------------------------------------------------

class TestBuildStitchSiteRecord:
    def test_happy_path(self, tmp_path: Path) -> None:
        """Generation → sanitize → all artifacts written."""
        run_id = "test_run_01"
        brief_row = _write_fixtures(tmp_path, run_id)
        client = FakeStitchClient()

        status = build_stitch_site_record(tmp_path, run_id, brief_row, client)

        assert status["status"] == "done"
        assert status["generation_mode"] == "premium_stitch"
        assert status["business_slug"] == "frisco-mobile-detailing"

        slug_dir = tmp_path / "runs" / run_id / PHASE_SLUG / "frisco-mobile-detailing"

        # All required artifacts exist
        assert (slug_dir / "site" / "index.html").exists()
        assert (slug_dir / "site" / "styles.css").exists()
        assert (slug_dir / "build_status.json").exists()
        assert (slug_dir / "fact_usage_report.json").exists()
        assert (slug_dir / "sanitizer_report.json").exists()
        assert (slug_dir / "stitch_generation_metadata.json").exists()
        assert (slug_dir / "stitch_prompt_contract.json").exists()
        assert (slug_dir / "screenshot_desktop.png").exists()
        assert (slug_dir / "screenshot_mobile.png").exists()

    def test_loads_safe_business_guidance_without_raw_bi_in_prompt_contract(self, tmp_path: Path) -> None:
        run_id = "test_run_bi_guidance"
        raw_bi = {
            "overall_score": 91.5,
            "component_scores": {"website_need": 95},
            "risk_flags": ["missing_phone"],
            "prompt_hints": ["position_as_missing_website_upgrade"],
        }
        brief_row = _write_fixtures(tmp_path, run_id, business_intelligence=raw_bi)
        client = FakeStitchClient()

        build_stitch_site_record(tmp_path, run_id, brief_row, client)

        slug_dir = tmp_path / "runs" / run_id / PHASE_SLUG / "frisco-mobile-detailing"
        contract = read_json(str(slug_dir / "stitch_prompt_contract.json"))
        contract_text = str(contract)

        # v2 prompt uses concise BI guidance — "booking and service discovery easy"
        assert "booking and service discovery easy" in client.last_prompt
        assert "business_guidance" in contract
        assert "booking and service discovery easy" in "\n".join(contract["business_guidance"])
        for raw in [
            "overall_score",
            "component_scores",
            "risk_flags",
            "missing_phone",
            "position_as_missing_website_upgrade",
            "business_intelligence",
        ]:
            assert raw not in client.last_prompt
            assert raw not in contract_text

    def test_build_status_fields(self, tmp_path: Path) -> None:
        """build_status.json has correct structure including generation_mode."""
        run_id = "test_run_02"
        brief_row = _write_fixtures(tmp_path, run_id)
        client = FakeStitchClient()

        build_stitch_site_record(tmp_path, run_id, brief_row, client)

        slug_dir = tmp_path / "runs" / run_id / PHASE_SLUG / "frisco-mobile-detailing"
        bs = read_json(str(slug_dir / "build_status.json"))
        assert bs["generation_mode"] == "premium_stitch"
        assert bs["status"] == "done"
        assert bs["run_id"] == run_id
        assert bs["business_slug"] == "frisco-mobile-detailing"
        assert "screenshots" in bs
        assert bs["screenshots"]["desktop"]["width"] == 1280
        assert bs["screenshots"]["mobile"]["width"] == 390
        assert "site_path" in bs

    def test_generation_failure(self, tmp_path: Path) -> None:
        """StitchAdapter returns status=failed → build_status reflects it."""
        run_id = "test_run_03"
        brief_row = _write_fixtures(tmp_path, run_id)
        client = FakeStitchClient(should_fail=True)

        status = build_stitch_site_record(tmp_path, run_id, brief_row, client)

        assert status["status"] == "failed"
        assert status["generation_mode"] == "premium_stitch"
        assert len(status["errors"]) > 0

    def test_hard_block(self, tmp_path: Path) -> None:
        """HTML with security issues → hard_blocked status."""
        run_id = "test_run_04"
        brief_row = _write_fixtures(tmp_path, run_id)
        # Use HTML with script tags — sanitizer won't hard_block for just
        # removed scripts, but let's make it have leftover danger.
        # Actually, sanitizer removes scripts but doesn't hard_block.
        # We need something that triggers hard_block.
        # hard_block fires when dangerous tags remain after removal pass
        # or CSS-based attacks persist. Let's use a workaround:
        # inject an enormous number of scripts so the sanitizer's
        # remaining-tag check fires. Actually from reading the code,
        # hard_block only fires on style-based security issues
        # remaining post-cleanup. We'll monkeypatch instead.
        client = FakeStitchClient(html_content=SAMPLE_HTML)

        # Monkeypatch sanitize_html to return hard_block
        import packages.phases.phase_05_stitch_site_generation as mod
        from packages.generation.html_sanitizer import SanitizationResult

        original = mod.sanitize_html

        def _fake_sanitize(html: str, verified_facts: Any = None, strict: bool = True) -> SanitizationResult:
            return SanitizationResult(
                original_html=html,
                sanitized_html=html,
                hard_block=True,
                hard_block_reasons=["security_script_remaining"],
            )

        mod.sanitize_html = _fake_sanitize  # type: ignore[assignment]
        try:
            status = build_stitch_site_record(tmp_path, run_id, brief_row, client)
            assert status["status"] == "hard_blocked"
            assert "hard_block_reasons" in status
        finally:
            mod.sanitize_html = original  # type: ignore[assignment]

    def test_fact_usage_report(self, tmp_path: Path) -> None:
        """fact_usage_report.json written with correct mode."""
        run_id = "test_run_05"
        brief_row = _write_fixtures(tmp_path, run_id)
        client = FakeStitchClient()

        build_stitch_site_record(tmp_path, run_id, brief_row, client)

        slug_dir = tmp_path / "runs" / run_id / PHASE_SLUG / "frisco-mobile-detailing"
        fu = read_json(str(slug_dir / "fact_usage_report.json"))
        assert fu["generation_mode"] == "premium_stitch"
        assert fu["run_id"] == run_id
        assert len(fu["facts_used"]) > 0

    def test_styles_css_placeholder(self, tmp_path: Path) -> None:
        """If Stitch HTML has no external CSS, a minimal placeholder is written."""
        run_id = "test_run_06"
        brief_row = _write_fixtures(tmp_path, run_id)
        client = FakeStitchClient()

        build_stitch_site_record(tmp_path, run_id, brief_row, client)

        css_path = tmp_path / "runs" / run_id / PHASE_SLUG / "frisco-mobile-detailing" / "site" / "styles.css"
        assert css_path.exists()
        content = css_path.read_text(encoding="utf-8")
        assert "placeholder" in content.lower() or "minimal" in content.lower()


# ---------------------------------------------------------------------------
# Tests: run_stitch_phase_05
# ---------------------------------------------------------------------------

class TestRunStitchPhase05:
    def test_missing_preview_ready(self, tmp_path: Path) -> None:
        """Missing preview_ready_briefs.json → blocked ResultEnvelope."""
        run_id = "test_run_10"
        client = FakeStitchClient()

        result = run_stitch_phase_05(run_id, str(tmp_path), client)

        assert result["status"] == "blocked"
        assert "preview_ready_briefs.json" in result.get("missing_fields", [])

    def test_processes_multiple_briefs(self, tmp_path: Path) -> None:
        """Multiple briefs all get processed."""
        run_id = "test_run_11"
        row1 = _write_fixtures(tmp_path, run_id, slug="biz-alpha")
        row2 = _write_fixtures(tmp_path, run_id, slug="biz-beta")
        _write_preview_ready(tmp_path, run_id, [row1, row2])

        # Need FACTS.md for both - _write_fixtures already handles that
        # but the brief_row business_name doesn't matter since facts come from FACTS.md
        # Update facts for biz-alpha and biz-beta
        for slug in ("biz-alpha", "biz-beta"):
            facts_path = tmp_path / "runs" / run_id / "04_briefs" / slug / "FACTS.md"
            facts_path.write_text(
                f"- business_name: {slug.replace('-', ' ').title()}\n"
                "- category: Test Category\n"
                "- phone: (555) 000-1111\n",
                encoding="utf-8",
            )

        client = FakeStitchClient()
        result = run_stitch_phase_05(run_id, str(tmp_path), client)

        assert result["status"] == "done"
        assert result["records_created"] == 2
        assert result["records_processed"] == 2

        # Both output dirs exist
        for slug in ("biz-alpha", "biz-beta"):
            slug_dir = tmp_path / "runs" / run_id / PHASE_SLUG / slug
            assert (slug_dir / "site" / "index.html").exists()
            assert (slug_dir / "build_status.json").exists()

    def test_skips_blocked_briefs(self, tmp_path: Path) -> None:
        """Blocked briefs are skipped (same as deterministic Phase 05)."""
        run_id = "test_run_12"
        row = _write_fixtures(tmp_path, run_id, slug="blocked-biz")
        _write_preview_ready(tmp_path, run_id, [row])

        # Write blocked list
        blocked = [{"business_slug": "blocked-biz", "blocked_reason": "no channel"}]
        briefs_dir = tmp_path / "runs" / run_id / "04_briefs"
        write_json(str(briefs_dir / "blocked_no_recipient_channel.json"), blocked)

        client = FakeStitchClient()
        result = run_stitch_phase_05(run_id, str(tmp_path), client)

        assert result["status"] == "done"
        assert result["records_skipped"] == 1
        assert result["records_created"] == 0

    def test_result_envelope_structure(self, tmp_path: Path) -> None:
        """ResultEnvelope has expected keys."""
        run_id = "test_run_13"
        row = _write_fixtures(tmp_path, run_id)
        _write_preview_ready(tmp_path, run_id, [row])

        client = FakeStitchClient()
        result = run_stitch_phase_05(run_id, str(tmp_path), client)

        assert result["phase"] == PHASE_NAME
        assert result["status"] == "done"
        assert result["run_id"] == run_id
        assert "inputs_used" in result
        assert "outputs_created" in result
        assert "decisions" in result
        assert "next_tasks" in result
        assert "Phase 06" in result["next_tasks"][0]

    def test_result_json_written(self, tmp_path: Path) -> None:
        """result.json artifact is written to output dir."""
        run_id = "test_run_14"
        row = _write_fixtures(tmp_path, run_id)
        _write_preview_ready(tmp_path, run_id, [row])

        client = FakeStitchClient()
        run_stitch_phase_05(run_id, str(tmp_path), client)

        result_path = tmp_path / "runs" / run_id / PHASE_SLUG / "result.json"
        assert result_path.exists()
        result = read_json(str(result_path))
        assert result["phase"] == PHASE_NAME

    def test_failed_generation_in_batch(self, tmp_path: Path) -> None:
        """Failed generation still produces a result envelope with errors."""
        run_id = "test_run_15"
        row = _write_fixtures(tmp_path, run_id)
        _write_preview_ready(tmp_path, run_id, [row])

        client = FakeStitchClient(should_fail=True)
        result = run_stitch_phase_05(run_id, str(tmp_path), client)

        assert result["status"] == "done"  # overall envelope is "done"
        assert result["records_created"] == 0
        assert len(result.get("errors", [])) > 0


# ---------------------------------------------------------------------------
# Tests: retry logic for SVG-only output
# ---------------------------------------------------------------------------

class _RetryCountingClient:
    """StitchClient fake that returns small HTML for the first N calls,
    then returns a full valid page.  Tracks how many times generate is called."""

    def __init__(self, *, fail_count: int = 0) -> None:
        self.fail_count = fail_count
        self.generate_calls = 0

    # -- StitchClient protocol ------------------------------------------------

    def create_project(self, *, title: str) -> dict[str, Any]:
        return {"name": "projects/retry-proj", "project_id": "retry-proj"}

    def generate_screen_from_text(self, *, project_id, prompt, design_system=None,
                                  device_type="DESKTOP", model_id=None):
        self.generate_calls += 1
        return {
            "structuredContent": {
                "outputComponents": [{
                    "design": {
                        "screens": [{
                            "name": f"projects/{project_id}/screens/sc_retry",
                            "htmlCode": {"downloadUrl": "https://example.com/html"},
                            "screenshot": {"downloadUrl": "https://example.com/ss"},
                        }]
                    }
                }]
            }
        }

    def list_screens(self, *, project_id):
        return {"screens": []}

    def get_project(self, *, project_id):
        return {"name": f"projects/{project_id}"}

    def get_screen(self, *, project_id, screen_id):
        return {
            "name": f"projects/{project_id}/screens/{screen_id}",
            "htmlCode": {"downloadUrl": "https://example.com/html"},
            "screenshot": {"downloadUrl": "https://example.com/ss"},
        }

    def download_assets(self, *, project_id, output_dir, html_url=None):
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        if self.generate_calls <= self.fail_count:
            # SVG-only / tiny output
            (out / "index.html").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>',
                encoding="utf-8",
            )
        else:
            # Full valid page > 2KB
            (out / "index.html").write_text(
                "<!DOCTYPE html><html><body>" + ("x" * 3000) + "</body></html>",
                encoding="utf-8",
            )
        return {"status": "ok", "output_dir": str(out)}


class TestRetryLogic:
    def test_retries_and_succeeds_on_second_attempt(self, tmp_path: Path) -> None:
        """First attempt returns SVG-only (retryable), second succeeds."""
        run_id = "test_retry_01"
        brief_row = _write_fixtures(tmp_path, run_id, slug="retry-biz")
        client = _RetryCountingClient(fail_count=1)

        status = build_stitch_site_record(tmp_path, run_id, brief_row, client)

        assert status["status"] == "done"
        assert status["generation_mode"] == "premium_stitch"
        assert client.generate_calls == 2

    def test_retries_and_succeeds_on_third_attempt(self, tmp_path: Path) -> None:
        """First two attempts return SVG-only, third succeeds."""
        run_id = "test_retry_02"
        brief_row = _write_fixtures(tmp_path, run_id, slug="retry-biz2")
        client = _RetryCountingClient(fail_count=2)

        status = build_stitch_site_record(tmp_path, run_id, brief_row, client)

        assert status["status"] == "done"
        assert client.generate_calls == 3

    def test_fails_after_three_retryable_attempts(self, tmp_path: Path) -> None:
        """All 3 attempts return SVG-only → final status is 'failed'."""
        run_id = "test_retry_03"
        brief_row = _write_fixtures(tmp_path, run_id, slug="retry-biz3")
        client = _RetryCountingClient(fail_count=99)  # always returns small HTML

        status = build_stitch_site_record(tmp_path, run_id, brief_row, client)

        assert status["status"] == "failed"
        assert len(status.get("errors", [])) > 0
        assert client.generate_calls == 3

    def test_succeeds_immediately_on_valid_html(self, tmp_path: Path) -> None:
        """Valid HTML on first attempt → no retries, one generate call."""
        run_id = "test_retry_04"
        brief_row = _write_fixtures(tmp_path, run_id, slug="retry-biz4")
        client = _RetryCountingClient(fail_count=0)  # always returns good HTML

        status = build_stitch_site_record(tmp_path, run_id, brief_row, client)

        assert status["status"] == "done"
        assert client.generate_calls == 1

    def test_retry_in_run_phase_05(self, tmp_path: Path) -> None:
        """run_stitch_phase_05 retries SVG-only output and ultimately reports correctly."""
        run_id = "test_retry_05"
        brief_row = _write_fixtures(tmp_path, run_id, slug="retry-biz5")
        _write_preview_ready(tmp_path, run_id, [brief_row])

        client = _RetryCountingClient(fail_count=1)
        result = run_stitch_phase_05(run_id, str(tmp_path), client)

        assert result["status"] == "done"
        assert result["records_created"] == 1
        assert result["records_processed"] == 1
