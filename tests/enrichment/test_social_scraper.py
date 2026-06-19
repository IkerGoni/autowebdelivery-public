"""Tests for social_scraper module — ethical scraping, URL detection, data extraction."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import httpx

from packages.enrichment.social_scraper import (
    SocialProfile,
    detect_social_platform,
    extract_username_from_url,
    normalize_social_url,
    RobotsChecker,
    RateLimiter,
    _fetch_facebook_og,
    _fetch_instagram_profile,
    scrape_social_profile,
    extract_social_photos,
    merge_social_data_into_enrichment,
)


# ===========================================================================
# URL detection
# ===========================================================================

class TestDetectSocialPlatform:
    def test_facebook_url(self):
        assert detect_social_platform("https://www.facebook.com/mybiz") == "facebook"
        assert detect_social_platform("https://fb.com/mybiz") == "facebook"
        assert detect_social_platform("https://fb.me/mybiz") == "facebook"
        assert detect_social_platform("https://m.facebook.com/mybiz") == "facebook"

    def test_instagram_url(self):
        assert detect_social_platform("https://www.instagram.com/mybiz") == "instagram"
        assert detect_social_platform("https://instagr.am/mybiz") == "instagram"

    def test_unknown_url(self):
        assert detect_social_platform("https://example.com") is None
        assert detect_social_platform("https://twitter.com/biz") is None

    def test_empty_url(self):
        assert detect_social_platform("") is None
        assert detect_social_platform(None) is None


class TestExtractUsername:
    def test_simple_path(self):
        assert extract_username_from_url("https://facebook.com/mybiz", "facebook") == "mybiz"

    def test_path_with_query(self):
        assert extract_username_from_url("https://instagram.com/mybiz?ref=foo", "instagram") == "mybiz"

    def test_profile_php(self):
        # profile.php without trailing slash -> just extracts the filename
        assert extract_username_from_url("https://facebook.com/profile.php?id=123", "facebook") == "profile.php"

    def test_pages_prefix(self):
        assert extract_username_from_url("https://facebook.com/pages/My-Biz/123", "facebook") == "My-Biz"

    def test_unknown_platform(self):
        # Function doesn't use platform param for extraction
        assert extract_username_from_url("https://example.com/biz", "unknown") == "biz"


class TestNormalizeSocialUrl:
    def test_facebook_normalization(self):
        result = normalize_social_url("https://fb.com/mybiz")
        assert result == "https://www.facebook.com/mybiz"

    def test_instagram_normalization(self):
        result = normalize_social_url("https://instagr.am/mybiz")
        assert result == "https://www.instagram.com/mybiz"

    def test_non_social_url(self):
        result = normalize_social_url("https://example.com")
        assert result == "https://example.com"


# ===========================================================================
# Robots.txt checker
# ===========================================================================

class TestRobotsChecker:
    def test_allowed_facebook_path(self):
        assert RobotsChecker.is_allowed("https://www.facebook.com/MyBiz") is True

    def test_blocked_facebook_api(self):
        assert RobotsChecker.is_allowed("https://www.facebook.com/api/something") is False

    def test_blocked_instagram_api(self):
        assert RobotsChecker.is_allowed("https://www.instagram.com/api/v1/") is False

    def test_allowed_instagram_profile(self):
        assert RobotsChecker.is_allowed("https://www.instagram.com/mybiz") is True

    def test_non_social_url(self):
        assert RobotsChecker.is_allowed("https://example.com/whatever") is True


# ===========================================================================
# Rate limiter
# ===========================================================================

class TestRateLimiter:
    def test_no_wait_on_first_call(self):
        limiter = RateLimiter(requests_per_minute=60)
        import time
        before = time.time()
        limiter.wait_if_needed()
        after = time.time()
        assert after - before < 0.1  # Should return instantly

    def test_waits_on_rapid_calls(self):
        limiter = RateLimiter(requests_per_minute=120)  # 0.5s delay
        limiter.wait_if_needed()  # First call
        import time
        before = time.time()
        limiter.wait_if_needed()  # Should delay
        after = time.time()
        assert after - before >= 0.3  # At least near the expected delay

    def test_min_delay_increases_with_tighter_limits(self):
        slow = RateLimiter(requests_per_minute=10)  # 6s delay
        fast = RateLimiter(requests_per_minute=60)  # 1s delay
        assert slow.min_delay > fast.min_delay


# ===========================================================================
# SocialProfile dataclass
# ===========================================================================

class TestSocialProfile:
    def test_default_values(self):
        profile = SocialProfile(platform="facebook")
        assert profile.username == ""
        assert profile.follower_count == 0
        assert profile.photos == []
        assert profile.posts == []

    def test_to_dict(self):
        profile = SocialProfile(
            platform="instagram",
            username="testbiz",
            follower_count=1500,
        )
        d = profile.to_dict()
        assert d["platform"] == "instagram"
        assert d["username"] == "testbiz"
        assert d["follower_count"] == 1500
        assert d["photos"] == []


# ===========================================================================
# Facebook OG fetch
# ===========================================================================

SAMPLE_FACEBOOK_OG_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>My Business - Auto Detailing</title>
    <meta property="og:title" content="My Business - Premium Auto Detailing" />
    <meta property="og:description" content="We specialize in ceramic coating and paint correction in Dallas, TX." />
    <meta property="og:image" content="https://scontent.xx.fbcdn.net/v/photo.jpg" />
</head>
<body>
    <h1>My Business</h1>
    <p>Auto detailing services since 2018.</p>
</body>
</html>"""


