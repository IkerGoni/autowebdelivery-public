"""Social-only presence detection for business websites.

Detects businesses that only have social media presence (Facebook/Instagram)
without an owned domain.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# Social media patterns that indicate social-only presence
SOCIAL_ONLY_PATTERNS = [
    "facebook.com/",
    "fb.com/",
    "fb.me/",
    "instagram.com/",
    "ig.me/",
    "instagr.am/",
    "m.facebook.com/",
    "mobile.facebook.com/",
    "www.facebook.com/",
    "www.instagram.com/",
]


def is_social_only_website(url: str) -> bool:
    """Check if a URL is a social-only presence (no owned domain).

    Args:
        url: Website URL to check

    Returns:
        True if the URL is ONLY a social media profile, False otherwise.

    Examples:
        >>> is_social_only_website("https://facebook.com/mybusiness")
        True
        >>> is_social_only_website("https://www.mybusiness.com")
        False
        >>> is_social_only_website("")
        False
    """
    if not url or not isinstance(url, str):
        return False

    url_lower = url.lower().strip()

    # Empty or placeholder URLs
    if not url_lower or url_lower in ("n/a", "none", "null"):
        return False

    # Check if URL contains social media patterns
    return any(pattern in url_lower for pattern in SOCIAL_ONLY_PATTERNS)


def classify_website_presence(url: str) -> dict[str, bool]:
    """Classify website presence type.

    Args:
        url: Website URL to classify

    Returns:
        Dict with classification flags:
        - has_website: Any website URL present
        - has_owned_domain: Has own domain (not social-only)
        - social_only: Only has social media presence
    """
    has_url = bool(url and url.strip())
    is_social = is_social_only_website(url) if has_url else False

    return {
        "has_website": has_url,
        "has_owned_domain": has_url and not is_social,
        "social_only": is_social,
    }


def extract_domain(url: str) -> str:
    """Extract domain from URL.

    Args:
        url: Full URL

    Returns:
        Domain name or empty string if invalid
    """
    if not url:
        return ""

    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split("/")[0]
        return domain.lower().strip()
    except Exception:
        return ""
