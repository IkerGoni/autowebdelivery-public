"""Unit tests for Task 1C.2 — Flag defaults in vnext_integration.py.

Verifies that use_competitor_intelligence and use_patch_phase exist in
_VNEXT_FLAG_DEFAULTS and default to False.
"""

from __future__ import annotations

from packages.pipeline.vnext_integration import _VNEXT_FLAG_DEFAULTS, get_vnext_flags


class TestFlagDefaults:
    def test_competitor_intelligence_default_false(self):
        """use_competitor_intelligence is in defaults and is False."""
        assert "use_competitor_intelligence" in _VNEXT_FLAG_DEFAULTS
        assert _VNEXT_FLAG_DEFAULTS["use_competitor_intelligence"] is False

    def test_patch_phase_default_false(self):
        """use_patch_phase is in defaults and is False."""
        assert "use_patch_phase" in _VNEXT_FLAG_DEFAULTS
        assert _VNEXT_FLAG_DEFAULTS["use_patch_phase"] is False

    def test_both_defaults_via_get_vnext_flags(self):
        """Both flags default to False when config has no vnext_flags."""
        flags = get_vnext_flags({})
        assert flags.get("use_competitor_intelligence") is False
        assert flags.get("use_patch_phase") is False

    def test_both_can_be_enabled(self):
        """Both flags can be explicitly set to True."""
        flags = get_vnext_flags({
            "vnext_flags": {
                "use_competitor_intelligence": True,
                "use_patch_phase": True,
            }
        })
        assert flags["use_competitor_intelligence"] is True
        assert flags["use_patch_phase"] is True

    def test_count_includes_new_flags(self):
        """Total flag count includes the new entries."""
        assert len(_VNEXT_FLAG_DEFAULTS) == 15
