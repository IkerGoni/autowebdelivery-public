"""HTML sanitizer for Stitch/Gemini-generated websites.

Scans FULL HTML source (hidden elements, attributes, comments, data-attrs)
for fabricated content, unsafe claims, and security risks. Patches HTML
in-place and produces a sanitizer_report.json artifact.

Runs BEFORE Phase 06 so downstream validators see clean content.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SanitizationRule:
    """A single sanitization rule."""

    name: str
    category: str  # "fake_contact", "certification", "review_rating", "trust_claim", "orphaned_html", "security"
    description: str


@dataclass
class SanitizationFinding:
    """A single finding from sanitization."""

    rule_name: str
    category: str
    severity: str  # "hard_block", "removed", "replaced", "warning"
    element_tag: str
    element_text_preview: str  # first 100 chars
    action_taken: str
    line_hint: int | None = None


@dataclass
class SanitizationResult:
    """Complete sanitization result."""

    original_html: str
    sanitized_html: str
    findings: list[SanitizationFinding] = field(default_factory=list)
    hard_block: bool = False
    hard_block_reasons: list[str] = field(default_factory=list)
    removals_count: int = 0
    replacements_count: int = 0


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

_FAKE_555_PHONE = re.compile(r"\b555[.\-\s]?01\d{2}\b", re.IGNORECASE)
# Broad US phone: (xxx) xxx-xxxx, xxx-xxx-xxxx, xxx.xxx.xxxx, +1 xxx-xxx-xxxx
_PHONE_PATTERN = re.compile(
    r"(?:\+?1[\s.\-]?)?"
    r"(?:\(?\d{3}\)?[\s.\-]?)"
    r"\d{3}[\s.\-]?\d{4}\b"
)
_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z]{2,}", re.IGNORECASE)
_TEL_LINK = re.compile(r"tel:\s*[\+\d\s\-().]+", re.IGNORECASE)
_MAILTO_LINK = re.compile(r"mailto:\s*[^\s\"']+", re.IGNORECASE)

_CERTIFICATION_PATTERNS = [
    re.compile(r"\bcertified\b", re.IGNORECASE),
    re.compile(r"\baccredited\b", re.IGNORECASE),
    re.compile(r"\blicensed\b", re.IGNORECASE),
    re.compile(r"\binsured\b", re.IGNORECASE),
]

_REVIEW_RATING_PATTERNS = [
    re.compile(r"\b5[\s\-]?star\b", re.IGNORECASE),
    re.compile(r"\bfive[\s\-]?star\b", re.IGNORECASE),
    re.compile(r"\d+\+?\s*reviews?\b", re.IGNORECASE),
    re.compile(r"customer\s+says?\b", re.IGNORECASE),
    re.compile(r"review\s+says?\b", re.IGNORECASE),
    re.compile(r"\btestimonials?\b", re.IGNORECASE),
]
_STAR_CHARS = {"★", "⭐", "✦", "✧", "☆"}

_TRUST_CLAIM_PATTERNS = [
    re.compile(r"\bbest\s+(in|around|for|service|quality|choice|deal|price)\b", re.IGNORECASE),
    re.compile(r"\bthe\s+best\b", re.IGNORECASE),
    re.compile(r"#1\b", re.IGNORECASE),
    re.compile(r"\btop[\s\-]?rated\b", re.IGNORECASE),
    re.compile(r"\btrusted\s+by\s+(\d|thousands|millions|many|countless|locals)", re.IGNORECASE),
    re.compile(r"\bpremier\b", re.IGNORECASE),
    re.compile(r"\belite\b", re.IGNORECASE),
    re.compile(r"\baward[\s\-]?winning\b", re.IGNORECASE),
    re.compile(r"\bguaranteed?\b", re.IGNORECASE),
    re.compile(r"\b\d+\s*years?\s+(?:in\s+business|of\s+experience)\b", re.IGNORECASE),
    re.compile(r"\bestablished\s+in\b", re.IGNORECASE),
    re.compile(r"\bsince\s+\d{4}\b", re.IGNORECASE),
    re.compile(r"\bofficial\s+partner\b", re.IGNORECASE),
    re.compile(r"\bfamily[\s\-]?owned\s+(?:and|since|for|business)", re.IGNORECASE),
]

_STITCH_DATA_ATTR = re.compile(r"^data-(stitch|screen|component)-", re.IGNORECASE)
_STITCH_COMMENT = re.compile(r"stitch|data-screen|data-component", re.IGNORECASE)

_EVENT_HANDLER_ATTR = re.compile(r"^on[a-z]+$", re.IGNORECASE)
_DANGEROUS_URL = re.compile(r"^\s*(javascript|vbscript)\s*:", re.IGNORECASE)
_DATA_URL_DANGEROUS = re.compile(r"^\s*data\s*:(?!image/)", re.IGNORECASE)

_URL_ATTRS = frozenset({"href", "src", "action", "formaction", "poster",
    "dynsrc", "lowsrc", "srcset", "xlink:href", "data", "codebase",
    "cite", "background", "ping"})

_DANGEROUS_CSS_PATTERNS = [
    re.compile(r"@import\s", re.IGNORECASE),
    re.compile(r"expression\s*\(", re.IGNORECASE),
    re.compile(r"url\s*\(\s*[\"']?\s*(javascript|vbscript|data)\s*:", re.IGNORECASE),
    re.compile(r"-moz-binding", re.IGNORECASE),
]

_DANGEROUS_TAGS = frozenset({"script", "iframe", "embed", "object"})
_SECURITY_TAGS = frozenset({"script", "iframe", "embed", "object"})

# Safe script source patterns — CDNs considered safe for controlled deployment
_SAFE_SCRIPT_DOMAINS = frozenset({
    "cdn.tailwindcss.com",
    "cdnjs.cloudflare.com",
    "fonts.googleapis.com",
    "ajax.googleapis.com",
    "code.jquery.com",
    "unpkg.com",
    "cdn.jsdelivr.net",
    "kit.fontawesome.com",
})
_SAFE_SCRIPT_TYPES = frozenset({
    "application/ld+json",
    "application/json",
})
# Tailwind config pattern: inline config block
_TAILWIND_CONFIG_RE = re.compile(r"tailwind\.config\s*=", re.IGNORECASE)
# Structural tags should not be removed based on text content of descendants
_STRUCTURAL_TAGS = frozenset({"html", "head", "body", "main", "header", "footer", "nav", "article", "aside"})

_VOID_ELEMENTS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
})

_NEUTRAL_PHONE_CTA = "Contact for availability"
_NEUTRAL_EMAIL_CTA = "Request a quote"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_phone(phone: str) -> str:
    """Strip non-digit chars and leading country code '1' for comparison."""
    digits = re.sub(r"\D", "", phone)
    # Strip leading US country code for consistent matching
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def _preview(text: str, maxlen: int = 100) -> str:
    text = text.replace("\n", " ").strip()
    return text[:maxlen] if len(text) > maxlen else text


def _has_star_chars(text: str) -> bool:
    return any(ch in text for ch in _STAR_CHARS)


# ---------------------------------------------------------------------------
# HTML tokeniser — produces a token stream we can filter
# ---------------------------------------------------------------------------

_TOKEN_START = "start"
_TOKEN_END = "end"
_TOKEN_DATA = "data"
_TOKEN_COMMENT = "comment"
_TOKEN_DECL = "decl"
_TOKEN_PI = "pi"
_TOKEN_STARTEND = "startend"  # self-closing like <br/>


@dataclass
class _Token:
    kind: str
    tag: str = ""
    attrs: list[tuple[str, str | None]] = field(default_factory=list)
    data: str = ""
    line: int = 0


class _Tokenizer(HTMLParser):
    """Turn HTML into a flat token list."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.tokens: list[_Token] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        line, _ = self.getpos()
        self.tokens.append(_Token(kind=_TOKEN_START, tag=tag.lower(), attrs=list(attrs), line=line))

    def handle_endtag(self, tag: str) -> None:
        line, _ = self.getpos()
        self.tokens.append(_Token(kind=_TOKEN_END, tag=tag.lower(), line=line))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        line, _ = self.getpos()
        self.tokens.append(_Token(kind=_TOKEN_STARTEND, tag=tag.lower(), attrs=list(attrs), line=line))

    def handle_data(self, data: str) -> None:
        line, _ = self.getpos()
        self.tokens.append(_Token(kind=_TOKEN_DATA, data=data, line=line))

    def handle_entityref(self, name: str) -> None:
        line, _ = self.getpos()
        self.tokens.append(_Token(kind=_TOKEN_DATA, data=f"&{name};", line=line))

    def handle_charref(self, name: str) -> None:
        line, _ = self.getpos()
        self.tokens.append(_Token(kind=_TOKEN_DATA, data=f"&#{name};", line=line))

    def handle_comment(self, data: str) -> None:
        line, _ = self.getpos()
        self.tokens.append(_Token(kind=_TOKEN_COMMENT, data=data, line=line))

    def handle_decl(self, decl: str) -> None:
        line, _ = self.getpos()
        self.tokens.append(_Token(kind=_TOKEN_DECL, data=decl, line=line))

    def handle_pi(self, data: str) -> None:
        line, _ = self.getpos()
        self.tokens.append(_Token(kind=_TOKEN_PI, data=data, line=line))


