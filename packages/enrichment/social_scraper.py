"""Social Media Scraper - Public data extraction from Facebook/Instagram.

Ethical scraping: respects robots.txt, rate limits, public-only data.
NO login required - extracts publicly visible business information.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class SocialProfile:
    """Structured social media profile data."""
    
    platform: str  # "facebook" or "instagram"
    username: str = ""
    profile_url: str = ""
    about_text: str = ""
    posts: list[dict[str, Any]] = field(default_factory=list)
    photos: list[str] = field(default_factory=list)
    follower_count: int = 0
    following_count: int = 0
    post_count: int = 0
    is_verified: bool = False
    business_category: str = ""
    contact_info: dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# URL detection and validation
# ---------------------------------------------------------------------------

def detect_social_platform(url: str) -> str | None:
    """Detect social media platform from URL.
    
    Returns: "facebook", "instagram", or None
    """
    if not url:
        return None
    
    url_lower = url.lower()
    
    if any(pattern in url_lower for pattern in [
        "facebook.com/", "fb.com/", "fb.me/", "m.facebook.com/"
    ]):
        return "facebook"
    
    if any(pattern in url_lower for pattern in [
        "instagram.com/", "instagr.am/", "ig.me/"
    ]):
        return "instagram"
    
    return None


def extract_username_from_url(url: str, platform: str) -> str:
    """Extract username/page name from social URL."""
    if not url or not platform:
        return ""
    
    try:
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        
        # Remove common prefixes
        path = re.sub(r"^(profile\.php|pages?|pg)/", "", path, flags=re.I)
        
        # Extract first path segment
        parts = path.split("/")
        if parts and parts[0]:
            # Clean query params
            username = parts[0].split("?")[0]
            return username
    except Exception as e:
        logger.debug(f"Failed to extract username from {url}: {e}")
    
    return ""


def normalize_social_url(url: str) -> str:
    """Normalize social media URL to canonical format."""
    platform = detect_social_platform(url)
    if not platform:
        return url
    
    username = extract_username_from_url(url, platform)
    if not username:
        return url
    
    if platform == "facebook":
        return f"https://www.facebook.com/{username}"
    elif platform == "instagram":
        return f"https://www.instagram.com/{username}"
    
    return url


# ---------------------------------------------------------------------------
# Robots.txt checker
# ---------------------------------------------------------------------------

class RobotsChecker:
    """Simple robots.txt checker for ethical scraping."""
    
    # Known disallowed patterns for major platforms
    KNOWN_RULES = {
        "facebook.com": [
            "/ajax/", "/dialog/", "/connect/", "/intern/",
            "/api/", "/tr/", "/plugins/", "/l.php"
        ],
        "instagram.com": [
            "/api/", "/graphql/", "/accounts/", "/direct/"
        ]
    }
    
    @classmethod
    def is_allowed(cls, url: str, user_agent: str = "*") -> bool:
        """Check if URL is allowed by robots.txt rules.
        
        Conservative approach: uses known rules for major platforms.
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            path = parsed.path.lower()
            
            # Check known rules
            for rule_domain, disallowed_paths in cls.KNOWN_RULES.items():
                if rule_domain in domain:
                    for disallowed in disallowed_paths:
                        if path.startswith(disallowed):
                            logger.warning(f"URL blocked by robots.txt: {url}")
                            return False
            
            return True
        except Exception as e:
            logger.error(f"Error checking robots.txt for {url}: {e}")
            return False


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """Simple rate limiter for ethical scraping."""
    
    def __init__(self, requests_per_minute: int = 10):
        self.requests_per_minute = requests_per_minute
        self.min_delay = 60.0 / requests_per_minute
        self.last_request_time: float = 0.0
    
    def wait_if_needed(self) -> None:
        """Wait if necessary to respect rate limit."""
        now = time.time()
        time_since_last = now - self.last_request_time
        
        if time_since_last < self.min_delay:
            sleep_time = self.min_delay - time_since_last
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()


# ---------------------------------------------------------------------------
# HTTP fetching functions
# ---------------------------------------------------------------------------

_USER_AGENT = "Mozilla/5.0 (compatible; Autowebdelivery/1.0)"
_FETCH_TIMEOUT = 10.0
_MIN_RATE_LIMIT = 5  # requests per minute


