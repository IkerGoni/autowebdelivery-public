"""Tests for Phase 04.5 enrichment extractors."""


from packages.enrichment.hours_extractor import (
    format_hours_display,
    merge_hours,
    parse_hours_text,
)
from packages.enrichment.pricing_extractor import (
    extract_pricing_from_html,
    format_pricing_hint,
)
from packages.enrichment.services_extractor import (
    extract_services_from_html,
    extract_services_from_text,
    merge_services_with_existing,
)


class TestServicesExtractor:
    """Tests for services_extractor module."""

    def test_extract_auto_detailing_services(self):
        """Verify services extracted from auto_detailing HTML."""
        html = """
        <h2>Our Services</h2>
        <ul>
            <li>Ceramic Coating - Gtechniq Certified</li>
            <li>Paint Correction Services</li>
            <li>Interior Detailing & Steam Cleaning</li>
            <li>Paint Protection Film Installation</li>
        </ul>
        """
        services = extract_services_from_html(html, "auto_detailing")

        assert len(services) >= 2
        service_names = [s["service_name"] for s in services]
        assert "Ceramic Coating" in service_names
        assert "Paint Correction" in service_names
        assert any("Protection" in s for s in service_names)

    def test_extract_plumbing_services(self):
        """Verify services extracted from plumbing HTML."""
        html = """
        <div class="services">
            <h3>Drain Repair</h3>
            <p>Leak Detection Services Available</p>
            <p>Water Heater Repair and Installation</p>
        </div>
        """
        services = extract_services_from_html(html, "plumbing")

        assert len(services) >= 2
        service_names = [s["service_name"] for s in services]
        assert "Drain Service" in service_names
        assert "Leak Detection" in service_names
        assert any("Water Heater" in s for s in service_names)

    def test_extract_hvac_services(self):
        """Verify services extracted from HVAC HTML."""
        html = """
        <h2>AC Repair Services</h2>
        <p>Furnace Repair and Duct Cleaning</p>
        """
        services = extract_services_from_html(html, "hvac")

        service_names = [s["service_name"] for s in services]
        assert "AC Repair" in service_names
        assert "Duct Cleaning" in service_names

    def test_extract_services_unknown_category(self):
        """Verify empty list for unknown category."""
        services = extract_services_from_html("Some text", "unknown_category")
        assert services == []

    def test_confidence_scoring(self):
        """Verify confidence scoring based on match count."""
        html = "Ceramic Coating is offered. We also do Ceramic Coating for wheels."
        services = extract_services_from_html(html, "auto_detailing")

        ceramic = next((s for s in services if s["service_name"] == "Ceramic Coating"), None)
        assert ceramic is not None
        assert ceramic["confidence"] == 0.9  # Multiple matches

    def test_extract_services_from_text_alias(self):
        """Verify extract_services_from_text works as alias."""
        text = "We provide Drain Repair and Leak Detection services."
        services = extract_services_from_text(text, "plumbing")

        assert len(services) == 2
        service_names = [s["service_name"] for s in services]
        assert "Drain Service" in service_names
        assert "Leak Detection" in service_names

    def test_merge_services_with_existing(self):
        """Verify merging extracted services with existing list."""
        extracted = [
            {"service_name": "Ceramic Coating", "confidence": 0.9},
            {"service_name": "Paint Correction", "confidence": 0.8},
        ]
        existing = "Interior Detailing"

        merged = merge_services_with_existing(existing=existing, extracted=extracted)

        assert "Ceramic Coating" in merged
        assert "Paint Correction" in merged
        assert "Interior Detailing" in merged


class TestPricingExtractor:
    """Tests for pricing_extractor module."""

    def test_extract_simple_prices(self):
        """Verify prices extracted from HTML text."""
        html = "Starting at $199. Premium packages from $499."
        source_url = "https://example.com"

        prices = extract_pricing_from_html(html, source_url)

        assert len(prices) == 2
        assert "199" in prices[0]["price"]
        assert "499" in prices[1]["price"]

    def test_extract_prices_with_various_formats(self):
        """Verify prices extracted from various formats."""
        html = "Prices: $99, from $199, starting at $1,299.99"
        source_url = "https://example.com"

        prices = extract_pricing_from_html(html, source_url)

        assert len(prices) >= 2
        assert any("99" in p["price"] for p in prices)
        assert any("199" in p["price"] for p in prices)

    def test_format_pricing_hint_no_prices(self):
        """Verify generic hint when no prices found."""
        hint = format_pricing_hint([])
        assert hint == "Multiple service packages available"

    def test_format_pricing_hint_single_price(self):
        """Verify hint format for single price."""
        prices = [{"price": "199", "confidence": 0.85}]
        hint = format_pricing_hint(prices)
        assert "from $199" in hint

    def test_format_pricing_hint_multiple_prices(self):
        """Verify hint format for price range."""
        prices = [
            {"price": "99", "confidence": 0.85},
            {"price": "499", "confidence": 0.85},
        ]
        hint = format_pricing_hint(prices)
        assert "starting from" in hint.lower()


class TestHoursExtractor:
    """Tests for hours_extractor module."""

    def test_parse_day_range_hours(self):
        """Verify parsing of day range format."""
        hours = "Mon-Fri: 9am-5pm, Sat: 10am-2pm"
        result = parse_hours_text(hours)

        assert "Monday" in result
        assert "Tuesday" in result
        assert "Friday" in result
        assert "Saturday" in result
        assert "Sunday" not in result

    def test_parse_single_day_hours(self):
        """Verify parsing of single day format."""
        hours = "Monday: 9:00 AM - 5:00 PM"
        result = parse_hours_text(hours)

        assert "Monday" in result
        assert "9" in result["Monday"]

    def test_format_hours_display(self):
        """Verify formatted display output."""
        hours_dict = {
            "Monday": "9am-5pm",
            "Tuesday": "9am-5pm",
            "Wednesday": "9am-5pm",
            "Thursday": "9am-5pm",
            "Friday": "9am-5pm",
        }
        summary = format_hours_display(hours_dict)

        expected = "Monday: 9am-5pm"
        assert expected in summary
        assert "9am" in summary

    def test_parse_empty_hours(self):
        """Verify empty result for empty input."""
        result = parse_hours_text("")
        assert result == {}

    def test_merge_hours(self):
        """Verify hours merging with existing text."""
        original = "Mon-Fri 9am-5pm"
        parsed = {"monday": "9am-5pm", "tuesday": "9am-5pm"}

        merged = merge_hours(original, parsed)

        assert merged["raw"] == original
        assert "monday" in merged["parsed_structured"]
        assert merged["confidence"] >= 0.5