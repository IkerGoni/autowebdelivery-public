"""Phase 02: Basic Lead Discovery Fixture Adapter.

Produces RawPlace and NormalizedPlace artifacts from fixture input.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Any

from pipeline.contracts import RawPlace, NormalizedPlace
from pipeline.json_io import read_json, write_json
from pipeline.result_envelope import ResultEnvelope


PHASE_NAME = "phase_02_basic_lead_discovery"


def make_business_slug(business_name: str, record_id: str) -> str:
    """Generate deterministic business slug per contract rules.

    Rules:
    - lowercase
    - transliterate to Latin where possible
    - strip non-ASCII after transliteration
    - replace spaces and symbols with hyphen
    - collapse repeated hyphens
    - trim leading/trailing hyphens
    - max 50 characters before suffix
    - append last 4-6 characters of record_id for uniqueness
    """
    # Normalize and lowercase
    name = unicodedata.normalize("NFKD", business_name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = name.lower()

    # Replace spaces and symbols with hyphen
    name = re.sub(r"[^a-z0-9]+", "-", name)

    # Collapse repeated hyphens
    name = re.sub(r"-+", "-", name)

    # Trim leading/trailing hyphens
    name = name.strip("-")

    # Max 50 characters
    if len(name) > 50:
        name = name[:50].rstrip("-")

    # Get suffix from record_id (last 4-6 chars)
    id_suffix = record_id.replace("rec_", "")[-4:] if len(record_id) > 4 else record_id[-4:]

    # Combine
    if name:
        return f"{name}-{id_suffix}"
    return f"business-{id_suffix}"


def make_dedupe_key(place: dict[str, Any]) -> str:
    """Create dedupe key from business identity fields."""
    parts = [
        place.get("business_name", "").lower().strip(),
        place.get("address", "").lower().strip(),
    ]
    key_str = "|".join(parts)
    return hashlib.md5(key_str.encode()).hexdigest()[:12]


def make_record_id(source: str, index: int) -> str:
    """Create deterministic record ID."""
    prefix = "rec"
    suffix = hashlib.md5(f"{source}_{index}".encode()).hexdigest()[:8]
    return f"{prefix}_{suffix}"


def make_raw_place(run_id: str, raw_data: dict[str, Any], index: int) -> RawPlace:
    """Convert raw fixture data to RawPlace contract."""
    record_id = raw_data.get("record_id") or make_record_id(raw_data.get("source", "fixture"), index)

    return RawPlace(
        run_id=run_id,
        record_id=record_id,
        source=raw_data.get("source", "manual_fixture"),
        source_query=raw_data.get("source_query", ""),
        business_name=raw_data.get("business_name", ""),
        place_id=raw_data.get("place_id", ""),
        category=raw_data.get("category", ""),
        rating=raw_data.get("rating", 0.0) or 0.0,
        review_count=raw_data.get("review_count", 0) or 0,
        address=raw_data.get("address", ""),
        phone=raw_data.get("phone", ""),
        website=raw_data.get("website", ""),
        maps_url=raw_data.get("maps_url", ""),
        hours=raw_data.get("hours", ""),
        business_status=raw_data.get("business_status", "unknown"),
        raw_payload_ref=raw_data.get("raw_payload_ref", ""),
    )


def normalize_place(raw: RawPlace) -> NormalizedPlace:
    """Convert RawPlace to NormalizedPlace with slug and dedupe key."""
    business_slug = make_business_slug(raw.business_name, raw.record_id)
    dedupe_key = make_dedupe_key(raw.model_dump())

    notes = []
    social_only = False
    
    if not raw.website:
        notes.append("website_field_empty")
    else:
        # Check for social-only presence
        try:
            from discovery.social_detection import is_social_only_website
        except ModuleNotFoundError:
            from packages.discovery.social_detection import is_social_only_website
        
        social_only = is_social_only_website(raw.website)
        if social_only:
            notes.append("social_only_presence_detected")

    return NormalizedPlace(
        run_id=raw.run_id,
        record_id=f"norm_{raw.record_id}",
        raw_record_id=raw.record_id,
        business_name=raw.business_name,
        business_slug=business_slug,
        place_id=raw.place_id,
        category=raw.category,
        rating=raw.rating,
        review_count=raw.review_count,
        address=raw.address,
        phone=raw.phone,
        website_raw=raw.website,
        maps_url=raw.maps_url,
        hours=raw.hours,
        business_status=raw.business_status,
        dedupe_key=dedupe_key,
        social_only_presence=social_only,
        normalization_notes=notes,
    )


def _resolve_discovery_input(
    run_id: str,
    workspace_path: Path,
) -> list[dict[str, Any]] | None:
    """Resolve lead discovery input based on config discovery_source.

    Supported sources:
    - "fixture": Load from existing fixture file (default)
    - "csv_file": Load from config csv_path
    - "overpass": Fetch from OpenStreetMap Overpass API (free, no key)
    - "maps_api": Fetch from Google Maps Places API
    - "maps_search": Direct HTTP search (falls back to fixture)

    Returns:
        List of raw place dicts, or None if discovery failed.
    """
    # Read config
    config_path = workspace_path / "runs" / run_id / "config" / "input_config.json"
    discovery_source = "fixture"
    if config_path.exists():
        try:
            config = read_json(str(config_path))
            discovery_source = config.get("discovery_source", "fixture")
        except Exception:
            pass

    if discovery_source == "fixture":
        fixture_path = (
            workspace_path / "tests" / "fixtures" / PHASE_NAME / "input" / "raw_places_with_websites.json"
        )
        if not fixture_path.exists():
            return None
        return read_json(str(fixture_path))

    if discovery_source == "csv_file":
        csv_path = config_path.parent / "csv_path" if config_path.exists() else None
        if config_path.exists():
            try:
                config = read_json(str(config_path))
                csv_path_str = config.get("csv_path", "")
                if csv_path_str:
                    csv_path = Path(csv_path_str)
                    if not csv_path.is_absolute():
                        csv_path = workspace_path / csv_path
            except Exception:
                csv_path = None

        if csv_path is None or not csv_path.exists():
            return None

        try:
            from discovery.csv_loader import load_leads_from_csv
        except ModuleNotFoundError:
            from packages.discovery.csv_loader import load_leads_from_csv

        return load_leads_from_csv(csv_path)

    if discovery_source == "overpass":
        niche = ""
        area = ""
        if config_path.exists():
            try:
                config = read_json(str(config_path))
                niche = config.get("niche", "")
                area = config.get("area", "")
            except Exception:
                pass

        if not niche or not area:
            return None

        try:
            from discovery.overpass_fetcher import fetch_overpass_leads
        except ModuleNotFoundError:
            from packages.discovery.overpass_fetcher import fetch_overpass_leads

        return fetch_overpass_leads(niche, area)

    if discovery_source in ("maps_api", "maps_search"):
        niche = ""
        area = ""
        if config_path.exists():
            try:
                config = read_json(str(config_path))
                niche = config.get("niche", "")
                area = config.get("area", "")
            except Exception:
                pass

        try:
            from discovery.maps_fetcher import fetch_maps_leads
        except ModuleNotFoundError:
            from packages.discovery.maps_fetcher import fetch_maps_leads

        return fetch_maps_leads(niche, area)

    # Unknown source — fall back to fixture
    fixture_path = (
        workspace_path / "tests" / "fixtures" / PHASE_NAME / "input" / "raw_places_with_websites.json"
    )
    if fixture_path.exists():
        return read_json(str(fixture_path))
    return None


def run(
    run_id: str,
    workspace: str,
    input_places: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute Phase 02 and return result envelope.

    Args:
        run_id: Run identifier
        workspace: Base workspace directory
        input_places: List of raw place dicts. If None, discovers leads
            based on discovery_source config (fixture, maps_api, csv_file).

    Returns:
        Result envelope dict
    """
    workspace_path = Path(workspace)

    # Check for required Phase 01 outputs first
    config_dir = workspace_path / "runs" / run_id / "config"
    phase_dir = workspace_path / "runs" / run_id / "01_input"
    if not config_dir.exists() or not phase_dir.exists():
        return ResultEnvelope.blocked(
            phase=PHASE_NAME,
            run_id=run_id,
            missing_fields=["RunConfig", "QueryPlan"],
            inputs_used=[],
            errors=["Phase 01 must complete before Phase 02"],
        ).to_dict()

    # Load input — resolve discovery source if not provided directly
    if input_places is None:
        input_places = _resolve_discovery_input(run_id, workspace_path)
        if input_places is None:
            return ResultEnvelope.blocked(
                phase=PHASE_NAME,
                run_id=run_id,
                missing_fields=["raw_places_input"],
                inputs_used=[],
            ).to_dict()

    # Create output directory
    output_dir = workspace_path / "runs" / run_id / "02_discovery"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Process places
    raw_places: list[dict[str, Any]] = []
    normalized_places: list[dict[str, Any]] = []
    missing_website_count = 0
    social_only_count = 0

    seen_dedupe_keys: set[str] = set()
    deduped_count = 0

    for idx, raw_data in enumerate(input_places):
        raw_place = make_raw_place(run_id, raw_data, idx)
        raw_places.append(raw_place.model_dump())

        # Check for website field
        if not raw_place.website:
            missing_website_count += 1

        # Normalize
        norm_place = normalize_place(raw_place)

        # Track social-only presence
        if norm_place.social_only_presence:
            social_only_count += 1

        # Deduplication
        if norm_place.dedupe_key in seen_dedupe_keys:
            deduped_count += 1
            continue
        seen_dedupe_keys.add(norm_place.dedupe_key)
        normalized_places.append(norm_place.model_dump())

    # Write outputs
    leads_raw_path = output_dir / "leads_raw.json"
    leads_normalized_path = output_dir / "leads_normalized.json"
    discovery_report_path = output_dir / "discovery_report.json"
    result_path = output_dir / "result.json"

    write_json(str(leads_raw_path), raw_places)
    write_json(str(leads_normalized_path), normalized_places)

    # Create discovery report
    discovery_report = {
        "run_id": run_id,
        "phase": "02_discovery",
        "raw_places_count": len(raw_places),
        "normalized_places_count": len(normalized_places),
        "deduped_count": deduped_count,
        "missing_website_count": missing_website_count,
        "social_only_count": social_only_count,
        "status": "complete",
    }
    write_json(str(discovery_report_path), discovery_report)

    # Determine status
    # Note: missing website is NOT a blocker — these are leads that need
    # a website generated (the core value proposition of this pipeline).
    if missing_website_count == len(input_places):
        status = "needs_review"
        errors = ["All input records missing website field — candidates for site generation"]
    elif missing_website_count > 0:
        status = "needs_review"
        errors = [f"{missing_website_count} records missing website field"]
    else:
        status = "done"
        errors = []

    # Create result
    result = ResultEnvelope(
        phase=PHASE_NAME,
        status=status,
        run_id=run_id,
        inputs_used=["raw_places_input"],
        outputs_created=[
            "02_discovery/leads_raw.json",
            "02_discovery/leads_normalized.json",
            "02_discovery/discovery_report.json",
            "02_discovery/result.json",
        ],
        records_processed=len(input_places),
        records_created=len(normalized_places),
        records_skipped=deduped_count,
        missing_fields=["website"] if missing_website_count > 0 else [],
        decisions=[
            f"Processed {len(input_places)} raw places",
            f"Created {len(normalized_places)} normalized leads",
            f"Deduped {deduped_count} duplicate records",
        ],
        errors=errors,
    ).model_dump(exclude_none=True, by_alias=True)

    write_json(str(result_path), result)

    return result


if __name__ == "__main__":
    import sys
    workspace = sys.argv[1] if len(sys.argv) > 1 else "."
    run_id = sys.argv[2] if len(sys.argv) > 2 else "test_run"
    result = run(workspace, run_id)
    print(f"Phase 02 complete: {result['status']}")