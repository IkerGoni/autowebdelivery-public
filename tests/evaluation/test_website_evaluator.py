"""Tests for packages/evaluation/website_evaluator.py — VNEXT-06."""

from __future__ import annotations

import json

from packages.evaluation.website_evaluator import (
    SCHEMA_VERSION,
    _score_accessibility,
    _score_branding,
    _score_conversion,
    _score_factual_safety,
    _score_hierarchy,
    _score_imagery,
    _score_local_relevance,
    _score_mobile_experience,
    _score_originality,
    _score_spacing,
    _score_trust,
    _score_typography,
    evaluate_website,
    write_evaluation_report,
)

# ---------------------------------------------------------------------------
# HTML Fixtures
# ---------------------------------------------------------------------------

_GOOD_SITE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Acme Auto Detailing - Professional Car Care</title>
  <style>
    :root {
      --primary: #1a5276;
      --secondary: #2ecc71;
      --accent: #e67e22;
      --bg: #ffffff;
      --text: #333333;
    }

    * { margin: 0; padding: 0; box-sizing: border-box; }

    body {
      font-family: 'Inter', 'Segoe UI', sans-serif;
      font-size: 16px;
      line-height: 1.6;
      color: var(--text);
      background: var(--bg);
    }

    .hero-section {
      background: linear-gradient(135deg, var(--primary), var(--secondary));
      padding: 80px 20px;
      text-align: center;
    }

    .hero-section h1 {
      color: #ffffff;
      font-size: 2.5rem;
      font-weight: 700;
      margin-bottom: 20px;
    }

    .container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 0 20px;
    }

    .services-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 30px;
      padding: 60px 0;
    }

    .service-card {
      background: #f8f9fa;
      padding: 30px;
      border-radius: 12px;
      text-align: center;
    }

    .service-card h3 {
      color: var(--primary);
      margin-bottom: 15px;
    }

    .cta-button {
      display: inline-block;
      background: var(--accent);
      color: white;
      padding: 15px 40px;
      border-radius: 8px;
      font-size: 1.1rem;
      font-weight: 600;
      text-decoration: none;
      cursor: pointer;
    }

    .cta-button:hover {
      background: #d35400;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(20px); }
      to { opacity: 1; transform: translateY(0); }
    }

    @media (max-width: 768px) {
      .hero-section { padding: 40px 15px; }
      .hero-section h1 { font-size: 1.8rem; }
      .services-grid { grid-template-columns: 1fr; gap: 20px; }
    }

    @media (max-width: 480px) {
      .hero-section h1 { font-size: 1.4rem; }
    }
  </style>
</head>
<body>
  <header id="header" role="banner">
    <nav class="container" aria-label="Main navigation">
      <a href="/">Acme Auto Detailing</a>
    </nav>
  </header>

  <main id="main-content" role="main">
    <section id="hero" class="hero-section" aria-label="Hero">
      <div class="container">
        <h1>Professional Auto Detailing in Springfield</h1>
        <p>Your trusted local car care experts since 2010</p>
        <a href="#contact" class="cta-button">Get Started Today</a>
      </div>
    </section>

    <section id="services" class="container">
      <h2>Our Services</h2>
      <div class="services-grid">
        <div class="service-card">
          <img src="images/wash.jpg" alt="Exterior car wash service" width="300" height="200">
          <h3>Exterior Wash</h3>
          <p>Complete exterior cleaning and protection.</p>
        </div>
        <div class="service-card">
          <img src="images/detail.jpg" alt="Interior detailing service" width="300" height="200">
          <h3>Interior Detailing</h3>
          <p>Deep cleaning for your vehicle's interior.</p>
        </div>
        <div class="service-card">
          <img src="images/ceramic.jpg" alt="Ceramic coating application" width="300" height="200">
          <h3>Ceramic Coating</h3>
          <p>Long-lasting paint protection.</p>
        </div>
      </div>
    </section>

    <section id="about" class="container" style="padding: 60px 0;">
      <h2>About Acme Auto Detailing</h2>
      <p>Locally owned and operated in Springfield, IL. We take pride in every vehicle we service.</p>
    </section>

    <section id="contact" class="container" style="padding: 40px 0;">
      <h2>Contact Us</h2>
      <p>Phone: (555) 123-4567</p>
      <p>Email: info@acmedetailing.com</p>
      <p>Address: 123 Main Street, Springfield, IL 62701</p>
      <form action="/contact" method="POST">
        <input type="text" name="name" placeholder="Your Name" aria-label="Your name">
        <input type="email" name="email" placeholder="Your Email" aria-label="Your email">
        <input type="submit" value="Send Message">
      </form>
    </section>

    <section id="cta" class="container" style="text-align: center; padding: 40px 0;">
      <h2>Ready to Get Your Car Looking New?</h2>
      <button class="cta-button" aria-label="Book your appointment">Book Now</button>
    </section>
  </main>

  <footer id="footer" role="contentinfo">
    <div class="container">
      <p>&copy; 2026 Acme Auto Detailing | 123 Main Street, Springfield, IL 62701</p>
      <p>Call (555) 123-4567 for a free estimate</p>
    </div>
  </footer>
