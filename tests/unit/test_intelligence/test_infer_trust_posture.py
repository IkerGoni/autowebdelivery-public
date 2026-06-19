"""Tests for _infer_trust_posture category-aware logic."""

from __future__ import annotations

from packages.intelligence.brand_reconstruction import _infer_trust_posture


class TestInferTrustPostureCategoryAware:
    """Test category-aware trust posture inference."""

    def test_healthcare_returns_conservative(self):
        result = _infer_trust_posture(category="healthcare")
        assert result["value"] == "conservative"

    def test_medical_clinic_returns_conservative(self):
        result = _infer_trust_posture(category="Medical Clinic")
        assert result["value"] == "conservative"

    def test_dental_returns_conservative(self):
        result = _infer_trust_posture(category="dental")
        assert result["value"] == "conservative"

    def test_legal_returns_authoritative(self):
        result = _infer_trust_posture(category="legal")
        assert result["value"] == "authoritative"

    def test_law_firm_returns_authoritative(self):
        result = _infer_trust_posture(category="Law Firm")
        assert result["value"] == "authoritative"

    def test_auto_detailing_returns_credential_safe(self):
        result = _infer_trust_posture(category="auto detailing")
        assert result["value"] == "credential_safe"

    def test_hvac_returns_credential_safe(self):
        result = _infer_trust_posture(category="hvac")
        assert result["value"] == "credential_safe"

    def test_restaurant_returns_experience_safe(self):
        result = _infer_trust_posture(category="restaurant")
        assert result["value"] == "experience_safe"

    def test_none_category_falls_back_to_heuristic(self):
        result = _infer_trust_posture(category=None)
        assert "value" in result
        assert isinstance(result["value"], str)

    def test_no_category_falls_back_to_existing_heuristic(self):
        result = _infer_trust_posture()
        assert "value" in result
        assert isinstance(result["value"], str)

    def test_category_overrides_market_profile(self):
        mp = {"sellability": {"category": {"value": "Restaurant"}}}
        result = _infer_trust_posture(market_profile=mp, category="healthcare")
        assert result["value"] == "conservative"

    def test_unknown_category_returns_credential_safe(self):
        result = _infer_trust_posture(category="unknown_niche")
        assert result["value"] == "credential_safe"
