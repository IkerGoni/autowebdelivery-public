import tempfile
from pathlib import Path

from pipeline.json_io import read_json, write_json
from packages.phases.phase_10_manual_sending import (
    SEND_APPROVAL_CHECKLIST_FIELDS,
    build_send_queue_record,
    build_sent_log_record,
    run_phase_10,
)


def _checklist_true():
    return {field: True for field in SEND_APPROVAL_CHECKLIST_FIELDS}


class TestPhase10ManualSending:
    def test_build_send_queue_record_email_has_mailto_and_send_ready(self):
        approval = {
            "run_id": "fixture_001",
            "record_id": "rev_test-business",
            "business_slug": "test-business",
            "approval_status": "send",
            **_checklist_true(),
        }
        draft = {
            "run_id": "fixture_001",
            "record_id": "out_test-business",
            "business_slug": "test-business",
            "business_name": "Test Business",
            "niche": "dentist",
            "area": "Madrid",
            "country": "Spain",
            "template_family": "clinical_trust",
            "template_variant": "single_page_preview",
            "stitch_project_id": "stitch_123",
            "offer_type": "setup_only",
            "offer_price": "299",
            "currency": "EUR",
            "pricing_market": "Madrid, Spain",
            "recipient_channel": "email",
            "recipient_value": "owner@example.com",
            "subject": "Quick website preview for Test Business",
            "body": "Hello there",
            "preview_url": "https://test.example.com",
            "outward_send_allowed": True,
            "draft_status": "ready_for_review",
        }

        record = build_send_queue_record(approval, draft)

        assert record["send_ready"] is True
        assert record["automation_mode"] == "manual_required"
        assert record["blocked_reasons"] == []
        assert record["niche"] == "dentist"
        assert record["area"] == "Madrid"
        assert record["country"] == "Spain"
        assert record["template_family"] == "clinical_trust"
        assert record["template_variant"] == "single_page_preview"
        assert record["stitch_project_id"] == "stitch_123"
        assert record["offer_price"] == "299"
        assert record["currency"] == "EUR"
        assert record["pricing_market"] == "Madrid, Spain"
        assert record["mailto_url"].startswith("mailto:owner@example.com?")

    def test_build_send_queue_record_blocks_unknown_channel(self):
        approval = {
            "business_slug": "blocked-business",
            "approval_status": "send",
            **_checklist_true(),
        }
        draft = {
            "business_slug": "blocked-business",
            "recipient_channel": "unknown",
            "recipient_value": "",
            "subject": "",
            "body": "",
            "preview_url": "https://blocked.example.com",
            "outward_send_allowed": True,
            "draft_status": "ready_for_review",
        }

        record = build_send_queue_record(approval, draft)

        assert record["send_ready"] is False
        assert "recipient_channel is not known: unknown" in record["blocked_reasons"]

    def test_build_send_queue_record_requires_https_checklist_and_outward_allowed(self):
        approval = {
            "business_slug": "blocked-business",
            "approval_status": "send",
            "outward_send_allowed": False,
            **{field: True for field in SEND_APPROVAL_CHECKLIST_FIELDS if field != "sender_contact_confirmed"},
        }
        draft = {
            "business_slug": "blocked-business",
            "recipient_channel": "email",
            "recipient_value": "owner@example.com",
            "subject": "Subject",
            "body": "Body",
            "preview_url": "http://blocked.example.com",
            "draft_status": "ready_for_review",
        }

        record = build_send_queue_record(approval, draft)

        assert record["send_ready"] is False
        assert "preview_url is not https" in record["blocked_reasons"]
        assert "outward_send_allowed is not true" in record["blocked_reasons"]
        assert "sender_contact_confirmed is not true" in record["blocked_reasons"]

    def test_build_send_queue_record_fails_closed_when_outward_allowed_missing(self):
        approval = {
            "business_slug": "blocked-business",
            "approval_status": "send",
            **_checklist_true(),
        }
        draft = {
            "business_slug": "blocked-business",
            "recipient_channel": "email",
            "recipient_value": "owner@example.com",
            "subject": "Subject",
            "body": "Body",
            "preview_url": "https://blocked.example.com",
            "draft_status": "ready_for_review",
        }

        record = build_send_queue_record(approval, draft)

        assert record["send_ready"] is False
        assert "outward_send_allowed is not true" in record["blocked_reasons"]

    def test_build_sent_log_record_sent_requires_confirmation_fields(self):
        record = build_sent_log_record(
            "fixture_001",
            {"business_slug": "test-business"},
            {"business_slug": "test-business"},
            {"sent_status": "sent", "sent_channel": "email"},
        )

        assert record["sent_status"] == "failed"
        assert "sent_status=sent requires sent_at" in record["errors"]
        assert "sent_status=sent requires sender_account" in record["errors"]
        assert "sent_status=sent requires message_ref" in record["errors"]

    def test_build_sent_log_record_unknown_channel_fails(self):
        record = build_sent_log_record(
            "fixture_001",
            {"business_slug": "test-business"},
            {"business_slug": "test-business"},
            {
                "sent_status": "sent",
                "sent_channel": "carrier_pigeon",
                "sent_at": "2026-05-11T10:00:00Z",
                "sender_account": "sales@example.com",
                "message_ref": "ref-1",
            },
        )

        assert record["sent_status"] == "failed"
        assert "invalid sent_channel: carrier_pigeon" in record["errors"]

    def test_build_sent_log_record_accepts_actual_sent_channel(self):
        approval = {
            "record_id": "rev_test-business",
            "business_slug": "test-business",
        }
        draft = {
            "record_id": "out_test-business",
            "business_slug": "test-business",
            "business_name": "Test Business",
            "niche": "dentist",
            "area": "Madrid",
            "country": "Spain",
            "template_family": "clinical_trust",
            "template_variant": "single_page_preview",
            "stitch_project_id": "stitch_123",
            "offer_type": "setup_only",
            "offer_price": "299",
            "currency": "EUR",
            "pricing_market": "Madrid, Spain",
            "recipient_channel": "email",
            "recipient_value": "owner@example.com",
            "preview_url": "https://test.example.com",
        }
        confirmation = {
            "sent_status": "sent",
            "sent_channel": "contact_form",
            "sent_at": "2026-05-11T10:00:00Z",
            "sender_account": "sales@example.com",
            "message_ref": "https://crm.local/msg/1",
            "notes": "Used contact form instead of email",
        }

        record = build_sent_log_record("fixture_001", approval, draft, confirmation)

        assert record["sent_status"] == "sent"
        assert record["automation_mode"] == "manual_required"
        assert record["sent_channel"] == "contact_form"
        assert record["business_name"] == "Test Business"
        assert record["niche"] == "dentist"
        assert record["area"] == "Madrid"
        assert record["country"] == "Spain"
        assert record["template_family"] == "clinical_trust"
        assert record["template_variant"] == "single_page_preview"
        assert record["stitch_project_id"] == "stitch_123"
        assert record["offer_price"] == "299"
        assert record["currency"] == "EUR"
        assert record["pricing_market"] == "Madrid, Spain"
        assert record["errors"] == []

    def test_run_phase_10_blocked_when_inputs_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_phase_10("missing_run", tmp)
            assert result["status"] == "blocked"
            assert any("approval_decisions.json" in item for item in result["missing_fields"])

    def test_run_phase_10_blocked_when_no_approved_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_001"
            run_dir = root / "runs" / run_id

            (run_dir / "09_review").mkdir(parents=True, exist_ok=True)
            (run_dir / "08_outreach").mkdir(parents=True, exist_ok=True)
            write_json(str(run_dir / "09_review" / "approval_decisions.json"), [{
                "business_slug": "test-business",
                "approval_status": "pending",
            }])
            write_json(str(run_dir / "08_outreach" / "outreach_drafts.json"), [{
                "business_slug": "test-business",
                "draft_status": "ready_for_review",
                "recipient_channel": "email",
                "preview_url": "https://test.example.com",
            }])

            result = run_phase_10(run_id, str(root))

            assert result["status"] == "blocked"
            assert result["errors"] == ["no approved records"]

    def test_run_phase_10_blocked_when_manual_confirmation_missing_but_helpers_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_001"
            run_dir = root / "runs" / run_id

            (run_dir / "09_review").mkdir(parents=True, exist_ok=True)
            (run_dir / "08_outreach").mkdir(parents=True, exist_ok=True)
            write_json(str(run_dir / "09_review" / "approval_decisions.json"), [{
                "run_id": run_id,
                "record_id": "rev_test-business",
                "business_slug": "test-business",
                "approval_status": "send",
                **_checklist_true(),
            }])
            write_json(str(run_dir / "08_outreach" / "outreach_drafts.json"), [{
                "run_id": run_id,
                "record_id": "out_test-business",
                "business_slug": "test-business",
                "business_name": "Test Business",
                "draft_status": "ready_for_review",
                "recipient_channel": "email",
                "recipient_value": "owner@example.com",
                "subject": "Quick website preview for Test Business",
                "body": "Hello there",
                "preview_url": "https://test.example.com",
                "outward_send_allowed": True,
            }])

            result = run_phase_10(run_id, str(root))

            assert result["status"] == "blocked"
            assert result["errors"] == ["manual sent confirmation missing"]
            assert (run_dir / "10_sent" / "approved_send_records.json").exists()
            assert (run_dir / "10_sent" / "manual_send_queue.json").exists()
            assert (run_dir / "10_sent" / "manual_send_checklist.md").exists()
            assert (run_dir / "10_sent" / "manual_confirmation_missing.json").exists()

    def test_run_phase_10_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_001"
            run_dir = root / "runs" / run_id

            (run_dir / "09_review").mkdir(parents=True, exist_ok=True)
            (run_dir / "08_outreach").mkdir(parents=True, exist_ok=True)
            (run_dir / "10_sent").mkdir(parents=True, exist_ok=True)

            write_json(str(run_dir / "09_review" / "approval_decisions.json"), [
                {
                    "run_id": run_id,
                    "record_id": "rev_test-business",
                    "business_slug": "test-business",
                    "approval_status": "send",
                    **_checklist_true(),
                },
                {
                    "run_id": run_id,
                    "record_id": "rev_second-business",
                    "business_slug": "second-business",
                    "approval_status": "send",
                    **_checklist_true(),
                },
            ])
            write_json(str(run_dir / "08_outreach" / "outreach_drafts.json"), [
                {
                    "run_id": run_id,
                    "record_id": "out_test-business",
                    "business_slug": "test-business",
                    "business_name": "Test Business",
                    "niche": "dentist",
                    "area": "Madrid",
                    "country": "Spain",
                    "template_family": "clinical_trust",
                    "template_variant": "single_page_preview",
                    "stitch_project_id": "stitch_123",
                    "offer_type": "setup_only",
                    "offer_price": "299",
                    "currency": "EUR",
                    "pricing_market": "Madrid, Spain",
                    "draft_status": "ready_for_review",
                    "recipient_channel": "email",
                    "recipient_value": "owner@example.com",
                    "subject": "Quick website preview for Test Business",
                    "body": "Hello there",
                    "preview_url": "https://test.example.com",
                    "outward_send_allowed": True,
                },
                {
                    "run_id": run_id,
                    "record_id": "out_second-business",
                    "business_slug": "second-business",
                    "business_name": "Second Business",
                    "niche": "restaurant",
                    "area": "Barcelona",
                    "country": "Spain",
                    "template_family": "warm_editorial",
                    "template_variant": "single_page_preview",
                    "stitch_project_id": "stitch_456",
                    "offer_type": "setup_only",
                    "offer_price": "349",
                    "currency": "EUR",
                    "pricing_market": "Barcelona, Spain",
                    "draft_status": "ready_for_review",
                    "recipient_channel": "instagram_dm",
                    "recipient_value": "@secondbiz",
                    "subject": "",
                    "body": "Hi from DM",
                    "preview_url": "https://second.example.com",
                    "outward_send_allowed": True,
                },
            ])
            write_json(str(run_dir / "10_sent" / "manual_confirmation.json"), [
                {
                    "business_slug": "test-business",
                    "sent_status": "sent",
                    "sent_channel": "email",
                    "sent_at": "2026-05-11T10:00:00Z",
                    "sender_account": "sales@example.com",
                    "message_ref": "gmail-draft-1",
                    "notes": "Sent from Gmail",
                },
                {
                    "business_slug": "second-business",
                    "sent_status": "not_sent",
                    "sent_channel": "instagram_dm",
                    "sent_at": "",
                    "sender_account": "@saleshandle",
                    "message_ref": "",
                    "notes": "Waiting for better screenshot",
                },
            ])

            result = run_phase_10(run_id, str(root))

            assert result["status"] == "done"
            assert result["records_processed"] == 2
            assert result["records_created"] == 2
            assert result["records_skipped"] == 1
            assert (run_dir / "10_sent" / "sent_log.json").exists()
            assert (run_dir / "10_sent" / "sent_log.csv").exists()
            assert (run_dir / "10_sent" / "result.json").exists()

            sent_log = read_json(str(run_dir / "10_sent" / "sent_log.json"))
            assert len(sent_log) == 2
            assert sent_log[0]["sent_status"] == "sent"
            assert sent_log[1]["sent_status"] == "not_sent"
            assert sent_log[0]["niche"] == "dentist"
            assert sent_log[0]["area"] == "Madrid"
            assert sent_log[0]["country"] == "Spain"
            assert sent_log[0]["template_family"] == "clinical_trust"
            assert sent_log[0]["template_variant"] == "single_page_preview"
            assert sent_log[0]["stitch_project_id"] == "stitch_123"
            assert sent_log[0]["offer_price"] == "299"
            assert sent_log[0]["currency"] == "EUR"
            assert sent_log[0]["pricing_market"] == "Madrid, Spain"
            assert result["next_tasks"] == ["Phase 11 — Monetization Tracking"]
