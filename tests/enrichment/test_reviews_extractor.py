"""Tests for reviews_extractor module — theme detection, differentiators, sentiment."""

from __future__ import annotations

from packages.enrichment.reviews_extractor import (
    ReviewInsights,
    clean_review_text,
    extract_themes,
    extract_differentiators_from_reviews,
    extract_key_phrases,
    analyze_sentiment,
    extract_review_insights,
    merge_review_insights_into_enrichment,
)


# ===========================================================================
# Review text cleaning
# ===========================================================================

class TestCleanReviewText:
    def test_removes_excess_whitespace(self):
        result = clean_review_text("Great   service!   Very  professional.")
        assert result == "Great service! Very professional."

    def test_removes_read_more_pattern(self):
        result = clean_review_text("Amazing work! Read more Show less")
        assert "Read more" not in result

    def test_removes_star_ratings(self):
        result = clean_review_text("5 stars out of 5. Great service!")
        assert "5 stars" not in result

    def test_empty_input(self):
        assert clean_review_text("") == ""
        assert clean_review_text(None) == ""


# ===========================================================================
# Theme extraction
# ===========================================================================

SAMPLE_REVIEWS = [
    "The quality was excellent! Very professional and detail-oriented work.",
    "He came to my office and my car looks brand new. Amazing quality.",
    "Fair pricing and great communication. They kept me updated throughout.",
    "Very professional team. Showed up on time and did amazing work.",
    "Great value for the price. Highly recommend their ceramic coating service.",
    "They went above and beyond. The attention to detail was outstanding.",
    "Excellent service from start to finish. Very responsive and communicative.",
]


class TestExtractThemes:
    def test_extracts_quality_theme(self):
        themes = extract_themes(SAMPLE_REVIEWS)
        theme_names = [t[0] for t in themes]
        assert "quality" in theme_names

    def test_extracts_professionalism_theme(self):
        themes = extract_themes(SAMPLE_REVIEWS)
        theme_names = [t[0] for t in themes]
        assert "professionalism" in theme_names

    def test_themes_sorted_by_frequency(self):
        themes = extract_themes(SAMPLE_REVIEWS)
        for i in range(len(themes) - 1):
            assert themes[i][1] >= themes[i + 1][1]

    def test_no_reviews_returns_empty(self):
        assert extract_themes([]) == []

    def test_single_review_single_theme(self):
        themes = extract_themes(["Very professional and detail-oriented."])
        assert len(themes) >= 1


# ===========================================================================
# Differentiator extraction
# ===========================================================================

SAMPLE_REVIEWS_DIFF = [
    "He came to my office and detailed my car. My car looks brand new!",
    "Very detail-oriented work. He brought his own water and supplies.",
    "Finished ahead of schedule. Fair pricing for the quality.",
    "The ceramic coating he applied is incredible.",
    "Very professional and punctual. Showed up on time.",
]


class TestExtractDifferentiators:
    def test_extracts_mobile_service(self):
        diffs = extract_differentiators_from_reviews(SAMPLE_REVIEWS_DIFF)
        assert any("mobile" in d.lower() for d in diffs)

    def test_extracts_attention_to_detail(self):
        diffs = extract_differentiators_from_reviews(SAMPLE_REVIEWS_DIFF)
        assert any("detail" in d.lower() for d in diffs)

    def test_respects_max_results(self):
        diffs = extract_differentiators_from_reviews(SAMPLE_REVIEWS_DIFF, max_results=2)
        assert len(diffs) <= 2

    def test_no_reviews(self):
        assert extract_differentiators_from_reviews([]) == []

    def test_no_matching_patterns(self):
        diffs = extract_differentiators_from_reviews(["Nice place.", "OK service."])
        assert diffs == []


# ===========================================================================
# Key phrase extraction
# ===========================================================================

SAMPLE_REVIEWS_PHRASES = [
    "He came to my office and detailed my car in the parking lot. My car looks brand new! The owner himself did the work.",
    "Very detail-oriented work. He brought his own water and supplies. Finished ahead of schedule.",
    "The ceramic coating is incredible. My car looks like it just rolled off the showroom floor.",
]


class TestExtractKeyPhrases:
    def test_extracts_meaningful_phrases(self):
        phrases = extract_key_phrases(SAMPLE_REVIEWS_PHRASES)
        assert len(phrases) > 0
        # Should contain at least one meaningful sentence
        assert any(len(p) >= 20 for p in phrases)

    def test_no_reviews(self):
        assert extract_key_phrases([]) == []

    def test_quoted_text_preferred(self):
        reviews = ['Customer said "Amazing service, will definitely return!"']
        phrases = extract_key_phrases(reviews)
        assert len(phrases) > 0

    def test_skips_short_phrases(self):
        phrases = extract_key_phrases(["OK"])
        assert phrases == []

    def test_deduplicates_similar_phrases(self):
        reviews = ["Great service! Amazing work!", "Great service! Wonderful work!"]
        phrases = extract_key_phrases(reviews)
        # "Great service!" should only appear once due to dedup normalization
        great_service_count = sum(1 for p in phrases if "Great service" in p)
        assert great_service_count <= 1


