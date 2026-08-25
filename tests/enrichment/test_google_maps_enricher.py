"""Tests for Google Maps Business Enricher."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

from packages.enrichment.google_maps_enricher import (
    BusinessEnrichment,
    _parse_description,
    _parse_hours,
    _parse_photos,
    _parse_rating,
    _parse_review_count,
    _parse_review_snippets,
    _parse_services,
    extract_differentiators,
    extract_owner_signals,
    find_maps_url_from_results,
    parse_maps_page,
    run_enrichment,
    save_enrichment,
    slugify,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_MAPS_TEXT = textwrap.dedent("""\
    Frisco Mobile Detailing
    4.9 (327 Google reviews)
    
    About
    Frisco Mobile Detailing is a professional mobile auto detailing service
    serving the Frisco, TX area. We come to your home or office and provide
    premium detailing services including ceramic coating, paint correction,
    and interior deep cleaning.
    
    Hours
    Monday: 8:00 AM - 6:00 PM
    Tuesday: 8:00 AM - 6:00 PM
    Wednesday: 8:00 AM - 6:00 PM
    Thursday: 8:00 AM - 6:00 PM
    Friday: 8:00 AM - 5:00 PM
    Saturday: 9:00 AM - 3:00 PM
    Sunday: Closed
    
    Services:
    Exterior detailing, Interior detailing, Ceramic coating, Paint correction,
    Headlight restoration, Engine bay cleaning, Mobile service
    
    Photos
    https://lh3.googleusercontent.com/abc123/photo1.jpg?w=800
    https://lh3.googleusercontent.com/def456/photo2.jpg?w=800
    https://lh3.googleusercontent.com/ghi789/photo3.jpg?w=800
    
    Reviews
    
    "He came to my office and detailed my car in the parking lot. 
    My car looks brand new! The owner himself did the work and explained 
    everything he was doing. Super friendly guy."
    
    "Very detail-oriented work. He brought his own water and supplies.
    Finished ahead of schedule and the interior smelled amazing.
    Highly recommend!"
    
    "Great guy, very professional. The ceramic coating he applied 
    is incredible. My car looks like it just rolled off the showroom floor.
    Will definitely use again."
    
    "Best price in Frisco for the quality you get. He really cares about 
    his work. Paint correction was flawless. Easy to work with and 
    scheduled same day."
    
    "The owner personally came out on a Saturday. Steam cleaned the 
    interior and shampooed the seats. Very professional and punctual.
    Above and beyond service."
    
    "Very responsive and showed up on time. Before and after photos 
    were impressive. Fair pricing for mobile service. 
    Strongly recommend to anyone in Frisco."