def _fetch_facebook_og(url: str, rate_limiter: RateLimiter | None = None) -> SocialProfile | None:
    """Fetch Facebook page HTML and extract Open Graph metadata.

    Extracts og:title, og:description, og:image, and business name from
    the page <title> tag.  Respects robots.txt and rate limiting.

    Args:
        url: Facebook profile / page URL.
        rate_limiter: Optional RateLimiter instance.  If not provided a
            default limiter at 5 req/min is created.

    Returns:
        SocialProfile with available data, or None on failure.
    """
    # --- robots.txt check ---------------------------------------------------
    if not RobotsChecker.is_allowed(url):
        logger.warning("Facebook URL blocked by robots.txt: %s", url)
        return None

    # --- rate limiter --------------------------------------------------------
    limiter = rate_limiter or RateLimiter(requests_per_minute=_MIN_RATE_LIMIT)
    limiter.wait_if_needed()

    # --- HTTP request --------------------------------------------------------
    try:
        response = httpx.get(url, headers={"User-Agent": _USER_AGENT}, timeout=_FETCH_TIMEOUT, follow_redirects=True)
        response.raise_for_status()
    except httpx.TimeoutException:
        logger.warning("Facebook fetch timed out (10s) for: %s", url)
        return None
    except httpx.HTTPStatusError as e:
        logger.warning("Facebook fetch HTTP error %s for: %s", e.response.status_code, url)
        return None
    except httpx.RequestError as e:
        logger.warning("Facebook fetch request error for %s: %s", url, e)
        return None

    html = response.text

    # --- extract data --------------------------------------------------------
    username = extract_username_from_url(url, "facebook")
    profile = SocialProfile(
        platform="facebook",
        username=username,
        profile_url=normalize_social_url(url),
    )

    # page <title>
    title_match = re.search(r"<title[^>]*>(.+?)</title>", html, re.I | re.DOTALL)
    if title_match:
        profile.business_category = title_match.group(1).strip()[:200]

    # og:title
    og_title = re.search(
        r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']',
        html,
        re.I,
    )
    if not og_title:
        og_title = re.search(
            r'<meta\s+content=["\']([^"\']+)["\']\s+property=["\']og:title["\']',
            html,
            re.I,
        )
    if og_title and not profile.about_text:
        profile.about_text = og_title.group(1).strip()[:500]

    # og:description
    og_desc = re.search(
        r'<meta\s+property=["\']og:description["\']\s+content=["\']([^"\']+)["\']',
        html,
        re.I,
    )
    if not og_desc:
        og_desc = re.search(
            r'<meta\s+content=["\']([^"\']+)["\']\s+property=["\']og:description["\']',
            html,
            re.I,
        )
    if og_desc:
        profile.about_text = og_desc.group(1).strip()[:500]

    # og:image
    og_image = re.search(
        r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
        html,
        re.I,
    )
    if not og_image:
        og_image = re.search(
            r'<meta\s+content=["\']([^"\']+)["\']\s+property=["\']og:image["\']',
            html,
            re.I,
        )
    if og_image:
        img_url = og_image.group(1).strip()
        if img_url:
            profile.photos.append(img_url)

    logger.info("Fetched Facebook OG data for %s — title=%s", url, bool(title_match))
    return profile


