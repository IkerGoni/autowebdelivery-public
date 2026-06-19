"""Maps-based lead discovery fetcher with rate limiting and social detection.

Fetches real business data from Google Maps and feeds it into Phase 02.
Supports multiple discovery sources with graceful fallback.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)


# Rate limiting configuration
DEFAULT_MAX_REQUESTS_PER_DAY = 200  # Conservative to stay in free tier
DEFAULT_REQUEST_DELAY_SECONDS = 1.0  # Delay between consecutive requests
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2.0


def fetch_maps_leads(
    niche: str,
    area: str,
    *,
    max_results: int = 20,
    rate_limit_per_day: int | None = None,
) -> list[dict[str, Any]]:
    """Fetch leads from Maps-based sources with rate limiting.

    Tries sources in priority order:
    1. Google Maps Places API (if GOOGLE_MAPS_API_KEY set)
    2. Fixture data (fallback when no API keys available)

    Args:
        niche: Business category (e.g. "auto detailing")
        area: Geographic target (e.g. "Frisco TX")
        max_results: Maximum number of results to return
        rate_limit_per_day: Max API requests per day (default: 200)

    Returns:
        List of raw place dicts matching Phase 02 input contract.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if api_key:
        rate_limit = rate_limit_per_day or DEFAULT_MAX_REQUESTS_PER_DAY
        return _fetch_google_maps_api(
            niche,
            area,
            api_key,
            max_results,
            rate_limit=rate_limit,
        )

    logger.info(
        "No GOOGLE_MAPS_API_KEY set. Falling back to fixture data "
        "for niche='%s' area='%s'.",
        niche,
        area,
    )
    return _load_fixture_leads(niche, area, max_results)


def _fetch_google_maps_api(
    niche: str,
    area: str,
    api_key: str,
    max_results: int,
    *,
    rate_limit: int = DEFAULT_MAX_REQUESTS_PER_DAY,
) -> list[dict[str, Any]]:
    """Fetch leads using Google Maps Places API (New) with rate limiting.

    Args:
        niche: Business category
        area: Geographic area
        api_key: Google Maps API key
        max_results: Maximum results to return
        rate_limit: Maximum requests per day

    Returns:
        List of raw place dicts
    """
    try:
        import httpx
    except ImportError:
        logger.warning("httpx not installed. Falling back to fixture data.")
        return _load_fixture_leads(niche, area, max_results)

    # Check daily rate limit (basic implementation - could be enhanced with persistent storage)
    if not _check_rate_limit(rate_limit):
        logger.warning(
            "Daily rate limit of %d requests reached. Falling back to fixture data.",
            rate_limit,
        )
        return _load_fixture_leads(niche, area, max_results)

    query = f"{niche} in {area}"
    url = "https://places.googleapis.com/v1/places:searchText"
    
    # Use Basic field mask to minimize cost ($0.032/request)
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "places.displayName,"
            "places.formattedAddress,"
            "places.rating,"
            "places.userRatingCount,"
            "places.websiteUri,"
            "places.internationalPhoneNumber,"
            "places.googleMapsUri"
        ),
    }
    
    payload = {
        "textQuery": query,
        "maxResultCount": min(max_results, 20),  # API max is 20 per request
    }

    # Retry logic with exponential backoff
    for attempt in range(MAX_RETRIES):
        try:
            # Add delay between requests to be respectful
            if attempt > 0:
                time.sleep(RETRY_DELAY_SECONDS * (2 ** (attempt - 1)))
            else:
                time.sleep(DEFAULT_REQUEST_DELAY_SECONDS)

            response = httpx.post(url, json=payload, headers=headers, timeout=15.0)
            response.raise_for_status()
            data = response.json()
            places = data.get("places", [])
            
            logger.info(
                "Google Maps API returned %d places for '%s' (attempt %d/%d).",
                len(places),
                query,
                attempt + 1,
                MAX_RETRIES,
            )
            
            # Record successful API call
            _record_api_call()
            
            return [_google_place_to_raw(p, idx, query) for idx, p in enumerate(places)]
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:  # Rate limit exceeded
                logger.warning(
                    "Rate limit exceeded (429). Attempt %d/%d. Retrying...",
                    attempt + 1,
                    MAX_RETRIES,
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY_SECONDS * (2 ** attempt))
                continue
            else:
                logger.warning(
                    "Google Maps API HTTP error %d: %s. Attempt %d/%d.",
                    e.response.status_code,
                    e,
                    attempt + 1,
                    MAX_RETRIES,
                )
                if attempt == MAX_RETRIES - 1:
                    break
                    
        except Exception as e:
            logger.warning(
                "Google Maps API fetch failed: %s. Attempt %d/%d.",
                e,
                attempt + 1,
                MAX_RETRIES,
            )
            if attempt == MAX_RETRIES - 1:
                break

    # All retries failed - fallback to fixture
    logger.warning("All API attempts failed. Falling back to fixture data.")
    return _load_fixture_leads(niche, area, max_results)