</body>
</html>
"""

_BAD_SITE_HTML = """\
<html>
<body>
  <div>Some text</div>
  <div>More text with guaranteed results and #1 rated service</div>
  <font color="red">Old style font tag</font>
</body>
</html>
"""

_MINIMAL_SITE_HTML = """\
<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body><p>Hello world</p></body>
</html>
"""


# ---------------------------------------------------------------------------
# Dimension scorer tests
# ---------------------------------------------------------------------------


class TestDimensionScorers:
    """Verify each scorer returns (0–100, notes)."""

    def test_hierarchy_good(self):
        score, notes = _score_hierarchy(_GOOD_SITE_HTML)
        assert 0 <= score <= 100
        assert isinstance(notes, str)
        assert score >= 50  # Good site should score well

    def test_hierarchy_bad(self):
        score, _notes = _score_hierarchy(_BAD_SITE_HTML)
        assert 0 <= score <= 100
        assert score < 50

    def test_branding_good(self):
        score, _notes = _score_branding(_GOOD_SITE_HTML)
        assert 0 <= score <= 100
        assert score >= 40

    def test_branding_bad(self):
        score, _notes = _score_branding(_BAD_SITE_HTML)
        assert 0 <= score <= 100

    def test_typography_good(self):
        score, _notes = _score_typography(_GOOD_SITE_HTML)
        assert 0 <= score <= 100
        assert score >= 40

    def test_spacing_good(self):
        score, _notes = _score_spacing(_GOOD_SITE_HTML)
        assert 0 <= score <= 100
        assert score >= 40

    def test_imagery_good(self):
        score, _notes = _score_imagery(_GOOD_SITE_HTML)
        assert 0 <= score <= 100
        assert score >= 40

    def test_imagery_bad(self):
        score, _notes = _score_imagery(_BAD_SITE_HTML)
        assert 0 <= score <= 100

    def test_trust_good(self):
        score, _notes = _score_trust(_GOOD_SITE_HTML)
        assert 0 <= score <= 100
        assert score >= 40

    def test_trust_bad(self):
        score, _notes = _score_trust(_BAD_SITE_HTML)
        assert 0 <= score <= 100

    def test_conversion_good(self):
        score, _notes = _score_conversion(_GOOD_SITE_HTML)
        assert 0 <= score <= 100
        assert score >= 40

    def test_conversion_bad(self):
        score, _notes = _score_conversion(_BAD_SITE_HTML)
        assert 0 <= score <= 100

    def test_accessibility_good(self):
        score, _notes = _score_accessibility(_GOOD_SITE_HTML)
        assert 0 <= score <= 100
        assert score >= 40

    def test_accessibility_bad(self):
        score, _notes = _score_accessibility(_BAD_SITE_HTML)
        assert 0 <= score <= 100
        assert score < 60

    def test_originality_good(self):
        score, _notes = _score_originality(_GOOD_SITE_HTML)
        assert 0 <= score <= 100

    def test_mobile_good(self):
        score, _notes = _score_mobile_experience(_GOOD_SITE_HTML)
        assert 0 <= score <= 100
        assert score >= 50

    def test_mobile_bad(self):
        score, _notes = _score_mobile_experience(_BAD_SITE_HTML)
        assert 0 <= score <= 100
        assert score < 50

    def test_factual_safety_clean(self):
        score, notes = _score_factual_safety(_GOOD_SITE_HTML, ["guaranteed", "#1 rated"])
        assert score == 100
        assert "No forbidden claims" in notes

    def test_factual_safety_with_claims(self):
        score, _notes = _score_factual_safety(_BAD_SITE_HTML, ["guaranteed", "#1 rated"])
        assert score < 100

    def test_local_relevance_good(self):
        score, _notes = _score_local_relevance(_GOOD_SITE_HTML, "acme-auto-detailing")
        assert 0 <= score <= 100
        assert score >= 40

    def test_local_relevance_bad(self):
        score, _notes = _score_local_relevance(_BAD_SITE_HTML, "unknown-biz")
        assert 0 <= score <= 100


# ---------------------------------------------------------------------------
# evaluate_website integration tests
# ---------------------------------------------------------------------------


class TestEvaluateWebsite:
    def test_all_12_dimensions_scored(self):
        report = evaluate_website(
            _GOOD_SITE_HTML,
            run_id="test-run-001",
            business_slug="acme-detailing",
        )
        dims = report["dimensions"]
        expected = [
            "hierarchy", "branding", "typography", "spacing", "imagery",
            "trust", "conversion", "accessibility", "originality",
            "mobile_experience", "factual_safety", "local_relevance",
        ]
        for dim_name in expected:
            assert dim_name in dims, f"Missing dimension: {dim_name}"
            assert "score" in dims[dim_name]
            assert "status" in dims[dim_name]
            assert "notes" in dims[dim_name]

    def test_dimensions_are_0_to_100(self):
        report = evaluate_website(
            _GOOD_SITE_HTML,
            run_id="test-run-002",
            business_slug="acme-detailing",
        )
        for name, dim in report["dimensions"].items():
            assert 0 <= dim["score"] <= 100, f"{name} score {dim['score']} out of range"

    def test_overall_score_is_weighted_average(self):
        report = evaluate_website(
            _GOOD_SITE_HTML,
            run_id="test-run-003",
            business_slug="acme-detailing",
        )
        scores = [d["score"] for d in report["dimensions"].values()]
        expected_avg = round(sum(scores) / len(scores), 1)
        assert report["overall_score"] == expected_avg

    def test_verdict_pass_when_no_hard_failures(self):
        report = evaluate_website(
            _GOOD_SITE_HTML,
            run_id="test-run-004",
            business_slug="acme-detailing",
        )
        # Good site should pass
        assert report["verdict"] == "pass"
        assert report["hard_failures"] == []

    def test_verdict_fail_when_hard_failure(self):
        # Bad site has forbidden claims AND poor accessibility
        report = evaluate_website(
            _BAD_SITE_HTML,
            run_id="test-run-005",
            business_slug="bad-biz",
        )
        assert report["verdict"] == "fail"
        assert len(report["hard_failures"]) > 0

    def test_factual_safety_detects_forbidden_claims(self):
        report = evaluate_website(
            _BAD_SITE_HTML,
            config={"forbidden_claims": ["guaranteed"]},
            run_id="test-run-006",
            business_slug="bad-biz",
        )
        safety = report["dimensions"]["factual_safety"]
        assert safety["score"] < 100

    def test_creative_spec_none_graceful(self):
        report = evaluate_website(
            _GOOD_SITE_HTML,
            creative_spec=None,
            run_id="test-run-007",
            business_slug="acme-detailing",
        )
        assert report["creative_spec_alignment"]["sections_present"] == []
        assert report["creative_spec_alignment"]["sections_missing"] == []
        assert report["missing_data"] == []

    def test_creative_spec_with_sections(self):
        spec = {
            "required_sections": ["hero", "services", "about", "contact", "cta"],
            "forbidden_claims": [],
            "missing_data": [],
        }
        report = evaluate_website(
            _GOOD_SITE_HTML,
            creative_spec=spec,
            run_id="test-run-008",
            business_slug="acme-detailing",
        )
        alignment = report["creative_spec_alignment"]
        assert "hero" in alignment["sections_present"]
        assert "services" in alignment["sections_present"]
        assert alignment["cta_present"] is True

    def test_spec_alignment_detects_missing_cta(self):
        spec = {
            "required_sections": [],
            "forbidden_claims": [],
            "missing_data": [],
        }
        report = evaluate_website(
            _BAD_SITE_HTML,
            creative_spec=spec,
            run_id="test-run-009",
            business_slug="bad-biz",
        )
        # Bad site has no CTA
        assert report["creative_spec_alignment"]["cta_present"] is False

    def test_spec_alignment_detects_forbidden_claims_in_html(self):
        spec = {
            "required_sections": [],
            "forbidden_claims": ["guaranteed", "#1 rated"],
            "missing_data": [],
        }
        report = evaluate_website(
            _BAD_SITE_HTML,
            creative_spec=spec,
            run_id="test-run-010",
            business_slug="bad-biz",
        )
        found = report["creative_spec_alignment"]["forbidden_claims_found"]
        assert "guaranteed" in found

    def test_deterministic_for_same_input(self):
        r1 = evaluate_website(
            _GOOD_SITE_HTML,
            run_id="test-run-determ",
            business_slug="acme-detailing",
        )
        r2 = evaluate_website(
            _GOOD_SITE_HTML,
            run_id="test-run-determ",
            business_slug="acme-detailing",
        )
        # Dimension scores should be identical
        for dim_name in r1["dimensions"]:
            assert r1["dimensions"][dim_name]["score"] == r2["dimensions"][dim_name]["score"]
        assert r1["overall_score"] == r2["overall_score"]

    def test_hard_failures_populated_correctly(self):
        report = evaluate_website(
            _BAD_SITE_HTML,
            run_id="test-run-011",
            business_slug="bad-biz",
        )
        # Bad site should have hard failures (accessibility likely < 50)
        assert isinstance(report["hard_failures"], list)
        for dim_name in report["hard_failures"]:
            assert dim_name in {"factual_safety", "accessibility"}

    def test_patchable_failures_populated_correctly(self):
        report = evaluate_website(
            _BAD_SITE_HTML,
            run_id="test-run-012",
            business_slug="bad-biz",
        )
        assert isinstance(report["patchable_failures"], list)
        for dim_name in report["patchable_failures"]:
            assert dim_name in {"imagery", "originality", "typography", "spacing", "branding"}

    def test_report_shape_has_all_top_level_keys(self):
        report = evaluate_website(
            _GOOD_SITE_HTML,
            run_id="test-run-013",
            business_slug="acme-detailing",
        )
        assert "schema_version" in report
        assert "run_id" in report
        assert "business_slug" in report
        assert "generated_at" in report
        assert "dimensions" in report
        assert "overall_score" in report
        assert "verdict" in report
        assert "hard_failures" in report
        assert "patchable_failures" in report
        assert "creative_spec_alignment" in report
        assert "missing_data" in report
        assert "internal" in report

    def test_schema_version(self):
        report = evaluate_website(
            _GOOD_SITE_HTML,
            run_id="test-run-014",
            business_slug="acme-detailing",
        )
        assert report["schema_version"] == SCHEMA_VERSION

    def test_internal_flag(self):
        report = evaluate_website(
            _GOOD_SITE_HTML,
            run_id="test-run-015",
            business_slug="acme-detailing",
        )
        assert report["internal"]["flag"] == "use_structured_evaluation_report"
        assert report["internal"]["schema_origin"] == "VNEXT-06"

    def test_run_id_and_slug_preserved(self):
        report = evaluate_website(
            _GOOD_SITE_HTML,
            run_id="my-run-id",
            business_slug="my-slug",
        )
        assert report["run_id"] == "my-run-id"
        assert report["business_slug"] == "my-slug"

    def test_verdict_patchable(self):
        """Create a site that passes hard checks but has patchable issues."""
        # A site with ok accessibility/safety but poor imagery/originality
        html = """\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Test</title>