def _fetch_instagram_profile(url: str, rate_limiter: RateLimiter | None = None) -> SocialProfile | None:
    """Fetch Instagram profile HTML and extract embedded JSON data.

    Extracts biography, follower count (edge_followed_by), following count
    (edge_follow), post count (edge_owner_to_timeline_media), profile picture,
    and verification status from the page's embedded JSON.

    Args:
        url: Instagram profile URL.
        rate_limiter: Optional RateLimiter instance.  If not provided a
            default limiter at 5 req/min is created.

    Returns:
        SocialProfile with available data, or None on failure.
    """
    # --- robots.txt check ---------------------------------------------------
    if not RobotsChecker.is_allowed(url):
        logger.warning("Instagram URL blocked by robots.txt: %s", url)
        return None

    # --- rate limiter --------------------------------------------------------
    limiter = rate_limiter or RateLimiter(requests_per_minute=_MIN_RATE_LIMIT)
    limiter.wait_if_needed()

    # --- HTTP request --------------------------------------------------------
    try:
        response = httpx.get(url, headers={"User-Agent": _USER_AGENT}, timeout=_FETCH_TIMEOUT, follow_redirects=True)
        response.raise_for_status()
    except httpx.TimeoutException:
        logger.warning("Instagram fetch timed out (10s) for: %s", url)
        return None
    except httpx.HTTPStatusError as e:
        logger.warning("Instagram fetch HTTP error %s for: %s", e.response.status_code, url)
        return None
    except httpx.RequestError as e:
        logger.warning("Instagram fetch request error for %s: %s", url, e)
        return None

    html = response.text

    # --- extract data --------------------------------------------------------
    username = extract_username_from_url(url, "instagram")
    profile = SocialProfile(
        platform="instagram",
        username=username,
        profile_url=normalize_social_url(url),
    )

    # Try to find JSON data in <script> tags.
    # Instagram embeds profile data in __NEXT_DATA__ or sharedData.
    json_data: dict[str, Any] | None = None

    # 1. Try __NEXT_DATA__ (current Instagram)
    script_match = re.search(
        r'<script[^>]*id="__NEXT_DATA__"[^>]*type="application/json"[^>]*>(.*?)</script>',
        html,
        re.I | re.DOTALL,
    )
    if script_match:
        try:
            parsed = json.loads(script_match.group(1))
            json_data = parsed
        except json.JSONDecodeError:
            pass

    # 2. Try window.__INITIAL_STATE__ embedded in a script tag
    if not json_data:
        init_match = re.search(
            r'<script[^>]*>window\.__INITIAL_STATE__\s*=\s*({.*?});</script>',
            html,
            re.I | re.DOTALL,
        )
        if init_match:
            try:
                json_data = json.loads(init_match.group(1))
            except json.JSONDecodeError:
                pass

    # 3. Fallback: try any script with application/ld+json
    if not json_data:
        ld_match = re.search(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
            html,
            re.I | re.DOTALL,
        )
        if ld_match:
            try:
                parsed = json.loads(ld_match.group(1))
                if isinstance(parsed, dict):
                    json_data = parsed
            except json.JSONDecodeError:
                pass

    # Extract profile data from JSON structure
    if json_data:
        _extract_instagram_from_json(json_data, profile)
    else:
        # Fallback to regex-based extraction on raw HTML
        _extract_instagram_from_html(html, profile)

    logger.info(
        "Fetched Instagram profile for %s — bio=%s, followers=%s",
        url,
        bool(profile.about_text),
        profile.follower_count,
    )
    return profile


def _extract_instagram_from_json(data: dict[str, Any], profile: SocialProfile) -> None:
    """Helper: extract Instagram profile fields from parsed JSON data.

    Traverses common Instagram JSON structures (__NEXT_DATA__, __INITIAL_STATE__, etc.).
    """
    # Try to find user data in the JSON tree
    user_data: dict[str, Any] | None = None

    # __NEXT_DATA__ structure: props > pageProps > user > username
    if "props" in data:
        props = data["props"]
        if isinstance(props, dict):
            page_props = props.get("pageProps", {})
            if isinstance(page_props, dict):
                user_data = page_props.get("user", None)

    # __INITIAL_STATE__ structure: user > {username}
    if not user_data and "user" in data:
        user_data = data["user"]
        # user might be keyed by username — grab the first value if it's a dict of users
        if isinstance(user_data, dict) and profile.username in user_data:
            user_data = user_data[profile.username]

    if not user_data or not isinstance(user_data, dict):
        return

    # biography
    bio = user_data.get("biography") or user_data.get("bio") or ""
    if bio:
        profile.about_text = str(bio)[:500]

    # follower count
    edge_followed_by = user_data.get("edge_followed_by") or user_data.get("edge_followed_by", {})
    if isinstance(edge_followed_by, dict):
        profile.follower_count = int(edge_followed_by.get("count", 0))
    elif isinstance(edge_followed_by, (int, float)):
        profile.follower_count = int(edge_followed_by)

    # following count
    edge_follow = user_data.get("edge_follow") or user_data.get("edge_follow", {})
    if isinstance(edge_follow, dict):
        profile.following_count = int(edge_follow.get("count", 0))
    elif isinstance(edge_follow, (int, float)):
        profile.following_count = int(edge_follow)

    # post count
    edge_owner = user_data.get("edge_owner_to_timeline_media") or user_data.get("edge_owner_to_timeline_media", {})
    if isinstance(edge_owner, dict):
        profile.post_count = int(edge_owner.get("count", 0))
    elif isinstance(edge_owner, (int, float)):
        profile.post_count = int(edge_owner)

    # verification
    if user_data.get("is_verified") or user_data.get("verified"):
        profile.is_verified = True

    # profile pic
    profile_pic = (
        user_data.get("profile_pic_url")
        or user_data.get("profile_pic_url_hd")
        or user_data.get("profilePictureUrl")
        or user_data.get("profile_picture")
        or ""
    )
    if profile_pic:
        profile.photos.append(str(profile_pic))


