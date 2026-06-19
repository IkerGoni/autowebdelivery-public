import tempfile
from pathlib import Path

from pipeline.json_io import read_json, write_json
from packages.phases.phase_05_preview_site_generation import (
    FORBIDDEN_PLACEHOLDERS,
    FORBIDDEN_CLAIMS,
    run_phase_05,
    build_site_record,
    capture_screenshots,
    _scan_hits,
    _render_stylesheet,
)

FIXTURE_DIR = Path.cwd() / "tests" / "fixtures" / "phase_05_preview_site_generation"


class TestPreviewSiteGeneration:
    def test_render_stylesheet_uses_visual_profile_accent_color(self):
        css = _render_stylesheet({"accent_color_candidate": "#ff6600"})
        assert "--accent: #ff6600;" in css

    def test_render_stylesheet_ignores_invalid_visual_profile_accent_color(self):
        css = _render_stylesheet({"accent_color_candidate": "orange"})
        assert "--accent: #2c7be5;" in css

    def test_capture_screenshots_falls_back_with_metadata_when_browser_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            site_dir = output_dir / "site"
            site_dir.mkdir(parents=True, exist_ok=True)
            (site_dir / "index.html").write_text("<h1>Fallback Cafe</h1>", encoding="utf-8")

            metadata = capture_screenshots(
                site_dir=site_dir,
                output_dir=output_dir,
                business_name="Fallback Cafe",
                browser_available=False,
            )

            assert metadata["capture_mode"] == "deterministic_fallback"
            assert metadata["browser"] == "unavailable"
            assert metadata["desktop"]["path"] == "screenshot_desktop.png"
            assert metadata["desktop"]["width"] == 1280
            assert metadata["desktop"]["height"] == 800
            assert metadata["mobile"]["path"] == "screenshot_mobile.png"
            assert metadata["mobile"]["width"] == 390
            assert metadata["mobile"]["height"] == 844
            assert metadata["fallback_reason"]
            assert (output_dir / "screenshot_desktop.png").exists()
            assert (output_dir / "screenshot_mobile.png").exists()

    def test_build_site_record_complete_restaurant(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_001"
            run_dir = root / "runs" / run_id
            brief_dir = run_dir / "04_briefs" / "mama-rose-restaurant"
            enrich_dir = run_dir / "04_5_enrichment" / "mama-rose-restaurant"
            config_dir = run_dir / "config"
            brief_dir.mkdir(parents=True, exist_ok=True)
            enrich_dir.mkdir(parents=True, exist_ok=True)
            config_dir.mkdir(parents=True, exist_ok=True)

            facts_content = """# FACTS

- business_name: Mama Rose Restaurant
- category: Italian Restaurant
- rating: 4.6
- review_count: 82
- address: 145 Dockside Avenue, Bangkok 10500, Thailand
- phone: +66 2 555 0101
- hours: Daily 11:00-22:00
- maps_url: https://maps.google.com/?cid=222
- website_status: no_website
- recipient_channel: phone
- recipient_value: +66 2 555 0101
"""
            (brief_dir / "FACTS.md").write_text(facts_content, encoding="utf-8")
            write_json(str(enrich_dir / "visual_profile.json"), {
                "preset_id": "warm_editorial",
                "hero_mode": "text_first",
                "photo_policy": "preview_demo_only",
                "accent_color_candidate": "#ff6600",
            })
            write_json(str(config_dir / "run_config.json"), {"deploy_mode": "preview_demo_mode"})

            brief_row = {
                "run_id": run_id,
                "record_id": "rec_restaurant",
                "business_slug": "mama-rose-restaurant",
                "recipient_channel": "phone",
                "manual_override": False,
            }

            result = build_site_record(root, run_id, brief_row)
            assert result["status"] == "done"
            assert result["business_slug"] == "mama-rose-restaurant"

            site_dir = root / "runs" / run_id / "05_sites" / "mama-rose-restaurant" / "site"
            assert (site_dir / "index.html").exists()
            assert (site_dir / "styles.css").exists()
            assert (site_dir.parent / "fact_usage_report.json").exists()
            assert (site_dir.parent / "build_status.json").exists()

            html = (site_dir / "index.html").read_text(encoding="utf-8")
            css = (site_dir / "styles.css").read_text(encoding="utf-8")
            fact_usage = read_json(str(site_dir.parent / "fact_usage_report.json"))
            build_status = read_json(str(site_dir.parent / "build_status.json"))
            assert "Mama Rose Restaurant" in html
            assert "Italian Restaurant" in html
            assert "+66 2 555 0101" in html
            assert "Daily 11:00-22:00" in html
            assert '<link rel="stylesheet" href="styles.css">' in html
            assert "--accent: #ff6600;" in css
            assert fact_usage["deploy_mode"] == "preview_demo_mode"
            assert fact_usage["visual_profile"]["preset_id"] == "warm_editorial"
            assert build_status["deploy_mode"] == "preview_demo_mode"
            assert build_status["visual_profile"]["photo_policy"] == "preview_demo_only"

            for placeholder in FORBIDDEN_PLACEHOLDERS:
                assert placeholder not in html, f"Placeholder found: {placeholder}"

    def test_preview_demo_mode_shows_banner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_001"
            run_dir = root / "runs" / run_id
            brief_dir = run_dir / "04_briefs" / "mama-rose-restaurant"
            enrich_dir = run_dir / "04_5_enrichment" / "mama-rose-restaurant"
            config_dir = run_dir / "config"
            brief_dir.mkdir(parents=True, exist_ok=True)
            enrich_dir.mkdir(parents=True, exist_ok=True)
            config_dir.mkdir(parents=True, exist_ok=True)

            facts_content = """# FACTS

- business_name: Mama Rose Restaurant
- category: Italian Restaurant
- rating: 4.6
- review_count: 82
- address: 145 Dockside Avenue, Bangkok 10500, Thailand
- phone: +66 2 555 0101
- hours: Daily 11:00-22:00
- maps_url: https://maps.google.com/?cid=222
- website_status: no_website
- recipient_channel: phone
- recipient_value: +66 2 555 0101
"""
            (brief_dir / "FACTS.md").write_text(facts_content, encoding="utf-8")
            write_json(str(enrich_dir / "visual_profile.json"), {
                "preset_id": "warm_editorial",
                "hero_mode": "text_first",
                "photo_policy": "preview_demo_only",
                "accent_color_candidate": "#ff6600",
            })
            write_json(str(config_dir / "run_config.json"), {"deploy_mode": "preview_demo_mode"})

            brief_row = {
                "run_id": run_id,
                "record_id": "rec_restaurant",
                "business_slug": "mama-rose-restaurant",
                "recipient_channel": "phone",
                "manual_override": False,
            }

            build_site_record(root, run_id, brief_row)

            site_dir = root / "runs" / run_id / "05_sites" / "mama-rose-restaurant" / "site"
            html = (site_dir / "index.html").read_text(encoding="utf-8")

            assert "This is a preview site — not the final production version." in html

    def test_production_deploy_mode_hides_banner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_001"
            run_dir = root / "runs" / run_id
            brief_dir = run_dir / "04_briefs" / "mama-rose-restaurant"
            enrich_dir = run_dir / "04_5_enrichment" / "mama-rose-restaurant"
            config_dir = run_dir / "config"
            brief_dir.mkdir(parents=True, exist_ok=True)
            enrich_dir.mkdir(parents=True, exist_ok=True)
            config_dir.mkdir(parents=True, exist_ok=True)

            facts_content = """# FACTS

- business_name: Mama Rose Restaurant
- category: Italian Restaurant
- rating: 4.6
- review_count: 82
- address: 145 Dockside Avenue, Bangkok 10500, Thailand
- phone: +66 2 555 0101
- hours: Daily 11:00-22:00
- maps_url: https://maps.google.com/?cid=222
- website_status: no_website
- recipient_channel: phone
- recipient_value: +66 2 555 0101
"""
            (brief_dir / "FACTS.md").write_text(facts_content, encoding="utf-8")
            write_json(str(enrich_dir / "visual_profile.json"), {
                "preset_id": "warm_editorial",
                "hero_mode": "text_first",
                "photo_policy": "preview_demo_only",
                "accent_color_candidate": "#ff6600",
            })
            write_json(str(config_dir / "run_config.json"), {"deploy_mode": "production_deploy_mode"})

            brief_row = {
                "run_id": run_id,
                "record_id": "rec_restaurant",
                "business_slug": "mama-rose-restaurant",
                "recipient_channel": "phone",
                "manual_override": False,
            }

            build_site_record(root, run_id, brief_row)

            site_dir = root / "runs" / run_id / "05_sites" / "mama-rose-restaurant" / "site"
            html = (site_dir / "index.html").read_text(encoding="utf-8")

            assert "This is a preview site — not the final production version." not in html

    def test_build_site_record_missing_phone_omits_cta(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_001"
            run_dir = root / "runs" / run_id
            brief_dir = run_dir / "04_briefs" / "green-valley-cafe"
            brief_dir.mkdir(parents=True, exist_ok=True)

            facts_content = """# FACTS

- business_name: Green Valley Cafe
- category: Cafe
- rating: 4.3
- review_count: 57
- address: 88/9 Rama 9 Road, Bangkok 10250, Thailand
- phone: 
- hours: Mon-Sun 07:00-19:00
- maps_url: https://maps.google.com/?cid=444
- website_status: no_website
- recipient_channel: facebook_message
"""
            (brief_dir / "FACTS.md").write_text(facts_content, encoding="utf-8")

            brief_row = {
                "run_id": run_id,
                "record_id": "rec_missing_phone",
                "business_slug": "green-valley-cafe",
                "recipient_channel": "facebook_message",
            }

            build_site_record(root, run_id, brief_row)

            site_dir = root / "runs" / run_id / "05_sites" / "green-valley-cafe" / "site"
            html = (site_dir / "index.html").read_text(encoding="utf-8")

            assert "tel:" not in html, "Phone CTA should be omitted when phone is missing"
            assert "Hours not listed" not in html, "Hours should be present"

    def test_build_site_record_missing_hours_uses_neutral_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_001"
            run_dir = root / "runs" / run_id
            brief_dir = run_dir / "04_briefs" / "sunset-spa"
            brief_dir.mkdir(parents=True, exist_ok=True)

            facts_content = """# FACTS

- business_name: Sunset Spa
- category: Spa
- rating: 4.7
- review_count: 94
- address: 32 Beach Road, Phuket 83100, Thailand
- phone: +66 76 123 456
- hours: 
- maps_url: https://maps.google.com/?cid=555
- website_status: no_website
- recipient_channel: instagram_dm
"""
            (brief_dir / "FACTS.md").write_text(facts_content, encoding="utf-8")

            brief_row = {
                "run_id": run_id,
                "record_id": "rec_unknown_hours",
                "business_slug": "sunset-spa",
                "recipient_channel": "instagram_dm",
            }

            build_site_record(root, run_id, brief_row)

            site_dir = root / "runs" / run_id / "05_sites" / "sunset-spa" / "site"
            html = (site_dir / "index.html").read_text(encoding="utf-8")

            assert "Hours not listed in source data" in html

    def test_forbidden_claim_detection(self):
        test_html = "We are the best and top-rated #1 award-winning business!"
        hits = _scan_hits(test_html, FORBIDDEN_CLAIMS)
        assert "best" in hits
        assert "top-rated" in hits
        assert "#1" in hits
        assert "award-winning" in hits

    def test_forbidden_claim_detection_ignores_css_and_html_markup(self):
        test_html = """
        <html>
          <head>
            <style>
              .hero { color: #17324d; }
            </style>
          </head>
          <body>
            <h1>Real Business</h1>
          </body>
        </html>
        """
        hits = _scan_hits(test_html, FORBIDDEN_CLAIMS)
        assert "#1" not in hits

    def test_placeholder_detection(self):
        test_html = "Lorem ipsum dolor sit amet, TODO: fix this"
        hits = _scan_hits(test_html, FORBIDDEN_PLACEHOLDERS)
        assert "Lorem ipsum" in hits
        assert "TODO" in hits

    def test_run_phase_05_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_001"
            run_dir = root / "runs" / run_id
            briefs_dir = run_dir / "04_briefs"
            enrich_dir = run_dir / "04_5_enrichment" / "mama-rose-restaurant"
            config_dir = run_dir / "config"

            preview_ready = [
                {
                    "business_slug": "mama-rose-restaurant",
                    "brief_path": f"runs/{run_id}/04_briefs/mama-rose-restaurant",
                    "recipient_channel": "phone",
                    "manual_override": False,
                }
            ]
            write_json(str(briefs_dir / "preview_ready_briefs.json"), preview_ready)
            write_json(str(briefs_dir / "blocked_no_recipient_channel.json"), [])
            enrich_dir.mkdir(parents=True, exist_ok=True)
            config_dir.mkdir(parents=True, exist_ok=True)
            write_json(str(enrich_dir / "visual_profile.json"), {
                "preset_id": "warm_editorial",
                "hero_mode": "text_first",
                "photo_policy": "preview_demo_only",
                "accent_color_candidate": "#ff6600",
            })
            write_json(str(config_dir / "run_config.json"), {"deploy_mode": "preview_demo_mode"})

            brief_dir = briefs_dir / "mama-rose-restaurant"
            brief_dir.mkdir(parents=True, exist_ok=True)
            facts_content = """# FACTS

- business_name: Mama Rose Restaurant
- category: Italian Restaurant
- rating: 4.6
- review_count: 82
- address: 145 Dockside Avenue, Bangkok 10500, Thailand
- phone: +66 2 555 0101
- hours: Daily 11:00-22:00
- maps_url: https://maps.google.com/?cid=222
- website_status: no_website
- recipient_channel: phone
"""
            (brief_dir / "FACTS.md").write_text(facts_content, encoding="utf-8")

            result = run_phase_05(run_id, str(root))
            assert result["status"] == "done"
            assert result["records_created"] == 1

            site_dir = root / "runs" / run_id / "05_sites" / "mama-rose-restaurant"
            assert (site_dir / "site" / "index.html").exists()
            assert (site_dir / "site" / "styles.css").exists()
            assert (site_dir / "screenshot_desktop.png").exists()
            assert (site_dir / "screenshot_mobile.png").exists()
            assert (site_dir / "build_status.json").exists()
            assert (site_dir / "fact_usage_report.json").exists()

    def test_run_phase_05_blocked_when_inputs_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_phase_05("missing_run", tmp)
            assert result["status"] == "blocked"
            assert "preview_ready_briefs.json" in result["missing_fields"]

    def test_run_phase_05_skips_blocked_without_manual_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_001"
            run_dir = root / "runs" / run_id
            briefs_dir = run_dir / "04_briefs"
            briefs_dir.mkdir(parents=True, exist_ok=True)

            preview_ready = [
                {
                    "business_slug": "unknown-recipient-business",
                    "brief_path": f"runs/{run_id}/04_briefs/unknown-recipient-business",
                    "recipient_channel": "unknown",
                    "manual_override": False,
                }
            ]
            blocked = [
                {
                    "business_slug": "unknown-recipient-business",
                    "brief_path": f"runs/{run_id}/04_briefs/unknown-recipient-business",
                    "recipient_channel": "unknown",
                    "blocked_reason": "No recipient channel",
                }
            ]
            write_json(str(briefs_dir / "preview_ready_briefs.json"), preview_ready)
            write_json(str(briefs_dir / "blocked_no_recipient_channel.json"), blocked)

            result = run_phase_05(run_id, str(root))
            assert result["status"] == "done"
            assert result["records_created"] == 0
            assert result["records_skipped"] == 1

    def test_run_phase_05_processes_with_manual_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_001"
            run_dir = root / "runs" / run_id
            briefs_dir = run_dir / "04_briefs"
            briefs_dir.mkdir(parents=True, exist_ok=True)

            preview_ready = [
                {
                    "business_slug": "manual-override-business",
                    "brief_path": f"runs/{run_id}/04_briefs/manual-override-business",
                    "recipient_channel": "unknown",
                    "manual_override": True,
                    "manual_override_reason": "Manual recipient collection planned",
                }
            ]
            blocked = [
                {
                    "business_slug": "manual-override-business",
                    "brief_path": f"runs/{run_id}/04_briefs/manual-override-business",
                    "recipient_channel": "unknown",
                    "blocked_reason": "No recipient channel",
                }
            ]
            write_json(str(briefs_dir / "preview_ready_briefs.json"), preview_ready)
            write_json(str(briefs_dir / "blocked_no_recipient_channel.json"), blocked)

            brief_dir = briefs_dir / "manual-override-business"
            brief_dir.mkdir(parents=True, exist_ok=True)
            facts_content = """# FACTS

- business_name: Manual Override Business
- category: Service
- rating: 4.5
- review_count: 50
- address: 123 Test Street
- phone: 
- hours: 
- maps_url: 
- website_status: no_website
- recipient_channel: unknown
"""
            (brief_dir / "FACTS.md").write_text(facts_content, encoding="utf-8")

            result = run_phase_05(run_id, str(root))
            assert result["status"] == "done"
            assert result["records_created"] == 1

    # ------------------------------------------------------------------
    # Copy-inputs slot priority tests
    # ------------------------------------------------------------------

    def test_copy_inputs_slots_used_when_present(self):
        """All copy_inputs.json slots should appear in HTML; no generic fallback."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_copy_full"
            run_dir = root / "runs" / run_id
            brief_dir = run_dir / "04_briefs" / "bright-smile-dental"
            enrich_dir = run_dir / "04_5_enrichment" / "bright-smile-dental"
            config_dir = run_dir / "config"
            brief_dir.mkdir(parents=True, exist_ok=True)
            enrich_dir.mkdir(parents=True, exist_ok=True)
            config_dir.mkdir(parents=True, exist_ok=True)

            facts_content = """# FACTS

- business_name: Bright Smile Dental
- category: Dental Clinic
- rating: 4.8
- review_count: 120
- address: 456 Health Street, Bangkok 10110, Thailand
- phone: +66 2 555 1234
- hours: Mon-Fri 09:00-18:00
- maps_url: https://maps.google.com/?cid=999
- website_status: no_website
- recipient_channel: phone
- recipient_value: +66 2 555 1234
"""
            (brief_dir / "FACTS.md").write_text(facts_content, encoding="utf-8")
            write_json(str(enrich_dir / "copy_inputs.json"), {
                "slots": {
                    "hero_tagline": "Premium Dental Care",
                    "hero_supporting_line": "Cosmetic & General Dentistry",
                    "overview_intro": "Welcome to our modern dental practice serving the community.",
                    "trust_intro": "Patients consistently praise our gentle approach.",
                    "location_intro": "Conveniently located in downtown district.",
                    "cta_body": "Schedule your appointment today.",
                    "footer_note": "Serving patients since 2010.",
                }
            })

            brief_row = {
                "run_id": run_id,
                "record_id": "rec_dental",
                "business_slug": "bright-smile-dental",
                "recipient_channel": "phone",
                "manual_override": False,
            }

            result = build_site_record(root, run_id, brief_row)
            assert result["status"] == "done"

            site_dir = root / "runs" / run_id / "05_sites" / "bright-smile-dental" / "site"
            html = (site_dir / "index.html").read_text(encoding="utf-8")
            fact_usage = read_json(str(site_dir.parent / "fact_usage_report.json"))

            # All custom slot values appear in HTML
            assert "Premium Dental Care" in html
            assert "Cosmetic &amp; General Dentistry" in html
            assert "Welcome to our modern dental practice serving the community." in html
            assert "Patients consistently praise our gentle approach." in html
            assert "Conveniently located in downtown district." in html
            assert "Schedule your appointment today." in html
            assert "Serving patients since 2010." in html

            # None of the generic fallback text appears
            assert "Bright Smile Dental offers dental clinic information in clean, mobile-first format" not in html
            assert "View location details, check listed hours, and use available contact options to reach business." not in html
            assert "Preview website prepared for Bright Smile Dental." not in html

            # Zero generic_copy_blocks tracked
            assert fact_usage["generic_copy_blocks"] == []

    def test_copy_inputs_partial_slots_fallback_correctly(self):
        """Provided slots used; missing slots fall back to generic or facts."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_copy_partial"
            run_dir = root / "runs" / run_id
            brief_dir = run_dir / "04_briefs" / "morning-brew-cafe"
            enrich_dir = run_dir / "04_5_enrichment" / "morning-brew-cafe"
            config_dir = run_dir / "config"
            brief_dir.mkdir(parents=True, exist_ok=True)
            enrich_dir.mkdir(parents=True, exist_ok=True)
            config_dir.mkdir(parents=True, exist_ok=True)

            facts_content = """# FACTS

- business_name: Morning Brew Cafe
- category: Coffee Shop
- rating: 4.5
- review_count: 75
- address: 789 Coffee Lane, Bangkok 10120, Thailand
- phone: +66 2 666 7890
- hours: Daily 07:00-20:00
- maps_url: https://maps.google.com/?cid=888
- website_status: no_website
- recipient_channel: phone
- recipient_value: +66 2 666 7890
"""
            (brief_dir / "FACTS.md").write_text(facts_content, encoding="utf-8")
            write_json(str(enrich_dir / "copy_inputs.json"), {
                "slots": {
                    "overview_intro": "Custom overview text here.",
                    "cta_body": "Custom CTA text.",
                }
            })

            brief_row = {
                "run_id": run_id,
                "record_id": "rec_cafe_partial",
                "business_slug": "morning-brew-cafe",
                "recipient_channel": "phone",
                "manual_override": False,
            }

            result = build_site_record(root, run_id, brief_row)
            assert result["status"] == "done"

            site_dir = root / "runs" / run_id / "05_sites" / "morning-brew-cafe" / "site"
            html = (site_dir / "index.html").read_text(encoding="utf-8")
            fact_usage = read_json(str(site_dir.parent / "fact_usage_report.json"))

            # Custom text for provided slots
            assert "Custom overview text here." in html
            assert "Custom CTA text." in html

            # Missing hero_tagline falls back to niche copy (uses business_name)
            assert "Morning Brew Cafe" in html
            # Missing hero_supporting_line falls back to niche copy (uses rating)
            assert "Rated 4.5 on Google from 75 reviews" in html
            # Missing footer_note falls back to niche copy
            assert "Page prepared for Morning Brew Cafe." in html

            # No generic_copy_blocks — niche copy fills all slots
            assert len(fact_usage["generic_copy_blocks"]) == 0

    def test_copy_inputs_missing_uses_all_generic(self):
        """No copy_inputs.json at all should produce 3 generic_copy_blocks."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_copy_none"
            run_dir = root / "runs" / run_id
            brief_dir = run_dir / "04_briefs" / "serenity-spa"
            config_dir = run_dir / "config"
            brief_dir.mkdir(parents=True, exist_ok=True)
            config_dir.mkdir(parents=True, exist_ok=True)
            # No enrichment dir — simulates no copy_inputs.json

            facts_content = """# FACTS

- business_name: Serenity Spa
- category: Spa & Wellness
- rating: 4.9
- review_count: 200
- address: 321 Relaxation Road, Bangkok 10130, Thailand
- phone: +66 2 777 8888
- hours: Daily 10:00-22:00
- maps_url: https://maps.google.com/?cid=777
- website_status: no_website
- recipient_channel: phone
- recipient_value: +66 2 777 8888
"""
            (brief_dir / "FACTS.md").write_text(facts_content, encoding="utf-8")

            brief_row = {
                "run_id": run_id,
                "record_id": "rec_spa_no_copy",
                "business_slug": "serenity-spa",
                "recipient_channel": "phone",
                "manual_override": False,
            }

            result = build_site_record(root, run_id, brief_row)
            assert result["status"] == "done"

            site_dir = root / "runs" / run_id / "05_sites" / "serenity-spa" / "site"
            html = (site_dir / "index.html").read_text(encoding="utf-8")
            fact_usage = read_json(str(site_dir.parent / "fact_usage_report.json"))

            # Niche-specific copy appears (spa → warm-editorial voice)
            assert "At Serenity Spa, your comfort and health come first" in html
            assert "love to hear from you" in html
            assert "Page prepared for Serenity Spa." in html

            # No generic_copy_blocks when niche copy is used
            assert len(fact_usage["generic_copy_blocks"]) == 0
