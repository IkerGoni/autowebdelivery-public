"""Tests for packages.generation.html_sanitizer."""

from __future__ import annotations

import json

from packages.generation.html_sanitizer import (
    SanitizationFinding,
    SanitizationResult,
    SanitizationRule,
    sanitize_html,
    write_sanitized_html,
    write_sanitizer_report,
)

# ---------------------------------------------------------------------------
# 1. Clean HTML passes through unchanged
# ---------------------------------------------------------------------------

def test_clean_html_unchanged():
    html = "<html><body><h1>Welcome</h1><p>We offer detailing services.</p></body></html>"
    result = sanitize_html(html, verified_facts={"phone": "555-1234"})
    assert result.sanitized_html == html
    assert result.findings == []
    assert result.hard_block is False
    assert result.removals_count == 0
    assert result.replacements_count == 0


def test_clean_html_with_verified_phone_preserved():
    html = '<p>Call us: (903) 456-9029</p><a href="tel:+19034569029">Call</a>'
    result = sanitize_html(html, verified_facts={"phone": "+1 903-456-9029"})
    assert "(903) 456-9029" in result.sanitized_html
    assert "tel:+19034569029" in result.sanitized_html
    assert result.replacements_count == 0


# ---------------------------------------------------------------------------
# 2-3. Fake phone detection and verified phone preservation
# ---------------------------------------------------------------------------

def test_fake_555_phone_removed():
    html = "<p>Call 555-0123 for a quote</p>"
    result = sanitize_html(html)
    assert "555-0123" not in result.sanitized_html
    assert "Contact for availability" in result.sanitized_html
    assert any(f.rule_name == "fake_555_phone" for f in result.findings)


def test_unverified_phone_replaced_when_no_verified():
    html = "<p>Call (972) 555-1234 today!</p>"
    result = sanitize_html(html, verified_facts={})
    assert "(972) 555-1234" not in result.sanitized_html
    assert "Contact for availability" in result.sanitized_html


def test_unverified_phone_replaced_when_different_verified():
    html = "<p>Call (972) 555-1234 today!</p>"
    result = sanitize_html(html, verified_facts={"phone": "(214) 999-8888"})
    assert "(972) 555-1234" not in result.sanitized_html
    assert "Contact for availability" in result.sanitized_html


def test_verified_phone_preserved():
    html = "<p>Call (214) 999-8888 today!</p>"
    result = sanitize_html(html, verified_facts={"phone": "(214) 999-8888"})
    assert "(214) 999-8888" in result.sanitized_html
    # No phone-related findings
    phone_findings = [f for f in result.findings if "phone" in f.rule_name.lower()]
    assert phone_findings == []


# ---------------------------------------------------------------------------
# 4. Fake email removal
# ---------------------------------------------------------------------------

def test_fake_email_removed():
    html = "<p>Email us at fake@example.com</p>"
    result = sanitize_html(html)
    assert "fake@example.com" not in result.sanitized_html
    assert "Request a quote" in result.sanitized_html
    assert any(f.rule_name == "unverified_email" for f in result.findings)


def test_verified_email_preserved():
    html = "<p>Email us at real@biz.com</p>"
    result = sanitize_html(html, verified_facts={"email": "real@biz.com"})
    assert "real@biz.com" in result.sanitized_html


def test_mailto_link_unverified_replaced():
    html = '<a href="mailto:spam@fake.com">Contact</a>'
    result = sanitize_html(html)
    assert "mailto:" not in result.sanitized_html
    assert any(f.rule_name == "fake_mailto_link" for f in result.findings)


def test_mailto_link_verified_preserved():
    html = '<a href="mailto:ok@biz.com">Contact</a>'
    result = sanitize_html(html, verified_facts={"email": "ok@biz.com"})
    assert "mailto:ok@biz.com" in result.sanitized_html


# ---------------------------------------------------------------------------
# 5. Certification badge removal
# ---------------------------------------------------------------------------

def test_certification_removed():
    html = "<div>Ceramic Pro Certified Installer</div>"
    result = sanitize_html(html)
    assert "Certified" not in result.sanitized_html
    assert any(f.category == "certification" for f in result.findings)