def _extract_instagram_from_html(html: str, profile: SocialProfile) -> None:
    """Helper: extract Instagram profile fields from raw HTML (regex fallback)."""
    # Use the existing extract_instagram_profile_data logic
    extracted = extract_instagram_profile_data(html, profile.profile_url)
    if extracted.about_text:
        profile.about_text = extracted.about_text
    if extracted.follower_count:
        profile.follower_count = extracted.follower_count
    if extracted.following_count:
        profile.following_count = extracted.following_count
    if extracted.post_count:
        profile.post_count = extracted.post_count
    if extracted.is_verified:
        profile.is_verified = True
    if extracted.photos:
        profile.photos = extracted.photos


# ---------------------------------------------------------------------------
# Public data extraction from page content
# ---------------------------------------------------------------------------

def extract_facebook_profile_data(page_text: str, profile_url: str) -> SocialProfile:
    """Extract public Facebook page data from extracted page text."""
    username = extract_username_from_url(profile_url, "facebook")
    
    profile = SocialProfile(
        platform="facebook",
        username=username,
        profile_url=normalize_social_url(profile_url)
    )
    
    # Extract about text
    about_patterns = [
        r"(?:About|Description|Bio)[:\s]+([^\n]{20,500})",
        r"<meta\s+property=\"og:description\"\s+content=\"([^\"]+)\"",
        r"\"description\":\s*\"([^\"]+)\"",
    ]
    for pattern in about_patterns:
        match = re.search(pattern, page_text, re.I | re.DOTALL)
        if match:
            profile.about_text = match.group(1).strip()[:500]
            break
    
    # Extract photos (look for image URLs)
    photo_pattern = re.compile(
        r"https?://[^\\s\"'<>)]+?\.(?:jpg|jpeg|png|webp)(?:\?[^\\s\"'<>)]*)?",
        re.I
    )
    seen_photos = set()
    for match in photo_pattern.finditer(page_text):
        url = match.group(0)
        # Skip icons, thumbnails, profile pics
        if any(skip in url.lower() for skip in [
            "icon", "logo", "avatar", "profile_pic", "emoji",
            "static.xx", "pixel", "1x1", "spacer"
        ]):
            continue
        if url not in seen_photos and len(seen_photos) < 10:
            seen_photos.add(url)
            profile.photos.append(url)
    
    # Extract follower count
    follower_patterns = [
        r"(\d[\d,\.]+)\s*(?:followers?|likes?|fans?)",
        r"(?:followers?|likes?)[\s:]+(\d[\d,\.]+)",
    ]
    for pattern in follower_patterns:
        match = re.search(pattern, page_text, re.I)
        if match:
            try:
                count_str = match.group(1).replace(",", "").replace(".", "")
                profile.follower_count = int(count_str)
                break
            except (ValueError, IndexError):
                continue
    
    # Extract business category
    category_patterns = [
        r"(?:Category|Business\s+type)[:\s]+([A-Za-z\s&-]+)",
        r"\"category\":\s*\"([^\"]+)\"",
    ]
    for pattern in category_patterns:
        match = re.search(pattern, page_text, re.I)
        if match:
            profile.business_category = match.group(1).strip()[:100]
            break
    
    return profile


def extract_instagram_profile_data(page_text: str, profile_url: str) -> SocialProfile:
    """Extract public Instagram profile data from extracted page text."""
    username = extract_username_from_url(profile_url, "instagram")
    
    profile = SocialProfile(
        platform="instagram",
        username=username,
        profile_url=normalize_social_url(profile_url)
    )
    
    # Extract bio
    bio_patterns = [
        r"\"biography\":\s*\"([^\"]+)\"",
        r"<meta\s+property=\"og:description\"\s+content=\"([^\"]+)\"",
    ]
    for pattern in bio_patterns:
        match = re.search(pattern, page_text, re.I)
        if match:
            profile.about_text = match.group(1).strip()[:500]
            break
    
    # Extract photos from page
    photo_pattern = re.compile(
        r"https?://[^\\s\"'<>)]+?\.(?:cdninstagram|fbcdn)\.net/[^\\s\"'<>)]+?\.(?:jpg|jpeg|png|webp)",
        re.I
    )
    seen_photos = set()
    for match in photo_pattern.finditer(page_text):
        url = match.group(0)
        if "profile_pic" not in url.lower() and url not in seen_photos and len(seen_photos) < 10:
            seen_photos.add(url)
            profile.photos.append(url)
    
    # Extract follower/following/post counts
    stats_pattern = r'"edge_followed_by":\s*\{"count":\s*(\d+)\}'
    match = re.search(stats_pattern, page_text)
    if match:
        profile.follower_count = int(match.group(1))
    
    following_pattern = r'"edge_follow":\s*\{"count":\s*(\d+)\}'
    match = re.search(following_pattern, page_text)
    if match:
        profile.following_count = int(match.group(1))
    
    posts_pattern = r'"edge_owner_to_timeline_media":\s*\{"count":\s*(\d+)\}'
    match = re.search(posts_pattern, page_text)
    if match:
        profile.post_count = int(match.group(1))
    
    # Check verification status
    if '"is_verified":true' in page_text.lower():
        profile.is_verified = True
    
    return profile


