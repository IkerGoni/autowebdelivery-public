"""Protective test: Stitch prompt templates must be facts-only.

Sprint S1-T4 (finding U-02). The prompt files under
``packages/templates/stitch_prompts/`` may contain structure, layout, tone
guidance, and ``{{verified_field}}`` placeholders only. Any instruction that
implies a default business fact (invented prices, certifications, availability
claims, warranty/financing defaults, promotional discounts) must fail CI.

Line-level policy: lines that carry the omission policy itself ("Never
display...", "only if ... verified") legitimately mention the banned concepts,
so keyword scans apply to content lines; structural hazards (price literals,
contact literals, literal years) are banned everywhere.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = PROJECT_ROOT / "packages" / "templates" / "stitch_prompts"

# Banned everywhere, even on policy lines: these never belong in compliant text.
HARD_BANS: dict[str, re.Pattern[str]] = {
    "price_literal": re.compile(r"\$\s?\d"),
    "phone_literal": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),
    "tel_literal": re.compile(r"\btel:\+?\d{7,}\b"),
    "email_literal": re.compile(r"[A-Za-z0-9._%+-]+@(?!example\.com)[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "certification_name": re.compile(r"\b(?:NATE|EPA)\b"),
    "literal_year": re.compile(r"\b(?:19|20)\d{2}\b"),
}

# Banned on content lines only: the policy sentences legitimately name them.
POLICY_LINE_MARKERS = (
    "never",
    "omit",
    "only if",
    "only when",
    "unless",
    "do not",
    "facts-only",
    "verified field",
)

CONTENT_LINE_BANS: dict[str, re.Pattern[str]] = {
    "certification_claim": re.compile(
        r"\b(?:licensed|insured|bonded|certified|certification|certifications|accredited|licensure|license)\b",
        re.IGNORECASE,
    ),
    "availability_claim": re.compile(
        r"\b(?:24/7|24-7|around[- ]the[- ]clock|always available|emergency service)\b",
        re.IGNORECASE,
    ),
    "offer_default": re.compile(
        r"\b(?:warrant(?:y|ies)|guarantee|financing|discount|starting price|price range|flat rate|special offer)\b",
        re.IGNORECASE,
    ),
}

PLACEHOLDER = re.compile(r"\{\{[^}]*\}\}")


def _prompt_files() -> list[Path]:
    return sorted(PROMPTS_DIR.glob("*.md"))


def _is_policy_line(line: str) -> bool:
    lowered = line.lower()
    return any(marker in lowered for marker in POLICY_LINE_MARKERS)


def _scan_prompt(text: str) -> list[str]:
    """Return violations for a prompt file body (placeholders removed)."""
    violations: list[str] = []
    body = PLACEHOLDER.sub("", text)
    for label, pattern in HARD_BANS.items():
        matches = pattern.findall(body)
        if matches:
            violations.append(f"{label}: {sorted(set(matches))[:5]}")
    for i, line in enumerate(text.splitlines(), start=1):
        if _is_policy_line(line):
            continue
        stripped = PLACEHOLDER.sub("", line)
        for label, pattern in CONTENT_LINE_BANS.items():
            matches = pattern.findall(stripped)
            if matches:
                violations.append(f"{label}: line {i}: {sorted(set(matches))[:5]}")
    return violations


def test_prompt_files_exist() -> None:
    files = _prompt_files()
    assert {p.name for p in files} >= {"auto_detailing.md", "hvac.md", "plumbing.md"}


@pytest.mark.parametrize("path", _prompt_files(), ids=lambda p: p.name)
def test_stitch_prompt_contains_no_unverified_defaults(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    violations = _scan_prompt(text)
    assert not violations, f"{path.name} contains unverified factual defaults: {violations}"


@pytest.mark.parametrize("path", _prompt_files(), ids=lambda p: p.name)
def test_stitch_prompt_keeps_structure_and_verified_placeholders(path: Path) -> None:
    """Facts-only must not mean structure-less: layout guidance and verified
    placeholders must remain."""
    text = path.read_text(encoding="utf-8")
    assert "## Layout Structure" in text
    assert "{{business_name}}" in text
    assert "{{city}}" in text
    assert "{{verified_field}}" in text or "verified field" in text.lower()


# ---------------------------------------------------------------------------
# Negative controls: the scanner must catch reintroduced defaults.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("injected", "expected_label"),
    [
        ("Ceramic Coating ($599+ 5-year protection)", "price_literal"),
        ("NATE certified technicians", "certification_name"),
        ("licensed & insured team", "certification_claim"),
        ("24/7 Emergency Service", "availability_claim"),
        ("Include warranty where applicable", "offer_default"),
        ("Call 555-012-3456 today", "phone_literal"),
        ("Serving the area since 2015", "literal_year"),
        ("Email us at bookings@autodetail.example.com", "email_literal"),
    ],
)
def test_negative_control_scanner_catches_reintroduced_defaults(injected: str, expected_label: str) -> None:
    template = (
        "# Stitch Prompt Template: X\n\n"
        "Facts-only policy: this prompt contains structure, layout, and tone guidance only.\n"
        "## Layout Structure\n\n"
        "1. HERO section: headline for {{business_name}} in {{city}}\n"
        f"2. TRUST section: {injected}\n"
    )
    violations = _scan_prompt(template)
    labels = {v.split(":")[0] for v in violations}
    # (labels are parsed from the violation strings below.)
    assert expected_label in labels, f"expected {expected_label}, got {labels} (violations: {violations})"