def _tokenize(html: str) -> list[_Token]:
    t = _Tokenizer()
    t.feed(html)
    return t.tokens


def _render(tokens: list[_Token]) -> str:
    """Render token list back to HTML string."""
    parts: list[str] = []
    for tok in tokens:
        if tok.kind == _TOKEN_START:
            attr_str = _render_attrs(tok.attrs)
            parts.append(f"<{tok.tag}{attr_str}>")
        elif tok.kind == _TOKEN_END:
            parts.append(f"</{tok.tag}>")
        elif tok.kind == _TOKEN_STARTEND:
            attr_str = _render_attrs(tok.attrs)
            parts.append(f"<{tok.tag}{attr_str} />")
        elif tok.kind == _TOKEN_DATA:
            parts.append(tok.data)
        elif tok.kind == _TOKEN_COMMENT:
            parts.append(f"<!--{tok.data}-->")
        elif tok.kind == _TOKEN_DECL:
            parts.append(f"<!{tok.data}>")
        elif tok.kind == _TOKEN_PI:
            parts.append(f"<?{tok.data}>")
    return "".join(parts)


def _render_attrs(attrs: list[tuple[str, str | None]]) -> str:
    parts: list[str] = []
    for name, val in attrs:
        if val is None:
            parts.append(f" {name}")
        else:
            escaped = (val.replace("&", "&amp;")
                          .replace('"', "&quot;")
                          .replace("<", "&lt;")
                          .replace(">", "&gt;"))
            parts.append(f' {name}="{escaped}"')
    return "".join(parts)


