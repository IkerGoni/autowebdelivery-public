"""Tests for packages/evaluation/spec_alignment.py — VNEXT-06."""

from __future__ import annotations

from packages.evaluation.spec_alignment import (
    check_spec_alignment,
    _check_sections,
    _check_cta,
    _check_forbidden_claims,
    _check_missing_data_handling,
)


# ---------------------------------------------------------------------------
# HTML Fixtures
# ---------------------------------------------------------------------------

_GOOD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Test Site</title></head>
<body>
  <header id="header"><nav><a href="/">Home</a></nav></header>
  <section id="hero" class="hero-section">
    <h1>Welcome to Acme Corp</h1>
    <p>Your trusted partner in excellence</p>
  </section>
  <section id="services" class="services-section">
    <h2>Our Services</h2>
    <p>We offer great services.</p>
  </section>
  <section id="about" class="about-section">
    <h2>About Us</h2>
    <p>Founded in 2010.</p>
  </section>
  <section id="contact" class="contact-section">
    <h2>Contact Us</h2>
    <p>Call (555) 123-4567 or email info@acme.com</p>
  </section>
  <section id="cta" class="cta-section">
    <button class="btn cta-button">Get Started Today</button>
  </section>
  <footer id="footer">
    <p>&copy; 2026 Acme Corp, 123 Main St, Springfield, IL 62701</p>
  </footer>
</body>
</html>
"""

_MINIMAL_HTML = """\
<!DOCTYPE html>
<html><head><title>Test</title></head>
<body><p>Hello world</p></body></html>
"""

_BAD_HTML = """\
<html>
<body>
  <div>Some text</div>
  <div>More text</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Tests for check_spec_alignment
# ---------------------------------------------------------------------------


class TestCheckSpecAlignment:
    """Tests for the top-level check_spec_alignment function."""

    def test_returns_all_keys(self):
        spec = {
            "required_sections": ["hero", "services", "about", "contact"],
            "forbidden_claims": ["guaranteed"],
            "missing_data": [],
        }
        result = check_spec_alignment(_GOOD_HTML, spec)
        assert "sections_present" in result
        assert "sections_missing" in result
        assert "cta_present" in result
        assert "forbidden_claims_found" in result
        assert "missing_data_handled_correctly" in result

    def test_detects_present_sections(self):
        spec = {
            "required_sections": ["hero", "services", "about", "contact"],
            "forbidden_claims": [],
            "missing_data": [],
        }
        result = check_spec_alignment(_GOOD_HTML, spec)
        assert "hero" in result["sections_present"]
        assert "services" in result["sections_present"]
        assert "about" in result["sections_present"]
        assert "contact" in result["sections_present"]
        assert result["sections_missing"] == []

    def test_detects_missing_sections(self):
        spec = {
            "required_sections": ["hero", "services", "testimonials", "pricing"],
            "forbidden_claims": [],
            "missing_data": [],
        }
        result = check_spec_alignment(_GOOD_HTML, spec)
        assert "testimonials" in result["sections_missing"]
        assert "pricing" in result["sections_missing"]

    def test_cta_detected_in_good_html(self):
        spec = {"required_sections": [], "forbidden_claims": [], "missing_data": []}
        result = check_spec_alignment(_GOOD_HTML, spec)
        assert result["cta_present"] is True

    def test_cta_not_detected_in_minimal_html(self):
        spec = {"required_sections": [], "forbidden_claims": [], "missing_data": []}
        result = check_spec_alignment(_MINIMAL_HTML, spec)
        assert result["cta_present"] is False

    def test_detects_forbidden_claims_in_html(self):
        html_with_claim = _GOOD_HTML.replace(
            "trusted partner", "guaranteed results"
        )
        spec = {
            "required_sections": [],
            "forbidden_claims": ["guaranteed"],
            "missing_data": [],
        }
        result = check_spec_alignment(html_with_claim, spec)
        assert "guaranteed" in result["forbidden_claims_found"]

    def test_no_forbidden_claims_clean_html(self):
        spec = {
            "required_sections": [],
            "forbidden_claims": ["guaranteed", "miracle cure"],
            "missing_data": [],
        }
        result = check_spec_alignment(_GOOD_HTML, spec)
        assert result["forbidden_claims_found"] == []

    def test_missing_data_handled_correctly_when_no_placeholders(self):
        spec = {"required_sections": [], "forbidden_claims": [], "missing_data": ["phone"]}
        result = check_spec_alignment(_GOOD_HTML, spec)
        assert result["missing_data_handled_correctly"] is True

    def test_missing_data_not_handled_with_placeholders(self):
        html = _GOOD_HTML.replace("Acme Corp", "{{business_name}}")
        spec = {"required_sections": [], "forbidden_claims": [], "missing_data": ["business_name"]}
        result = check_spec_alignment(html, spec)
        assert result["missing_data_handled_correctly"] is False

    def test_empty_spec_returns_defaults(self):
        spec = {}
        result = check_spec_alignment(_GOOD_HTML, spec)
        assert result["sections_present"] == []
        assert result["sections_missing"] == []
        assert result["forbidden_claims_found"] == []

    def test_spec_alignment_detects_missing_cta(self):
        """spec alignment with bad HTML should not find CTA."""
        spec = {"required_sections": [], "forbidden_claims": [], "missing_data": []}
        result = check_spec_alignment(_BAD_HTML, spec)
        assert result["cta_present"] is False


