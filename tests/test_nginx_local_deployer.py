"""Tests for the nginx_local deployer."""

import os
import tempfile
from pathlib import Path

from packages.deployers.nginx_local import deploy_nginx_local


class TestNginxLocalDeployer:
    """Test deploy_nginx_local returns HTTP URLs and handles edge cases."""

    def test_returns_http_url_with_site_subdir_layout(self):
        """Site with site/index.html layout returns http:// URL."""
        with tempfile.TemporaryDirectory() as tmp:
            site_root = Path(tmp) / "runs" / "run_001" / "05_sites" / "test-biz"
            (site_root / "site").mkdir(parents=True, exist_ok=True)
            (site_root / "site" / "index.html").write_text("<html><h1>Test</h1></html>")

            result = deploy_nginx_local(str(site_root))

            assert result["deployment_status"] == "live"
            assert result["provider"] == "nginx_local"
            assert result["preview_url"].startswith("http://")
            assert "file://" not in result["preview_url"]
            assert result["http_status"] == 200
            assert result["error"] == ""
            # URL should contain the relative path from runs/
            assert "runs/run_001/05_sites/test-biz" in result["preview_url"]

    def test_returns_http_url_with_flat_index_layout(self):
        """Site with index.html at root (modular layout) returns http:// URL."""
        with tempfile.TemporaryDirectory() as tmp:
            site_root = Path(tmp) / "runs" / "run_002" / "05_sites" / "flat-biz"
            site_root.mkdir(parents=True, exist_ok=True)
            (site_root / "index.html").write_text("<html><h1>Flat</h1></html>")

            result = deploy_nginx_local(str(site_root))

            assert result["deployment_status"] == "live"
            assert result["provider"] == "nginx_local"
            assert result["preview_url"].startswith("http://")
            assert "file://" not in result["preview_url"]
            assert result["http_status"] == 200
            assert "runs/run_002/05_sites/flat-biz" in result["preview_url"]

    def test_handles_missing_index_html(self):
        """Missing index.html returns failed status."""
        with tempfile.TemporaryDirectory() as tmp:
            site_root = Path(tmp) / "runs" / "run_003" / "05_sites" / "no-html"
            site_root.mkdir(parents=True, exist_ok=True)

            result = deploy_nginx_local(str(site_root))

            assert result["deployment_status"] == "failed"
            assert result["provider"] == "nginx_local"
            assert result["http_status"] == 0
            assert "index" in result["error"].lower()

    def test_handles_nonexistent_path(self):
        """Non-existent site path returns failed status."""
        result = deploy_nginx_local("/nonexistent/path/to/site")

        assert result["deployment_status"] == "failed"
        assert result["provider"] == "nginx_local"
        assert result["http_status"] == 0
        assert "not found" in result["error"].lower()

    def test_uses_site_host_env_variable(self):
        """SITE_HOST env var overrides the default host."""
        with tempfile.TemporaryDirectory() as tmp:
            site_root = Path(tmp) / "runs" / "run_004" / "05_sites" / "env-biz"
            (site_root / "site").mkdir(parents=True, exist_ok=True)
            (site_root / "site" / "index.html").write_text("<html></html>")

            old_host = os.environ.get("SITE_HOST")
            old_port = os.environ.get("SITE_PORT")
            try:
                os.environ["SITE_HOST"] = "myhost.example.com"
                os.environ["SITE_PORT"] = "9090"
                result = deploy_nginx_local(str(site_root))
            finally:
                if old_host is None:
                    os.environ.pop("SITE_HOST", None)
                else:
                    os.environ["SITE_HOST"] = old_host
                if old_port is None:
                    os.environ.pop("SITE_PORT", None)
                else:
                    os.environ["SITE_PORT"] = old_port

            assert result["deployment_status"] == "live"
            assert result["preview_url"].startswith("http://myhost.example.com:9090/")

    def test_default_host_and_port(self):
        """Default host is the RFC 5737 placeholder and port is 8081."""
        with tempfile.TemporaryDirectory() as tmp:
            site_root = Path(tmp) / "runs" / "run_005" / "05_sites" / "def-biz"
            (site_root / "site").mkdir(parents=True, exist_ok=True)
            (site_root / "site" / "index.html").write_text("<html></html>")

            # Ensure env vars are not set
            old_host = os.environ.pop("SITE_HOST", None)
            old_port = os.environ.pop("SITE_PORT", None)
            try:
                result = deploy_nginx_local(str(site_root))
            finally:
                if old_host is not None:
                    os.environ["SITE_HOST"] = old_host
                if old_port is not None:
                    os.environ["SITE_PORT"] = old_port

            # Default points at the Tailscale tailnet — not localhost, not public.
            assert result["preview_url"].startswith("http://192.0.2.1:8081/")
