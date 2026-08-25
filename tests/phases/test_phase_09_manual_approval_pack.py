import tempfile
from pathlib import Path

from packages.phases.phase_09_manual_approval_pack import (
    SEND_APPROVAL_CHECKLIST_FIELDS,
    build_review_record,
    generate_approval_decisions,
    generate_review_pack_md,
    generate_review_table_csv,
    generate_screenshots_index,
    run_phase_09,
)
from pipeline.json_io import read_json, write_json

FIXTURE_DIR = Path.cwd() / "tests" / "fixtures" / "phase_09_manual_approval_pack"


class TestPhase09ManualApprovalPack:
    def test_build_review_record_complete(self):
        """Test building a complete review record."""
        lead_score = {
            "run_id": "test_run",
            "record_id": "rec_123",
            "business_slug": "test-business",
            "business_name": "Test Business",
            "lead_score": 75,
            "qualification_status": "qualified",
        }
        recipient = {
            "business_slug": "test-business",
            "recipient_channel": "email",
            "recipient_value": "test@example.com",
        }
        deployment = {
            "run_id": "test_run",
            "record_id": "rec_123",
            "business_slug": "test-business",
            "preview_url": "https://test-business.example.com",
            "preview_url_type": "https",
            "outward_send_allowed": True,
            "deployment_status": "live",
        }
        outreach = {
            "run_id": "test_run",
            "record_id": "rec_123",
            "business_slug": "test-business",
            "subject": "Website preview for Test Business",
            "draft_status": "ready_for_review",
        }
        site_info = {
            "status": "approved_for_deploy",
            "screenshot_desktop_path": "/path/desktop.png",
            "screenshot_mobile_path": "/path/mobile.png",
        }

        record = build_review_record(lead_score, recipient, deployment, outreach, site_info)

        assert record["business_slug"] == "test-business"
        assert record["business_name"] == "Test Business"
        assert record["lead_score"] == 75
        assert record["recipient_channel"] == "email"
        assert record["preview_url"] == "https://test-business.example.com"
        assert record["preview_url_type"] == "https"
        assert record["outward_send_allowed"] is True
        assert record["site_status"] == "approved_for_deploy"
        assert record["draft_status"] == "ready_for_review"
        assert record["site_review_status"] == "approved"
        assert record["outreach_review_status"] == "approved"
        for field in SEND_APPROVAL_CHECKLIST_FIELDS:
            assert record[field] is False
        assert record["reviewer_name"] == ""

    def test_build_review_record_missing_outreach(self):
        """Test building review record with missing outreach."""
        lead_score = {"business_slug": "test-business", "business_name": "Test", "lead_score": 50}
        recipient = {"recipient_channel": "phone", "recipient_value": "1234567890"}
        deployment = {"preview_url": "https://test.example.com", "deployment_status": "live"}
        site_info = {"status": "approved_for_deploy", "screenshot_desktop_path": "d.png", "screenshot_mobile_path": "m.png"}

        record = build_review_record(lead_score, recipient, deployment, None, site_info)

        assert record["draft_status"] == "missing"
        assert record["outreach_review_status"] == "needs_edit"
        assert record["preview_url_type"] == ""
        assert record["outward_send_allowed"] is False

    def test_generate_review_table_csv(self):
        """Test CSV generation."""
        records = [
            {"business_slug": "biz1", "business_name": "Business 1", "lead_score": 80, "qualification_status": "qualified",
             "recipient_channel": "email", "preview_url": "https://b1.example.com", "preview_url_type": "https",
             "outward_send_allowed": True, "site_status": "approved_for_deploy",
             "draft_status": "ready_for_review", "approval_status": "pending", "site_review_status": "approved",
             "outreach_review_status": "approved", **{field: False for field in SEND_APPROVAL_CHECKLIST_FIELDS}, "reviewer_name": ""},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "review_table.csv"
            generate_review_table_csv(records, output_path)

            assert output_path.exists()
            content = output_path.read_text(encoding="utf-8")
            assert "business_slug,business_name,lead_score" in content
            assert "preview_url_type,outward_send_allowed" in content
            assert "identity_truthful_confirmed" in content
            assert "biz1,Business 1,80" in content

    def test_generate_review_pack_md_includes_send_approval_checklist(self):
        """Test review pack contains send approval checklist section."""
        records = [
            {"business_slug": "biz1", "business_name": "Business 1", "lead_score": 80,
             "recipient_channel": "email", "preview_url": "https://b1.example.com", "preview_url_type": "https",
             "outward_send_allowed": True, "site_status": "approved_for_deploy", "draft_status": "ready_for_review"},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "review_pack.md"
            generate_review_pack_md(records, output_path)

            content = output_path.read_text(encoding="utf-8")
            assert "### Send Approval Checklist" in content
            assert "- [ ] Identity truthful confirmed" in content
            assert "- [ ] Takedown policy reviewed" in content
            assert "- **Preview URL Type**: https" in content
            assert "- **Outward Send Allowed**: True" in content

    def test_generate_screenshots_index(self):
        """Test screenshots index generation."""
        records = [
            {"business_slug": "biz1", "screenshot_desktop_path": "/d1.png", "screenshot_mobile_path": "/m1.png"},
            {"business_slug": "biz2", "screenshot_desktop_path": "", "screenshot_mobile_path": ""},
            {"business_slug": "biz3", "screenshot_desktop_path": "/d3.png", "screenshot_mobile_path": "/m3.png"},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "screenshots_index.json"
            generate_screenshots_index(records, output_path)

            assert output_path.exists()
            data = read_json(str(output_path))
            assert len(data) == 2  # Only biz1 and biz3 have both paths

    def test_generate_approval_decisions(self):
        """Test approval decisions generation."""
        records = [
            {
                "business_slug": "biz1",
                "site_review_status": "approved",
                "outreach_review_status": "approved",
                "preview_url_type": "https",
                "outward_send_allowed": True,
                "screenshot_desktop_path": "/d1.png",
                "screenshot_mobile_path": "/m1.png",
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "approval_decisions.json"
            generate_approval_decisions(records, output_path)

            assert output_path.exists()
            data = read_json(str(output_path))
            assert data[0]["business_slug"] == "biz1"
            assert data[0]["approval_status"] == "pending"
            assert data[0]["site_review_status"] == "approved"
            assert data[0]["preview_url_type"] == "https"
            assert data[0]["outward_send_allowed"] is True
            for field in SEND_APPROVAL_CHECKLIST_FIELDS:
                assert data[0][field] is False
            assert data[0]["reviewer_name"] == ""

    def test_run_phase_09_blocked_when_sites_missing(self):
        """Test phase is blocked when required inputs are missing."""
        with tempfile.TemporaryDirectory() as tmp:
            result = run_phase_09("missing_run", tmp)
            assert result["status"] == "blocked"

    def test_run_phase_09_skips_missing_screenshots(self):
        """Test that sites missing either screenshot are skipped."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_001"
            run_dir = root / "runs" / run_id

            # Setup directories
            site_dir = run_dir / "05_sites" / "test-business"
            site_dir.mkdir(parents=True, exist_ok=True)
            (site_dir / "screenshot_desktop.png").write_bytes(b"fake")

            # Missing screenshot_mobile.png

            brief_dir = run_dir / "04_briefs" / "test-business"
            brief_dir.mkdir(parents=True, exist_ok=True)
            write_json(str(brief_dir / "recipient_channel.json"), {"recipient_channel": "email"})

            quality_dir = run_dir / "06_quality" / "test-business"
            quality_dir.mkdir(parents=True, exist_ok=True)
            write_json(str(quality_dir / "site_quality_report.json"), {"status": "approved_for_deploy"})

            deploy_dir = run_dir / "07_deployments" / "test-business"
            deploy_dir.mkdir(parents=True, exist_ok=True)
            write_json(str(deploy_dir / "deployment_record.json"), {"preview_url": "https://test.example.com"})

            outreach_dir = run_dir / "08_outreach"
            outreach_dir.mkdir(parents=True, exist_ok=True)
            write_json(str(outreach_dir / "outreach_drafts.json"), [])

            scoring_dir = run_dir / "03_scoring"
            scoring_dir.mkdir(parents=True, exist_ok=True)
            write_json(str(scoring_dir / "leads_scored.json"), [])

            result = run_phase_09(run_id, str(root))
            assert result["status"] == "done"
            assert result["records_processed"] == 0  # Skipped due to missing mobile screenshot

    def test_run_phase_09_complete(self):
        """Test complete phase run with all inputs."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_001"
            run_dir = root / "runs" / run_id

            business_slug = "test-business"
            site_dir = run_dir / "05_sites" / business_slug
            site_dir.mkdir(parents=True, exist_ok=True)
            (site_dir / "screenshot_desktop.png").write_bytes(b"fake")
            (site_dir / "screenshot_mobile.png").write_bytes(b"fake")

            brief_dir = run_dir / "04_briefs" / business_slug
            brief_dir.mkdir(parents=True, exist_ok=True)
            write_json(str(brief_dir / "recipient_channel.json"), {
                "business_slug": business_slug,
                "recipient_channel": "email",
                "recipient_value": "test@example.com",
            })

            quality_dir = run_dir / "06_quality" / business_slug
            quality_dir.mkdir(parents=True, exist_ok=True)
            write_json(str(quality_dir / "site_quality_report.json"), {"status": "approved_for_deploy"})

            deploy_dir = run_dir / "07_deployments" / business_slug
            deploy_dir.mkdir(parents=True, exist_ok=True)
            write_json(str(deploy_dir / "deployment_record.json"), {
                "business_slug": business_slug,
                "preview_url": "https://test.example.com",
                "preview_url_type": "https",
                "outward_send_allowed": True,
                "deployment_status": "live",
            })

            outreach_dir = run_dir / "08_outreach"
            outreach_dir.mkdir(parents=True, exist_ok=True)
            write_json(str(outreach_dir / "outreach_drafts.json"), [{
                "business_slug": business_slug,
                "subject": "Preview for Test Business",
                "draft_status": "ready_for_review",
            }])

            scoring_dir = run_dir / "03_scoring"
            scoring_dir.mkdir(parents=True, exist_ok=True)
            write_json(str(scoring_dir / "leads_scored.json"), [{
                "business_slug": business_slug,
                "business_name": "Test Business",
                "lead_score": 75,
                "qualification_status": "qualified",
            }])

            result = run_phase_09(run_id, str(root))
            assert result["status"] == "done"
            assert result["records_processed"] == 1

            # Verify outputs exist
            assert (run_dir / "09_review" / "review_table.csv").exists()
            assert (run_dir / "09_review" / "review_pack.md").exists()
            assert (run_dir / "09_review" / "screenshots_index.json").exists()
            assert (run_dir / "09_review" / "approval_decisions.json").exists()
            decisions = read_json(str(run_dir / "09_review" / "approval_decisions.json"))
            assert decisions[0]["preview_url_type"] == "https"
            assert decisions[0]["outward_send_allowed"] is True
            assert decisions[0]["identity_truthful_confirmed"] is False

    def test_run_phase_09_skips_missing_stubs(self):
        """Test that Phase 09 works with skip_missing_stubs when 07/08 are absent."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_001"
            run_dir = root / "runs" / run_id

            business_slug = "test-business"
            site_dir = run_dir / "05_sites" / business_slug
            site_dir.mkdir(parents=True, exist_ok=True)
            (site_dir / "screenshot_desktop.png").write_bytes(b"fake")
            (site_dir / "screenshot_mobile.png").write_bytes(b"fake")

            brief_dir = run_dir / "04_briefs" / business_slug
            brief_dir.mkdir(parents=True, exist_ok=True)
            write_json(str(brief_dir / "recipient_channel.json"), {
                "business_slug": business_slug,
                "recipient_channel": "email",
                "recipient_value": "test@example.com",
            })

            quality_dir = run_dir / "06_quality" / business_slug
            quality_dir.mkdir(parents=True, exist_ok=True)
            write_json(str(quality_dir / "site_quality_report.json"), {"status": "approved_for_deploy"})

            # Note: NO 07_deployments or 08_outreach directories

            scoring_dir = run_dir / "03_scoring"
            scoring_dir.mkdir(parents=True, exist_ok=True)
            write_json(str(scoring_dir / "leads_scored.json"), [{
                "business_slug": business_slug,
                "business_name": "Test Business",
                "lead_score": 75,
                "qualification_status": "qualified",
            }])

            # Without skip_missing_stubs, should be blocked
            result = run_phase_09(run_id, str(root))
            assert result["status"] == "blocked"

            # With skip_missing_stubs, should succeed
            result = run_phase_09(run_id, str(root), skip_missing_stubs=True)
            assert result["status"] == "done"
            assert result["records_processed"] == 1

            # Verify outputs exist
            assert (run_dir / "09_review" / "review_table.csv").exists()
            assert (run_dir / "09_review" / "review_pack.md").exists()
            assert (run_dir / "09_review" / "screenshots_index.json").exists()
            assert (run_dir / "09_review" / "approval_decisions.json").exists()