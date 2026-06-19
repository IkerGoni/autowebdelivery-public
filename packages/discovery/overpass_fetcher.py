"""Overpass API-based business discovery for Phase 02.

Discovers local businesses via OpenStreetMap's Overpass API using
niche keyword → OSM tag mapping, geocoded bounding boxes, and
normalized RawPlace output.

No API key required — purely free, donation-supported infrastructure.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class RawPlace:
    """Normalised output record from an Overpass query.

    Mirrors the Phase 02 input contract but keeps OSM-specific metadata
    (osm_type, osm_id, tags) for traceability.
    """

    name: str
    lat: float
    lng: float
    address: str = ""
    phone: str = ""
    website: str = ""
    osm_type: str = ""
    osm_id: str = ""
    tags: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Niche → OSM tag mapping
# ---------------------------------------------------------------------------

_NICHE_TAG_MAP: dict[str, list[tuple[str, str]]] = {
    "dental clinic": [("amenity", "dentist")],
    "auto detailing": [("shop", "car_repair"), ("amenity", "car_wash")],
    "car wash": [("shop", "car_repair"), ("amenity", "car_wash")],
    "plumber": [("craft", "plumber")],
    "plumbing": [("craft", "plumber")],
    "hvac": [("craft", "hvac")],
    "restaurant": [("amenity", "restaurant"), ("amenity", "cafe")],
    "cafe": [("amenity", "restaurant"), ("amenity", "cafe")],
    "gym": [("leisure", "fitness_centre"), ("leisure", "sports_centre")],
    "fitness": [("leisure", "fitness_centre"), ("leisure", "sports_centre")],
    "hotel": [("tourism", "hotel")],
    "grocery": [("shop", "supermarket"), ("shop", "convenience")],
    "supermarket": [("shop", "supermarket"), ("shop", "convenience")],
}


def _niche_to_osm_tags(niche: str) -> list[tuple[str, str]]:
    """Map a niche string to one or more (key, value) OSM tag pairs.

    Uses the pre-defined mapping table. Falls back to treating the niche as
    an ``amenity`` value (e.g. ``("amenity", niche)``).
    """
    niche_lower = niche.strip().lower()
    tags = _NICHE_TAG_MAP.get(niche_lower)
    if tags is not None:
        return tags
    logger.debug("No mapping for niche '%s'; falling back to amenity=%s", niche, niche_lower)
    return [("amenity", niche_lower)]


# ---------------------------------------------------------------------------
# Nominatim geocoding
# ---------------------------------------------------------------------------

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_NOMINATIM_USER_AGENT = "Autowebdelivery/1.0"


def _geocode_area(area: str, client: httpx.Client) -> tuple[float, float, float, float] | None:
    """Resolve an area string to a bounding box via Nominatim.

    Returns ``(south, west, north, east)`` or ``None`` on failure.
    """
    try:
        resp = client.get(
            _NOMINATIM_URL,
            params={"q": area, "format": "json", "limit": 1},
            headers={"User-Agent": _NOMINATIM_USER_AGENT},
            timeout=10.0,
        )
        resp.raise_for_status()
        results = resp.json()
        if not results:
            logger.warning("Nominatim returned no results for area='%s'", area)
            return None

        bbox = results[0].get("boundingbox")
        if not bbox or len(bbox) < 4:
            logger.warning("Nominatim response missing boundingbox for area='%s'", area)
            return None

        south = float(bbox[0])
        north = float(bbox[1])
        west = float(bbox[2])
        east = float(bbox[3])
        logger.info(
            "Geocoded area='%s' → bbox (%.4f, %.4f, %.4f, %.4f)",
            area,
            south,
            west,
            north,
            east,
        )
        return (south, west, north, east)

    except httpx.HTTPStatusError as exc:
        logger.warning("Nominatim HTTP error %d for area='%s': %s", exc.response.status_code, area, exc)
    except httpx.TimeoutException:
        logger.warning("Nominatim timeout for area='%s'", area)
    except (httpx.RequestError, ValueError, TypeError, IndexError) as exc:
        logger.warning("Nominatim geocode failed for area='%s': %s", area, exc)

    return None


# ---------------------------------------------------------------------------
# Overpass QL query building
# ---------------------------------------------------------------------------

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_OVERPASS_TIMEOUT = 25.0


def _build_overpass_query(
    tags: list[tuple[str, str]],
    bbox: tuple[float, float, float, float],
    max_results: int,
) -> str:
    """Build an Overpass QL query string.

    Generates a union of (node, way, relation) with the given tag filters,
    clipped to the supplied bounding box.
    """
    south, west, north, east = bbox
    bbox_str = f"{south},{west},{north},{east}"

    elements: list[str] = []
    for key, value in tags:
        tag_filter = f'["{key}"="{value}"]'
        elements.append(f"  node{tag_filter}({bbox_str});")
        elements.append(f"  way{tag_filter}({bbox_str});")
        elements.append(f"  rel{tag_filter}({bbox_str});")

    union_body = "\n".join(elements)

    query = f"""[out:json][timeout:{int(_OVERPASS_TIMEOUT)}];
