"""R0-04 (F-01) — failure-path tests for files removed from the BLE001 allowlist.

These files narrowed `except Exception` to typed exceptions in the R0 sweep:
vercel.py, social_detection.py, social_scraper.py (parsing sites),
phase_02_1_website_filter.py, phase_06_strict_quality_gate.py,
premium_quality_scorecard.py. Each test proves the typed catch still handles
its failure class (no regression to raising) AND that unexpected exception
types are no longer silently swallowed.
"""

import subprocess

import pytest

from packages.deployers.vercel import deploy_to_vercel
from packages.discovery.social_detection import extract_domain


class TestVercelTypedCatch:
    def _site(self, tmp_path):
        site_dir = tmp_path / "site"
        site_dir.mkdir(parents=True)
        (site_dir / "index.html").write_text("<html></html>", encoding="utf-8")
        return str(tmp_path)

    def test_missing_cli_binary_returns_failed_record(self, tmp_path, monkeypatch):
        """OSError (vercel CLI not installed) still yields a failed record."""
        monkeypatch.delenv("VERCEL_TOKEN", raising=False)

        def _raise(cmd, **kwargs):
            raise FileNotFoundError("vercel binary not found")

        monkeypatch.setattr(subprocess, "run", _raise)
        res = deploy_to_vercel(self._site(tmp_path))
        assert res["deployment_status"] == "failed"
        assert "vercel binary not found" in res["error"]

    def test_unexpected_exception_no_longer_swallowed(self, tmp_path, monkeypatch):
        """R0-04: a non-subprocess/OSError bug now propagates instead of being
        converted into a misleading 'deployment failed' record."""

        def _raise(cmd, **kwargs):
            raise RuntimeError("internal state corruption")

        monkeypatch.setattr(subprocess, "run", _raise)
        with pytest.raises(RuntimeError):
            deploy_to_vercel(self._site(tmp_path))


class TestSocialDetectionTypedCatch:
    def test_malformed_url_returns_empty(self):
        # urlparse raises ValueError on malformed IPv6 literals — must be caught.
        assert extract_domain("http://[invalid-ipv6") == ""

    def test_empty_url_returns_empty(self):
        assert extract_domain("") == ""
        assert extract_domain(None) == ""


class TestWebsiteFilterTypedCatch:
    def test_malformed_url_classified_invalid(self):
        from packages.phases.phase_02_1_website_filter import classify_website

        category, _status, flags = classify_website("http://[invalid-ipv6")
        assert category == "invalid_url"
        assert "malformed_url" in flags


class TestReadJsonSafeTypedCatch:
    """The strict gate and scorecard `_read_json_safe` helpers: OSError and
    ValueError handled, anything else surfaces."""

    @pytest.mark.parametrize(
        "module",
        [
            "packages.phases.phase_06_strict_quality_gate",
            "packages.phases.premium_quality_scorecard",
        ],
    )
    def test_missing_file_returns_none(self, module):
        helper = _get_read_json_safe(module)
        assert helper(_missing_path()) is None

    @pytest.mark.parametrize(
        "module",
        [
            "packages.phases.phase_06_strict_quality_gate",
            "packages.phases.premium_quality_scorecard",
        ],
    )
    def test_unreadable_file_returns_none(self, module, tmp_path):
        helper = _get_read_json_safe(module)
        target = tmp_path / "x.json"
        target.write_text("{}", encoding="utf-8")
        target.chmod(0o000)
        try:
            assert helper(target) is None
        except PermissionError:
            pytest.skip("running as root ignores file permissions")

    @pytest.mark.parametrize(
        "module",
        [
            "packages.phases.phase_06_strict_quality_gate",
            "packages.phases.premium_quality_scorecard",
        ],
    )
    def test_invalid_json_returns_none(self, module, tmp_path):
        helper = _get_read_json_safe(module)
        target = tmp_path / "x.json"
        target.write_text("{not json", encoding="utf-8")
        assert helper(target) is None


def _missing_path():
    from pathlib import Path

    return Path("/nonexistent/run/x.json")


def _get_read_json_safe(module_name):
    import importlib

    module = importlib.import_module(module_name)
    return module._read_json_safe
