"""Tests for packages/shared/provenance.py — provenance utilities."""

from packages.shared.provenance import (
    _deterministic_generated_at,
    _envelope,
    _has_value,
    _safe_str,
)


class TestSafeStr:
    def test_none_returns_empty(self):
        assert _safe_str(None) == ""

    def test_empty_string_returns_empty(self):
        assert _safe_str("") == ""

    def test_whitespace_only_returns_empty(self):
        assert _safe_str("   ") == ""

    def test_normal_string(self):
        assert _safe_str("hello") == "hello"

    def test_string_with_whitespace(self):
        assert _safe_str("  hello  ") == "hello"

    def test_integer(self):
        assert _safe_str(42) == "42"

    def test_zero_returns_empty(self):
        # 0 is falsy → str(0 or "") = str("") = ""
        assert _safe_str(0) == ""

    def test_false(self):
        # bool False is falsy → str(False or "") = str("") = ""
        assert _safe_str(False) == ""


class TestHasValue:
    def test_none(self):
        assert _has_value(None) is False

    def test_empty_string(self):
        assert _has_value("") is False

    def test_whitespace_string(self):
        assert _has_value("   ") is False

    def test_normal_string(self):
        assert _has_value("hello") is True

    def test_zero_is_true(self):
        assert _has_value(0) is True

    def test_false_is_true(self):
        # False is not None, not a string, not a collection → True
        assert _has_value(False) is True

    def test_empty_list(self):
        assert _has_value([]) is False

    def test_nonempty_list(self):
        assert _has_value([1]) is True

    def test_empty_dict(self):
        assert _has_value({}) is False

    def test_nonempty_dict(self):
        assert _has_value({"a": 1}) is True

    def test_empty_tuple(self):
        assert _has_value(()) is False

    def test_nested_dict(self):
        assert _has_value({"outer": {"inner": "val"}}) is True

    def test_nested_empty_dict(self):
        assert _has_value({"outer": {}}) is True  # dict has len > 0


class TestEnvelope:
    def test_structure(self):
        result = _envelope("lead.json", "verified")
        assert result == {"source": "lead.json", "confidence": "verified"}

    def test_keys(self):
        result = _envelope("config.json", "inferred")
        assert "source" in result
        assert "confidence" in result
        assert len(result) == 2


class TestDeterministicGeneratedAt:
    def test_determinism(self):
        """Same inputs always produce the same output."""
        a = _deterministic_generated_at("run_123", "acme-corp")
        b = _deterministic_generated_at("run_123", "acme-corp")
        assert a == b

    def test_different_inputs_different_output(self):
        a = _deterministic_generated_at("run_123", "acme-corp")
        b = _deterministic_generated_at("run_456", "acme-corp")
        assert a != b

    def test_iso8601_format(self):
        result = _deterministic_generated_at("run_123", "acme-corp")
        assert result.endswith("Z")
        assert "T" in result

    def test_within_epoch_range(self):
        """Output is between 2026 and 2036 (10-year window)."""
        result = _deterministic_generated_at("run_123", "acme-corp")
        year = int(result[:4])
        assert 2026 <= year <= 2035