def test_ppf_certified_removed():
    html = "<span>PPF Certified</span>"
    result = sanitize_html(html)
    assert result.sanitized_html.strip() == ""
    assert result.removals_count >= 1


def test_ida_certified_removed():
    html = "<p>IDA Certified Detailer</p>"
    result = sanitize_html(html)
    assert "IDA" not in result.sanitized_html


def test_licensed_removed_unless_verified():
    html = "<p>Licensed and Insured</p>"
    result = sanitize_html(html, verified_facts={})
    assert "Licensed" not in result.sanitized_html

    result2 = sanitize_html(html, verified_facts={"licensed": True, "insured": True})
    assert "Licensed" in result2.sanitized_html


# ---------------------------------------------------------------------------
# 6. Review/rating removal
# ---------------------------------------------------------------------------

def test_five_star_removed():
    html = "<div>5-Star Service</div>"
    result = sanitize_html(html)
    assert "5-Star" not in result.sanitized_html
    assert any(f.category == "review_rating" for f in result.findings)


def test_five_star_word_removed():
    html = "<div>Five-Star Reviews</div>"
    result = sanitize_html(html)
    assert "Five-Star" not in result.sanitized_html


def test_star_unicode_removed():
    html = "<span>★★★★★</span>"
    result = sanitize_html(html)
    assert "★" not in result.sanitized_html


def test_star_emoji_removed():
    html = "<span>⭐⭐⭐⭐⭐</span>"
    result = sanitize_html(html)
    assert "⭐" not in result.sanitized_html


def test_testimonial_removed():
    html = '<div class="testimonial">Great service! - Customer</div>'
    result = sanitize_html(html)
    assert "testimonial" not in result.sanitized_html.lower() or result.sanitized_html.strip() == ""


def test_review_count_removed_unless_exact():
    html = "<p>120+ reviews</p>"
    result = sanitize_html(html, verified_facts={})
    assert "120" not in result.sanitized_html

    html2 = "<p>108 reviews</p>"
    result2 = sanitize_html(html2, verified_facts={"review_count": 108})
    assert "108 reviews" in result2.sanitized_html


def test_customer_says_removed():
    html = "<blockquote>Customer says: Amazing work!</blockquote>"
    result = sanitize_html(html)
    assert "Customer says" not in result.sanitized_html


# ---------------------------------------------------------------------------
# 7. Trust claim removal
# ---------------------------------------------------------------------------

def test_best_removed():
    html = "<h2>The Best Detailing in Texas</h2>"
    result = sanitize_html(html)
    assert "Best" not in result.sanitized_html
    assert any(f.category == "trust_claim" for f in result.findings)


def test_number_one_removed():
    html = "<p>#1 Detailing Service</p>"
    result = sanitize_html(html)
    assert "#1" not in result.sanitized_html


def test_top_rated_removed():
    html = "<span>Top-Rated Service</span>"
    result = sanitize_html(html)
    assert "Top-Rated" not in result.sanitized_html


def test_award_winning_removed():
    html = "<div>Award-Winning Team</div>"
    result = sanitize_html(html)
    assert "Award-Winning" not in result.sanitized_html


def test_guaranteed_removed():
    html = "<p>Satisfaction Guaranteed</p>"
    result = sanitize_html(html)
    assert "Guaranteed" not in result.sanitized_html


def test_years_in_business_removed():
    html = "<p>15 years in business</p>"
    result = sanitize_html(html)
    assert "years in business" not in result.sanitized_html


def test_since_year_removed():
    html = "<p>Serving since 2005</p>"
    result = sanitize_html(html)
    assert "since 2005" not in result.sanitized_html


def test_family_owned_removed():
    html = "<p>Family-Owned Business</p>"
    result = sanitize_html(html)
    assert "Family-Owned" not in result.sanitized_html


def test_trusted_by_removed():
    html = "<p>Trusted by thousands</p>"
    result = sanitize_html(html)
    assert "Trusted by" not in result.sanitized_html


def test_official_partner_removed():
    html = "<p>Official Partner of XYZ</p>"
    result = sanitize_html(html)
    assert "Official Partner" not in result.sanitized_html


