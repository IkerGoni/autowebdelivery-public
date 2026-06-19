import tempfile
from pathlib import Path

from pipeline.json_io import write_json
from packages.phases.phase_06_quality_gate import (
    FORBIDDEN_PLACEHOLDERS,
    FORBIDDEN_CLAIMS,
    run_phase_06,
    run_quality_check,
    _scan_hits,
    _check_build_status,
    _check_business_name_match,
)
from pipeline.template_slots import find_unresolved_slots

FIXTURE_DIR = Path.cwd() / "tests" / "fixtures" / "phase_06_quality_gate"


class TestPhase06QualityGate:
    def test_scan_hits_finds_placeholders(self):
        text = "Lorem ipsum dolor sit amet, TODO fix this"
        hits = _scan_hits(text, FORBIDDEN_PLACEHOLDERS)
        assert "Lorem ipsum" in hits
        assert "TODO" in hits

    def test_scan_hits_finds_claims(self):
        text = "We are the best and top-rated #1"
        hits = _scan_hits(text, FORBIDDEN_CLAIMS)
        assert "best in town" not in hits  # different from "best"
        assert "top-rated" in hits
        assert "#1" in hits

    def test_scan_hits_ignores_css_and_html_markup(self):
        text = """
        <html>
          <head>
            <style>
              .hero { color: #17324d; }
            </style>
          </head>
          <body>
            <h1>Test Business</h1>
          </body>
        </html>
        """
        hits = _scan_hits(text, FORBIDDEN_CLAIMS)
        assert "#1" not in hits

    def test_find_unresolved_slots_detects_unique_mustache_placeholders(self):
        html = "<html><h1>{{ business_name }}</h1><p>{{hero_description}}</p><p>{{ business_name }}</p></html>"
        hits = find_unresolved_slots(html)
        assert hits == ["{{ business_name }}", "{{hero_description}}"]

    def test_check_build_status_pass(self):
        ok, reason = _check_build_status({"status": "done"})
        assert ok
        assert reason == ""

    def test_check_build_status_fail(self):
        ok, reason = _check_build_status({"status": "failed"})
        assert not ok
        assert "failed" in reason

    def test_check_business_name_match_pass(self):
        ok, reason = _check_business_name_match("<html>Mama Rose Restaurant</html>", "Mama Rose Restaurant")
        assert ok

    def test_check_business_name_match_fail(self):
        ok, reason = _check_business_name_match("<html>Wrong Name</html>", "Mama Rose Restaurant")
        assert not ok
        assert "not found" in reason

    def test_run_quality_check_valid_site(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_dir = root / "site"
            brief_dir = root / "brief"
            site_dir.mkdir(parents=True, exist_ok=True)
            brief_dir.mkdir(parents=True, exist_ok=True)

            write_json(str(site_dir / "build_status.json"), {"status": "done"})
            (site_dir / "site").mkdir(parents=True, exist_ok=True)
            (site_dir / "site" / "index.html").write_text("<html><h1>Mama Rose Restaurant</h1></html>", encoding="utf-8")
            (site_dir / "screenshot_desktop.png").write_bytes(b"fake_png")
            (site_dir / "screenshot_mobile.png").write_bytes(b"fake_png")

            facts = "# FACTS\n\n- business_name: Mama Rose Restaurant\n- category: Restaurant\n"
            (brief_dir / "FACTS.md").write_text(facts, encoding="utf-8")

            result = run_quality_check(site_dir, brief_dir)
            assert result["status"] == "approved_for_deploy"

    def test_run_quality_check_build_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_dir = root / "site"
            brief_dir = root / "brief"
            site_dir.mkdir(parents=True, exist_ok=True)
            brief_dir.mkdir(parents=True, exist_ok=True)

            facts = "# FACTS\n\n- business_name: Test Business\n"
            (brief_dir / "FACTS.md").write_text(facts, encoding="utf-8")

            write_json(str(site_dir / "build_status.json"), {"status": "failed"})

            result = run_quality_check(site_dir, brief_dir)
            assert result["status"] == "rejected"

    def test_run_quality_check_fake_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_dir = root / "site"
            brief_dir = root / "brief"
            site_dir.mkdir(parents=True, exist_ok=True)
            brief_dir.mkdir(parents=True, exist_ok=True)

            facts = "# FACTS\n\n- business_name: Test Business\n"
            (brief_dir / "FACTS.md").write_text(facts, encoding="utf-8")

            write_json(str(site_dir / "build_status.json"), {"status": "done"})
            (site_dir / "site").mkdir(parents=True, exist_ok=True)
            (site_dir / "site" / "index.html").write_text("<html><p>We are award-winning and #1</p></html>", encoding="utf-8")
            (site_dir / "screenshot_desktop.png").write_bytes(b"fake_png")
            (site_dir / "screenshot_mobile.png").write_bytes(b"fake_png")

            result = run_quality_check(site_dir, brief_dir)
            assert result["status"] == "rejected"

    def test_run_quality_check_business_name_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_dir = root / "site"
            brief_dir = root / "brief"
            site_dir.mkdir(parents=True, exist_ok=True)
            brief_dir.mkdir(parents=True, exist_ok=True)

            facts = "# FACTS\n\n- business_name: Correct Name\n"
            (brief_dir / "FACTS.md").write_text(facts, encoding="utf-8")

            write_json(str(site_dir / "build_status.json"), {"status": "done"})
            (site_dir / "site").mkdir(parents=True, exist_ok=True)
            (site_dir / "site" / "index.html").write_text("<html><h1>Wrong Name</h1></html>", encoding="utf-8")
            (site_dir / "screenshot_desktop.png").write_bytes(b"fake_png")
            (site_dir / "screenshot_mobile.png").write_bytes(b"fake_png")

            result = run_quality_check(site_dir, brief_dir)
            assert result["status"] == "rejected"

    def test_run_quality_check_missing_mobile_screenshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_dir = root / "site"
            brief_dir = root / "brief"
            site_dir.mkdir(parents=True, exist_ok=True)
            brief_dir.mkdir(parents=True, exist_ok=True)

            facts = "# FACTS\n\n- business_name: Test Business\n"
            (brief_dir / "FACTS.md").write_text(facts, encoding="utf-8")

            write_json(str(site_dir / "build_status.json"), {"status": "done"})
            (site_dir / "site").mkdir(parents=True, exist_ok=True)
            (site_dir / "site" / "index.html").write_text("<html><h1>Test Business</h1></html>", encoding="utf-8")
            (site_dir / "screenshot_desktop.png").write_bytes(b"fake_png")

            result = run_quality_check(site_dir, brief_dir)
            assert result["status"] == "needs_edit"

    def test_run_quality_check_placeholder_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_dir = root / "site"
            brief_dir = root / "brief"
            site_dir.mkdir(parents=True, exist_ok=True)
            brief_dir.mkdir(parents=True, exist_ok=True)

            facts = "# FACTS\n\n- business_name: Test Business\n"
            (brief_dir / "FACTS.md").write_text(facts, encoding="utf-8")

            write_json(str(site_dir / "build_status.json"), {"status": "done"})
            (site_dir / "site").mkdir(parents=True, exist_ok=True)
            (site_dir / "site" / "index.html").write_text("<html><p>Lorem ipsum dolor sit</p></html>", encoding="utf-8")
            (site_dir / "screenshot_desktop.png").write_bytes(b"fake_png")
            (site_dir / "screenshot_mobile.png").write_bytes(b"fake_png")

            result = run_quality_check(site_dir, brief_dir)
            assert result["status"] == "rejected"

    def test_run_quality_check_unresolved_template_slots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_dir = root / "site"
            brief_dir = root / "brief"
            site_dir.mkdir(parents=True, exist_ok=True)
            brief_dir.mkdir(parents=True, exist_ok=True)

            facts = "# FACTS\n\n- business_name: Test Business\n"
            (brief_dir / "FACTS.md").write_text(facts, encoding="utf-8")

            write_json(str(site_dir / "build_status.json"), {"status": "done"})
            (site_dir / "site").mkdir(parents=True, exist_ok=True)
            (site_dir / "site" / "index.html").write_text("<html><h1>Test Business</h1><p>{{hero_description}}</p></html>", encoding="utf-8")
            (site_dir / "screenshot_desktop.png").write_bytes(b"fake_png")
            (site_dir / "screenshot_mobile.png").write_bytes(b"fake_png")

            result = run_quality_check(site_dir, brief_dir)
            assert result["status"] == "rejected"
            assert any("Unresolved template slots found" in reason for reason in result.get("rejection_reasons", []))

    def test_run_quality_check_rejects_premium_factual_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_dir = root / "site"
            brief_dir = root / "brief"
            site_dir.mkdir(parents=True, exist_ok=True)
            brief_dir.mkdir(parents=True, exist_ok=True)

            facts = "# FACTS\n\n- business_name: Test Business\n"
            (brief_dir / "FACTS.md").write_text(facts, encoding="utf-8")

            write_json(str(site_dir / "build_status.json"), {"status": "done"})
            (site_dir / "site").mkdir(parents=True, exist_ok=True)
            html = "<html><h1>Test Business</h1><p>5-star premier service, trusted by locals, official partner guarantee.</p></html>"
            (site_dir / "site" / "index.html").write_text(html, encoding="utf-8")
            (site_dir / "screenshot_desktop.png").write_bytes(b"fake_png")
            (site_dir / "screenshot_mobile.png").write_bytes(b"fake_png")

            result = run_quality_check(site_dir, brief_dir)
            assert result["status"] == "rejected"
            assert any("Unsupported factual claims found" in reason for reason in result.get("rejection_reasons", []))

    def test_run_quality_check_rejects_fake_555_01xx_phone_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_dir = root / "site"
            brief_dir = root / "brief"
            site_dir.mkdir(parents=True, exist_ok=True)
            brief_dir.mkdir(parents=True, exist_ok=True)

            facts = "# FACTS\n\n- business_name: Test Business\n"
            (brief_dir / "FACTS.md").write_text(facts, encoding="utf-8")

            write_json(str(site_dir / "build_status.json"), {"status": "done"})
            (site_dir / "site").mkdir(parents=True, exist_ok=True)
            html = '<html><h1>Test Business</h1><a href="tel:4695550123">(469) 555-0123</a></html>'
            (site_dir / "site" / "index.html").write_text(html, encoding="utf-8")
            (site_dir / "screenshot_desktop.png").write_bytes(b"fake_png")
            (site_dir / "screenshot_mobile.png").write_bytes(b"fake_png")

            result = run_quality_check(site_dir, brief_dir)
            assert result["status"] == "rejected"
            assert any("Fake phone numbers found" in reason for reason in result.get("rejection_reasons", []))

    def test_run_quality_check_rejects_generic_verified_contact_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_dir = root / "site"
            brief_dir = root / "brief"
            site_dir.mkdir(parents=True, exist_ok=True)
            brief_dir.mkdir(parents=True, exist_ok=True)

            facts = "# FACTS\n\n- business_name: Test Business\n"
            (brief_dir / "FACTS.md").write_text(facts, encoding="utf-8")

            write_json(str(site_dir / "build_status.json"), {"status": "done"})
            (site_dir / "site").mkdir(parents=True, exist_ok=True)
            html = "<html><h1>Test Business</h1><p>Call our verified phone number or visit our verified address.</p></html>"
            (site_dir / "site" / "index.html").write_text(html, encoding="utf-8")
            (site_dir / "screenshot_desktop.png").write_bytes(b"fake_png")
            (site_dir / "screenshot_mobile.png").write_bytes(b"fake_png")

            result = run_quality_check(site_dir, brief_dir)
            assert result["status"] == "rejected"
            assert any("Generic verified contact placeholders found" in reason for reason in result.get("rejection_reasons", []))

    def test_run_phase_06_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_001"
            run_dir = root / "runs" / run_id

            site_dir = run_dir / "05_sites" / "test-business"
            site_dir.mkdir(parents=True, exist_ok=True)

            brief_dir = run_dir / "04_briefs" / "test-business"
            brief_dir.mkdir(parents=True, exist_ok=True)

            facts = "# FACTS\n\n- business_name: Test Business\n- category: Restaurant\n"
            (brief_dir / "FACTS.md").write_text(facts, encoding="utf-8")

            write_json(str(site_dir / "build_status.json"), {"status": "done"})
            (site_dir / "site").mkdir(parents=True, exist_ok=True)
            (site_dir / "site" / "index.html").write_text("<html><h1>Test Business</h1></html>", encoding="utf-8")
            (site_dir / "screenshot_desktop.png").write_bytes(b"fake_png")
            (site_dir / "screenshot_mobile.png").write_bytes(b"fake_png")

            result = run_phase_06(run_id, str(root))
            assert result["status"] == "done"
            assert result["records_processed"] == 1
            assert result["records_created"] == 1

    def test_run_phase_06_blocked_when_sites_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_phase_06("missing_run", tmp)
            assert result["status"] == "blocked"

    # Wave 1 Regression Tests

    def test_production_deploy_mode_rejects_google_photo(self):
        """Test that production_deploy_mode rejects Google-derived photos.

        Photos hosted on Google's usercontent CDN (lh3.googleusercontent.com)
        are rejected UNLESS the URL is a Stitch-generated asset (aida/aida-public
        path), since those are AI-generated visuals owned by the pipeline.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_dir = root / "site"
            brief_dir = root / "brief"
            site_dir.mkdir(parents=True, exist_ok=True)
            brief_dir.mkdir(parents=True, exist_ok=True)

            facts = "# FACTS\n\n- business_name: Test Business\n"
            (brief_dir / "FACTS.md").write_text(facts, encoding="utf-8")

            write_json(str(site_dir / "build_status.json"), {
                "status": "done",
                "deploy_mode": "production_deploy_mode"
            })
            (site_dir / "site").mkdir(parents=True, exist_ok=True)
            html_with_google_photo = '<html><body><h1>Test Business</h1><img src="https://lh3.googleusercontent.com/photo123"></body></html>'
            (site_dir / "site" / "index.html").write_text(html_with_google_photo, encoding="utf-8")
            (site_dir / "screenshot_desktop.png").write_bytes(b"fake_png")
            (site_dir / "screenshot_mobile.png").write_bytes(b"fake_png")

            result = run_quality_check(site_dir, brief_dir)
            assert result["status"] == "rejected"
            assert any(
                "Google Maps photo" in reason or "Google-derived photo" in reason
                for reason in result.get("rejection_reasons", [])
            )

    def test_production_deploy_mode_allows_stitch_aida_assets(self):
        """lh3.googleusercontent.com/aida-public/... URLs are Stitch-generated
        assets and must NOT trigger the Google Maps photo rejection."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_dir = root / "site"
            brief_dir = root / "brief"
            site_dir.mkdir(parents=True, exist_ok=True)
            brief_dir.mkdir(parents=True, exist_ok=True)

            facts = "# FACTS\n\n- business_name: Test Business\n"
            (brief_dir / "FACTS.md").write_text(facts, encoding="utf-8")

            write_json(str(site_dir / "build_status.json"), {
                "status": "done",
                "deploy_mode": "production_deploy_mode"
            })
            (site_dir / "site").mkdir(parents=True, exist_ok=True)
            html_with_stitch_assets = (
                '<html><body><h1>Test Business</h1>'
                '<img src="https://lh3.googleusercontent.com/aida-public/AB6AXuCabc123">'
                '<img src="https://lh3.googleusercontent.com/aida/AB6AXuCdef456">'
                '</body></html>'
            )
            (site_dir / "site" / "index.html").write_text(html_with_stitch_assets, encoding="utf-8")
            (site_dir / "screenshot_desktop.png").write_bytes(b"fake_png")
            (site_dir / "screenshot_mobile.png").write_bytes(b"fake_png")

            result = run_quality_check(site_dir, brief_dir)
            assert not any(
                "Google Maps photo" in reason or "Google-derived photo" in reason
                for reason in result.get("rejection_reasons", [])
            ), f"Stitch aida assets were rejected: {result.get('rejection_reasons')}"

    def test_preview_demo_mode_allows_google_photo(self):
        """Test that preview_demo_mode allows Google-derived photos."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_dir = root / "site"
            brief_dir = root / "brief"
            site_dir.mkdir(parents=True, exist_ok=True)
            brief_dir.mkdir(parents=True, exist_ok=True)

            facts = "# FACTS\n\n- business_name: Test Business\n"
            (brief_dir / "FACTS.md").write_text(facts, encoding="utf-8")

            write_json(str(site_dir / "build_status.json"), {
                "status": "done",
                "deploy_mode": "preview_demo_mode"
            })
            (site_dir / "site").mkdir(parents=True, exist_ok=True)
            html_with_google_photo = '<html><body><h1>Test Business</h1><img src="https://lh3.googleusercontent.com/photo123"></body></html>'
            (site_dir / "site" / "index.html").write_text(html_with_google_photo, encoding="utf-8")
            (site_dir / "screenshot_desktop.png").write_bytes(b"fake_png")
            (site_dir / "screenshot_mobile.png").write_bytes(b"fake_png")

            result = run_quality_check(site_dir, brief_dir)
            assert result["status"] == "approved_for_deploy"

    def test_generic_copy_blocks_over_three_rejected(self):
        """Test that more than 3 generic copy blocks triggers rejection."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_dir = root / "site"
            brief_dir = root / "brief"
            site_dir.mkdir(parents=True, exist_ok=True)
            brief_dir.mkdir(parents=True, exist_ok=True)

            facts = "# FACTS\n\n- business_name: Test Business\n"
            (brief_dir / "FACTS.md").write_text(facts, encoding="utf-8")

            write_json(str(site_dir / "build_status.json"), {"status": "done"})
            (site_dir / "site").mkdir(parents=True, exist_ok=True)
            (site_dir / "site" / "index.html").write_text("<html><h1>Test Business</h1></html>", encoding="utf-8")
            (site_dir / "screenshot_desktop.png").write_bytes(b"fake_png")
            (site_dir / "screenshot_mobile.png").write_bytes(b"fake_png")

            # Create fact_usage_report.json with 4 generic copy blocks
            fact_usage = {
                "generic_copy_blocks": [
                    {"site_location": "services.item1", "text": "Generic service 1"},
                    {"site_location": "services.item2", "text": "Generic service 2"},
                    {"site_location": "about.paragraph", "text": "Generic about"},
                    {"site_location": "footer.text", "text": "Generic footer"}
                ]
            }
            write_json(str(site_dir / "fact_usage_report.json"), fact_usage)

            result = run_quality_check(site_dir, brief_dir)
            assert result["status"] == "rejected"
            assert any("Too many fallback/generic slots" in reason for reason in result.get("rejection_reasons", []))

    def test_core_fallback_over_one_needs_edit(self):
        """Test that more than 1 core fallback slot triggers needs_edit."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_dir = root / "site"
            brief_dir = root / "brief"
            site_dir.mkdir(parents=True, exist_ok=True)
            brief_dir.mkdir(parents=True, exist_ok=True)

            facts = "# FACTS\n\n- business_name: Test Business\n"
            (brief_dir / "FACTS.md").write_text(facts, encoding="utf-8")

            write_json(str(site_dir / "build_status.json"), {"status": "done"})
            (site_dir / "site").mkdir(parents=True, exist_ok=True)
            (site_dir / "site" / "index.html").write_text("<html><h1>Test Business</h1></html>", encoding="utf-8")
            (site_dir / "screenshot_desktop.png").write_bytes(b"fake_png")
            (site_dir / "screenshot_mobile.png").write_bytes(b"fake_png")

            # Create fact_usage_report.json with 2 core fallback entries
            fact_usage = {
                "generic_copy_blocks": [
                    {"site_location": "hero.heading", "text": "Welcome to our business"},
                    {"site_location": "trust", "text": "Trusted by many"}
                ]
            }
            write_json(str(site_dir / "fact_usage_report.json"), fact_usage)

            result = run_quality_check(site_dir, brief_dir)
            assert result["status"] == "needs_edit"
            assert any("core fallback" in reason for reason in result.get("needs_edit_reasons", []))

    def test_review_summary_without_attribution_needs_edit(self):
        """Test that review summary without attribution triggers needs_edit."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_dir = root / "site"
            brief_dir = root / "brief"
            site_dir.mkdir(parents=True, exist_ok=True)
            brief_dir.mkdir(parents=True, exist_ok=True)

            facts = "# FACTS\n\n- business_name: Test Business\n"
            (brief_dir / "FACTS.md").write_text(facts, encoding="utf-8")

            write_json(str(site_dir / "build_status.json"), {"status": "done"})
            (site_dir / "site").mkdir(parents=True, exist_ok=True)
            (site_dir / "site" / "index.html").write_text("<html><h1>Test Business</h1></html>", encoding="utf-8")
            (site_dir / "screenshot_desktop.png").write_bytes(b"fake_png")
            (site_dir / "screenshot_mobile.png").write_bytes(b"fake_png")

            # Create fact_usage_report.json with review summary without attribution
            fact_usage = {
                "review_summary": [
                    {"text": "Great service", "attribution_visible": False}
                ]
            }
            write_json(str(site_dir / "fact_usage_report.json"), fact_usage)

            result = run_quality_check(site_dir, brief_dir)
            assert result["status"] == "needs_edit"
            assert any("attribution" in reason.lower() for reason in result.get("needs_edit_reasons", []))

    def test_unverified_trust_chip_needs_edit(self):
        """Test that unverified trust chip triggers needs_edit."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_dir = root / "site"
            brief_dir = root / "brief"
            site_dir.mkdir(parents=True, exist_ok=True)
            brief_dir.mkdir(parents=True, exist_ok=True)

            facts = "# FACTS\n\n- business_name: Test Business\n"
            (brief_dir / "FACTS.md").write_text(facts, encoding="utf-8")

            write_json(str(site_dir / "build_status.json"), {"status": "done"})
            (site_dir / "site").mkdir(parents=True, exist_ok=True)
            (site_dir / "site" / "index.html").write_text("<html><h1>Test Business</h1></html>", encoding="utf-8")
            (site_dir / "screenshot_desktop.png").write_bytes(b"fake_png")
            (site_dir / "screenshot_mobile.png").write_bytes(b"fake_png")

            # Create fact_usage_report.json with unverified trust chip
            fact_usage = {
                "trust_chips": [
                    {"label": "Wheelchair Accessible", "source_type": "unverified_attribute"}
                ]
            }
            write_json(str(site_dir / "fact_usage_report.json"), fact_usage)

            result = run_quality_check(site_dir, brief_dir)
            assert result["status"] == "needs_edit"
            assert any("unverified" in reason.lower() for reason in result.get("needs_edit_reasons", []))

    def test_accent_override_rejected_needs_edit(self):
        """Test that accent override rejection triggers needs_edit."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_dir = root / "site"
            brief_dir = root / "brief"
            site_dir.mkdir(parents=True, exist_ok=True)
            brief_dir.mkdir(parents=True, exist_ok=True)

            facts = "# FACTS\n\n- business_name: Test Business\n"
            (brief_dir / "FACTS.md").write_text(facts, encoding="utf-8")

            write_json(str(site_dir / "build_status.json"), {"status": "done"})
            (site_dir / "site").mkdir(parents=True, exist_ok=True)
            (site_dir / "site" / "index.html").write_text("<html><h1>Test Business</h1></html>", encoding="utf-8")
            (site_dir / "screenshot_desktop.png").write_bytes(b"fake_png")
            (site_dir / "screenshot_mobile.png").write_bytes(b"fake_png")

            # Create fact_usage_report.json with accent override rejection
            fact_usage = {
                "design_metadata": {
                    "accent_override_rejected_reason": "contrast ratio 2.8:1 below 4.5:1"
                }
            }
            write_json(str(site_dir / "fact_usage_report.json"), fact_usage)

            result = run_quality_check(site_dir, brief_dir)
            assert result["status"] == "needs_edit"
            assert any("contrast" in reason.lower() for reason in result.get("needs_edit_reasons", []))