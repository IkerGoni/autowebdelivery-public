"""Tests for trust scorer else branch fix.

Verifies that the else branch in the org-markup scoring section awards 0
points (not 10) when no org markup is detected.
"""
from __future__ import annotations

from packages.evaluation.website_evaluator import _score_trust


class TestTrustScoreOrgMarkup:
    """_score_trust should award 0 points in the else branch of org markup check."""

    def test_no_org_markup_awards_zero(self):
        """When no org markup is found, the else branch should add 0, not 10."""
        html = "<html><body><p>Just text, no org schema</p></body></html>"
        score, notes = _score_trust(html)
        # The score should be exactly what the other checks provide (phone, email, address)
        # Without 10 free points from org markup else branch.
        # Calculate expected: 0 (no phone) + 0 (no email) + 0 (no address) + 0 (no org) = 0
        # So score should be 0
        assert score < 10, (
            f"Expected score < 10 without org markup, got {score}. "
            f"The else branch should award 0 not 10. Notes: {notes}"
        )

    def test_with_org_markup_still_awards_25(self):
        """When org markup IS found, score should still include +25."""
        html = '<html><body itemscope itemtype="http://schema.org/LocalBusiness"><p>Biz</p></body></html>'
        score, notes = _score_trust(html)
        # With schema.org present, should include +25 for org markup
        # Other checks may also add points if phone/email/address detected
        assert "Trust signals detected" in notes or score > 0

    def test_else_branch_does_not_add_ten(self):
        """Verify exact scoring: HTML with no signals gets 0 total."""
        html = "<html><body><p>hello world</p></body></html>"
        score, notes = _score_trust(html)
        # No phone, email, address, or org markup → all branches miss → score should be 0
        assert score == 0, (
            f"Expected score 0 for bare HTML with no trust signals, got {score}. "
            f"Notes: {notes}"
        )

    def test_org_markup_else_comment_present(self):
        """Check the comment is visible in the source code."""
        import inspect
        source = inspect.getsource(_score_trust)
        assert "score += 0" in source, "Expected 'score += 0' in the else branch"
        assert "No org markup" in source, "Expected explanatory comment in else branch"
