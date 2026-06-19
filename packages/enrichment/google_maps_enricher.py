"""
Google Maps Business Enricher.

Scrapes Google Maps business profiles via web_search + web_extract.
Returns structured BusinessEnrichment data with descriptions, photos,
review snippets, hours, services, differentiators, and owner signals.

No API keys required. No browser automation.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class BusinessEnrichment:
    """Structured enrichment data extracted from a Google Maps listing."""

    business_name: str
    description: str = ""
    photos: list[str] = field(default_factory=list)
    review_snippets: list[str] = field(default_factory=list)
    hours: dict[str, str] = field(default_factory=dict)
    services: list[str] = field(default_factory=list)
    differentiators: list[str] = field(default_factory=list)
    owner_signals: list[str] = field(default_factory=list)
    rating: float = 0.0
    review_count: int = 0
    source_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Pattern-based extractors
# ---------------------------------------------------------------------------

# Phrases from reviews that signal real service differentiators.
DIFFERENTIATOR_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"came to my (?:office|work|house|home|location|job site)", re.I),
     "mobile/on-site service"),
    (re.compile(r"came to (?:my|the) (?:workplace|apartment|complex)", re.I),
     "mobile/on-site service"),
    (re.compile(r"mobile detailing|mobile wash|came to me", re.I),
     "mobile service"),
    (re.compile(r"my car looks (?:brand new|like new|showroom)", re.I),
     "restoration quality"),
    (re.compile(r"(?:looks|feels) brand new", re.I),
     "restoration quality"),
    (re.compile(r"very detail[\s-]?oriented|attention to detail", re.I),
     "attention to detail"),
    (re.compile(r"finished (?:ahead of schedule|early|before the deadline)", re.I),
     "efficiency / fast turnaround"),
    (re.compile(r"finished in under|done in under|completed in", re.I),
     "fast service"),
    (re.compile(r"explained everything|walked me through|took time to explain", re.I),
     "education / transparency"),
    (re.compile(r"brought (?:his|their|her) own (?:water|supplies|equipment|products)", re.I),
     "self-sufficient / brings own supplies"),
    (re.compile(r"went above and beyond|extra mile|beyond expectations", re.I),
     "goes above and beyond"),
    (re.compile(r"very (?:professional|punctual|reliable|responsive)", re.I),
     "professionalism"),
    (re.compile(r"on time|punctual|showed up (?:on time|early)", re.I),
     "punctuality"),
    (re.compile(r"scheduled (?:same day|next day|last minute)", re.I),
     "flexible scheduling"),
    (re.compile(r"(?:fair|reasonable|great) price(?:ing)?|best price|competitive rate", re.I),
     "fair pricing"),
    (re.compile(r"before and after (?:photos|pics|pictures)", re.I),
     "documents work with photos"),
    (re.compile(r"interior (?:was|looked|smelled)|inside (?:was|looked|smelled)", re.I),
     "interior detailing expertise"),
    (re.compile(r"paint (?:correction|protection|coating|ceramic)", re.I),
     "paint correction / coating specialist"),
    (re.compile(r"ceramic (?:coat|coating|pro)", re.I),
     "ceramic coating specialist"),
    (re.compile(r"steam clean|shampoo|deep clean", re.I),
     "deep cleaning capability"),
]

# Phrases that signal owner personality.
OWNER_SIGNAL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"the owner (?:himself|herself|personally)", re.I),
     "owner personally involved"),
    (re.compile(r"(?:he|she) (?:is|was) (?:super |very )?(?:friendly|nice|kind|personable|warm)", re.I),
     "friendly personality"),
    (re.compile(r"great (?:guy|dude|person|fellow|gal|lady)", re.I),
     "personal warmth"),
    (re.compile(r"(?:super |very )?friendly (?:guy|dude|person|staff|team)", re.I),
     "friendly team"),
    (re.compile(r"(?:he|she) (?:really |truly )?cares", re.I),
     "cares about customers"),
    (re.compile(r"passionate (?:about|for)", re.I),
     "passionate about work"),
    (re.compile(r"honest|trustworthy|straight shooter", re.I),
     "honest / trustworthy"),
    (re.compile(r"easy to (?:talk to|work with|communicate with)", re.I),
     "easy to work with"),
    (re.compile(r"(?:will |definitely |absolutely )?(?:use again|coming back|return customer|repeat customer)", re.I),
     "repeat customer magnet"),
    (re.compile(r"(?:highly |strongly )?recommend", re.I),
     "highly recommended"),
]


def extract_differentiators(reviews: list[str]) -> list[str]:
    """Extract unique differentiator labels from review text."""
    seen: set[str] = set()
    results: list[str] = []
    text = " ".join(reviews)
    for pattern, label in DIFFERENTIATOR_PATTERNS:
        if pattern.search(text) and label not in seen:
            seen.add(label)
            results.append(label)
    return results


def extract_owner_signals(reviews: list[str]) -> list[str]:
    """Extract owner personality signals from review text."""
    seen: set[str] = set()
    results: list[str] = []
    for review in reviews:
        for pattern, label in OWNER_SIGNAL_PATTERNS:
            if pattern.search(review) and label not in seen:
                seen.add(label)
                results.append(label)
    return results


# ---------------------------------------------------------------------------
# Text parsing from extracted Maps page content
# ---------------------------------------------------------------------------

def _parse_hours(text: str) -> dict[str, str]:
    """Extract day -> hours mapping from page text."""
    days = [
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday",
    ]
    hours: dict[str, str] = {}
    for day in days:
        pattern = re.compile(
            rf"{day}[:\s]+([\w:\s\-–\.]+?)(?:\n|$|,)",
            re.I,
        )
        m = pattern.search(text)
        if m:
            val = m.group(1).strip().rstrip(",").strip()
            if val and val.lower() not in ("", "closed"):
                hours[day] = val
    return hours


def _parse_services(text: str) -> list[str]:
    """Extract service keywords from page text."""
    service_indicators = [
        r"Services?\s*[:\-]\s*(.+?)(?:\n\n|\n[A-Z]|\Z)",
        r"Offerings?\s*[:\-]\s*(.+?)(?:\n\n|\n[A-Z]|\Z)",
        r"Service options\s*[:\-]\s*(.+?)(?:\n\n|\n[A-Z]|\Z)",
    ]
    services: list[str] = []
    for pat in service_indicators:
        for m in re.finditer(pat, text, re.I | re.DOTALL):
            block = m.group(1)
            # Split on commas, semicolons, bullets, or newlines with bullets
            items = re.split(r"[,;|]|[\n\r]+\s*[\u2022\u00b7•\-*]\s*", block)
            for item in items:
                cleaned = item.strip().strip("•·-* \t")
                if cleaned and len(cleaned) > 2 and cleaned.lower() not in (
                    "none", "n/a", "yes", "no",
                ):
                    services.append(cleaned)
    return services[:20]


def _parse_rating(text: str) -> float:
    """Extract star rating from page text."""
    patterns = [
        r"(\d+\.?\d*)\s*(?:out of\s*5|/\s*5|stars?|⭐)",
        r"(?:rated?|rating)\s*[:\s]*\s*(\d+\.?\d*)",
        r"(\d+\.?\d*)\s*\(\d+\s*(?:reviews?|Google reviews)\)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            try:
                return float(m.group(1))
            except (ValueError, IndexError):
                continue
    return 0.0


def _parse_review_count(text: str) -> int:
    """Extract total review count from page text."""
    patterns = [
        r"(\d[\d,]*)\s*(?:Google\s+)?reviews?",
        r"(\d[\d,]*)\s*(?:reviews?|ratings?)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            try:
                return int(m.group(1).replace(",", ""))
            except (ValueError, IndexError):
                continue
    return 0


def _parse_photos(text: str) -> list[str]:
    """Extract photo image URLs from page text."""
    url_pattern = re.compile(
        r"https?://[^\s\"'<>)\]]+?\.(?:jpg|jpeg|png|webp|gif)[^\s\"'<>)\]]*",
        re.I,
    )
    urls: list[str] = []
    seen: set[str] = set()
    for m in url_pattern.finditer(text):
        url = m.group(0).rstrip(".,;:")
        # Skip tiny icons/logos by checking URL patterns
        if any(skip in url.lower() for skip in (
            "icon", "logo", "avatar", "emoji", "favicon",
            "pixel", "1x1", "spacer", "blank",
        )):
            continue
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls[:10]


def _parse_review_snippets(text: str, max_snippets: int = 15) -> list[str]:
    """Extract individual review text excerpts from page content."""
    snippets: list[str] = []

    # Look for quoted review text patterns
    quote_patterns = [
        r'"([^"]{20,300})"',
        r'"([^"]{20,300})"',
        r'\u201c([^\u201d]{20,300})\u201d',  # smart quotes
        r'([A-Z][^.!?]{20,250}[.!?](?:\s+[A-Z][^.!?]{10,150}[.!?])?)',
    ]

    seen: set[str] = set()
    for pat in quote_patterns:
        for m in re.finditer(pat, text):
            snippet = m.group(1).strip()
            # Filter out non-review text
            if any(skip in snippet.lower() for skip in (
                "cookie", "privacy", "terms", "javascript",
                "navigation", "sign in", "google maps",
            )):
                continue
            norm = snippet.lower().strip()[:50]
            if norm not in seen and len(snippet) > 15:
                seen.add(norm)
                snippets.append(snippet)
                if len(snippets) >= max_snippets:
                    return snippets
    return snippets


def _parse_description(text: str) -> str:
    """Extract business description from About section."""
    patterns = [
        r"(?:About|Description)\s*\n\s*(.+?)(?:\n\n|\n(?:Hours|Services|Contact|Reviews|Photos))",
        r"(?:About|Description)\s*[:\-]\s*(.+?)(?:\n\n|\n[A-Z])",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I | re.DOTALL)
        if m:
            desc = m.group(1).strip()
            if len(desc) > 20:
                return desc[:500]
    return ""


# ---------------------------------------------------------------------------
# Search & extraction (web tool interface)
# ---------------------------------------------------------------------------

def search_maps_url(business_name: str, city: str) -> str:
    """Search for the Google Maps URL for a business.

    Returns the first maps.google.com URL found, or empty string.
    This function is designed to be called with web_search results
    passed in via the `run_enrichment` orchestrator.
    """
    query = f"{business_name} {city} google maps"
    return query


def find_maps_url_from_results(
    business_name: str,
    search_results: list[dict[str, Any]],
    city: str = "",
) -> str:
    """Pick the best Google Maps URL from search results."""
    candidates: list[tuple[str, int]] = []
    for result in search_results:
        url = result.get("url", "") or result.get("href", "")
        title = result.get("title", "") or result.get("text", "")
        name_lower = business_name.lower()
        title_lower = title.lower()
        url_lower = url.lower()

        if "maps.google" in url_lower or "google.com/maps" in url_lower:
            score = 0
            if name_lower in title_lower:
                score += 2
            candidates.append((url, score))

    if not candidates:
        query = f"{business_name} {city}".strip()
        encoded = quote_plus(query)
        return f"https://www.google.com/maps/search/{encoded}"

    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0]


# ---------------------------------------------------------------------------
# Main enrichment logic
# ---------------------------------------------------------------------------

def parse_maps_page(text: str, business_name: str, source_url: str) -> BusinessEnrichment:
    """Parse extracted Google Maps page text into structured enrichment."""
    rating = _parse_rating(text)
    review_count = _parse_review_count(text)
    review_snippets = _parse_review_snippets(text)
    photos = _parse_photos(text)
    hours = _parse_hours(text)
    services = _parse_services(text)
    description = _parse_description(text)

    differentiators = extract_differentiators(review_snippets)
    owner_signals = extract_owner_signals(review_snippets)

    return BusinessEnrichment(
        business_name=business_name,
        description=description,
        photos=photos,
        review_snippets=review_snippets,
        hours=hours,
        services=services,
        differentiators=differentiators,
        owner_signals=owner_signals,
        rating=rating,
        review_count=review_count,
        source_url=source_url,
    )


def run_enrichment(
    business_name: str,
    city: str,
    maps_url: str | None = None,
    search_results: list[dict[str, Any]] | None = None,
    page_text: str | None = None,
) -> BusinessEnrichment:
    """Run full enrichment pipeline.

    This is the main entry point. It needs external data to be passed in:
    - If maps_url is not provided, search_results must contain search results
    - If page_text is not provided, the caller should extract the maps URL page

    For CLI usage, this uses web_search/web_extract tools.
    For library usage, pass pre-fetched data directly.
    """
    source_url = maps_url or ""

    if not source_url and search_results:
        source_url = find_maps_url_from_results(business_name, search_results)

    if not source_url:
        encoded = quote_plus(f"{business_name} {city}")
        source_url = f"https://www.google.com/maps/search/{encoded}"

    if not page_text:
        return BusinessEnrichment(
            business_name=business_name,
            source_url=source_url,
        )

    return parse_maps_page(page_text, business_name, source_url)


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def save_enrichment(enrichment: BusinessEnrichment, output_path: str) -> str:
    """Save enrichment data to JSON file. Returns absolute path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(enrichment.to_json(), encoding="utf-8")
    return str(path.resolve())


