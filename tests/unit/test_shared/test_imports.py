"""Test: verify all public names from packages.shared are importable."""


def test_import_safe_str():
    from packages.shared.provenance import _safe_str
    assert callable(_safe_str)


def test_import_has_value():
    from packages.shared.provenance import _has_value
    assert callable(_has_value)


def test_import_envelope():
    from packages.shared.provenance import _envelope
    assert callable(_envelope)


def test_import_deterministic_generated_at():
    from packages.shared.provenance import _deterministic_generated_at
    assert callable(_deterministic_generated_at)


def test_import_forbidden_public_claims_tuple():
    from packages.shared.forbidden_claims import FORBIDDEN_PUBLIC_CLAIMS
    assert isinstance(FORBIDDEN_PUBLIC_CLAIMS, tuple)


def test_import_forbidden_public_claims_fn():
    from packages.shared.forbidden_claims import forbidden_public_claims
    assert callable(forbidden_public_claims)


def test_top_level_re_exports():
    """Verify top-level packages.shared re-exports work."""
    from packages.shared import (
        _safe_str,
        _has_value,
        _envelope,
        FORBIDDEN_PUBLIC_CLAIMS,
        forbidden_public_claims,
    )
    assert callable(_safe_str)
    assert callable(_has_value)
    assert callable(_envelope)
    assert isinstance(FORBIDDEN_PUBLIC_CLAIMS, tuple)
    assert callable(forbidden_public_claims)