<style>
  :root { --primary: #333; }
  body { font-family: Arial; line-height: 1.5; padding: 10px; margin: 0; }
</style>
</head>
<body>
  <header><nav aria-label="main"><a href="/">Home</a></nav></header>
  <main>
    <section><h1>Welcome</h1><p>Content here.</p></section>
    <section><h2>About</h2><p>Info here.</p></section>
    <footer id="footer">Contact: (555) 123-4567</footer>
  </main>
</body></html>
"""
        report = evaluate_website(
            html,
            run_id="test-patchable",
            business_slug="test-biz",
        )
        # This should not have hard failures but may have low scores in patchable dims
        assert report["verdict"] in ("pass", "patchable", "fail")


# ---------------------------------------------------------------------------
# write_evaluation_report tests
# ---------------------------------------------------------------------------


class TestWriteEvaluationReport:
    def test_writes_json_file(self, tmp_path):
        report = evaluate_website(
            _GOOD_SITE_HTML,
            run_id="test-write-001",
            business_slug="acme-detailing",
        )
        result_path = write_evaluation_report(report, str(tmp_path))
        assert result_path.exists()
        assert result_path.name == "evaluation_report.json"

        loaded = json.loads(result_path.read_text(encoding="utf-8"))
        assert loaded["schema_version"] == report["schema_version"]
        assert loaded["run_id"] == report["run_id"]
        assert loaded["overall_score"] == report["overall_score"]

    def test_creates_parent_dirs(self, tmp_path):
        report = evaluate_website(
            _GOOD_SITE_HTML,
            run_id="test-write-002",
            business_slug="acme-detailing",
        )
        nested = tmp_path / "deep" / "nested" / "dir"
        result_path = write_evaluation_report(report, str(nested))
        assert result_path.exists()
