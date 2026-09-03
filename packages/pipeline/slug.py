"""Slug generation for URL-safe identifiers per pipeline_data_contract.md.

R0-02 (F-02): slugs and run ids are untrusted values that end up in filesystem
paths. ``validate_slug``/``safe_path`` enforce the safe charset at every path
construction site; ``make_slug``/``make_uuid_slug`` remain the generators and
their outputs are the compatibility baseline for the validator (hence the
{1,73} bound: ``make_uuid_slug`` appends ``-<8 hex>`` to a base truncated to
64 = 73 max).
"""

import re
import uuid
from pathlib import Path

# Every part of a run-directory chain ("runs", "04_briefs", run ids, slugs)
# matches this charset, so one rule covers them all.
SAFE_PART_RE = re.compile(r"^[a-z0-9_-]{1,73}$")

MAX_PART_LEN = 73


class UnsafeSlugError(ValueError):
    """Raised when a slug/run-id/path part is not a safe filesystem component."""


def validate_slug(value: str, *, field: str = "slug") -> str:
    """Validate an untrusted identifier before it touches a filesystem path.

    Raises UnsafeSlugError (never uses ``assert`` — validation must survive
    ``python -O``) for anything outside ``[a-z0-9_-]{1,73}``.
    """
    if not isinstance(value, str) or not SAFE_PART_RE.fullmatch(value):
        raise UnsafeSlugError(
            f"unsafe {field}: {value!r} does not match [a-z0-9_-]{{1,{MAX_PART_LEN}}}"
        )
    return value


def safe_path(root: Path | str, *parts: str) -> Path:
    """Build ``root / *parts`` rejecting unsafe path components.

    Every part must independently match the safe charset (this blocks ``..``,
    ``%2e``, backslashes, null bytes, unicode homographs and separators), and
    the final path must resolve inside ``root`` as defense in depth.
    """
    root_path = Path(root)
    for part in parts:
        validate_slug(part, field="path part")
    path = root_path.joinpath(*parts)
    if not path.resolve().is_relative_to(root_path.resolve()):
        raise UnsafeSlugError(f"path escapes root: {path} (root={root_path})")
    return path


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