def _normalize_url_for_check(val: str) -> str:
    """Strip whitespace/null chars that can obfuscate URL schemes."""
    return re.sub(r'[\t\n\r\x00]', '', val)


def _is_dangerous_url(val: str) -> bool:
    """Check if URL value uses a dangerous scheme."""
    normalized = _normalize_url_for_check(val)
    return bool(_DANGEROUS_URL.match(normalized) or _DATA_URL_DANGEROUS.match(normalized))


def _has_dangerous_css(css_text: str) -> str | None:
    """Return description of dangerous CSS pattern found, or None."""
    for pat in _DANGEROUS_CSS_PATTERNS:
        m = pat.search(css_text)
        if m:
            return m.group()
    return None


# ---------------------------------------------------------------------------
# Element span helpers
# ---------------------------------------------------------------------------

def _find_element_end(tokens: list[_Token], start_idx: int) -> int:
    """Find closing tag index for element starting at *start_idx*.

    Returns the index of the matching end-tag, or start_idx if self-closing/void.
    """
    tok = tokens[start_idx]
    if tok.kind == _TOKEN_STARTEND or tok.tag in _VOID_ELEMENTS:
        return start_idx
    tag = tok.tag
    depth = 1
    i = start_idx + 1
    while i < len(tokens):
        t = tokens[i]
        if t.kind == _TOKEN_START and t.tag == tag:
            depth += 1
        elif t.kind == _TOKEN_END and t.tag == tag:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return start_idx  # unmatched — treat as self-contained


def _element_text(tokens: list[_Token], start: int, end: int) -> str:
    """Gather all text data between start and end indices."""
    parts = []
    for i in range(start, end + 1):
        if tokens[i].kind == _TOKEN_DATA:
            parts.append(tokens[i].data)
    return " ".join(parts)


def _mark_range(removed: list[bool], start: int, end: int) -> None:
    for i in range(start, end + 1):
        removed[i] = True


# ---------------------------------------------------------------------------
# Core sanitizer
# ---------------------------------------------------------------------------