def slugify(text: str) -> str:
    """Create URL-safe slug from text."""
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:64] or "unknown"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Google Maps Business Enricher",
    )
    parser.add_argument(
        "--business", required=True, help="Business name",
    )
    parser.add_argument(
        "--city", required=True, help="City (e.g., 'Frisco TX')",
    )
    parser.add_argument(
        "--url", default=None, help="Direct Google Maps URL (skips search)",
    )
    parser.add_argument(
        "--output", default=None,
        help="Output JSON path (default: artifacts/enrichment/{slug}.json)",
    )
    parser.add_argument(
        "--search-results", default=None,
        help="Path to JSON file with pre-fetched search results",
    )
    parser.add_argument(
        "--page-text", default=None,
        help="Path to text file with pre-extracted Maps page content",
    )
    args = parser.parse_args()

    slug = slugify(args.business)
    output_path = args.output or f"artifacts/enrichment/{slug}.json"

    search_results: list[dict[str, Any]] = []
    if args.search_results:
        with open(args.search_results, encoding="utf-8") as f:
            search_results = json.load(f)

    page_text: str | None = None
    if args.page_text:
        page_text = Path(args.page_text).read_text(encoding="utf-8")

    enrichment = run_enrichment(
        business_name=args.business,
        city=args.city,
        maps_url=args.url,
        search_results=search_results or None,
        page_text=page_text,
    )

    saved = save_enrichment(enrichment, output_path)
    print(f"Saved enrichment to {saved}")
    print(json.dumps(enrichment.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
