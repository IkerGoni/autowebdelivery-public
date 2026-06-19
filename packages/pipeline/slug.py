"""Slug generation for URL-safe identifiers per pipeline_data_contract.md."""

import re
import uuid


def make_slug(text: str, max_len: int = 64) -> str:
    """
    Convert text to URL-safe slug.

    Args:
        text: Input text to slugify
        max_len: Maximum slug length (default 64)

    Returns:
        URL-safe slug string
    """
    # Lowercase
    slug = text.lower()
    # Replace non-alphanumeric with hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    # Remove leading/trailing hyphens
    slug = slug.strip("-")
    # Truncate
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug or str(uuid.uuid4())[:8]


def make_uuid_slug(text: str) -> str:
    """Create slug from text with UUID suffix for uniqueness."""
    base = make_slug(text)
    short_uuid = uuid.uuid4().hex[:8]
    return f"{base}-{short_uuid}"