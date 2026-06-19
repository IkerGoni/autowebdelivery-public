"""Tests for packages/shared/forbidden_claims.py — forbidden claims registry."""

from packages.shared.forbidden_claims import (
    FORBIDDEN_PUBLIC_CLAIMS,
    forbidden_public_claims,
)


class TestForbiddenPublicClaimsTuple:
    def test_non_empty(self):
        assert len(FORBIDDEN_PUBLIC_CLAIMS) > 0

    def test_is_tuple(self):
        assert isinstance(FORBIDDEN_PUBLIC_CLAIMS, tuple)

    def test_contains_known_entries(self):
        assert "licenses" in FORBIDDEN_PUBLIC_CLAIMS
        assert "testimonials" in FORBIDDEN_PUBLIC_CLAIMS
        assert "guarantees" in FORBIDDEN_PUBLIC_CLAIMS

    def test_tuple_is_immutable(self):
        """Tuple itself is frozen — cannot assign to indices."""
        import pytest

        with pytest.raises(TypeError):
            FORBIDDEN_PUBLIC_CLAIMS[0] = "hacked"  # type: ignore[index]


class TestForbiddenPublicClaimsFunction:
    def test_returns_list(self):
        result = forbidden_public_claims()
        assert isinstance(result, list)

    def test_list_matches_tuple(self):
        result = forbidden_public_claims()
        assert result == list(FORBIDDEN_PUBLIC_CLAIMS)

    def test_fresh_copy_each_call(self):
        a = forbidden_public_claims()
        b = forbidden_public_claims()
        assert a == b
        assert a is not b

    def test_catches_known_forbidden_word_in_text(self):
        """Each forbidden category name should be present in the returned list."""
        claims = forbidden_public_claims()
        # 'licenses' is a known forbidden category
        assert "licenses" in claims

    def test_returns_non_empty(self):
        assert len(forbidden_public_claims()) > 0
