"""Protective test: no modular template section may contain a hardcoded business fact.

Sprint S1-T4 (finding U-01/U-03). Encodes the facts-only template rule mechanically:

- every ``*.html`` file under ``packages/templates/modular/sections/`` is scanned
  (all families x variants x devices, enumerated via rglob so new sections are
  covered automatically) after removing ``{{...}}`` placeholders;
- violations: fake contact destinations, literal emails, prices, phone/tel
  literals, rating-like decimals, review-count literals, hardcoded schedules;
- a denylist of business names/claims removed during Sprint S1 guards against
  reintroduction;
- a render-level test composes every family (desktop + mobile) through the
  TemplateComposer with a distinctive fixture and asserts the only business
  facts present are the fixture's.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from packages.templates.modular.composer import TemplateComposer
from packages.templates.modular.models import BusinessData

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SECTIONS_DIR = PROJECT_ROOT / "packages" / "templates" / "modular" / "sections"

# Business facts removed during Sprint S1 (U-01/U-03). Reintroducing any of
# these must fail this suite. Extend when new hardcodes are removed.
REMOVED_FACTS_DENYLIST: tuple[str, ...] = (
    "Luxe Beauty Studio",
    "LUXE BEAUTY STUDIO",
    "LUXE STUDIO",
    "Smile Dental Clinic",
    "Smile Dental",
    "AUTO-PRO INDUSTRIAL",
    "AUTO-PRO SERVICE",
    "PRO AUTO SERVICE",
    "Spotless Home Cleaning",
    "Spotless Home",
    "Dependable Auto Repair",
    "Patient Choice Winner",
    "Aesthetic Avenue",
    "Elegance Blvd",
    "Wellness District",
    "Design District",
    "Healthcare Plaza",
    "Dental Way",
    "Industrial Way",
    "business@email.com",
)

# Patterns that indicate a hardcoded business fact outside {{...}} placeholders.
FACT_PATTERNS: dict[str, re.Pattern[str]] = {
    "fake_contact": re.compile(r"business@email\.com", re.IGNORECASE),
    "price_literal": re.compile(r"\$\s?\d"),
    "phone_literal": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),
    "tel_literal": re.compile(r"\btel:\+?\d{7,}\b"),
    # Ratings are 4.x/5.x; the lookbehind excludes CSS decimals (h-0.5, py-2.5,
    # 45.6). Arbitrary-value CSS like [4.5rem] is not used in these sections.
    "rating_literal": re.compile(r"(?<![\w.\-])[45]\.\d\b"),
    "review_count": re.compile(r"\b\d{2,}\+?\s*(?:verified\s+)?reviews\b", re.IGNORECASE),
    # Hardcoded schedules: "Mon - Sat: 9am", "7:00am", "Closed Mondays", "8:00 AM".
    "schedule_literal": re.compile(
        r"\b(?:Mon|Tues?|Wed(?:nes)?|Thurs?|Fri|Sat(?:ur)?|Sun)\w*\s*[-:]\s*\d"
        r"|\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b"
        r"|\bClosed\s+(?:Mondays?|Tuesdays?|Wednesdays?|Thursdays?|Fridays?|Saturdays?|Sundays?)\b",
        re.IGNORECASE,
    ),
}

PLACEHOLDER = re.compile(r"\{\{[^}]*\}\}")


def _all_section_files() -> list[Path]:
    return sorted(SECTIONS_DIR.rglob("*.html"))


def _strip_placeholders(text: str) -> str:
    return PLACEHOLDER.sub("", text)


def _scan_violations(text: str) -> list[str]:
    """Return human-readable violations for facts found in raw text."""
    violations: list[str] = []
    cleaned = _strip_placeholders(text)
    for label, pattern in FACT_PATTERNS.items():
        matches = pattern.findall(cleaned)
        if matches:
            violations.append(f"{label}: {sorted(set(matches))[:5]}")
    for fact in REMOVED_FACTS_DENYLIST:
        if fact in cleaned:
            violations.append(f"removed_fact_reintroduced: {fact!r}")
    return violations


def test_every_section_file_is_enumerated() -> None:
    """Guard the enumeration itself: the scanned population must be non-trivial."""
    files = _all_section_files()
    assert len(files) >= 80
    families = {p.relative_to(SECTIONS_DIR).parts[0] for p in files}
    assert {
        "clinical-trust",
        "common",
        "fresh-utility",
        "industrial-reliable",
        "warm-editorial",
    } <= families


@pytest.mark.parametrize("path", _all_section_files(), ids=lambda p: str(p.relative_to(SECTIONS_DIR)))
def test_section_has_no_hardcoded_business_facts(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    violations = _scan_violations(text)
    assert not violations, f"{path.relative_to(SECTIONS_DIR)} contains hardcoded facts: {violations}"


# ---------------------------------------------------------------------------
# Render-level checks: compose every family and verify only fixture facts.
# ---------------------------------------------------------------------------


def _fixture_business() -> BusinessData:
    return BusinessData(
        name="ACME Fixture Business Group",
        tagline="Fixture tagline for rendered output checks.",
        phone="(555) 010-7777",
        phone_raw="5550107777",
        address_line1="42 Fixture Lane",
        address_line2="Suite 7",
        city="Testville",
        state="TS",
        zip_code="00042",
        rating=4.2,
        review_count=77,
        trust_badge="Fixture Trust Badge",
    )


def _composable_families() -> list[str]:
    families = []
    for d in sorted(SECTIONS_DIR.iterdir()):
        if not d.is_dir():
            continue
        if (d / "header.html").exists() or (d / "header_mobile.html").exists():
            families.append(d.name)
    return families


@pytest.mark.parametrize("family", _composable_families())
@pytest.mark.parametrize("variant", ["desktop", "mobile"])
def test_composed_page_contains_only_fixture_facts(family: str, variant: str) -> None:
    composer = TemplateComposer()
    business = _fixture_business()
    html = composer.compose(family, business, variant)

    # No unresolved mustache placeholders survive composition.
    unresolved = re.findall(r"\{\{[^}]*\}\}", html)
    assert not unresolved, f"{family}/{variant}: unresolved placeholders: {unresolved[:5]}"

    # No fake or generic contact destination.
    assert "business@email.com" not in html
    assert not re.search(r"mailto:[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+", html)

    # Every tel: link must dial the fixture's verified number.
    tel_targets = set(re.findall(r"tel:([+0-9]{7,})", html))
    assert tel_targets <= {"5550107777"}, f"{family}/{variant}: unexpected tel: targets {tel_targets}"

    # No price literals.
    prices = re.findall(r"\$\s?\d[\d,]*", html)
    assert not prices, f"{family}/{variant}: price literals {sorted(set(prices))[:5]}"

    # The only rating-like decimal is the fixture's rating.
    ratings = set(re.findall(r"(?<![\w.\-])[45]\.\d\b", html))
    assert ratings <= {"4.2"}, f"{family}/{variant}: unexpected ratings {ratings}"

    # The fixture identity is rendered; removed hardcodes are not.
    assert "ACME Fixture Business Group" in html
    for fact in REMOVED_FACTS_DENYLIST:
        assert fact not in html, f"{family}/{variant}: removed fact {fact!r} reintroduced"


def test_common_family_sections_are_placeholder_only() -> None:
    """The shared 'common' sections must also be placeholder-only."""
    for path in sorted((SECTIONS_DIR / "common").glob("*.html")):
        violations = _scan_violations(path.read_text(encoding="utf-8"))
        assert not violations, f"{path.name}: {violations}"
