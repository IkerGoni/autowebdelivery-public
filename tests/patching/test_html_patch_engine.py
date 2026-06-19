"""Tests for VNEXT-07 — html_patch_engine.py."""

from __future__ import annotations

from packages.patching.html_patch_engine import (
    apply_html_patches,
    _insert_before,
    _remove,
    _replace,
)


# ---------------------------------------------------------------------------
# HTML Fixtures
# ---------------------------------------------------------------------------


def _basic_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head><title>Test</title></head>
<body>
<header><h1>Hello</h1></header>
<main><p>Content</p></main>
<footer><p>Footer</p></footer>
</body>
</html>"""


def _html_with_claim() -> str:
    return """<!DOCTYPE html>
<html><head><title>Test</title></head>
<body><p>We are guaranteed to satisfy you.</p></body></html>"""


def _html_with_element() -> str:
    return """<!DOCTYPE html>
<html><head><title>Test</title></head>
<body><div class="remove-me">Delete this</div><p>Keep this</p></body></html>"""


# ---------------------------------------------------------------------------
# Tests — apply_html_patches
# ---------------------------------------------------------------------------


class TestApplyHtmlPatches:
    """Tests for apply_html_patches."""

    def test_apply_html_patches_insert_before(self) -> None:
        """insert_before should add content before </body>."""
        html = _basic_html()
        patches = [{
            "id": "patch_001",
            "category": "missing_final_cta",
            "target": "html",
            "selector": "</body>",
            "action": "insert_before",
            "content": "<section class='cta'>CTA</section>",
            "safety": "approved",
        }]
        result = apply_html_patches(html, patches)
        assert "<section class='cta'>CTA</section>" in result
        # Content should appear before </body>
        cta_pos = result.find("<section class='cta'>CTA</section>")
        body_pos = result.lower().find("</body>")
        assert cta_pos < body_pos

    def test_apply_html_patches_replace(self) -> None:
        """replace should swap claim text with fallback."""
        html = _html_with_claim()
        patches = [{
            "id": "patch_001",
            "category": "forbidden_claim_removal",
            "target": "html",
            "selector": "guaranteed",
            "action": "replace",
            "content": "contact us for details",
            "safety": "approved",
        }]
        result = apply_html_patches(html, patches)
        assert "guaranteed" not in result
        assert "contact us for details" in result

    def test_apply_html_patches_remove(self) -> None:
        """remove should strip matching element."""
        html = _html_with_element()
        patches = [{
            "id": "patch_001",
            "category": "forbidden_claim_removal",
            "target": "html",
            "selector": "<div class=\"remove-me\">Delete this</div>",
            "action": "remove",
            "safety": "approved",
        }]
        result = apply_html_patches(html, patches)
        assert "Delete this" not in result or "remove-me" not in result

    def test_apply_html_patches_skips_non_html_target(self) -> None:
        """Patches with target != 'html' should be skipped."""
        html = _basic_html()
        patches = [{
            "id": "patch_001",
            "category": "mobile_overflow_css_fix",
            "target": "css",
            "selector": "body",
            "action": "insert_css",
            "content": "body{overflow-x:hidden;}",
            "safety": "approved",
        }]
        result = apply_html_patches(html, patches)
        assert result == html  # No changes

    def test_apply_html_patches_skips_unknown_action(self) -> None:
        """Unknown actions should be silently skipped."""
        html = _basic_html()
        patches = [{
            "id": "patch_001",
            "category": "missing_final_cta",
            "target": "html",
            "selector": "</body>",
            "action": "unknown_action",
            "content": "stuff",
            "safety": "approved",
        }]
        result = apply_html_patches(html, patches)
        assert result == html  # No changes

    def test_idempotent_patch_application(self) -> None:
        """Applying the same patch twice should be a no-op."""
        html = _basic_html()
        patches = [{
            "id": "patch_001",
            "category": "missing_final_cta",
            "target": "html",
            "selector": "</body>",
            "action": "insert_before",
            "content": "<section class='cta'>CTA</section>",
            "safety": "approved",
        }]
        result1 = apply_html_patches(html, patches)
        result2 = apply_html_patches(result1, patches)
        assert result1 == result2

    def test_idempotent_replace_patch(self) -> None:
        """Replace is idempotent — second application is no-op."""
        html = _html_with_claim()
        patches = [{
            "id": "patch_001",
            "category": "forbidden_claim_removal",
            "target": "html",
            "selector": "guaranteed",
            "action": "replace",
            "content": "contact us for details",
            "safety": "approved",
        }]
        result1 = apply_html_patches(html, patches)
        result2 = apply_html_patches(result1, patches)
        assert result1 == result2


class TestInsertBefore:
    """Tests for _insert_before."""

    def test_insert_before_body_close(self) -> None:
        html = "<html><body><p>Hi</p></body></html>"
        result = _insert_before(html, "</body>", "<div>New</div>")
        assert result.index("<div>New</div>") < result.lower().index("</body>")

    def test_insert_before_is_idempotent(self) -> None:
        html = "<html><body><p>Hi</p></body></html>"
        content = "<div>New</div>"
        result1 = _insert_before(html, "</body>", content)
        result2 = _insert_before(result1, "</body>", content)
        assert result1 == result2

    def test_insert_before_missing_selector(self) -> None:
        html = "<html><body><p>Hi</p></body></html>"
        result = _insert_before(html, "</nonexistent>", "<div>New</div>")
        assert result == html

    def test_insert_before_generic_selector(self) -> None:
        html = "<html><body><main><p>Hi</p></main></body></html>"
        result = _insert_before(html, "<main>", "<nav>Menu</nav>")
        assert result.index("<nav>Menu</nav>") < result.index("<main>")


class TestReplace:
    """Tests for _replace."""

    def test_replace_text(self) -> None:
        html = "<p>Hello World</p>"
        result = _replace(html, "World", "Universe")
        assert result == "<p>Hello Universe</p>"

    def test_replace_case_insensitive(self) -> None:
        html = "<p>GUARANTEED results</p>"
        result = _replace(html, "guaranteed", "contact us")
        assert "GUARANTEED" not in result
        assert "contact us" in result

    def test_replace_missing_selector(self) -> None:
        html = "<p>Hello</p>"
        result = _replace(html, "missing", "replacement")
        assert result == html


class TestRemove:
    """Tests for _remove."""

    def test_remove_text(self) -> None:
        html = "<p>Hello World</p>"
        result = _remove(html, "Hello World")
        assert "Hello World" not in result

    def test_remove_missing_selector(self) -> None:
        html = "<p>Hello</p>"
        result = _remove(html, "not present")
        assert result == html

    def test_remove_preserves_surrounding(self) -> None:
        html = "<div>Keep</div><span>Remove</span><div>Keep2</div>"
        result = _remove(html, "Remove")
        assert "Keep" in result
        assert "Keep2" in result
        assert "Remove" not in result
