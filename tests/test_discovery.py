"""Tests for lead discovery modules."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path

from discovery.csv_loader import load_leads_from_csv
from discovery.maps_fetcher import fetch_maps_leads


def test_csv_loader_basic():
    """Test CSV loader with a simple CSV file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["business_name", "area", "website_url", "rating", "review_count"])
        writer.writerow(["Test Auto Detailing", "Frisco TX", "https://example.com", "4.8", "150"])
        writer.writerow(["No Website Detailing", "Dallas TX", "", "4.2", "80"])
        f.flush()
        csv_path = f.name

    try:
        leads = load_leads_from_csv(csv_path)
        assert len(leads) == 2
        assert leads[0]["business_name"] == "Test Auto Detailing"
        assert leads[0]["website"] == "https://example.com"
        assert leads[0]["rating"] == 4.8
        assert leads[0]["review_count"] == 150
        assert leads[1]["business_name"] == "No Website Detailing"
        assert leads[1]["website"] == ""
    finally:
        Path(csv_path).unlink()


def test_csv_loader_max_results():
    """Test CSV loader with max_results limit."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["business_name", "area", "website_url"])
        for i in range(5):
            writer.writerow([f"Business {i}", "Area", "https://example.com"])
        f.flush()
        csv_path = f.name

    try:
        leads = load_leads_from_csv(csv_path, max_results=2)
        assert len(leads) == 2
    finally:
        Path(csv_path).unlink()


def test_csv_loader_missing_file():
    """Test CSV loader with non-existent file."""
    leads = load_leads_from_csv("/nonexistent/path/file.csv")
    assert leads == []


def test_csv_loader_defaults():
    """Test CSV loader applies defaults for missing fields."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["business_name"])
        writer.writerow(["Minimal Business"])
        f.flush()
        csv_path = f.name

    try:
        leads = load_leads_from_csv(csv_path)
        assert len(leads) == 1
        assert leads[0]["business_name"] == "Minimal Business"
        assert leads[0]["rating"] == 0.0
        assert leads[0]["review_count"] == 0
        assert leads[0]["website"] == ""
    finally:
        Path(csv_path).unlink()


def test_fetch_maps_leads_fallback_to_fixture():
    """Test maps fetcher falls back to fixture when no API key is set."""
    import os
    # Ensure no API key is set
    api_key = os.environ.pop("GOOGLE_MAPS_API_KEY", None)
    try:
        leads = fetch_maps_leads("auto detailing", "Frisco TX", max_results=5)
        # Should return fixture data (non-empty list)
        assert isinstance(leads, list)
        assert len(leads) > 0
        # Each lead should have required fields
        for lead in leads[:1]:
            assert "business_name" in lead
    finally:
        if api_key:
            os.environ["GOOGLE_MAPS_API_KEY"] = api_key