# ---------------------------------------------------------------------------
# Tests for internal helpers
# ---------------------------------------------------------------------------


class TestCheckSections:
    def test_all_present(self):
        result = _check_sections(_GOOD_HTML, ["hero", "services", "about"])
        assert result["present"] == ["hero", "services", "about"]
        assert result["missing"] == []

    def test_some_missing(self):
        result = _check_sections(_GOOD_HTML, ["hero", "gallery", "pricing"])
        assert "hero" in result["present"]
        assert "gallery" in result["missing"]
        assert "pricing" in result["missing"]

    def test_empty_requirements(self):
        result = _check_sections(_GOOD_HTML, [])
        assert result["present"] == []
        assert result["missing"] == []

    def test_footer_detection(self):
        result = _check_sections(_GOOD_HTML, ["footer"])
        assert "footer" in result["present"]

    def test_header_detection(self):
        result = _check_sections(_GOOD_HTML, ["header"])
        assert "header" in result["present"]


class TestCheckCta:
    def test_cta_with_button(self):
        html = '<button class="btn cta">Get Started</button>'
        assert _check_cta(html) is True

    def test_cta_with_form_submit(self):
        html = '<form><input type="submit" value="Send"></form>'
        assert _check_cta(html) is True

    def test_cta_with_anchor_btn(self):
        html = '<a href="#" class="btn btn-primary">Contact Us</a>'
        assert _check_cta(html) is True

    def test_no_cta(self):
        assert _check_cta(_MINIMAL_HTML) is False


class TestCheckForbiddenClaims:
    def test_finds_claim(self):
        html = "<p>We offer guaranteed results for everyone</p>"
        result = _check_forbidden_claims(html, ["guaranteed"])
        assert "guaranteed" in result

    def test_no_claims(self):
        result = _check_forbidden_claims(_GOOD_HTML, ["miracle cure", "FDA approved"])
        assert result == []

    def test_empty_list(self):
        result = _check_forbidden_claims(_GOOD_HTML, [])
        assert result == []

    def test_case_insensitive(self):
        html = "<p>GUARANTEED results</p>"
        result = _check_forbidden_claims(html, ["guaranteed"])
        assert "guaranteed" in result


class TestCheckMissingDataHandling:
    def test_no_missing_data(self):
        assert _check_missing_data_handling(_GOOD_HTML, []) is True

    def test_handled_correctly(self):
        assert _check_missing_data_handling(_GOOD_HTML, ["phone"]) is True

    def test_unhandled_placeholder_mustache(self):
        html = "<p>{{phone}}</p>"
        assert _check_missing_data_handling(html, ["phone"]) is False

    def test_unhandled_placeholder_brackets(self):
        html = "<p>[phone]</p>"
        assert _check_missing_data_handling(html, ["phone"]) is False

    def test_unhandled_placeholder_double_brackets(self):
        html = "<p>[[phone]]</p>"
        assert _check_missing_data_handling(html, ["phone"]) is False

    def test_unhandled_placeholder_missing_prefix(self):
        html = "<p>__missing_phone__</p>"
        assert _check_missing_data_handling(html, ["phone"]) is False