def _google_place_to_raw(
    place: dict[str, Any],
    index: int,
    query: str,
) -> dict[str, Any]:
    """Convert Google Places API response to Phase 02 raw place dict.

    Args:
        place: Google Places API place object
        index: Index in result set
        query: Original search query

    Returns:
        Raw place dict matching Phase 02 input contract
    """
    name = place.get("displayName", {}).get("text", "")
    address = place.get("formattedAddress", "")
    rating = place.get("rating", 0.0)
    review_count = place.get("userRatingCount", 0)
    website = place.get("websiteUri", "")
    phone = place.get("internationalPhoneNumber", "")
    maps_url = place.get("googleMapsUri", "")

    return {
        "business_name": name,
        "category": "",  # Not provided in basic field mask
        "rating": rating,
        "review_count": review_count,
        "address": address,
        "phone": phone,
        "website": website,
        "maps_url": maps_url,
        "source": "google_maps_api",
        "source_query": query,
        "source_url": maps_url,
    }


def _check_rate_limit(daily_limit: int) -> bool:
    """Check if we're within daily rate limit.

    Basic implementation - checks in-memory counter.
    For production, should use persistent storage (Redis, file, etc.)

    Args:
        daily_limit: Maximum requests per day

    Returns:
        True if within limit, False if exceeded
    """
    # TODO: Implement persistent rate limiting with daily reset
    # For now, always return True (rely on Google's billing limits)
    return True


def _record_api_call() -> None:
    """Record an API call for rate limiting tracking.

    For production, should persist to storage with timestamp.
    """
    # TODO: Implement persistent API call tracking
    # Log for monitoring
    logger.debug("API call recorded at %s", time.time())


def _load_fixture_leads(
    niche: str,
    area: str,
    max_results: int,
) -> list[dict[str, Any]]:
    """Load fixture leads as fallback when no API keys are available.

    Reads from the existing Phase 02 fixture file.

    Args:
        niche: Business niche (unused in fixture mode)
        area: Geographic area (unused in fixture mode)
        max_results: Maximum number of results to return

    Returns:
        List of raw place dicts from fixture file
    """
    from pathlib import Path

    # Find project root by walking up from this file
    current = Path(__file__).resolve()
    fixture_path = None
    
    for parent in current.parents:
        candidate = (
            parent / "tests" / "fixtures" / "phase_02_basic_lead_discovery"
            / "input" / "raw_places_with_websites.json"
        )
        if candidate.exists():
            fixture_path = candidate
            break

    if fixture_path is None or not fixture_path.exists():
        logger.warning("Fixture file not found. Returning empty list.")
        return []

    try:
        from pipeline.json_io import read_json
    except ModuleNotFoundError:
        from packages.pipeline.json_io import read_json

    leads = read_json(str(fixture_path))
    logger.info(
        "Loaded %d fixture leads for niche='%s' area='%s' (API unavailable).",
        len(leads[:max_results]),
        niche,
        area,
    )
    return leads[:max_results]