(
{union_body}
);
out {max_results};
"""
    return query


# ---------------------------------------------------------------------------
# Response normalisation
# ---------------------------------------------------------------------------

_ADDRESS_KEYS = [
    "addr:street",
    "addr:housenumber",
    "addr:city",
    "addr:postcode",
    "addr:state",
    "addr:country",
]


def _element_to_raw_place(element: dict[str, Any], source_query: str) -> RawPlace:
    """Convert a single Overpass JSON element to a ``RawPlace``."""
    tags: dict[str, Any] = element.get("tags", {}) or {}
    lat: float = element.get("lat", 0.0) or 0.0
    lon: float = element.get("lon", 0.0) or 0.0

    # Build a usable address from OSM addr:* tags
    address_parts = []
    for key in _ADDRESS_KEYS:
        val = tags.get(key)
        if val:
            address_parts.append(str(val).strip())

    address = ", ".join(address_parts) if address_parts else tags.get("display_name", "")

    return RawPlace(
        name=str(tags.get("name", "") or ""),
        lat=lat,
        lng=lon,
        address=address,
        phone=str(tags.get("phone", "") or ""),
        website=str(tags.get("website", "") or ""),
        osm_type=str(element.get("type", "") or ""),
        osm_id=str(element.get("id", "") or ""),
        tags={k: str(v) for k, v in tags.items()},
    )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class RateLimiter:
    """Simple token-bucket-style rate limiter for API calls."""

    def __init__(self, requests_per_minute: int = 10) -> None:
        self.min_interval = 60.0 / max(requests_per_minute, 1)
        self._last_call: float = 0.0

    def wait(self) -> None:
        """Block until the next call is allowed."""
        now = time.monotonic()
        elapsed = now - self._last_call
        if elapsed < self.min_interval:
            sleep_for = self.min_interval - elapsed
            time.sleep(sleep_for)
        self._last_call = time.monotonic()


class OverpassClient:
    """Client for discovering businesses via the Overpass API.

    Internally handles:
    - Niche-to-OSM-tag mapping
    - Nominatim geocoding of area strings
    - Overpass QL query building and execution
    - Response normalisation to ``RawPlace`` dataclass
    - Result caching with 1-hour TTL
    - Rate limiting and retry on 429

    Usage::

        client = OverpassClient()
        places = client.discover("auto detailing", "Frisco TX", max_results=30)
    """

    def __init__(
        self,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._rate_limiter = rate_limiter or RateLimiter(requests_per_minute=10)
        self._cache: dict[str, tuple[float, list[RawPlace]]] = {}
        self._cache_ttl: float = 3600.0  # 1 hour

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def discover(
        self,
        niche: str,
        area: str,
        max_results: int = 50,
    ) -> list[RawPlace]:
        """Discover businesses matching *niche* in the given *area*.

        Steps:
        1. Check cache (keyed by ``f"{niche}:{area}"``).
        2. Map niche → OSM tag pairs.
        3. Geocode area → bounding box via Nominatim.
        4. Build Overpass QL query and POST to the Overpass API.
        5. Normalise returned elements to ``RawPlace`` instances.
        6. Cache and return results.

        Returns an empty list on any recoverable error.
        """
        cache_key = f"{niche}:{area}"

        # 1. Cache check
        cached = self._check_cache(cache_key)
        if cached is not None:
            logger.info("Cache hit for '%s' (%d results)", cache_key, len(cached))
            return cached

        # 2. Tag mapping
        tags = _niche_to_osm_tags(niche)
        logger.info("Overpass discover niche='%s' area='%s' → tags=%s", niche, area, tags)

        # 3. Geocoding
        with httpx.Client() as client:
            bbox = _geocode_area(area, client)
            if bbox is None:
                logger.warning("Could not geocode area='%s'; returning empty", area)
                return []

            # 4. Build & execute query
            query = _build_overpass_query(tags, bbox, max_results)
            elements = self._execute_query(query, client)

        # 5. Normalise
        results = [_element_to_raw_place(el, f"{niche} in {area}") for el in elements]

        # Truncate to max_results
        results = results[:max_results]

        logger.info(
            "Overpass discover returned %d raw places for niche='%s' area='%s'",
            len(results),
            niche,
            area,
        )

        # 6. Cache
        self._set_cache(cache_key, results)

        return results

    def clear_cache(self) -> None:
        """Clear the in-memory result cache."""
        self._cache.clear()
        logger.info("Overpass client cache cleared")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _execute_query(self, query: str, client: httpx.Client) -> list[dict[str, Any]]:
        """POST an Overpass QL query and return the list of result elements.

        Handles:
        - Rate limiting
        - HTTP 429 with one retry after 60 s
        - Timeouts
        - JSON decode errors

        Returns an empty list on failure.
        """
        self._rate_limiter.wait()

        for attempt in range(2):  # max 1 retry
            try:
                resp = client.post(
                    _OVERPASS_URL,
                    data={"data": query},
                    headers={"Accept": "application/json"},
                    timeout=_OVERPASS_TIMEOUT,
                )

                if resp.status_code == 429:
                    logger.warning("Overpass rate limited (429); waiting 60s and retrying ...")
                    if attempt == 0:
                        time.sleep(60.0)
                        continue
                    logger.warning("Overpass rate limited again after retry; giving up")
                    return []

                resp.raise_for_status()
                data = resp.json()
                elements: list[dict[str, Any]] = data.get("elements", [])
                return elements

            except httpx.TimeoutException:
                logger.warning("Overpass query timed out after %ss", _OVERPASS_TIMEOUT)
                return []

            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "Overpass HTTP error %d: %s",
                    exc.response.status_code,
                    exc,
                )
                return []

            except (httpx.RequestError, ValueError, TypeError) as exc:
                logger.warning("Overpass request failed: %s", exc)
                return []

        return []

    # ------------------------------------------------------------------
    # Cache internals
    # ------------------------------------------------------------------

    def _check_cache(self, key: str) -> list[RawPlace] | None:
        """Return cached results if still valid, or ``None``."""
        entry = self._cache.get(key)
        if entry is None:
            return None
        timestamp, results = entry
        if time.monotonic() - timestamp > self._cache_ttl:
            del self._cache[key]
            return None
        return results

    def _set_cache(self, key: str, results: list[RawPlace]) -> None:
        """Store results in cache with the current timestamp."""
        self._cache[key] = (time.monotonic(), results)


# ---------------------------------------------------------------------------
# Phase 02 adapter — convert Overpass RawPlace → Phase 02 raw place dicts
# ---------------------------------------------------------------------------

def overpass_to_raw_place_dicts(
    results: list[RawPlace],
    niche: str,
    area: str,
) -> list[dict[str, Any]]:
    """Convert Overpass ``RawPlace`` instances to dicts compatible with Phase 02.

    Maps the Overpass-specific ``RawPlace`` dataclass fields to the dict
    shape expected by ``make_raw_place()`` in Phase 02:

    - name → business_name
    - address → address
    - phone → phone
    - website → website
    - osm_type/osm_id → place_id
    - tags → category (best guess from amenity/shop/craft keys)
    - source → "overpass"
    - source_query → "{niche} in {area}"

    Fields not available from OSM (rating, review_count, hours,
    business_status) are left as defaults.
    """
    source_query = f"{niche} in {area}"
    out: list[dict[str, Any]] = []

    for place in results:
        tags = place.tags or {}

        # Best-guess category from OSM tags
        category = (
            tags.get("amenity", "")
            or tags.get("shop", "")
            or tags.get("craft", "")
            or tags.get("leisure", "")
            or tags.get("tourism", "")
        )
        if category:
            category = category.replace("_", " ").title()

        # Build a place_id from OSM type + id
        place_id = ""
        if place.osm_type and place.osm_id:
            place_id = f"osm_{place.osm_type}_{place.osm_id}"

        out.append({
            "business_name": place.name,
            "address": place.address,
            "phone": place.phone,
            "website": place.website,
            "category": category,
            "place_id": place_id,
            "source": "overpass",
            "source_query": source_query,
            "rating": 0.0,
            "review_count": 0,
            "hours": tags.get("opening_hours", ""),
            "business_status": "unknown",
            "raw_payload_ref": "",
        })

    return out


def fetch_overpass_leads(
    niche: str,
    area: str,
    *,
    max_results: int = 50,
) -> list[dict[str, Any]]:
    """Discover businesses via Overpass and return Phase 02-compatible dicts.

    Convenience wrapper that instantiates an ``OverpassClient``, calls
    ``discover()``, and converts results to the raw-place-dict format
    expected by Phase 02's ``make_raw_place()``.
    """
    client = OverpassClient()
    results = client.discover(niche, area, max_results=max_results)
    return overpass_to_raw_place_dicts(results, niche, area)