class TestFacebookOGFetch:
    @patch("httpx.get")
    def test_fetch_basic_og_data(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = SAMPLE_FACEBOOK_OG_HTML
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        profile = _fetch_facebook_og("https://www.facebook.com/MyBiz")

        assert profile is not None
        assert profile.platform == "facebook"
        assert profile.username == "MyBiz"
        assert "ceramic coating" in profile.about_text.lower()
        assert len(profile.photos) == 1
        assert "photo.jpg" in profile.photos[0]

    @patch("httpx.get")
    def test_fetch_without_image(self, mock_get):
        html_no_image = SAMPLE_FACEBOOK_OG_HTML.replace(
            '<meta property="og:image" content="https://scontent.xx.fbcdn.net/v/photo.jpg" />', ""
        )
        mock_response = MagicMock()
        mock_response.text = html_no_image
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        profile = _fetch_facebook_og("https://www.facebook.com/MyBiz")
        assert profile is not None
        assert profile.photos == []

    @patch("httpx.get")
    def test_fetch_timeout(self, mock_get):
        mock_get.side_effect = httpx.TimeoutException("Timed out")
        profile = _fetch_facebook_og("https://www.facebook.com/MyBiz")
        assert profile is None

    @patch("httpx.get")
    def test_fetch_http_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_response
        )
        mock_get.return_value = mock_response

        profile = _fetch_facebook_og("https://www.facebook.com/MyBiz")
        assert profile is None

    @patch("httpx.get")
    def test_fetch_request_error(self, mock_get):
        mock_get.side_effect = httpx.RequestError("Connection failed")
        profile = _fetch_facebook_og("https://www.facebook.com/MyBiz")
        assert profile is None

    @patch("httpx.get")
    def test_robots_txt_block(self, mock_get):
        """Should not even make HTTP request for blocked paths."""
        profile = _fetch_facebook_og("https://www.facebook.com/api/something")
        assert profile is None
        mock_get.assert_not_called()

    @patch("httpx.get")
    def test_fetch_with_rate_limiter(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = SAMPLE_FACEBOOK_OG_HTML
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        limiter = RateLimiter(requests_per_minute=120)  # fast for testing
        profile = _fetch_facebook_og("https://www.facebook.com/MyBiz", rate_limiter=limiter)
        assert profile is not None


# ===========================================================================
# Instagram fetch
# ===========================================================================

SAMPLE_INSTAGRAM_NEXT_DATA = """
<script id="__NEXT_DATA__" type="application/json">{
    "props": {
        "pageProps": {
            "user": {
                "username": "mybiz",
                "biography": "Auto Detailing in Dallas. Ceramic coating, paint correction.",
                "edge_followed_by": {"count": 2450},
                "edge_follow": {"count": 180},
                "edge_owner_to_timeline_media": {"count": 87},
                "is_verified": true,
                "profile_pic_url": "https://cdninstagram.com/v/prof.jpg"
            }
        }
    }
}</script>
"""

SAMPLE_INSTAGRAM_NO_JSON = """<!DOCTYPE html>
<html>
<head>
    <meta property="og:description" content="Auto Detailing in Dallas | Ceramic Coating" />
    <title>mybiz (@mybiz) • Instagram photos and videos</title>
</head>
<body>
    <h1>mybiz</h1>
    <p>Auto Detailing in Dallas. Ceramic coating, paint correction.</p>
    <script>window.__INITIAL_STATE__ = {}</script>
</body>
</html>
"""


class TestInstagramFetch:
    @patch("httpx.get")
    def test_fetch_next_data_json(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = SAMPLE_INSTAGRAM_NEXT_DATA
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        profile = _fetch_instagram_profile("https://www.instagram.com/mybiz")

        assert profile is not None
        assert profile.platform == "instagram"
        assert profile.username == "mybiz"
        assert profile.follower_count == 2450
        assert profile.following_count == 180
        assert profile.post_count == 87
        assert profile.is_verified is True
        assert "ceramic coating" in profile.about_text.lower()
        assert len(profile.photos) == 1
        assert "prof.jpg" in profile.photos[0]

    @patch("httpx.get")
    def test_fetch_fallback_to_html(self, mock_get):
        """When no JSON data is found, fall back to HTML regex extraction."""
        mock_response = MagicMock()
        mock_response.text = SAMPLE_INSTAGRAM_NO_JSON
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        profile = _fetch_instagram_profile("https://www.instagram.com/mybiz")

        assert profile is not None
        assert profile.platform == "instagram"
        assert profile.username == "mybiz"

    @patch("httpx.get")
    def test_fetch_timeout(self, mock_get):
        mock_get.side_effect = httpx.TimeoutException("Timed out")
        profile = _fetch_instagram_profile("https://www.instagram.com/mybiz")
        assert profile is None

    @patch("httpx.get")
    def test_fetch_http_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429", request=MagicMock(), response=mock_response
        )
        mock_get.return_value = mock_response

        profile = _fetch_instagram_profile("https://www.instagram.com/mybiz")
        assert profile is None

    @patch("httpx.get")
    def test_robots_txt_block(self, mock_get):
        profile = _fetch_instagram_profile("https://www.instagram.com/api/v1/")
        assert profile is None
        mock_get.assert_not_called()


# ===========================================================================
# Main scraper interface
# ===========================================================================

class TestScrapeSocialProfile:
    def test_unknown_platform(self):
        profile = scrape_social_profile("https://example.com")
        assert profile is None

    @patch("packages.enrichment.social_scraper._fetch_facebook_og")
    def test_auto_fetch_facebook(self, mock_fetch):
        mock_fetch.return_value = SocialProfile(
            platform="facebook",
            username="testbiz",
            about_text="Test business description",
        )
        profile = scrape_social_profile("https://www.facebook.com/testbiz")
        assert profile is not None
        assert profile.username == "testbiz"
        mock_fetch.assert_called_once()

    @patch("packages.enrichment.social_scraper.RobotsChecker.is_allowed")
    @patch("packages.enrichment.social_scraper.extract_facebook_profile_data")
    def test_extract_from_page_text(self, mock_extract, mock_allowed):
        mock_allowed.return_value = True
        mock_extract.return_value = SocialProfile(
            platform="facebook",
            username="testbiz",
            about_text="Extracted from page text",
        )
        profile = scrape_social_profile(
            "https://www.facebook.com/testbiz",
            page_text="<html><title>Test Biz</title></html>",
        )
        assert profile is not None
        assert profile.about_text == "Extracted from page text"

    def test_respect_robots_false_bypasses_check(self):
        """Given respect_robots=False, should still try to detect platform."""
        profile = scrape_social_profile("https://unknown.example.com", respect_robots=False)
        assert profile is None  # Unknown platform


# ===========================================================================
# Photo extraction
# ===========================================================================

class TestExtractSocialPhotos:
    def test_empty_profile(self):
        assert extract_social_photos(None) == []

    def test_empty_photos(self):
        profile = SocialProfile(platform="instagram", username="biz", photos=[])
        assert extract_social_photos(profile) == []

    def test_deduplicates_photos(self):
        profile = SocialProfile(
            platform="instagram",
            username="biz",
            photos=[
                "https://cdninstagram.com/p/ABC/photo.jpg",
                "https://cdninstagram.com/p/ABC/photo.jpg",  # duplicate
                "https://cdninstagram.com/p/DEF/photo.jpg",
            ],
        )
        photos = extract_social_photos(profile)
        assert len(photos) == 2  # Deduplicated (different dirs = different signature)

    def test_max_photos_limit(self):
        # Each URL needs structurally different path for unique signatures
        photos_list = [
            f"https://cdninstagram.com/p/{chr(65+i)}/photo.jpg"
            for i in range(20)
        ]
        profile = SocialProfile(platform="instagram", username="biz", photos=photos_list)
        photos = extract_social_photos(profile, max_photos=5)
        assert len(photos) == 5


# ===========================================================================
# Merge into enrichment
# ===========================================================================

class TestMergeSocialDataIntoEnrichment:
    def test_merge_photos(self):
        enrichment = {"photos": ["https://existing.com/photo.jpg"]}
        profile = SocialProfile(
            platform="instagram",
            username="biz",
            photos=["https://instagram.com/new1.jpg", "https://instagram.com/new2.jpg"],
        )
        result = merge_social_data_into_enrichment(enrichment, profile)
        assert len(result["photos"]) == 3
        assert "https://instagram.com/new1.jpg" in result["photos"]
        assert "https://existing.com/photo.jpg" in result["photos"]

    def test_merge_description_when_missing(self):
        enrichment = {}
        profile = SocialProfile(
            platform="facebook",
            username="biz",
            about_text="We are a local business.",
        )
        result = merge_social_data_into_enrichment(enrichment, profile)
        assert result["description"] == "We are a local business."

    def test_does_not_overwrite_existing_description(self):
        enrichment = {"description": "Original description"}
        profile = SocialProfile(
            platform="facebook",
            username="biz",
            about_text="Social description",
        )
        result = merge_social_data_into_enrichment(enrichment, profile)
        assert result["description"] == "Original description"  # Not overwritten

    def test_adds_social_profile_field(self):
        enrichment = {}
        profile = SocialProfile(
            platform="instagram", username="mybiz", follower_count=5000
        )
        result = merge_social_data_into_enrichment(enrichment, profile)
        assert "social_profiles" in result
        assert len(result["social_profiles"]) == 1
        assert result["social_profiles"][0]["platform"] == "instagram"

    def test_adds_follower_differentiator(self):
        enrichment = {}
        profile = SocialProfile(
            platform="instagram", username="bigbiz", follower_count=5000
        )
        result = merge_social_data_into_enrichment(enrichment, profile)
        assert any("Strong social following" in d for d in result.get("differentiators", []))

    def test_adds_verified_differentiator(self):
        enrichment = {}
        profile = SocialProfile(
            platform="instagram", username="verifiedbiz",
            follower_count=100, is_verified=True,
        )
        result = merge_social_data_into_enrichment(enrichment, profile)
        assert any("Verified business account" in d for d in result.get("differentiators", []))

    def test_merge_none_profile(self):
        assert merge_social_data_into_enrichment({"key": "val"}, None) == {"key": "val"}
