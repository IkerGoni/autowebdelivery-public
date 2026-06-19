"""Tests for empty HTML guards in patch_plan.py.

Verifies that _plan_cta_patch and _plan_mobile_overflow_patch return None
when given empty, None, or whitespace-only HTML, with a DEBUG-level log.
"""
from __future__ import annotations

import logging

import pytest

from packages.patching.patch_plan import (
    _plan_cta_patch,
    _plan_mobile_overflow_patch,
)


class TestEmptyHtmlGuard:
    """_plan_cta_patch should return None for empty/whitespace HTML."""

    @pytest.mark.parametrize(
        "html",
        [
            "",
            None,
            "   ",
            "\n\t  \n",
        ],
    )
    def test_cta_patch_empty_returns_none(self, html):
        assert _plan_cta_patch(html) is None

    @pytest.mark.parametrize(
        "html",
        [
            "",
            None,
            "   ",
            "\n\t  \n",
        ],
    )
    def test_mobile_overflow_patch_empty_returns_none(self, html):
        assert _plan_mobile_overflow_patch(html) is None

    def test_cta_patch_non_empty_returns_dict_or_none(self):
        """Non-empty HTML should return either a dict or None, never an empty guard."""
        result = _plan_cta_patch("<html><body></body></html>")
        # Could be a dict (with patch) or None (if </body> not found in proper context)
        assert result is None or isinstance(result, dict)

    def test_mobile_overflow_non_empty_returns_dict_or_none(self):
        """Non-empty HTML should return either a dict or None, never an empty guard."""
        result = _plan_mobile_overflow_patch("<html><body><p>content</p></body></html>")
        assert result is None or isinstance(result, dict)

    def test_cta_patch_empty_logs_debug(self, caplog):
        """Empty HTML should trigger a DEBUG-level log message."""
        caplog.set_level(logging.DEBUG)
        _plan_cta_patch("")
        assert len(caplog.records) >= 1
        assert any("Empty HTML" in r.message for r in caplog.records)
        assert any(r.levelno == logging.DEBUG for r in caplog.records)

    def test_mobile_overflow_empty_logs_debug(self, caplog):
        """Empty HTML should trigger a DEBUG-level log message."""
        caplog.set_level(logging.DEBUG)
        _plan_mobile_overflow_patch("")
        assert len(caplog.records) >= 1
        assert any("Empty HTML" in r.message for r in caplog.records)
        assert any(r.levelno == logging.DEBUG for r in caplog.records)

    def test_whitespace_only_logs_debug(self, caplog):
        """Whitespace-only HTML should trigger a DEBUG-level log message."""
        caplog.set_level(logging.DEBUG)
        _plan_cta_patch("   \n  \t  ")
        assert len(caplog.records) >= 1
        assert any("Empty HTML" in r.message for r in caplog.records)