def test_elite_removed():
    html = "<div>Elite Detailing Crew</div>"
    result = sanitize_html(html)
    assert "Elite" not in result.sanitized_html


# ---------------------------------------------------------------------------
# 8-10. Security: scripts, event handlers, javascript URLs
# ---------------------------------------------------------------------------

def test_script_tag_removed():
    html = '<html><body><p>Hello</p><script>alert("xss")</script></body></html>'
    result = sanitize_html(html)
    assert "<script" not in result.sanitized_html
    assert "alert" not in result.sanitized_html
    assert any(f.rule_name == "security_script" for f in result.findings)
    # Should NOT hard block because it was successfully removed
    assert result.hard_block is False


def test_event_handler_removed():
    html = '<img src="pic.jpg" onload="alert(1)" onerror="alert(2)">'
    result = sanitize_html(html)
    assert "onload" not in result.sanitized_html
    assert "onerror" not in result.sanitized_html
    assert "src" in result.sanitized_html
    security_findings = [f for f in result.findings if f.rule_name == "security_event_handler"]
    assert len(security_findings) == 2


def test_javascript_url_removed():
    html = '<a href="javascript:alert(1)">Click</a>'
    result = sanitize_html(html)
    assert "javascript:" not in result.sanitized_html
    assert 'href="#"' in result.sanitized_html
    assert any(f.rule_name == "security_javascript_url" for f in result.findings)


# ---------------------------------------------------------------------------
# 11. Orphaned empty elements cleanup
# ---------------------------------------------------------------------------

def test_empty_div_removed():
    html = "<div></div><p>Real content</p>"
    result = sanitize_html(html)
    assert "<div>" not in result.sanitized_html
    assert "Real content" in result.sanitized_html


def test_empty_section_removed():
    html = "<section>   </section><p>Content</p>"
    result = sanitize_html(html)
    assert "<section>" not in result.sanitized_html


def test_div_with_content_preserved():
    html = "<div>I have content</div>"
    result = sanitize_html(html)
    assert "<div>" in result.sanitized_html
    assert "I have content" in result.sanitized_html


def test_div_with_child_elements_preserved():
    """Div containing child elements (like img) should not be removed as empty."""
    html = '<div><img src="photo.jpg"></div>'
    result = sanitize_html(html)
    assert "<div>" in result.sanitized_html
    assert "<img" in result.sanitized_html


# ---------------------------------------------------------------------------
# 12. Stitch data attribute removal
# ---------------------------------------------------------------------------

def test_stitch_data_attrs_removed():
    html = '<div data-stitch-id="abc" data-screen-name="hero" data-component-type="card">Content</div>'
    result = sanitize_html(html)
    assert "data-stitch" not in result.sanitized_html
    assert "data-screen" not in result.sanitized_html
    assert "data-component" not in result.sanitized_html
    assert "Content" in result.sanitized_html
    stitch_findings = [f for f in result.findings if f.rule_name == "stitch_data_attr"]
    assert len(stitch_findings) == 3


def test_stitch_comment_removed():
    html = "<!-- stitch: screen-id=abc --><p>Content</p>"
    result = sanitize_html(html)
    assert "stitch" not in result.sanitized_html
    assert "Content" in result.sanitized_html


# ---------------------------------------------------------------------------
# 13. Hard block when security risks survive
# ---------------------------------------------------------------------------

def test_hard_block_false_when_security_cleaned():
    """Normal case: script removed successfully -> no hard block."""
    html = "<p>Safe</p><script>bad</script>"
    result = sanitize_html(html)
    assert result.hard_block is False


# ---------------------------------------------------------------------------
# 14. Multiple findings in one document
# ---------------------------------------------------------------------------

def test_multiple_findings():
    html = (
        "<html><body>"
        "<h1>The Best Detailing</h1>"
        "<p>Ceramic Pro Certified</p>"
        "<p>Call 555-0199</p>"
        "<div>★★★★★</div>"
        '<script>alert("x")</script>'
        '<a href="javascript:void(0)">Click</a>'
        "</body></html>"
    )
    result = sanitize_html(html)
    assert len(result.findings) >= 5
    categories = {f.category for f in result.findings}
    assert "trust_claim" in categories
    assert "certification" in categories
    assert "fake_contact" in categories
    assert "review_rating" in categories
    assert "security" in categories


