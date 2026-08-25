"""Integration tests for VNEXT-14 Google Maps enrichment pipeline wiring.

Verifies that:
- The feature flag ``use_gmaps_enrichment`` gates the enricher
- The enricher is called with correct arguments from the pipeline
- Enrichment data (review text, rating, review count, etc.) is written
  as an artifact and injected into the lead payload
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from packages.enrichment.google_maps_enricher import BusinessEnrichment
from packages.pipeline.vnext_integration import (
    _VNEXT_FLAG_DEFAULTS,
    run_vnext_post_phase_04_5_gmaps_enrichment,
)

# ---------------------------------------------------------------------------
# Flag presence
# ---------------------------------------------------------------------------


def test_gmaps_flag_in_defaults():
    """use_gmaps_enrichment is present in flag defaults and is False."""
    assert "use_gmaps_enrichment" in _VNEXT_FLAG_DEFAULTS
    assert _VNEXT_FLAG_DEFAULTS["use_gmaps_enrichment"] is False


# ---------------------------------------------------------------------------
# Flag-gated behaviour
# ---------------------------------------------------------------------------


def test_gmaps_enrichment_no_flag():
    """Returns empty list when flag is disabled."""
    result = run_vnext_post_phase_04_5_gmaps_enrichment(
        run_id="test",
        workspace="/tmp",
        selected_leads=[{"business_slug": "test-biz"}],
        config={"vnext_flags": {"use_gmaps_enrichment": False}},
    )
    assert result == []


# ---------------------------------------------------------------------------
# Full integration: mock the enricher and verify end-to-end
# ---------------------------------------------------------------------------

SAMPLE_ENRICHMENT = BusinessEnrichment(
    business_name="Frisco Mobile Detailing",
    description="Professional mobile auto detailing in Frisco TX.",
    photos=[
        "https://lh3.googleusercontent.com/abc/photo1.jpg",
    ],
    review_snippets=[
        "He came to my office and detailed my car. My car looks brand new!",
        "Very professional and detail-oriented work. Highly recommend!",
    ],
    hours={
        "Monday": "8:00 AM - 6:00 PM",
        "Tuesday": "8:00 AM - 6:00 PM",
        "Wednesday": "8:00 AM - 6:00 PM",
        "Thursday": "8:00 AM - 6:00 PM",
        "Friday": "8:00 AM - 5:00 PM",
        "Saturday": "9:00 AM - 3:00 PM",
    },
    services=[
        "Exterior detailing",
        "Interior detailing",
        "Ceramic coating",
        "Paint correction",
    ],
    differentiators=[
        "mobile/on-site service",
        "restoration quality",
        "attention to detail",
    ],
    owner_signals=[
        "owner personally involved",
        "friendly personality",
        "highly recommended",
    ],
    rating=4.9,
    review_count=327,
    source_url="https://maps.google.com/maps?cid=123456789",
)


@patch("packages.enrichment.google_maps_enricher.run_enrichment")
def test_gmaps_enrichment_writes_artifact_and_injects_payload(mock_run_enrichment, tmp_path: Path):
    """When flag is ON, enrichment artifact is written and payload injected."""
    mock_run_enrichment.return_value = SAMPLE_ENRICHMENT

    run_id = "test_gmaps_run"
    workspace = str(tmp_path)
    slug = "frisco-mobile-detailing"

    # Set up minimal lead data
    leads = [
        {
            "business_slug": slug,
            "business_name": "Frisco Mobile Detailing",
            "city": "Frisco TX",
        }
    ]

    # Run the enrichment
    result = run_vnext_post_phase_04_5_gmaps_enrichment(
        run_id=run_id,
        workspace=workspace,
        selected_leads=leads,
        config={"vnext_flags": {"use_gmaps_enrichment": True}},
    )

    # 1. Should have written the gmaps_enrichment.json artifact
    artifact_path = (
        Path(workspace)
        / "runs"
        / run_id
        / "04_5_enrichment"
        / slug
        / "gmaps_enrichment.json"
    )
    assert artifact_path.exists(), f"Artifact not found: {artifact_path}"
    assert any("gmaps_enrichment.json" in p for p in result), (
        "gmaps_enrichment.json should be in returned paths"
    )

    # Also verify enrichment_sources.json exists with proper structure
    sources_path = Path(workspace) / "runs" / run_id / "04_5_enrichment" / slug / "enrichment_sources.json"
    assert sources_path.exists(), "enrichment_sources.json should be written"
    sources_data = json.loads(sources_path.read_text(encoding="utf-8"))
    assert "sources" in sources_data
    assert any(s.get("type") == "google_maps_api" for s in sources_data["sources"])

    # 2. Verify artifact content
    data = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert data["business_name"] == "Frisco Mobile Detailing"
    assert data["rating"] == 4.9
    assert data["review_count"] == 327
    assert len(data["review_snippets"]) == 2
    assert len(data["differentiators"]) >= 2
    assert len(data["owner_signals"]) >= 1
    assert data["source_url"] == "https://maps.google.com/maps?cid=123456789"

    # 3. Enricher was called with correct business_name and city
    mock_run_enrichment.assert_called_once()
    _, kwargs = mock_run_enrichment.call_args
    assert kwargs["business_name"] == "Frisco Mobile Detailing"
    assert kwargs["city"] == "Frisco TX"

    # 4. Lead payload has gmaps_enrichment injected
    assert "gmaps_enrichment" in leads[0]
    injected = leads[0]["gmaps_enrichment"]
    assert injected["rating"] == 4.9
    assert injected["review_count"] == 327
    assert len(injected["review_snippets"]) == 2
    assert "mobile/on-site service" in injected["differentiators"]


@patch("packages.enrichment.google_maps_enricher.run_enrichment")
def test_gmaps_enrichment_reads_facts_md_for_maps_url(mock_run_enrichment, tmp_path: Path):
    """Enricher reads maps_url and city from FACTS.md if available."""
    mock_run_enrichment.return_value = SAMPLE_ENRICHMENT

    run_id = "test_facts_run"
    workspace = str(tmp_path)
    slug = "test-biz"

    # Create FACTS.md with maps_url and city
    brief_dir = Path(workspace) / "runs" / run_id / "04_briefs" / slug
    brief_dir.mkdir(parents=True)
    facts_path = brief_dir / "FACTS.md"
    facts_path.write_text(
        "- business_name: Test Biz\n"
        "- maps_url: https://maps.google.com/maps?cid=999\n"
        "- city: Dallas TX\n"
        "- category: auto_detailing\n",
        encoding="utf-8",
    )

    leads = [
        {
            "business_slug": slug,
            "business_name": "Test Biz",
            "city": "Nowhere",  # Should be overridden by FACTS.md
        }
    ]

    run_vnext_post_phase_04_5_gmaps_enrichment(
        run_id=run_id,
        workspace=workspace,
        selected_leads=leads,
        config={"vnext_flags": {"use_gmaps_enrichment": True}},
    )

    mock_run_enrichment.assert_called_once()
    _, kwargs = mock_run_enrichment.call_args
    assert kwargs["maps_url"] == "https://maps.google.com/maps?cid=999"
    assert kwargs["city"] == "Dallas TX"  # Overridden from FACTS.md


@patch("packages.enrichment.google_maps_enricher.run_enrichment")
def test_gmaps_enrichment_reads_cache_page_text(mock_run_enrichment, tmp_path: Path):
    """Enricher reads pre-extracted page text from enrichment_cache."""
    mock_run_enrichment.return_value = SAMPLE_ENRICHMENT

    run_id = "test_cache_run"
    workspace = str(tmp_path)
    slug = "cache-biz"

    # Create enrichment_cache with gmaps_page.txt
    cache_dir = (
        Path(workspace) / "runs" / run_id / "04_briefs" / slug / "enrichment_cache"
    )
    cache_dir.mkdir(parents=True)
    page_text_path = cache_dir / "gmaps_page.txt"
    page_text_path.write_text(
        "4.9 (327 Google reviews)\n\"Great service, highly recommend!\"",
        encoding="utf-8",
    )

    leads = [
        {
            "business_slug": slug,
            "business_name": "Cache Biz",
            "area": "Austin TX",
        }
    ]

    run_vnext_post_phase_04_5_gmaps_enrichment(
        run_id=run_id,
        workspace=workspace,
        selected_leads=leads,
        config={"vnext_flags": {"use_gmaps_enrichment": True}},
    )

    mock_run_enrichment.assert_called_once()
    _, kwargs = mock_run_enrichment.call_args
    assert kwargs["page_text"] is not None
    assert "327" in kwargs["page_text"]


@patch("packages.enrichment.google_maps_enricher.run_enrichment")
def test_gmaps_enrichment_graceful_failure(mock_run_enrichment, tmp_path: Path):
    """Enricher does not crash the pipeline when one lead fails."""
    mock_run_enrichment.side_effect = RuntimeError("Simulated failure")

    leads = [
        {"business_slug": "good-biz", "business_name": "Good Biz", "city": "OK"},
        {"business_slug": "bad-biz", "business_name": "Bad Biz", "city": "Fail"},
        {"business_slug": "another-biz", "business_name": "Another", "city": "OK"},
    ]

    result = run_vnext_post_phase_04_5_gmaps_enrichment(
        run_id="test_run",
        workspace=str(tmp_path),
        selected_leads=leads,
        config={"vnext_flags": {"use_gmaps_enrichment": True}},
    )

    # The function wraps each lead in try/except, so all leads get processed
    # and it returns whatever was written
    assert isinstance(result, list)
    # Since all failed, no artifacts should be written
    assert result == []


@patch("packages.enrichment.google_maps_enricher.run_enrichment")
def test_gmaps_enrichment_multiple_leads(mock_run_enrichment, tmp_path: Path):
    """Multiple leads each get their own enrichment artifact."""
    mock_run_enrichment.return_value = SAMPLE_ENRICHMENT

    leads = [
        {"business_slug": "biz-one", "business_name": "Biz One", "city": "City A"},
        {"business_slug": "biz-two", "business_name": "Biz Two", "city": "City B"},
    ]

    result = run_vnext_post_phase_04_5_gmaps_enrichment(
        run_id="multi_run",
        workspace=str(tmp_path),
        selected_leads=leads,
        config={"vnext_flags": {"use_gmaps_enrichment": True}},
    )

    # Both leads should have artifacts for gmaps_enrichment.json
    for slug in ("biz-one", "biz-two"):
        path = (
            Path(tmp_path)
            / "runs"
            / "multi_run"
            / "04_5_enrichment"
            / slug
            / "gmaps_enrichment.json"
        )
        assert path.exists(), f"Missing gmaps_enrichment.json for {slug}"
        # Also verify enrichment_sources.json exists
        sources_path = Path(tmp_path) / "runs" / "multi_run" / "04_5_enrichment" / slug / "enrichment_sources.json"
        assert sources_path.exists(), f"Missing enrichment_sources.json for {slug}"

    # Both leads should have payload injected
    assert "gmaps_enrichment" in leads[0]
    assert "gmaps_enrichment" in leads[1]

    # Should have 4 artifact paths returned (2 gmaps + 2 sources)
    assert len(result) == 4
