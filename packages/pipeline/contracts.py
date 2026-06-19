"""Phase data contracts from pipeline_data_contract.md."""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


def utc_now() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


class RunConfig(BaseModel):
    """Created by Phase 01."""
    run_id: str
    niche: str
    area: str
    country: str
    language: str = "English"
    max_raw_results: int = 100
    max_preview_sites: int = 5
    minimum_rating: float = 4.3
    minimum_reviews: int = 40
    style_preset: Optional[str] = "clinical_trust"
    deploy_mode: str = "production_deploy_mode"
    price_offer: str
    offer_type: str = "setup_only"
    offer_price: str = ""
    currency: str = ""
    pricing_market: str = ""
    pricing_notes: str = ""
    mvp_stop_threshold: int = 20
    generation_mode: str = "stitch"
    deploy_provider: str = "local_only"
    created_at: str = Field(default_factory=utc_now)

    def get_phase_dir(self, phase: str) -> str:
        """Return the directory name for a given phase."""
        return f"{phase}"


class QueryPlan(BaseModel):
    """Created by Phase 01, consumed by Phase 02."""
    run_id: str
    queries: list[dict] = Field(default_factory=list)


class RawPlace(BaseModel):
    """Created by Phase 02."""
    run_id: str
    record_id: str
    source: str = "manual_fixture"
    source_query: str = ""
    business_name: str
    place_id: str = ""
    category: str = ""
    rating: float = 0.0
    review_count: int = 0
    address: str = ""
    phone: str = ""
    website: str = ""
    maps_url: str = ""
    hours: str = ""
    business_status: str = "unknown"  # open, closed, unknown
    raw_payload_ref: str = ""
    created_at: str = Field(default_factory=utc_now)

    @property
    def has_required_fields(self) -> bool:
        """Check minimum fields needed for downstream processing."""
        return bool(
            self.business_name
            and self.category
            and (self.address or self.maps_url)
            and self.website
        )


class NormalizedPlace(BaseModel):
    """Created by Phase 02."""
    run_id: str
    record_id: str
    raw_record_id: str
    business_name: str
    business_slug: str = ""
    place_id: str = ""
    category: str = ""
    rating: float = 0.0
    review_count: int = 0
    address: str = ""
    phone: str = ""
    website_raw: str = ""
    maps_url: str = ""
    hours: str = ""
    business_status: str = "unknown"
    dedupe_key: str = ""
    social_only_presence: bool = False  # True if website is only Facebook/Instagram
    normalization_notes: list[str] = Field(default_factory=list)


class RunMeta(BaseModel):
    """Phase execution metadata."""
    run_id: str
    phase: str | None = None
    status: str = "pending"
    created_at: str = Field(default_factory=utc_now)


class WebsiteClassification(BaseModel):
    """Created by Phase 02.1."""
    run_id: str
    record_id: str
    business_slug: str = ""
    website_raw: str = ""
    website_normalized: str = ""
    registered_domain: str = ""
    domain_type: str = "unknown"  # empty | maps | social | business_domain | malformed | unknown
    website_status: str = "no_website"  # no_website | social_only | has_website | uncertain | invalid_url
    confidence: float = 0.0
    decision: str = "keep"  # keep | skip | manual_review
    reason_codes: list[str] = Field(default_factory=list)
    http_checked: bool = False
    http_status: int | None = None
    final_url: str | None = None
    redirect_chain: list[str] = Field(default_factory=list)
    checked_redirect: bool = False
    website_resolution_status: str = "not_checked"  # not_checked | live | dead | parked | social_redirect | maps_redirect | shortlink | ssl_error | timeout | unknown
    notes: list[str] = Field(default_factory=list)