# ---------------------------------------------------------------------------
# 15. write_sanitizer_report produces valid JSON
# ---------------------------------------------------------------------------

def test_write_sanitizer_report(tmp_path):
    html = "<p>Call 555-0123</p>"
    result = sanitize_html(html)
    report_path = write_sanitizer_report(result, tmp_path)

    assert report_path.exists()
    assert report_path.name == "sanitizer_report.json"

    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert "hard_block" in data
    assert "findings" in data
    assert isinstance(data["findings"], list)
    assert "removals_count" in data
    assert "replacements_count" in data
    assert data["hard_block"] is False
    assert len(data["findings"]) >= 1


# ---------------------------------------------------------------------------
# 16. write_sanitized_html writes correct content
# ---------------------------------------------------------------------------

def test_write_sanitized_html(tmp_path):
    html = "<p>Clean content</p>"
    result = sanitize_html(html)
    out = tmp_path / "index.html"
    written = write_sanitized_html(result, out)

    assert written.exists()
    assert written.read_text(encoding="utf-8") == result.sanitized_html


def test_write_sanitized_html_creates_dirs(tmp_path):
    html = "<p>Content</p>"
    result = sanitize_html(html)
    out = tmp_path / "sub" / "dir" / "index.html"
    written = write_sanitized_html(result, out)
    assert written.exists()


# ---------------------------------------------------------------------------
# 17. iframe/embed/object removal
# ---------------------------------------------------------------------------

def test_iframe_removed():
    html = '<p>Content</p><iframe src="https://evil.com"></iframe>'
    result = sanitize_html(html)
    assert "<iframe" not in result.sanitized_html
    assert "evil.com" not in result.sanitized_html
    assert any(f.rule_name == "security_iframe" for f in result.findings)


def test_embed_removed():
    html = '<embed src="flash.swf" type="application/x-shockwave-flash">'
    result = sanitize_html(html)
    assert "<embed" not in result.sanitized_html


def test_object_removed():
    html = '<object data="movie.swf" type="application/x-shockwave-flash"><param name="movie" value="x"></object>'
    result = sanitize_html(html)
    assert "<object" not in result.sanitized_html


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_html():
    result = sanitize_html("")
    assert result.sanitized_html == ""
    assert result.findings == []


def test_html_with_doctype_preserved():
    html = "<!DOCTYPE html><html><body><p>OK</p></body></html>"
    result = sanitize_html(html)
    assert "<!DOCTYPE html>" in result.sanitized_html


def test_tel_link_unverified_replaced():
    html = '<a href="tel:+15550199">Call us</a>'
    result = sanitize_html(html)
    assert "tel:" not in result.sanitized_html


def test_tel_link_verified_preserved():
    html = '<a href="tel:+12149998888">Call</a>'
    result = sanitize_html(html, verified_facts={"phone": "+1 214-999-8888"})
    assert "tel:+12149998888" in result.sanitized_html


def test_data_classes_exist():
    """Verify data classes are importable and constructable."""
    rule = SanitizationRule(name="test", category="test", description="test rule")
    assert rule.name == "test"

    finding = SanitizationFinding(
        rule_name="test",
        category="test",
        severity="removed",
        element_tag="div",
        element_text_preview="text",
        action_taken="removed",
    )
    assert finding.line_hint is None

    res = SanitizationResult(original_html="<p>x</p>", sanitized_html="<p>x</p>")
    assert res.hard_block is False
    assert res.findings == []


def test_normal_data_attrs_preserved():
    """Non-stitch data attributes should survive."""
    html = '<div data-id="123" data-role="main">Content</div>'
    result = sanitize_html(html)
    assert 'data-id="123"' in result.sanitized_html
    assert 'data-role="main"' in result.sanitized_html


