"""VNEXT-07 — CSS Patch Engine.

Applies deterministic CSS patches (overflow fix, spacing fix) to a site's
HTML by modifying inline ``<style>`` blocks.  Only approved CSS-related
patch categories are processed.

Idempotency guarantee: applying the same patch twice is a no-op.
"""

from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_css_patches(html: str, patches: list[dict[str, Any]]) -> str:
    """Apply CSS-related patches to the site HTML (inline <style> modifications).

    Only patches with ``target == "css"`` and action ``insert_css`` are
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
        if patch.get("target") != "css":
            continue
        action = patch.get("action", "")
        content = patch.get("content", "")

        if action != "insert_css":
            continue

        category = patch.get("category", "")

        if category == "mobile_overflow_css_fix":
            result = _fix_overflow(result)
        elif category == "spacing_adjustment":
            result = _fix_spacing(result, content)
        # Unknown categories silently skipped

    return result


# ---------------------------------------------------------------------------
# CSS fix functions
# ---------------------------------------------------------------------------


def _fix_overflow(html: str) -> str:
    """Add ``overflow-x: hidden`` to body style if not already present.

    Idempotent: if the rule already exists, this is a no-op.
    """
    # Check if overflow-x:hidden already present
    if re.search(r"overflow-x\s*:\s*hidden", html, re.IGNORECASE):
        return html

    css_rule = "body{overflow-x:hidden!important;}"

    # Find existing <style> block and append
    style_pattern = re.compile(r"(<style[^>]*>)(.*?)(</style>)", re.IGNORECASE | re.DOTALL)
    match = style_pattern.search(html)

    if match:
        existing_css = match.group(2)
        new_css = existing_css + "\n" + css_rule + "\n"
        return html[:match.start()] + match.group(1) + new_css + match.group(3) + html[match.end():]

    # No <style> block — inject one before </head>
    head_close = html.lower().find("</head>")
    if head_close != -1:
        style_block = f"<style>{css_rule}</style>\n"
        return html[:head_close] + style_block + html[head_close:]

    # No </head> — inject before </body>
    body_close = html.lower().find("</body>")
    if body_close != -1:
        style_block = f"<style>{css_rule}</style>\n"
        return html[:body_close] + style_block + html[body_close:]

    # Last resort: append
    return html + f"\n<style>{css_rule}</style>"


def _fix_spacing(html: str, css_content: str = "") -> str:
    """Add spacing CSS rules for sections if not already present.

    Uses the provided ``css_content`` or a sensible default.

    Idempotent: if similar spacing rules already exist, this is a no-op.
    """
    default_spacing = "section{padding-top:1.5rem;padding-bottom:1.5rem;}"
    css_rule = css_content.strip() if css_content else default_spacing

    # Idempotency: check if section padding already set
    if re.search(r"section\s*\{[^}]*padding-top", html, re.IGNORECASE):
        return html

    # Find existing <style> block and append
    style_pattern = re.compile(r"(<style[^>]*>)(.*?)(</style>)", re.IGNORECASE | re.DOTALL)
    match = style_pattern.search(html)

    if match:
        existing_css = match.group(2)
        new_css = existing_css + "\n" + css_rule + "\n"
        return html[:match.start()] + match.group(1) + new_css + match.group(3) + html[match.end():]

    # No <style> block — inject one before </head>
    head_close = html.lower().find("</head>")
    if head_close != -1:
        style_block = f"<style>{css_rule}</style>\n"
        return html[:head_close] + style_block + html[head_close:]

    # No </head> — inject before </body>
    body_close = html.lower().find("</body>")
    if body_close != -1:
        style_block = f"<style>{css_rule}</style>\n"
        return html[:body_close] + style_block + html[body_close:]

    # Last resort: append
    return html + f"\n<style>{css_rule}</style>"
