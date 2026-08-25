"""VNEXT-07 — HTML Patch Engine.

Applies deterministic HTML patches (insert_before, replace, remove) to a
site's HTML string.  Only approved patch categories are processed.

Idempotency guarantee: applying the same patch twice is a no-op.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_html_patches(html: str, patches: list[dict[str, Any]]) -> str:
    """Apply a list of HTML patches to the site HTML.

    Only patches with ``target == "html"`` and an approved action are
    processed.  Unknown actions are silently skipped.

    Parameters
    ----------
    html:
        The full HTML string of the generated site.
    patches:
        List of patch dicts from a patch plan.

    Returns
    -------
    str
        The patched HTML string.
    """
    result = html
    for patch in patches:
        if patch.get("target") != "html":
            continue
        action = patch.get("action", "")
        selector = patch.get("selector", "")
        content = patch.get("content", "")

        if action == "insert_before":
            result = _insert_before(result, selector, content)
        elif action == "replace":
            result = _replace(result, selector, content)
        elif action == "remove":
            result = _remove(result, selector)
        # Unknown actions silently skipped

    return result


# ---------------------------------------------------------------------------
# Patch actions
# ---------------------------------------------------------------------------


def _insert_before(html: str, selector: str, content: str) -> str:
    """Insert *content* immediately before the first occurrence of *selector*.

    Idempotent: if *content* already appears in the HTML, this is a no-op.
    """
    # Idempotency check: if the content is already present, skip
    if content in html:
        return html

    # Handle </body> selector specifically
    if selector.lower() == "</body>":
        idx = html.lower().find("</body>")
        if idx == -1:
            return html
        return html[:idx] + content + "\n" + html[idx:]

    # Generic: find first occurrence and insert before
    idx = html.find(selector)
    if idx == -1:
        return html
    return html[:idx] + content + "\n" + html[idx:]


def _replace(html: str, selector: str, content: str) -> str:
    """Replace occurrences of *selector* text with *content*.

    Used for forbidden claim removal: selector is the claim text, content
    is the neutral fallback.

    Idempotent: if the selector text is no longer present, this is a no-op.
    """
    # Use case-insensitive regex to match the selector regardless of case.
    try:
        pattern = re.compile(re.escape(selector), re.IGNORECASE)
        if not pattern.search(html):
            return html
        return pattern.sub(content, html)
    except re.error:
        # Fallback to literal replacement
        if selector not in html:
            return html
        return html.replace(selector, content)


def _remove(html: str, selector: str) -> str:
    """Remove elements matching *selector* from the HTML.

    The selector can be:
      - An exact HTML string (e.g. ``<div class="x">text</div>``) — removed literally.
      - A bare tag name pattern (e.g. ``<div>``) — removes the full element.

    Idempotent: if no match found, returns unchanged HTML.
    """
    # First try exact string removal
    if selector in html:
        return html.replace(selector, "")

    # Then try tag-based removal if selector looks like an HTML tag
    if selector.startswith("<") and selector.endswith(">"):
        tag_name = re.sub(r"[<>/]", "", selector).strip()
        # Only use the tag name part (ignore attributes for broader matching)
        tag_name = tag_name.split()[0] if tag_name else ""
        if tag_name:
            pattern = re.compile(
                rf"<{tag_name}[^>]*>.*?</{tag_name}>",
                re.IGNORECASE | re.DOTALL,
            )
            return pattern.sub("", html)

    # Text-based removal (already handled above)
    return html