# ---------------------------------------------------------------------------
# Main scraper interface
# ---------------------------------------------------------------------------

def scrape_social_profile(
    url: str,
    page_text: str | None = None,
    respect_robots: bool = True,
    rate_limiter: RateLimiter | None = None
) -> SocialProfile | None:
    """Scrape public social media profile data.
    
    Args:
        url: Social media profile URL
        page_text: Pre-extracted page content (if available)
        respect_robots: Check robots.txt before scraping
        rate_limiter: Rate limiter instance for ethical scraping
    
    Returns:
        SocialProfile or None if extraction failed
    """
    platform = detect_social_platform(url)
    if not platform:
        logger.warning(f"Unknown platform for URL: {url}")
        return None
    
    # Check robots.txt
    if respect_robots and not RobotsChecker.is_allowed(url):
        logger.warning(f"URL blocked by robots.txt: {url}")
        return None
    
    # Apply rate limiting
    if rate_limiter:
        rate_limiter.wait_if_needed()
    
    # If no page text provided, auto-fetch it
    if not page_text:
        if platform == "facebook":
            return _fetch_facebook_og(url, rate_limiter)
        elif platform == "instagram":
            return _fetch_instagram_profile(url, rate_limiter)
        logger.info(f"No page text provided for {url} and no fetch handler for platform {platform}")
        return None
    
    # Extract data based on platform
    if platform == "facebook":
        return extract_facebook_profile_data(page_text, url)
    elif platform == "instagram":
        return extract_instagram_profile_data(page_text, url)
    
    return None


def extract_social_photos(profile: SocialProfile, max_photos: int = 10) -> list[str]:
    """Extract the best photos from a social profile.
    
    Returns list of photo URLs, filtered and ranked.
    """
    if not profile or not profile.photos:
        return []
    
    # Filter out duplicates and low-quality images
    unique_photos = []
    seen_signatures = set()
    
    for url in profile.photos:
        # Create signature from URL pattern
        signature = re.sub(r'\d+', 'N', url.split('?')[0])
        
        if signature not in seen_signatures:
            seen_signatures.add(signature)
            unique_photos.append(url)
            
            if len(unique_photos) >= max_photos:
                break
    
    return unique_photos


def merge_social_data_into_enrichment(
    enrichment_data: dict[str, Any],
    social_profile: SocialProfile
) -> dict[str, Any]:
    """Merge social profile data into enrichment data structure.
    
    Adds social-specific fields without overwriting existing enrichment.
    """
    if not social_profile:
        return enrichment_data
    
    # Add social metadata
    enrichment_data.setdefault("social_profiles", []).append(social_profile.to_dict())
    
    # Merge photos (add to existing, don't replace)
    if social_profile.photos:
        existing_photos = enrichment_data.get("photos", [])
        combined = existing_photos + social_profile.photos
        # Deduplicate
        enrichment_data["photos"] = list(dict.fromkeys(combined))[:20]
    
    # Add about text if enrichment description is missing
    if not enrichment_data.get("description") and social_profile.about_text:
        enrichment_data["description"] = social_profile.about_text
    
    # Add social signals to differentiators
    if social_profile.follower_count > 1000:
        signal = f"Strong social following ({social_profile.follower_count:,} followers)"
        enrichment_data.setdefault("differentiators", []).append(signal)
    
    if social_profile.is_verified:
        enrichment_data.setdefault("differentiators", []).append("Verified business account")
    
    return enrichment_data
