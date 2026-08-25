"""Tests for PremiumStitchAdapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from packages.generation.stitch_premium_adapter import (
    DESIGN_SYSTEM_PRESETS,
    DesignSystemConfig,
    PremiumStitchAdapter,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_stitch_client() -> MagicMock:
    """Create a mock StitchClient with full download simulation."""
    client = MagicMock()
    client.create_project.return_value = {"project_id": "proj_001"}
    client.generate_screen_from_text.return_value = {
        "structuredContent": {
            "outputComponents": [{
                "design": {
                    "screens": [{
                        "name": "projects/proj_001/screens/screen_001",
                        "htmlCode": {"downloadUrl": "https://example.com/screen.html"},
                        "screenshot": {"downloadUrl": "https://example.com/screenshot.png"},
                    }]
                }
            }]
        }
    }
    client.list_screens.return_value = {"screens": [{"name": "projects/proj_001/screens/screen_001"}]}
    client.get_screen.return_value = {
        "htmlCode": {"downloadUrl": "https://example.com/screen.html"},
        "screenshot": {"downloadUrl": "https://example.com/screenshot.png"},
    }
    # Simulate download_assets creating an index.html
    def mock_download(*, project_id: str, output_dir: Path | str, html_url: str | None = None) -> dict[str, Any]:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.html").write_text(
            "<html><body><h1>Test Business</h1>"
            "<section><p>Call us at 555-1234</p>"
            '<a href="tel:555-1234" class="btn">Call Now</a></section>'
            "<main><article><h2>Services</h2><p>Service details here.</p></article></main>"
            + ("x" * 3000)
            + "</body></html>",
            encoding="utf-8",
        )
        return {"status": "downloaded", "path": str(out)}
    client.download_assets.side_effect = mock_download
    return client


@pytest.fixture
def tmp_output(tmp_path: Path) -> Path:
    """Create a temporary output directory."""
    return tmp_path / "output"


# ---------------------------------------------------------------------------
# Design system presets
# ---------------------------------------------------------------------------

class TestDesignSystemPresets:
    def test_all_presets_exist(self):
        expected = {"clinical_trust", "warm_editorial", "industrial_reliable", "fresh_utility"}
        assert set(DESIGN_SYSTEM_PRESETS.keys()) == expected

    def test_presets_have_required_fields(self):
        for name, config in DESIGN_SYSTEM_PRESETS.items():
            assert isinstance(config, DesignSystemConfig)
            assert config.display_name
            assert config.color_mode in ("LIGHT", "DARK")
            assert config.headline_font
            assert config.body_font
            assert config.roundness.startswith("ROUND_")
            assert config.custom_color.startswith("#")

    def test_clinical_trust_config(self):
        config = DESIGN_SYSTEM_PRESETS["clinical_trust"]
        assert config.custom_color == "#0EA5E9"
        assert config.headline_font == "INTER"
        assert "medical" in config.design_md.lower()

    def test_warm_editorial_config(self):
        config = DESIGN_SYSTEM_PRESETS["warm_editorial"]
        assert config.custom_color == "#D97706"
        assert config.headline_font == "PLAYFAIR_DISPLAY"


# ---------------------------------------------------------------------------
# PremiumStitchAdapter
# ---------------------------------------------------------------------------

class TestPremiumStitchAdapterInit:
    def test_default_config(self, mock_stitch_client):
        adapter = PremiumStitchAdapter(mock_stitch_client)
        assert adapter.max_iterations == 3
        assert adapter.min_quality_score == 60
        assert adapter.enable_variants is False
        assert adapter.variant_count == 2

    def test_custom_config(self, mock_stitch_client):
        adapter = PremiumStitchAdapter(
            mock_stitch_client,
            max_iterations=5,
            min_quality_score=80,
            enable_variants=True,
            variant_count=3,
        )
        assert adapter.max_iterations == 5
        assert adapter.min_quality_score == 80
        assert adapter.enable_variants is True
        assert adapter.variant_count == 3


class TestGeneratePremium:
    def test_success_first_iteration(self, mock_stitch_client, tmp_output):
        adapter = PremiumStitchAdapter(mock_stitch_client)

        result = adapter.generate_premium(
            run_id="test_run",
            record_id="rec_001",
            business_slug="test-business",
            business_name="Test Business",
            prompt="Generate a site",
            prompt_contract={},
            output_dir=tmp_output,
            project_title="Test",
            project_id="proj_001",
            verified_facts={"business_name": "Test Business", "phone": "555-1234"},
        )

        assert result.status == "done"
        assert result.business_slug == "test-business"
        assert result.iterations == 1
        assert result.visual_quality_score is not None
        assert result.visual_quality_score >= 0

    def test_success_with_design_system(self, mock_stitch_client, tmp_output):
        mock_stitch_client.create_design_system.return_value = {"asset_id": "ds_001"}

        adapter = PremiumStitchAdapter(mock_stitch_client)

        result = adapter.generate_premium(
            run_id="test_run",
            record_id="rec_001",
            business_slug="test-business",
            business_name="Test Business",
            prompt="Generate a site",
            prompt_contract={},
            output_dir=tmp_output,
            project_title="Test",
            project_id="proj_001",
            visual_profile={"preset_id": "clinical_trust"},
        )

        assert result.status == "done"
        assert result.design_system_id is not None

    def test_failure_no_html(self, mock_stitch_client, tmp_output):
        # Override download to not create HTML
        def mock_no_download(*, project_id: str, output_dir: Path | str, html_url: str | None = None) -> dict[str, Any]:
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            return {"status": "no_html_url", "path": str(out)}

        mock_stitch_client.download_assets.side_effect = mock_no_download

        adapter = PremiumStitchAdapter(mock_stitch_client)

        result = adapter.generate_premium(
            run_id="test_run",
            record_id="rec_001",
            business_slug="test-business",
            business_name="Test Business",
            prompt="Generate a site",
            prompt_contract={},
            output_dir=tmp_output,
            project_title="Test",
            project_id="proj_001",
        )

        assert result.status == "failed"
        assert any("No HTML" in e for e in result.errors)


class TestQualityScore:
    def test_good_html_scores_high(self, mock_stitch_client, tmp_output):
        adapter = PremiumStitchAdapter(mock_stitch_client)

        good_html = """
        <html><body>
        <h1>Test Business - Best Service</h1>
        <section>
        <p>We provide excellent service for all your needs. Call us today at 555-1234.</p>
        <a href="tel:555-1234" class="btn">Call Now</a>
        </section>
        <main>
        <article>
        <h2>Our Services</h2>
        <p>Service 1, Service 2, Service 3. Contact us for more information.</p>
        </article>
        </main>
        </body></html>
        """

        from packages.generation.html_sanitizer import sanitize_html
        san_result = sanitize_html(good_html, verified_facts={"business_name": "Test Business"})
        score = adapter._compute_quick_quality_score(san_result, good_html)

        assert score >= 70  # Should score well with good structure

    def test_empty_html_scores_low(self, mock_stitch_client, tmp_output):
        adapter = PremiumStitchAdapter(mock_stitch_client)

        empty_html = "<html><body></body></html>"

        from packages.generation.html_sanitizer import sanitize_html
        san_result = sanitize_html(empty_html, verified_facts={})
        score = adapter._compute_quick_quality_score(san_result, empty_html)

        assert score < 50  # Should score poorly with no content


class TestExtractText:
    def test_extract_visible_text(self, mock_stitch_client):
        adapter = PremiumStitchAdapter(mock_stitch_client)

        html = """
        <html>
        <head><title>Test</title><style>.hidden { display: none; }</style></head>
        <body>
        <h1>Hello World</h1>
        <p>This is visible text.</p>
        <script>var x = 1;</script>
        </body>
        </html>
        """

        text = adapter._extract_text_from_html(html)
        assert "Hello World" in text
        assert "visible text" in text
        assert "display: none" not in text
        assert "var x" not in text
