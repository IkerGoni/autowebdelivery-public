"""Tests for VNEXT-07 — css_patch_engine.py."""

from __future__ import annotations

from packages.patching.css_patch_engine import (
    apply_css_patches,
    _fix_overflow,
    _fix_spacing,
)


# ---------------------------------------------------------------------------
# HTML Fixtures
# ---------------------------------------------------------------------------


def _html_with_style_block() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<style>body { margin: 0; }</style>
</head>
<body>
<header><h1>Hello</h1></header>
<main><section>Content</section></main>
</body>
</html>"""


def _html_without_style_block() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head><title>Test</title></head>
<body>
<header><h1>Hello</h1></header>
<main><section>Content</section></main>
</body>
</html>"""


def _html_with_overflow_already() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<style>body { margin: 0; overflow-x: hidden; }</style>
</head>
<body><p>Content</p></body>
</html>"""


def _html_with_section_padding_already() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<style>section { padding-top: 2rem; padding-bottom: 2rem; }</style>
</head>
<body><section>Content</section></body>
</html>"""


def _html_no_head_no_body_close() -> str:
    return "<div>No structure</div>"


# ---------------------------------------------------------------------------
# Tests — apply_css_patches
# ---------------------------------------------------------------------------


class TestApplyCssPatches:
    """Tests for apply_css_patches."""

    def test_apply_css_patches_fix_overflow(self) -> None:
        """Overflow patch should add overflow-x:hidden."""
        html = _html_with_style_block()
        patches = [{
            "id": "patch_001",
            "category": "mobile_overflow_css_fix",
            "target": "css",
            "selector": "body",
            "action": "insert_css",
            "content": "body{overflow-x:hidden!important;}",
            "safety": "approved",
        }]
        result = apply_css_patches(html, patches)
        assert "overflow-x" in result
        assert "hidden" in result

    def test_apply_css_patches_fix_spacing(self) -> None:
        """Spacing patch should add section padding CSS."""
        html = _html_with_style_block()
        patches = [{
            "id": "patch_001",
            "category": "spacing_adjustment",
            "target": "css",
            "selector": "section",
            "action": "insert_css",
            "content": "section{padding-top:1.5rem;padding-bottom:1.5rem;}",
            "safety": "approved",
        }]
        result = apply_css_patches(html, patches)
        assert "padding-top" in result
        assert "section" in result

    def test_apply_css_patches_skips_non_css_target(self) -> None:
        """Patches with target != 'css' should be skipped."""
        html = _html_with_style_block()
        patches = [{
            "id": "patch_001",
            "category": "missing_final_cta",
            "target": "html",
            "selector": "</body>",
            "action": "insert_before",
            "content": "<div>CTA</div>",
            "safety": "approved",
        }]
        result = apply_css_patches(html, patches)
        assert result == html  # No changes

    def test_apply_css_patches_skips_non_insert_css_action(self) -> None:
        """Non-insert_css actions should be skipped."""
        html = _html_with_style_block()
        patches = [{
            "id": "patch_001",
            "category": "mobile_overflow_css_fix",
            "target": "css",
            "selector": "body",
            "action": "replace",
            "content": "body{overflow-x:hidden;}",
            "safety": "approved",
        }]
        result = apply_css_patches(html, patches)
        assert result == html  # No changes

    def test_apply_css_patches_skips_unknown_category(self) -> None:
        """Unknown categories should be skipped."""
        html = _html_with_style_block()
        patches = [{
            "id": "patch_001",
            "category": "unknown_category",
            "target": "css",
            "selector": "body",
            "action": "insert_css",
            "content": "body{color:red;}",
            "safety": "approved",
        }]
        result = apply_css_patches(html, patches)
        assert result == html  # No changes


class TestFixOverflow:
    """Tests for _fix_overflow."""

    def test_adds_overflow_to_existing_style(self) -> None:
        html = _html_with_style_block()
        result = _fix_overflow(html)
        assert "overflow-x" in result
        assert "hidden" in result

    def test_idempotent_overflow(self) -> None:
        """Applying overflow fix twice should be no-op."""
        html = _html_with_style_block()
        result1 = _fix_overflow(html)
        result2 = _fix_overflow(result1)
        assert result1 == result2

    def test_no_double_overflow(self) -> None:
        """If overflow-x:hidden already present, don't add again."""
        html = _html_with_overflow_already()
        result = _fix_overflow(html)
        # Should only have one occurrence of overflow-x
        count = result.lower().count("overflow-x")
        assert count == 1

    def test_overflow_without_style_block(self) -> None:
        """Should inject a <style> block when none exists."""
        html = _html_without_style_block()
        result = _fix_overflow(html)
        assert "overflow-x" in result
        assert "<style>" in result

    def test_overflow_no_head_no_body(self) -> None:
        """Should still work with minimal HTML."""
        html = _html_no_head_no_body_close()
        result = _fix_overflow(html)
        assert "overflow-x" in result


class TestFixSpacing:
    """Tests for _fix_spacing."""

    def test_adds_spacing_to_existing_style(self) -> None:
        html = _html_with_style_block()
        result = _fix_spacing(html)
        assert "padding-top" in result
        assert "section" in result

    def test_idempotent_spacing(self) -> None:
        """Applying spacing fix twice should be no-op."""
        html = _html_with_style_block()
        result1 = _fix_spacing(html)
        result2 = _fix_spacing(result1)
        assert result1 == result2

    def test_no_double_spacing(self) -> None:
        """If section padding already present, don't add again."""
        html = _html_with_section_padding_already()
        result = _fix_spacing(html)
        # Should not duplicate the padding rules
        count = result.lower().count("padding-top")
        assert count == 1

    def test_spacing_without_style_block(self) -> None:
        """Should inject a <style> block when none exists."""
        html = _html_without_style_block()
        result = _fix_spacing(html)
        assert "padding" in result
        assert "<style>" in result

    def test_spacing_uses_custom_css_content(self) -> None:
        """Should use provided css_content when given."""
        html = _html_with_style_block()
        custom_css = "section{margin:2rem 0;}"
        result = _fix_spacing(html, custom_css)
        assert "margin:2rem 0" in result

    def test_idempotent_full_patch_cycle(self) -> None:
        """Full apply_css_patches with overflow + spacing is idempotent."""
        html = _html_with_style_block()
        patches = [
            {
                "id": "patch_001",
                "category": "mobile_overflow_css_fix",
                "target": "css",
                "selector": "body",
                "action": "insert_css",
                "content": "body{overflow-x:hidden!important;}",
                "safety": "approved",
            },
            {
                "id": "patch_002",
                "category": "spacing_adjustment",
                "target": "css",
                "selector": "section",
                "action": "insert_css",
                "content": "section{padding-top:1.5rem;padding-bottom:1.5rem;}",
                "safety": "approved",
            },
        ]
        result1 = apply_css_patches(html, patches)
        result2 = apply_css_patches(result1, patches)
        assert result1 == result2