def test_onclick_handler_removed():
    html = '<button onclick="doStuff()">Click</button>'
    result = sanitize_html(html)
    assert "onclick" not in result.sanitized_html
    assert "Click" in result.sanitized_html


def test_hidden_element_with_cert_removed():
    """Hidden elements with certifications must be caught — Phase 06 misses these."""
    html = '<div style="display:none"><span>Ceramic Pro Certified</span></div>'
    result = sanitize_html(html)
    assert "Certified" not in result.sanitized_html
    assert result.removals_count >= 1


# ---------------------------------------------------------------------------
# Security: expanded attack vector tests
# ---------------------------------------------------------------------------

def test_formaction_javascript_blocked():
    """C1: javascript: in formaction attribute must be blocked."""
    html = '<form><button formaction="javascript:alert(1)">Submit</button></form>'
    result = sanitize_html(html)
    assert "javascript:" not in result.sanitized_html
    assert 'formaction="#"' in result.sanitized_html
    assert any(f.rule_name == "security_javascript_url" for f in result.findings)


def test_tab_obfuscated_javascript_blocked():
    """C2: Tab/newline chars in javascript: URL must be caught."""
    html = '<a href="java\tscript:alert(1)">Click</a>'
    result = sanitize_html(html)
    assert "javascript" not in result.sanitized_html.lower() or 'href="#"' in result.sanitized_html
    assert any(f.rule_name == "security_javascript_url" for f in result.findings)


def test_data_uri_blocked():
    """C3: data: URIs (non-image) must be blocked."""
    html = '<a href="data:text/html,<script>alert(1)</script>">Click</a>'
    result = sanitize_html(html)
    assert 'href="#"' in result.sanitized_html
    assert any(f.rule_name == "security_javascript_url" for f in result.findings)


def test_data_image_uri_allowed():
    """C3: data:image/* should be allowed (safe inline images)."""
    html = '<img src="data:image/png;base64,iVBORw0KGgo=">'
    result = sanitize_html(html)
    assert "data:image/png" in result.sanitized_html
    security_findings = [f for f in result.findings if f.rule_name == "security_javascript_url"]
    assert len(security_findings) == 0


def test_vbscript_blocked():
    """C4: vbscript: URLs must be blocked."""
    html = '<a href="vbscript:MsgBox(1)">Click</a>'
    result = sanitize_html(html)
    assert "vbscript:" not in result.sanitized_html
    assert 'href="#"' in result.sanitized_html
    assert any(f.rule_name == "security_javascript_url" for f in result.findings)


def test_style_dangerous_css_removed():
    """C5: <style> with @import or expression() must be removed."""
    html = '<style>body { color: red; } @import url("https://evil.com/steal.css");</style><p>Content</p>'
    result = sanitize_html(html)
    assert "<style>" not in result.sanitized_html
    assert "@import" not in result.sanitized_html
    assert "Content" in result.sanitized_html
    assert any(f.rule_name == "security_dangerous_css" for f in result.findings)


def test_style_safe_css_preserved():
    """C5: <style> with safe CSS should be kept."""
    html = '<style>body { color: red; font-size: 16px; }</style><p>Content</p>'
    result = sanitize_html(html)
    assert "<style>" in result.sanitized_html
    assert "color: red" in result.sanitized_html
    css_findings = [f for f in result.findings if f.rule_name == "security_dangerous_css"]
    assert len(css_findings) == 0


def test_meta_refresh_javascript_blocked():
    """C6: <meta http-equiv=refresh> with javascript: URL must be removed."""
    html = '<meta http-equiv="refresh" content="0;url=javascript:alert(1)">'
    result = sanitize_html(html)
    assert "javascript:" not in result.sanitized_html
    assert any(f.rule_name == "security_meta_refresh" for f in result.findings)


def test_render_escapes_angle_brackets():
    """M1: < and > in attribute values must be escaped."""
    html = '<div data-val="a<b>c">Content</div>'
    result = sanitize_html(html)
    assert "&lt;" in result.sanitized_html
    assert "&gt;" in result.sanitized_html
    # Must not contain raw < or > inside attribute value
    assert 'data-val="a&lt;b&gt;c"' in result.sanitized_html