# ===========================================================================
# Sentiment analysis
# ===========================================================================

SAMPLE_POSITIVE = [
    "Amazing service! The best detailing I've ever had.",
    "Excellent quality and highly recommend.",
    "Great work, will return for sure!",
]

SAMPLE_NEGATIVE = [
    "Terrible service. Worst experience ever.",
    "Poor quality work, very disappointing.",
    "Avoid this place. Never again.",
]

SAMPLE_MIXED = [
    "Great work but a bit expensive.",
    "Good quality, but communication could be better.",
    "Nice results, though took longer than expected.",
]


class TestAnalyzeSentiment:
    def test_positive_sentiment(self):
        result = analyze_sentiment(SAMPLE_POSITIVE)
        assert result["positive"] > 0
        assert result["negative"] == 0

    def test_negative_sentiment(self):
        result = analyze_sentiment(SAMPLE_NEGATIVE)
        assert result["negative"] > 0
        assert result["positive"] == 0

    def test_mixed_sentiment(self):
        result = analyze_sentiment(SAMPLE_MIXED)
        # Mixed reviews should have both or be mostly neutral
        assert result["positive"] + result["negative"] + result["neutral"] > 0

    def test_no_reviews(self):
        result = analyze_sentiment([])
        assert result["positive"] == 0
        assert result["negative"] == 0

    def test_neutral_sentiment(self):
        result = analyze_sentiment(["The service was provided on Tuesday."])
        assert result.get("neutral", 0) >= 1


# ===========================================================================
# ReviewInsights dataclass
# ===========================================================================

class TestReviewInsights:
    def test_defaults(self):
        insights = ReviewInsights()
        assert insights.differentiators == []
        assert insights.common_themes == []
        assert insights.key_phrases == []
        assert insights.sentiment_signals == {}

    def test_to_dict(self):
        insights = ReviewInsights(
            differentiators=["mobile service"],
            common_themes=[("quality", 3)],
            key_phrases=["Great job!"],
            sentiment_signals={"positive": 2, "negative": 0},
        )
        d = insights.to_dict()
        assert d["differentiators"] == ["mobile service"]
        assert d["common_themes"] == [("quality", 3)]


# ===========================================================================
# Main extraction pipeline
# ===========================================================================

class TestExtractReviewInsights:
    def test_full_pipeline(self):
        insights = extract_review_insights(SAMPLE_REVIEWS)
        assert isinstance(insights, ReviewInsights)
        assert len(insights.differentiators) > 0
        assert len(insights.common_themes) > 0
        assert len(insights.key_phrases) >= 0
        assert "positive" in insights.sentiment_signals

    def test_no_reviews(self):
        insights = extract_review_insights([])
        assert insights.differentiators == []
        assert insights.common_themes == []
        assert insights.customer_quotes == []

    def test_empty_reviews_list(self):
        insights = extract_review_insights([], max_differentiators=3)
        assert isinstance(insights, ReviewInsights)


# ===========================================================================
# Merge into enrichment
# ===========================================================================

class TestMergeReviewInsights:
    def test_merges_differentiators(self):
        enrichment = {"differentiators": ["existing diff"]}
        insights = ReviewInsights(differentiators=["mobile service", "fair pricing"])
        result = merge_review_insights_into_enrichment(enrichment, insights)
        assert "mobile service" in result["differentiators"]
        assert "existing diff" in result["differentiators"]

    def test_adds_review_insights_field(self):
        enrichment = {}
        insights = ReviewInsights(
            differentiators=["mobile service"],
            common_themes=[("quality", 3)],
        )
        result = merge_review_insights_into_enrichment(enrichment, insights)
        assert "review_insights" in result
        assert result["review_insights"]["differentiators"] == ["mobile service"]

    def test_strong_theme_adds_signal(self):
        enrichment = {"differentiators": []}
        insights = ReviewInsights(
            differentiators=[],
            common_themes=[("quality", 5)],  # >= 3 should add signal
        )
        result = merge_review_insights_into_enrichment(enrichment, insights)
        assert any("quality" in d.lower() for d in result.get("differentiators", []))

    def test_weak_theme_does_not_add_signal(self):
        enrichment = {"differentiators": []}
        insights = ReviewInsights(
            differentiators=[],
            common_themes=[("value", 1)],  # < 3 should not add
        )
        merge_review_insights_into_enrichment(enrichment, insights)
        # The theme only has count=1, so it should NOT add a signal
        assert enrichment["differentiators"] == []  # Should be unchanged

    def test_none_insights(self):
        assert merge_review_insights_into_enrichment({"k": "v"}, None) == {"k": "v"}
