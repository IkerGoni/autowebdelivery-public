"""Reviews Extractor - Extract insights and differentiators from customer reviews.

Analyzes Google Reviews and other review sources to identify:
- Common themes and patterns
- Service differentiators
- Customer sentiment
- Key phrases that indicate business strengths
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ReviewInsights:
    """Structured insights extracted from reviews."""
    
    differentiators: list[str] = field(default_factory=list)
    common_themes: list[tuple[str, int]] = field(default_factory=list)  # (theme, count)
    key_phrases: list[str] = field(default_factory=list)
    sentiment_signals: dict[str, int] = field(default_factory=dict)
    customer_quotes: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Theme detection patterns
# ---------------------------------------------------------------------------

THEME_PATTERNS = {
    "quality": [
        r"\b(?:high|excellent|great|amazing|outstanding|superior) quality\b",
        r"\b(?:quality|craftsmanship) (?:is |was )?(?:excellent|amazing|top|great)\b",
        r"\bperfection\b",
        r"\bflawless\b",
    ],
    "speed": [
        r"\b(?:quick|fast|speedy|rapid|prompt) (?:service|turnaround|response)\b",
        r"\b(?:finished|completed|done) (?:quickly|fast|ahead of schedule)\b",
        r"\bsame day\b",
        r"\bnext day\b",
    ],
    "professionalism": [
        r"\b(?:very |extremely )?professional\b",
        r"\b(?:courteous|polite|respectful)\b",
        r"\bprofessionalism\b",
    ],
    "communication": [
        r"\b(?:great|excellent|good) communication\b",
        r"\b(?:responsive|quick to respond)\b",
        r"\bkept me (?:informed|updated)\b",
        r"\bexplained everything\b",
    ],
    "value": [
        r"\b(?:fair|reasonable|competitive|great|good) pric(?:e|ing)\b",
        r"\bworth every penny\b",
        r"\bgreat value\b",
        r"\baffordable\b",
    ],
    "reliability": [
        r"\b(?:reliable|dependable|trustworthy)\b",
        r"\bon time\b",
        r"\bpunctual\b",
        r"\bshowed up (?:on time|when promised)\b",
    ],
    "attention_to_detail": [
        r"\battention to detail\b",
        r"\bvery detailed\b",
        r"\bdetail[- ]oriented\b",
        r"\bmeticulous\b",
    ],
    "customer_service": [
        r"\b(?:excellent|great|amazing|outstanding) (?:customer )?service\b",
        r"\bwent above and beyond\b",
        r"\bextra mile\b",
        r"\bcustomer focused\b",
    ],
}


# ---------------------------------------------------------------------------
# Differentiator extraction patterns (from google_maps_enricher.py)
# ---------------------------------------------------------------------------

DIFFERENTIATOR_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"came to my (?:office|work|house|home|location|job site)", re.IGNORECASE),
     "mobile/on-site service"),
    (re.compile(r"mobile detailing|mobile wash|came to me", re.IGNORECASE),
     "mobile service"),
    (re.compile(r"my car looks (?:brand new|like new|showroom)", re.IGNORECASE),
     "restoration quality"),
    (re.compile(r"very detail[\\s-]?oriented|attention to detail", re.IGNORECASE),
     "attention to detail"),
    (re.compile(r"finished (?:ahead of schedule|early|before)", re.IGNORECASE),
     "efficiency / fast turnaround"),
    (re.compile(r"explained everything|walked me through", re.IGNORECASE),
     "education / transparency"),
    (re.compile(r"brought (?:his|their|her) own (?:water|supplies|equipment)", re.IGNORECASE),
     "self-sufficient / brings own supplies"),
    (re.compile(r"went above and beyond|extra mile", re.IGNORECASE),
     "goes above and beyond"),
    (re.compile(r"very (?:professional|punctual|reliable|responsive)", re.IGNORECASE),
     "professionalism"),
    (re.compile(r"on time|punctual|showed up (?:on time|early)", re.IGNORECASE),
     "punctuality"),
    (re.compile(r"scheduled (?:same day|next day|last minute)", re.IGNORECASE),
     "flexible scheduling"),
    (re.compile(r"(?:fair|reasonable|great) price|best price", re.IGNORECASE),
     "fair pricing"),
    (re.compile(r"before and after (?:photos|pics|pictures)", re.IGNORECASE),
     "documents work with photos"),
    (re.compile(r"paint (?:correction|protection|coating|ceramic)", re.IGNORECASE),
     "paint correction / coating specialist"),
    (re.compile(r"ceramic (?:coat|coating|pro)", re.IGNORECASE),
     "ceramic coating specialist"),
    (re.compile(r"steam clean|shampoo|deep clean", re.IGNORECASE),
     "deep cleaning capability"),
]


# ---------------------------------------------------------------------------
# Review text cleaning
# ---------------------------------------------------------------------------

def clean_review_text(text: str) -> str:
    """Clean and normalize review text."""
    if not text:
        return ""
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove common non-content patterns
    text = re.sub(r'Read more|Show less|Helpful\?|Report', '', text, flags=re.IGNORECASE)
    
    # Remove star ratings in text
    text = re.sub(r'\d+\s*(?:star|stars|out of \d+)', '', text, flags=re.IGNORECASE)
    
    return text.strip()


# ---------------------------------------------------------------------------
# Theme extraction
# ---------------------------------------------------------------------------

def extract_themes(reviews: list[str]) -> list[tuple[str, int]]:
    """Extract common themes from reviews with occurrence counts.
    
    Returns list of (theme_name, count) tuples sorted by frequency.
    """
    theme_counts: dict[str, int] = {}
    
    combined_text = " ".join(reviews).lower()
    
    for theme_name, patterns in THEME_PATTERNS.items():
        count = 0
        for pattern in patterns:
            matches = re.findall(pattern, combined_text, re.IGNORECASE)
            count += len(matches)
        
        if count > 0:
            theme_counts[theme_name] = count
    
    # Sort by count descending
    sorted_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)
    
    return sorted_themes


# ---------------------------------------------------------------------------
# Differentiator extraction
# ---------------------------------------------------------------------------

def extract_differentiators_from_reviews(reviews: list[str], max_results: int = 5) -> list[str]:
    """Extract unique differentiator labels from review text.
    
    Args:
        reviews: List of review text strings
        max_results: Maximum number of differentiators to return
    
    Returns:
        List of differentiator labels (e.g., "mobile service", "attention to detail")
    """
    seen: set[str] = set()
    results: list[str] = []
    
    text = " ".join(reviews)
    
    for pattern, label in DIFFERENTIATOR_PATTERNS:
        if pattern.search(text) and label not in seen:
            seen.add(label)
            results.append(label)
            
            if len(results) >= max_results:
                break
    
    return results


# ---------------------------------------------------------------------------
# Key phrase extraction
# ---------------------------------------------------------------------------

def extract_key_phrases(reviews: list[str], min_length: int = 20, max_length: int = 100) -> list[str]:
    """Extract meaningful quoted phrases from reviews.
    
    Looks for complete sentences or quoted text that captures customer voice.
    """
    phrases: list[str] = []
    seen: set[str] = set()
    
    # Patterns for extracting meaningful phrases
    quote_patterns = [
        r'"([^"]{20,100})"',  # Quoted text
        r'([A-Z][^.!?]{20,100}[.!?])',  # Complete sentences
    ]
    
    for review in reviews:
        cleaned = clean_review_text(review)
        
        for pattern in quote_patterns:
            for match in re.finditer(pattern, cleaned):
                phrase = match.group(1).strip()
                
                # Filter out non-meaningful phrases
                if any(skip in phrase.lower() for skip in [
                    'click here', 'read more', 'show less',
                    'helpful', 'report', 'translate'
                ]):
                    continue
                
                # Check length
                if min_length <= len(phrase) <= max_length:
                    # Normalize for deduplication
                    norm = phrase.lower()[:50]
                    if norm not in seen:
                        seen.add(norm)
                        phrases.append(phrase)
                        
                        if len(phrases) >= 10:
                            return phrases
    
    return phrases


# ---------------------------------------------------------------------------
# Sentiment analysis (simple pattern-based)
# ---------------------------------------------------------------------------

def analyze_sentiment(reviews: list[str]) -> dict[str, int]:
    """Simple sentiment analysis based on keyword patterns.
    
    Returns counts of positive, negative, and neutral signals.
    """
    sentiment = {
        "positive": 0,
        "negative": 0,
        "neutral": 0,
    }
    
    positive_patterns = [
        r"\b(?:amazing|excellent|outstanding|fantastic|wonderful|great|love|best)\b",
        r"\b(?:highly recommend|will return|coming back)\b",
    ]
    
    negative_patterns = [
        r"\b(?:terrible|awful|horrible|worst|disappointing|poor|bad)\b",
        r"\b(?:never again|not recommend|avoid)\b",
    ]
    
    combined_text = " ".join(reviews).lower()
    
    for pattern in positive_patterns:
        sentiment["positive"] += len(re.findall(pattern, combined_text, re.IGNORECASE))
    
    for pattern in negative_patterns:
        sentiment["negative"] += len(re.findall(pattern, combined_text, re.IGNORECASE))
    
    # If mostly neutral (few strong signals), mark as neutral
    total_signals = sentiment["positive"] + sentiment["negative"]
    if total_signals < len(reviews):
        sentiment["neutral"] = len(reviews) - total_signals
    
    return sentiment


# ---------------------------------------------------------------------------
# Main extraction pipeline
# ---------------------------------------------------------------------------

def extract_review_insights(reviews: list[str], max_differentiators: int = 5) -> ReviewInsights:
    """Extract structured insights from a list of reviews.
    
    Args:
        reviews: List of review text strings
        max_differentiators: Maximum differentiators to extract
    
    Returns:
        ReviewInsights with themes, differentiators, phrases, sentiment
    """
    if not reviews:
        return ReviewInsights()
    
    # Clean reviews
    cleaned_reviews = [clean_review_text(r) for r in reviews if r]
    
    # Extract all components
    themes = extract_themes(cleaned_reviews)
    differentiators = extract_differentiators_from_reviews(cleaned_reviews, max_differentiators)
    key_phrases = extract_key_phrases(cleaned_reviews)
    sentiment = analyze_sentiment(cleaned_reviews)
    
    # Pick best customer quotes (top 3 key phrases)
    customer_quotes = key_phrases[:3]
    
    return ReviewInsights(
        differentiators=differentiators,
        common_themes=themes,
        key_phrases=key_phrases,
        sentiment_signals=sentiment,
        customer_quotes=customer_quotes,
    )


def merge_review_insights_into_enrichment(
    enrichment_data: dict[str, Any],
    insights: ReviewInsights
) -> dict[str, Any]:
    """Merge review insights into enrichment data structure.
    
    Adds review-derived differentiators and signals without overwriting existing data.
    """
    if not insights:
        return enrichment_data
    
    # Merge differentiators (add new ones, deduplicate)
    existing_diff = set(enrichment_data.get("differentiators", []))
    for diff in insights.differentiators:
        if diff not in existing_diff:
            enrichment_data.setdefault("differentiators", []).append(diff)
    
    # Add review insights as separate field
    enrichment_data["review_insights"] = insights.to_dict()
    
    # Add top theme as a differentiator if strong signal
    if insights.common_themes and insights.common_themes[0][1] >= 3:
        top_theme, count = insights.common_themes[0]
        theme_signal = f"{top_theme.replace('_', ' ').title()} (mentioned {count}x in reviews)"
        if theme_signal not in existing_diff:
            enrichment_data.setdefault("differentiators", []).append(theme_signal)
    
    return enrichment_data
