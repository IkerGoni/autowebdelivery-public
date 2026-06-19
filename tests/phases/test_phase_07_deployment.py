import tempfile
from pathlib import Path

from pipeline.json_io import read_json, write_json
from packages.deployers.local_only import deploy_local_site
from packages.phases.phase_07_deployment import run_phase_07


def _make_site(site_root: Path, business_name: str = "Test Business") -> None:
    (site_root / "site").mkdir(parents=True, exist_ok=True)
    (site_root / "site" / "index.html").write_text(
        f"<html><h1>{business_name}</h1></html>",
        encoding="utf-8",
    )
    (site_root / "screenshot_desktop.png").write_bytes(b"fake")
    (site_root / "screenshot_mobile.png").write_bytes(b"fake")


class TestLocalOnlyDeployer:
    def test_deploy_local_site_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            site_root = Path(tmp) / "site-output"
            _make_site(site_root)

            result = deploy_local_site(str(site_root))

            assert result["deployment_status"] == "live"
            assert result["provider"] == "local_only"
            assert result["preview_url"].startswith("file://")
            assert result["http_status"] == 200

    def test_deploy_local_site_fails_when_index_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            site_root = Path(tmp) / "site-output"
            site_root.mkdir(parents=True, exist_ok=True)

            result = deploy_local_site(str(site_root))

            assert result["deployment_status"] == "failed"
            assert result["http_status"] == 0
            assert "index" in result["error"].lower()


class TestPhase07Deployment:
    def test_run_phase_07_blocked_when_inputs_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_phase_07("missing_run", tmp)
            assert result["status"] == "blocked"

    def test_run_phase_07_deploys_approved_site(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_001"

            site_dir = root / "runs" / run_id / "05_sites" / "test-business"
            _make_site(site_dir)

            quality_dir = root / "runs" / run_id / "06_quality" / "test-business"
            quality_dir.mkdir(parents=True, exist_ok=True)
            write_json(str(quality_dir / "site_quality_report.json"), {"status": "approved_for_deploy"})

            result = run_phase_07(run_id, str(root))
            assert result["status"] == "done"
            assert result["records_processed"] == 1
            assert result["records_created"] == 1

            record = read_json(str(root / "runs" / run_id / "07_deployments" / "test-business" / "deployment_record.json"))
            assert record["deployment_status"] == "live"
            assert record["provider"] == "local_only"
            assert record["preview_url"].startswith("file://")
            assert record["preview_url_type"] == "local_file"
            assert record["public_url_source"] == "none"
            assert record["outward_send_allowed"] is False
            assert record["cleanup_required"] is True
            assert record["takedown_after_days"] == 30
            assert record["takedown_status"] == "not_due"

            logs = (root / "runs" / run_id / "07_deployments" / "test-business" / "deployment_logs.txt").read_text(encoding="utf-8")
            assert "status=live" in logs

    def test_run_phase_07_marks_nonapproved_site_needs_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_001"

            site_dir = root / "runs" / run_id / "05_sites" / "test-business"
            _make_site(site_dir)

            quality_dir = root / "runs" / run_id / "06_quality" / "test-business"
            quality_dir.mkdir(parents=True, exist_ok=True)
            write_json(str(quality_dir / "site_quality_report.json"), {"status": "needs_edit"})

            result = run_phase_07(run_id, str(root))
            assert result["status"] == "done"
            assert result["records_processed"] == 1
            assert result["records_created"] == 0
            assert result["records_skipped"] == 1

            record = read_json(str(root / "runs" / run_id / "07_deployments" / "test-business" / "deployment_record.json"))
            assert record["deployment_status"] == "needs_review"
            assert record["preview_url"] == ""
            assert record["preview_url_type"] == "missing"
            assert record["public_url_source"] == "none"
            assert record["outward_send_allowed"] is False

    def test_run_phase_07_uses_https_public_url_manifest_for_outward_send(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_001"

            site_dir = root / "runs" / run_id / "05_sites" / "test-business"
            _make_site(site_dir)

            quality_dir = root / "runs" / run_id / "06_quality" / "test-business"
            quality_dir.mkdir(parents=True, exist_ok=True)
            write_json(str(quality_dir / "site_quality_report.json"), {"status": "approved_for_deploy"})

            deploy_dir = root / "runs" / run_id / "07_deployments"
            deploy_dir.mkdir(parents=True, exist_ok=True)
            write_json(str(deploy_dir / "public_url_manifest.json"), [{
                "business_slug": "test-business",
                "preview_url": "https://example.com/test-business",
                "provider": "vercel_manual",
                "verified_at": "2026-01-01T00:00:00+00:00",
                "http_status": 200,
            }])

            result = run_phase_07(run_id, str(root))
            assert result["status"] == "done"

            record = read_json(str(deploy_dir / "test-business" / "deployment_record.json"))
            assert record["preview_url"] == "https://example.com/test-business"
            assert record["provider"] == "vercel_manual"
            assert record["preview_url_type"] == "public_https"
            assert record["public_url_source"] == "manual_manifest"
            assert record["verified_at"] == "2026-01-01T00:00:00+00:00"
            assert record["http_status"] == 200
            assert record["outward_send_allowed"] is True

    def test_run_phase_07_blocks_outward_send_for_non_https_manifest_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_001"

            site_dir = root / "runs" / run_id / "05_sites" / "test-business"
            _make_site(site_dir)

            quality_dir = root / "runs" / run_id / "06_quality" / "test-business"
            quality_dir.mkdir(parents=True, exist_ok=True)
            write_json(str(quality_dir / "site_quality_report.json"), {"status": "approved_for_deploy"})

            deploy_dir = root / "runs" / run_id / "07_deployments"
            deploy_dir.mkdir(parents=True, exist_ok=True)
            write_json(str(deploy_dir / "public_url_manifest.json"), [{
                "business_slug": "test-business",
                "preview_url": "http://example.com/test-business",
                "provider": "bad_public_host",
                "verified_at": "2026-01-01T00:00:00+00:00",
                "http_status": 200,
            }])

            result = run_phase_07(run_id, str(root))
            assert result["status"] == "done"

            record = read_json(str(deploy_dir / "test-business" / "deployment_record.json"))
            assert record["preview_url"].startswith("file://")
            assert record["preview_url_type"] == "local_file"
            assert record["public_url_source"] == "none"
            assert record["provider"] == "local_only"
            assert record["outward_send_allowed"] is False