""")

SAMPLE_SEARCH_RESULTS = [
    {
        "title": "Frisco Mobile Detailing - Google Maps",
        "url": "https://maps.google.com/maps?cid=123456789",
    },
    {
        "title": "Some Other Business - Google Maps",
        "url": "https://maps.google.com/maps?cid=999999",
    },
    {
        "title": "Frisco Mobile Detailing Yelp",
        "url": "https://www.yelp.com/biz/frisco-mobile-detailing",
    },
]


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


class TestBusinessEnrichment:
    def test_default_values(self) -> None:
        e = BusinessEnrichment(business_name="Test Biz")
        assert e.business_name == "Test Biz"
        assert e.description == ""
        assert e.photos == []
        assert e.review_snippets == []
        assert e.hours == {}
        assert e.services == []
        assert e.differentiators == []
        assert e.owner_signals == []
        assert e.rating == 0.0
        assert e.review_count == 0
        assert e.source_url == ""

    def test_to_dict(self) -> None:
        e = BusinessEnrichment(
            business_name="Biz",
            rating=4.5,
            review_count=100,
            services=["wash", "wax"],
        )
        d = e.to_dict()
        assert d["business_name"] == "Biz"
        assert d["rating"] == 4.5
        assert d["services"] == ["wash", "wax"]

    def test_to_json(self) -> None:
        e = BusinessEnrichment(business_name="Test", rating=4.9)
        j = e.to_json()
        data = json.loads(j)
        assert data["business_name"] == "Test"
        assert data["rating"] == 4.9


# ---------------------------------------------------------------------------
# Rating / review count parsing
# ---------------------------------------------------------------------------


class TestParseRating:
    def test_rating_with_parens(self) -> None:
        assert _parse_rating("4.9 (327 Google reviews)") == 4.9

    def test_rating_stars(self) -> None:
        assert _parse_rating("Rated 4.8 stars") == 4.8

    def test_rating_out_of_five(self) -> None:
        assert _parse_rating("4.7 out of 5") == 4.7

    def test_rating_label(self) -> None:
        assert _parse_rating("rating: 4.6") == 4.6

    def test_no_rating(self) -> None:
        assert _parse_rating("No rating info here") == 0.0


class TestParseReviewCount:
    def test_google_reviews(self) -> None:
        assert _parse_review_count("4.9 (327 Google reviews)") == 327

    def test_comma_format(self) -> None:
        assert _parse_review_count("1,234 reviews") == 1234

    def test_simple_count(self) -> None:
        assert _parse_review_count("42 reviews") == 42

    def test_no_count(self) -> None:
        assert _parse_review_count("No reviews") == 0


# ---------------------------------------------------------------------------
# Hours parsing
# ---------------------------------------------------------------------------


class TestParseHours:
    def test_full_week(self) -> None:
        text = textwrap.dedent("""\
            Monday: 8:00 AM - 6:00 PM
            Tuesday: 8:00 AM - 6:00 PM
            Wednesday: 8:00 AM - 6:00 PM
            Thursday: 8:00 AM - 6:00 PM
            Friday: 8:00 AM - 5:00 PM
            Saturday: 9:00 AM - 3:00 PM
            Sunday: Closed
        """)
        hours = _parse_hours(text)
        assert hours["Monday"] == "8:00 AM - 6:00 PM"
        assert hours["Friday"] == "8:00 AM - 5:00 PM"
        assert hours["Saturday"] == "9:00 AM - 3:00 PM"
        assert "Sunday" not in hours  # Closed = omitted

    def test_no_hours(self) -> None:
        assert _parse_hours("No hours listed") == {}


    def test_partial_hours(self) -> None:
        text = "Monday: 9 AM - 5 PM\nWednesday: 10 AM - 4 PM"
        hours = _parse_hours(text)
        assert "Monday" in hours
        assert "Wednesday" in hours
        assert "Tuesday" not in hours


# ---------------------------------------------------------------------------
# Services parsing
# ---------------------------------------------------------------------------


class TestParseServices:
    def test_comma_separated(self) -> None:
        text = "Services: Exterior detailing, Interior detailing, Ceramic coating"
        services = _parse_services(text)
        assert "Exterior detailing" in services
        assert "Ceramic coating" in services

    def test_bullet_list(self) -> None:
        text = "Service options:\n• Mobile service\n• Paint correction\n• Headlight restoration"
        services = _parse_services(text)
        assert len(services) >= 3

    def test_no_services(self) -> None:
        assert _parse_services("Just a business page") == []


# ---------------------------------------------------------------------------
# Photo URL parsing
# ---------------------------------------------------------------------------


class TestParsePhotos:
    def test_google_photos(self) -> None:
        text = (
            "https://lh3.googleusercontent.com/abc/photo1.jpg?w=800\n"
            "https://lh3.googleusercontent.com/def/photo2.png\n"
        )
        photos = _parse_photos(text)
        assert len(photos) == 2
        assert all("googleusercontent" in p for p in photos)

    def test_skip_icons(self) -> None:
        text = "https://example.com/icon.png https://example.com/photo.jpg"
        photos = _parse_photos(text)
        assert len(photos) == 1
        assert "photo.jpg" in photos[0]

    def test_max_10(self) -> None:
        urls = "\n".join(f"https://example.com/photo{i}.jpg" for i in range(20))
        photos = _parse_photos(urls)
        assert len(photos) == 10


# ---------------------------------------------------------------------------
# Review snippet parsing
# ---------------------------------------------------------------------------


class TestParseReviewSnippets:
    def test_quoted_reviews(self) -> None:
        text = (
            '"He came to my office and detailed my car. '
            'My car looks brand new!"\n'
            '"Very professional service. Highly recommend this business."\n'
        )
        snippets = _parse_review_snippets(text)
        assert len(snippets) >= 1

    def test_max_snippets(self) -> None:
        reviews = " ".join(
            f'"This is review number {i} with enough text to be captured properly."'
            for i in range(20)
        )
        snippets = _parse_review_snippets(reviews, max_snippets=5)
        assert len(snippets) <= 5

    def test_skip_navigation_text(self) -> None:
        text = '"Sign in to Google Maps to see reviews. JavaScript is required."'
        snippets = _parse_review_snippets(text)
        assert len(snippets) == 0


# ---------------------------------------------------------------------------
# Description parsing
# ---------------------------------------------------------------------------


class TestParseDescription:
    def test_about_section(self) -> None:
        text = (
            "About\n"
            "Professional mobile auto detailing service serving "
            "the Frisco TX area with premium quality care.\n\n"
            "Hours\n"
        )
        desc = _parse_description(text)
        assert "mobile auto detailing" in desc
        assert len(desc) > 20

    def test_no_about(self) -> None:
        assert _parse_description("No description here") == ""


# ---------------------------------------------------------------------------
# Differentiator extraction
# ---------------------------------------------------------------------------


class TestExtractDifferentiators:
    def test_mobile_service(self) -> None:
        reviews = ["He came to my office and did an amazing job."]
        diffs = extract_differentiators(reviews)
        assert "mobile/on-site service" in diffs

    def test_brand_new(self) -> None:
        reviews = ["My car looks brand new after the detail!"]
        diffs = extract_differentiators(reviews)
        assert "restoration quality" in diffs

    def test_attention_to_detail(self) -> None:
        reviews = ["Very detail-oriented work on my vehicle."]
        diffs = extract_differentiators(reviews)
        assert "attention to detail" in diffs

    def test_finished_early(self) -> None:
        reviews = ["Finished ahead of schedule and it looks great."]
        diffs = extract_differentiators(reviews)
        assert "efficiency / fast turnaround" in diffs

    def test_brought_own_supplies(self) -> None:
        reviews = ["He brought his own water and supplies to the job."]
        diffs = extract_differentiators(reviews)
        assert "self-sufficient / brings own supplies" in diffs

    def test_ceramic_coating(self) -> None:
        reviews = ["The ceramic coating they applied is incredible."]
        diffs = extract_differentiators(reviews)
        assert "ceramic coating specialist" in diffs

    def test_multiple_differentiators(self) -> None:
        reviews = [
            "He came to my house and finished ahead of schedule.",
            "My car looks brand new, very detail-oriented work.",
        ]
        diffs = extract_differentiators(reviews)
        assert len(diffs) >= 3

    def test_no_duplicates(self) -> None:
        reviews = [
            "He came to my office. Great work.",
            "Came to my workplace too. Excellent.",
        ]
        diffs = extract_differentiators(reviews)
        assert diffs.count("mobile/on-site service") == 1

    def test_empty_reviews(self) -> None:
        assert extract_differentiators([]) == []


# ---------------------------------------------------------------------------
# Owner signal extraction
# ---------------------------------------------------------------------------


class TestExtractOwnerSignals:
    def test_owner_himself(self) -> None:
        reviews = ["The owner himself came to detail my car."]
        signals = extract_owner_signals(reviews)
        assert "owner personally involved" in signals

    def test_super_friendly(self) -> None:
        reviews = ["He is super friendly and does great work."]
        signals = extract_owner_signals(reviews)
        assert "friendly personality" in signals

    def test_great_guy(self) -> None:
        reviews = ["Great guy, would recommend to anyone."]
        signals = extract_owner_signals(reviews)
        assert "personal warmth" in signals

    def test_highly_recommend(self) -> None:
        reviews = ["I highly recommend this business to everyone."]
        signals = extract_owner_signals(reviews)
        assert "highly recommended" in signals

    def test_cares_about_customers(self) -> None:
        reviews = ["He really cares about his customers' satisfaction."]
        signals = extract_owner_signals(reviews)
        assert "cares about customers" in signals

    def test_easy_to_work_with(self) -> None:
        reviews = ["Very easy to work with and responsive."]
        signals = extract_owner_signals(reviews)
        assert "easy to work with" in signals

    def test_multiple_signals(self) -> None:
        reviews = [
            "The owner himself was super friendly.",
            "Highly recommend this honest business.",
        ]
        signals = extract_owner_signals(reviews)
        assert len(signals) >= 3

    def test_no_signals(self) -> None:
        reviews = ["The car was clean."]
        signals = extract_owner_signals(reviews)
        assert "highly recommended" not in signals

    def test_empty_reviews(self) -> None:
        assert extract_owner_signals([]) == []


# ---------------------------------------------------------------------------
# Search result URL finding
# ---------------------------------------------------------------------------


class TestFindMapsUrl:
    def test_finds_maps_url(self) -> None:
        url = find_maps_url_from_results(
            "Frisco Mobile Detailing",
            SAMPLE_SEARCH_RESULTS,
            city="Frisco TX",
        )
        assert "maps.google.com" in url
        assert "123456789" in url

    def test_no_maps_results(self) -> None:
        results = [
            {"title": "Something", "url": "https://yelp.com/biz/test"},
        ]
        url = find_maps_url_from_results(
            "Test Biz",
            results,
            city="Dallas TX",
        )
        assert "google.com/maps/search" in url
        assert "Test" in url

    def test_empty_results(self) -> None:
        url = find_maps_url_from_results(
            "Test Biz",
            [],
            city="Frisco TX",
        )
        assert "google.com/maps/search" in url


# ---------------------------------------------------------------------------
# Full page parsing
# ---------------------------------------------------------------------------


class TestParseMapsPage:
    def test_full_parse(self) -> None:
        enrichment = parse_maps_page(
            SAMPLE_MAPS_TEXT,
            "Frisco Mobile Detailing",
            "https://maps.google.com/maps?cid=123456789",
        )
        assert enrichment.business_name == "Frisco Mobile Detailing"
        assert enrichment.rating == 4.9
        assert enrichment.review_count == 327
        assert enrichment.source_url == "https://maps.google.com/maps?cid=123456789"
        assert len(enrichment.hours) >= 6
        assert len(enrichment.services) >= 3
        assert len(enrichment.photos) >= 2
        assert len(enrichment.review_snippets) >= 3
        assert len(enrichment.differentiators) >= 2
        assert len(enrichment.owner_signals) >= 1

    def test_empty_page(self) -> None:
        enrichment = parse_maps_page("", "Empty Biz", "https://example.com")
        assert enrichment.business_name == "Empty Biz"
        assert enrichment.rating == 0.0
        assert enrichment.review_count == 0


# ---------------------------------------------------------------------------
# run_enrichment integration
# ---------------------------------------------------------------------------


class TestRunEnrichment:
    def test_with_direct_text(self) -> None:
        enrichment = run_enrichment(
            business_name="Test Biz",
            city="Austin TX",
            maps_url="https://maps.google.com/test",
            page_text="4.8 (50 Google reviews)\n\"Great service, highly recommend.\"",
        )
        assert enrichment.business_name == "Test Biz"
        assert enrichment.source_url == "https://maps.google.com/test"
        assert enrichment.rating == 4.8
        assert enrichment.review_count == 50

    def test_with_search_results(self) -> None:
        enrichment = run_enrichment(
            business_name="Test Biz",
            city="Dallas TX",
            search_results=SAMPLE_SEARCH_RESULTS,
            page_text="4.7 (42 reviews)\nMonday: 9 AM - 5 PM",
        )
        assert enrichment.source_url != ""
        assert enrichment.rating == 4.7

    def test_no_data_provided(self) -> None:
        enrichment = run_enrichment(
            business_name="Unknown Biz",
            city="Nowhere TX",
        )
        assert enrichment.business_name == "Unknown Biz"
        assert enrichment.rating == 0.0
        assert "google.com/maps/search" in enrichment.source_url


# ---------------------------------------------------------------------------
# Save / slugify
# ---------------------------------------------------------------------------


class TestSaveEnrichment:
    def test_saves_json(self, tmp_path: Path) -> None:
        enrichment = BusinessEnrichment(
            business_name="Test Biz",
            rating=4.5,
        )
        out = str(tmp_path / "subdir" / "test.json")
        saved = save_enrichment(enrichment, out)
        assert Path(saved).exists()
        data = json.loads(Path(saved).read_text(encoding="utf-8"))
        assert data["business_name"] == "Test Biz"
        assert data["rating"] == 4.5


class TestSlugify:
    def test_basic(self) -> None:
        assert slugify("Frisco Mobile Detailing") == "frisco-mobile-detailing"

    def test_special_chars(self) -> None:
        assert slugify("Joe's Auto & Detail") == "joe-s-auto-detail"

    def test_truncation(self) -> None:
        long = "A" * 100
        assert len(slugify(long)) == 64

    def test_empty(self) -> None:
        assert slugify("!!!") == "unknown"
