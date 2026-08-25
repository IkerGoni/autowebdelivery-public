import tempfile
from pathlib import Path

from packages.phases.phase_08_outreach_generation import (
    BLOCKED_REASON,
    build_outreach_draft,
    run_phase_08,
)
from pipeline.json_io import read_json, write_json


class TestPhase08OutreachGeneration:
    def test_build_outreach_draft_email_ready_for_review(self):
        facts = {
            "business_name": "Test Business",
            "category": "Dentist",
            "rating": "4.8",
            "review_count": "120",
        }
        recipient = {
            "recipient_channel": "email",
            "recipient_value": "test@example.com",
        }

        draft = build_outreach_draft(
            "fixture_001",
            "test-business",
            facts,
            recipient,
            "https://test-business.example.com",
            "$299 setup",
            "Hi {business_name}\n{preview_url}\n{price_offer}\n{personalization_reason}",
            "DM {business_name} {preview_url} {price_offer} {personalization_reason}",
        )

        assert draft["draft_status"] == "ready_for_review"
        assert draft["subject"] == "Quick website preview for Test Business"
        assert "https://test-business.example.com" in draft["body"]
        assert "$299 setup" in draft["body"]
        assert "family-owned" not in draft["body"]

    def test_build_outreach_draft_blocked_unknown_without_override(self):
        facts = {"business_name": "Blocked Business"}
        recipient = {
            "recipient_channel": "unknown",
            "recipient_value": "",
            "manual_override": False,
        }

        draft = build_outreach_draft(
            "fixture_001",
            "blocked-business",
            facts,
            recipient,
            "https://blocked-business.example.com",
            "$299 setup",
            "email {business_name}",
            "dm {business_name}",
        )

        assert draft["draft_status"] == "blocked"
        assert draft["blocked_reason"] == BLOCKED_REASON

    def test_build_outreach_draft_blocked_missing_preview_url(self):
        facts = {"business_name": "No Preview Business"}
        recipient = {
            "recipient_channel": "facebook_message",
            "recipient_value": "facebook.com",
        }

        draft = build_outreach_draft(
            "fixture_001",
            "no-preview-business",
            facts,
            recipient,
            "",
            "$299 setup",
            "email {business_name}",
            "dm {business_name}",
        )

        assert draft["draft_status"] == "blocked"
        assert draft["blocked_reason"] == "preview_url missing"

    def test_run_phase_08_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_001"
            run_dir = root / "runs" / run_id

            (run_dir / "config").mkdir(parents=True, exist_ok=True)
            write_json(str(run_dir / "config" / "input_config.json"), {
                "price_offer": "$299 setup",
            })

            brief_dir = run_dir / "04_briefs" / "test-business"
            brief_dir.mkdir(parents=True, exist_ok=True)
            (brief_dir / "FACTS.md").write_text(
                "# FACTS\n\n"
                "- business_name: Test Business\n"
                "- category: Dentist\n"
                "- rating: 4.8\n"
                "- review_count: 120\n"
                "- niche: dentist\n"
                "- area: Madrid\n"
                "- country: Spain\n"
                "- template_family: clinical_trust\n"
                "- template_variant: single_page_preview\n"
                "- stitch_project_id: stitch_123\n"
                "- offer_type: setup_only\n"
                "- offer_price: 299\n"
                "- currency: EUR\n"
                "- pricing_market: Madrid, Spain\n",
                encoding="utf-8",
            )
            write_json(str(brief_dir / "recipient_channel.json"), {
                "recipient_channel": "facebook_message",
                "recipient_value": "facebook.com",
            })
            write_json(str(run_dir / "04_briefs" / "preview_ready_briefs.json"), [{
                "business_slug": "test-business",
                "recipient_channel": "facebook_message",
            }])
            write_json(str(run_dir / "04_briefs" / "blocked_no_recipient_channel.json"), [])

            deploy_dir = run_dir / "07_deployments" / "test-business"
            deploy_dir.mkdir(parents=True, exist_ok=True)
            write_json(str(deploy_dir / "deployment_record.json"), {
                "preview_url": "https://test-business.example.com",
            })

            result = run_phase_08(run_id, str(root))
            assert result["status"] == "done"
            assert result["records_processed"] == 1

            drafts = read_json(str(run_dir / "08_outreach" / "outreach_drafts.json"))
            assert len(drafts) == 1
            assert drafts[0]["draft_status"] == "ready_for_review"
            assert drafts[0]["recipient_channel"] == "facebook_message"
            assert drafts[0]["subject"] == ""
            assert drafts[0]["niche"] == "dentist"
            assert drafts[0]["area"] == "Madrid"
            assert drafts[0]["country"] == "Spain"
            assert drafts[0]["template_family"] == "clinical_trust"
            assert drafts[0]["template_variant"] == "single_page_preview"
            assert drafts[0]["stitch_project_id"] == "stitch_123"
            assert drafts[0]["offer_price"] == "299"
            assert drafts[0]["currency"] == "EUR"
            assert drafts[0]["pricing_market"] == "Madrid, Spain"
            assert "https://test-business.example.com" in drafts[0]["body"]
            assert (run_dir / "08_outreach" / "outreach_drafts.md").exists()
            assert (run_dir / "08_outreach" / "result.json").exists()

    def test_run_phase_08_includes_blocked_unknown_channel(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_001"
            run_dir = root / "runs" / run_id

            (run_dir / "config").mkdir(parents=True, exist_ok=True)
            write_json(str(run_dir / "config" / "input_config.json"), {
                "price_offer": "$299 setup",
            })

            blocked_dir = run_dir / "04_briefs" / "blocked-business"
            blocked_dir.mkdir(parents=True, exist_ok=True)
            (blocked_dir / "FACTS.md").write_text(
                "# FACTS\n\n- business_name: Blocked Business\n",
                encoding="utf-8",
            )
            write_json(str(blocked_dir / "recipient_channel.json"), {
                "recipient_channel": "unknown",
                "recipient_value": "",
                "manual_override": False,
            })
            write_json(str(run_dir / "04_briefs" / "preview_ready_briefs.json"), [])
            write_json(str(run_dir / "04_briefs" / "blocked_no_recipient_channel.json"), [{
                "business_slug": "blocked-business",
                "recipient_channel": "unknown",
                "blocked_reason": BLOCKED_REASON,
            }])

            result = run_phase_08(run_id, str(root))
            assert result["status"] == "done"

            drafts = read_json(str(run_dir / "08_outreach" / "outreach_drafts.json"))
            assert len(drafts) == 1
            assert drafts[0]["draft_status"] == "blocked"
            assert drafts[0]["blocked_reason"] == BLOCKED_REASON

    def test_run_phase_08_blocked_when_inputs_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_phase_08("missing_run", tmp)
            assert result["status"] == "blocked"
            assert "preview_ready_briefs.json" in result["missing_fields"]
            assert "RunConfig" in result["missing_fields"]