def sanitize_html(
    html: str,
    verified_facts: dict[str, Any] | None = None,
    strict: bool = True,
) -> SanitizationResult:
    """Sanitize generated HTML for factual safety and security.

    When *verified_facts* are provided (template path), only removes
    genuinely dangerous elements (scripts, event handlers, dangerous URLs).
    Content-level checks (certs, reviews, trust claims) are skipped because
    template-generated HTML only uses verified facts.

    When *verified_facts* is empty/None (Stitch path), runs full checks.
    """
    if verified_facts is None:
        verified_facts = {}

    tokens = _tokenize(html)
    n = len(tokens)
    removed = [False] * n  # marks tokens to drop
    findings: list[SanitizationFinding] = []
    removals = 0
    replacements = 0

    verified_phone_digits = _normalize_phone(verified_facts["phone"]) if "phone" in verified_facts else None
    verified_email = (verified_facts.get("email") or "").lower() or None
    _verified_address = (verified_facts.get("address") or "").lower() or None  # reserved for future use
    _verified_review_count = verified_facts.get("review_count")  # reserved for future use
    certified_ok = bool(verified_facts.get("certified"))
    licensed_ok = bool(verified_facts.get("licensed"))
    insured_ok = bool(verified_facts.get("insured"))
    accredited_ok = bool(verified_facts.get("accredited"))

    # When verified facts exist (template path), skip content-level checks.
    # Only run security checks. Content-level checks are for Stitch-generated
    # HTML where hallucination risk is high.
    # Empty dict {} means no verified facts (Stitch path) — run all checks.
    has_verified_facts = bool(verified_facts) and "business_name" in verified_facts

    # --- Pass 1: element-level removals (security, certs, reviews, trust) ---
    i = 0
    while i < n:
        tok = tokens[i]

        # -- security: dangerous tags --
        if tok.kind == _TOKEN_START and tok.tag in _SECURITY_TAGS:
            end_idx = _find_element_end(tokens, i)
            text = _element_text(tokens, i, end_idx)
            findings.append(SanitizationFinding(
                rule_name=f"security_{tok.tag}",
                category="security",
                severity="removed",
                element_tag=tok.tag,
                element_text_preview=_preview(text),
                action_taken=f"Removed <{tok.tag}> element",
                line_hint=tok.line,
            ))
            _mark_range(removed, i, end_idx)
            removals += 1
            i = end_idx + 1
            continue

        # -- start-tag attribute checks --
        if tok.kind in (_TOKEN_START, _TOKEN_STARTEND):
            new_attrs: list[tuple[str, str | None]] = []
            for attr_name, attr_val in tok.attrs:
                val_str = attr_val or ""

                # event handlers
                if _EVENT_HANDLER_ATTR.match(attr_name):
                    findings.append(SanitizationFinding(
                        rule_name="security_event_handler",
                        category="security",
                        severity="removed",
                        element_tag=tok.tag,
                        element_text_preview=_preview(f'{attr_name}="{val_str}"'),
                        action_taken=f"Removed {attr_name} attribute",
                        line_hint=tok.line,
                    ))
                    removals += 1
                    continue

                # dangerous URL schemes (javascript:, vbscript:, data:)
                if attr_name in _URL_ATTRS and _is_dangerous_url(val_str):
                    findings.append(SanitizationFinding(
                        rule_name="security_javascript_url",
                        category="security",
                        severity="removed",
                        element_tag=tok.tag,
                        element_text_preview=_preview(f'{attr_name}="{val_str}"'),
                        action_taken=f"Removed dangerous URL from {attr_name}",
                        line_hint=tok.line,
                    ))
                    new_attrs.append((attr_name, "#"))
                    removals += 1
                    continue

                # stitch data attributes
                if _STITCH_DATA_ATTR.match(attr_name):
                    findings.append(SanitizationFinding(
                        rule_name="stitch_data_attr",
                        category="orphaned_html",
                        severity="removed",
                        element_tag=tok.tag,
                        element_text_preview=_preview(f'{attr_name}="{val_str}"'),
                        action_taken=f"Removed Stitch attribute {attr_name}",
                        line_hint=tok.line,
                    ))
                    removals += 1
                    continue

                # tel: / mailto: links with unverified data
                if attr_name == "href":
                    tel_m = _TEL_LINK.match(val_str)
                    if tel_m:
                        phone_digits = _normalize_phone(val_str)
                        if verified_phone_digits and phone_digits == verified_phone_digits:
                            new_attrs.append((attr_name, attr_val))
                            continue
                        findings.append(SanitizationFinding(
                            rule_name="fake_tel_link",
                            category="fake_contact",
                            severity="replaced",
                            element_tag=tok.tag,
                            element_text_preview=_preview(val_str),
                            action_taken="Replaced tel: link with #",
                            line_hint=tok.line,
                        ))
                        new_attrs.append((attr_name, "#"))
                        replacements += 1
                        continue

                    mailto_m = _MAILTO_LINK.match(val_str)
                    if mailto_m:
                        email_in_link = val_str.split(":", 1)[1].strip().lower()
                        if verified_email and email_in_link == verified_email:
                            new_attrs.append((attr_name, attr_val))
                            continue
                        findings.append(SanitizationFinding(
                            rule_name="fake_mailto_link",
                            category="fake_contact",
                            severity="replaced",
                            element_tag=tok.tag,
                            element_text_preview=_preview(val_str),
                            action_taken="Replaced mailto: link with #",
                            line_hint=tok.line,
                        ))
                        new_attrs.append((attr_name, "#"))
                        replacements += 1
                        continue

                new_attrs.append((attr_name, attr_val))

            tok.attrs = new_attrs  # type: ignore[misc]

            # C6: <meta http-equiv="refresh"> with javascript: URL
            if tok.tag == "meta":
                http_equiv = ""
                content_val = ""
                for a_name, a_val in new_attrs:
                    if a_name.lower() == "http-equiv":
                        http_equiv = (a_val or "").lower()
                    if a_name.lower() == "content":
                        content_val = a_val or ""
                if http_equiv == "refresh":
                    refresh_url = content_val
                    url_match = re.search(r'url\s*=\s*', content_val, re.IGNORECASE)
                    if url_match:
                        refresh_url = content_val[url_match.end():]
                    if _is_dangerous_url(refresh_url):
                        findings.append(SanitizationFinding(
                            rule_name="security_meta_refresh",
                            category="security",
                            severity="removed",
                            element_tag=tok.tag,
                            element_text_preview=_preview(content_val),
                            action_taken="Removed <meta> with dangerous refresh URL",
                            line_hint=tok.line,
                        ))
                        removed[i] = True
                        removals += 1
                        i += 1
                        continue

        # -- C5: <style> tag CSS injection check --
        if tok.kind == _TOKEN_START and tok.tag == "style":
            end_idx = _find_element_end(tokens, i)
            css_text = _element_text(tokens, i, end_idx)
            danger = _has_dangerous_css(css_text)
            if danger:
                findings.append(SanitizationFinding(
                    rule_name="security_dangerous_css",
                    category="security",
                    severity="removed",
                    element_tag="style",
                    element_text_preview=_preview(css_text),
                    action_taken=f"Removed <style> with dangerous CSS: {danger}",
                    line_hint=tok.line,
                ))
                _mark_range(removed, i, end_idx)
                removals += 1
                i = end_idx + 1
                continue

        # -- element-level text content checks (ONLY for Stitch-generated HTML) --
        if not has_verified_facts and tok.kind == _TOKEN_START and tok.tag not in _VOID_ELEMENTS:
            end_idx = _find_element_end(tokens, i)
            text = _element_text(tokens, i, end_idx)
            text_stripped = text.strip()

            # Also gather attribute text for class/id-based detection
            attr_text = " ".join(v for _, v in tok.attrs if v) if tok.attrs else ""

            if not text_stripped and tok.tag in ("div", "section", "span", "p"):
                # Check if there are any non-data children (like img)
                has_child_elements = any(
                    tokens[j].kind in (_TOKEN_START, _TOKEN_STARTEND)
                    for j in range(i + 1, end_idx)
                    if not removed[j]
                )
                if not has_child_elements:
                    findings.append(SanitizationFinding(
                        rule_name="orphaned_empty_element",
                        category="orphaned_html",
                        severity="removed",
                        element_tag=tok.tag,
                        element_text_preview="(empty)",
                        action_taken=f"Removed empty <{tok.tag}>",
                        line_hint=tok.line,
                    ))
                    _mark_range(removed, i, end_idx)
                    removals += 1
                    i = end_idx + 1
                    continue

            # Skip structural tags for content-based removal (would remove entire page)
            if tok.tag in _STRUCTURAL_TAGS:
                i += 1
                continue

            # certification checks
            should_remove_cert = False
            for pat in _CERTIFICATION_PATTERNS:
                if pat.search(text):
                    # Check if this specific certification is allowed
                    matched_word = pat.pattern.replace(r"\b", "").lower()
                    if matched_word == "certified" and certified_ok:
                        continue
                    if matched_word == "licensed" and licensed_ok:
                        continue
                    if matched_word == "insured" and insured_ok:
                        continue
                    if matched_word == "accredited" and accredited_ok:
                        continue
                    should_remove_cert = True
                    break

            if should_remove_cert:
                findings.append(SanitizationFinding(
                    rule_name="unsupported_certification",
                    category="certification",
                    severity="removed",
                    element_tag=tok.tag,
                    element_text_preview=_preview(text),
                    action_taken=f"Removed <{tok.tag}> with unsupported certification claim",
                    line_hint=tok.line,
                ))
                _mark_range(removed, i, end_idx)
                removals += 1
                i = end_idx + 1
                continue

            # review/rating checks — only remove clearly fabricated content.
            # Factual rating mentions like "Rated 4.8 from 150 reviews" are OK.
            # We also remove: 5-star/five-star claims, review count mentions,
            # testimonial sections, fake star displays, review quotes.
            should_remove_review = False
            combined_text = text + " " + attr_text

            # Check review rating patterns (5-star, five-star, review counts, etc.)
            for pat in _REVIEW_RATING_PATTERNS:
                if pat.search(text):
                    # Allow factual "Rated X from Y reviews" format
                    is_factual_rating = bool(re.search(r"rated\s+\d", text, re.IGNORECASE))
                    # Allow exact review count match when verified
                    if _verified_review_count is not None:
                        is_exact_count = str(_verified_review_count) in text and "+" not in text
                        if is_exact_count:
                            continue
                    if not is_factual_rating:
                        should_remove_review = True
                        break

            if not should_remove_review:
                # Only remove elements that are clearly fabricated review sections:
                # 1. Testimonial sections (class/id/name contains "testimonial")
                # 2. "Customer says" / "Review says" fake quotes
                # 3. Pure star character displays with no factual context
                is_testimonial_section = any(
                    kw in combined_text.lower() for kw in ("testimonial", "customer says", "review says", "what our clients say")
                )
                is_pure_star_display = _has_star_chars(text) and not any(
                    kw in text.lower() for kw in ("rated", "rating", "google", "review")
                )

                if is_testimonial_section or is_pure_star_display:
                    should_remove_review = True

            if should_remove_review:
                findings.append(SanitizationFinding(
                    rule_name="fabricated_review_rating",
                    category="review_rating",
                    severity="removed",
                    element_tag=tok.tag,
                    element_text_preview=_preview(text),
                    action_taken=f"Removed <{tok.tag}> with fabricated review/rating",
                    line_hint=tok.line,
                ))
                _mark_range(removed, i, end_idx)
                removals += 1
                i = end_idx + 1
                continue

            # trust claim checks
            should_remove_trust = False
            for pat in _TRUST_CLAIM_PATTERNS:
                if pat.search(text):
                    should_remove_trust = True
                    break

            if should_remove_trust:
                findings.append(SanitizationFinding(
                    rule_name="absolute_trust_claim",
                    category="trust_claim",
                    severity="removed",
                    element_tag=tok.tag,
                    element_text_preview=_preview(text),
                    action_taken=f"Removed <{tok.tag}> with absolute/trust claim",
                    line_hint=tok.line,
                ))
                _mark_range(removed, i, end_idx)
                removals += 1
                i = end_idx + 1
                continue

        i += 1

    # --- Pass 2: text-level contact info patching in surviving tokens ---
    for i in range(n):
        if removed[i]:
            continue
        tok = tokens[i]
        if tok.kind != _TOKEN_DATA:
            continue

        original_data = tok.data

        # 555-01xx fake phones — always remove
        if _FAKE_555_PHONE.search(tok.data):
            tok.data = _FAKE_555_PHONE.sub(_NEUTRAL_PHONE_CTA, tok.data)
            findings.append(SanitizationFinding(
                rule_name="fake_555_phone",
                category="fake_contact",
                severity="replaced",
                element_tag="(text)",
                element_text_preview=_preview(original_data),
                action_taken="Replaced 555-01xx phone with neutral CTA",
                line_hint=tok.line,
            ))
            replacements += 1

        # Other phone numbers — keep only verified
        phone_matches = list(_PHONE_PATTERN.finditer(tok.data))
        for pm in reversed(phone_matches):
            matched_digits = _normalize_phone(pm.group())
            if verified_phone_digits and matched_digits == verified_phone_digits:
                continue  # verified, keep it
            # Replace
            tok.data = tok.data[:pm.start()] + _NEUTRAL_PHONE_CTA + tok.data[pm.end():]
            findings.append(SanitizationFinding(
                rule_name="unverified_phone",
                category="fake_contact",
                severity="replaced",
                element_tag="(text)",
                element_text_preview=_preview(pm.group()),
                action_taken="Replaced unverified phone with neutral CTA",
                line_hint=tok.line,
            ))
            replacements += 1

        # Emails
        email_matches = list(_EMAIL_PATTERN.finditer(tok.data))
        for em in reversed(email_matches):
            if verified_email and em.group().lower() == verified_email:
                continue
            tok.data = tok.data[:em.start()] + _NEUTRAL_EMAIL_CTA + tok.data[em.end():]
            findings.append(SanitizationFinding(
                rule_name="unverified_email",
                category="fake_contact",
                severity="replaced",
                element_tag="(text)",
                element_text_preview=_preview(em.group()),
                action_taken="Replaced unverified email with neutral CTA",
                line_hint=tok.line,
            ))
            replacements += 1

    # --- Pass 3: comment stripping for stitch markers ---
    for i in range(n):
        if removed[i]:
            continue
        tok = tokens[i]
        if tok.kind == _TOKEN_COMMENT and _STITCH_COMMENT.search(tok.data):
            removed[i] = True
            findings.append(SanitizationFinding(
                rule_name="stitch_comment",
                category="orphaned_html",
                severity="removed",
                element_tag="(comment)",
                element_text_preview=_preview(tok.data),
                action_taken="Removed Stitch comment marker",
                line_hint=tok.line,
            ))
            removals += 1

    # --- Build output ---
    surviving = [tokens[i] for i in range(n) if not removed[i]]
    sanitized = _render(surviving)

    # --- Post-sanitization security verification ---
    hard_block = False
    hard_block_reasons: list[str] = []
    verify_tokens = _tokenize(sanitized)
    for vt in verify_tokens:
        if vt.kind == _TOKEN_START and vt.tag in _SECURITY_TAGS:
            hard_block = True
            reason = f"<{vt.tag}> tag survived sanitization"
            hard_block_reasons.append(reason)
        if vt.kind in (_TOKEN_START, _TOKEN_STARTEND):
            for attr_name, attr_val in vt.attrs:
                if _EVENT_HANDLER_ATTR.match(attr_name):
                    hard_block = True
                    hard_block_reasons.append(f"Event handler {attr_name} survived sanitization")
                if attr_name in _URL_ATTRS and attr_val and _is_dangerous_url(attr_val):
                    hard_block = True
                    hard_block_reasons.append(f"Dangerous URL survived in {attr_name}")

    # Upgrade severity of security findings if hard_block
    if hard_block:
        for f in findings:
            if f.category == "security":
                f.severity = "hard_block"

    return SanitizationResult(
        original_html=html,
        sanitized_html=sanitized,
        findings=findings,
        hard_block=hard_block,
        hard_block_reasons=hard_block_reasons,
        removals_count=removals,
        replacements_count=replacements,
    )


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_sanitizer_report(result: SanitizationResult, output_dir: Path) -> Path:
    """Write sanitizer_report.json artifact."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "sanitizer_report.json"

    report: dict[str, Any] = {
        "hard_block": result.hard_block,
        "hard_block_reasons": result.hard_block_reasons,
        "findings_count": len(result.findings),
        "findings": [asdict(f) for f in result.findings],
        "removals_count": result.removals_count,
        "replacements_count": result.replacements_count,
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report_path


def write_sanitized_html(result: SanitizationResult, output_path: Path) -> Path:
    """Write the patched index.html."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.sanitized_html, encoding="utf-8")
    return output_path
