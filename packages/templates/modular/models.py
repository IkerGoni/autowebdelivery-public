"""Data models for business information used in template rendering."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field


def _digits_only(value: str) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


@dataclass
class ServiceItem:
    """A single service offering."""
    name: str
    description: str
    icon: str  # Material Symbols icon name, e.g. "dentistry"
    tag: str | None = None  # Optional label tag like "Weekly / Bi-Weekly"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ServiceItem:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class HoursSchedule:
    """Business hours schedule.

    TemplateComposer exposes the following flat variables for template rendering:
    - `hours_weekdays`      -> weekdays
    - `hours_weekday_hours` -> weekday_hours
    - `hours_weekend_day`   -> weekend_day
    - `hours_weekend_hours` -> weekend_hours
    - `hours_note`          -> note
    - `hours`               -> flat display string (hours_display property)
    """
    weekdays: str = "Mon - Sat"
    weekday_hours: str = "9:00 AM - 6:00 PM"
    weekend_day: str = "Sunday"
    weekend_hours: str = "Closed"
    note: str | None = None  # Additional note like "Emergency drop-off available"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> HoursSchedule:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class BusinessData:
    """Complete business data model for template rendering."""
    # Identity
    name: str = "Business Name"
    tagline: str = "Your trusted local service provider"
    niche: str = "dental"  # dental, beauty, automotive, cleaning, etc.

    # Contact
    phone: str = "(555) 000-0000"
    phone_raw: str = "5550000000"  # digits only for tel: links

    # Location
    address_line1: str = "123 Main Street"
    address_line2: str = "Suite 100"
    city: str = "New York"
    state: str = "NY"
    zip_code: str = "10001"

    # Rating & Reviews
    rating: float = 4.8
    review_count: int = 120
    trust_badge: str = "Patient Choice Winner"

    # Hours
    hours: HoursSchedule = field(default_factory=HoursSchedule)

    # Services (typically 3)
    services: list[ServiceItem] = field(default_factory=list)

    # CTA copy
    cta_headline: str = "Ready to get started?"
    cta_subtext: str = "Contact us today and take the first step."
    cta_button_label: str = "Call Now"
    cta_secondary_label: str = "View Services"

    # Hero/media/supporting copy
    hero_description: str | None = None
    hero_image_url: str = "https://images.unsplash.com/photo-1484154218962-a197022b5858?auto=format&fit=crop&w=1400&q=80"
    hero_image_alt: str = "Business hero image"
    coverage_area: str | None = None

    # Booking
    booking_url: str = ""  # Online booking link

    # Reviews
    review_samples: list[str] = field(default_factory=list)  # Sample review texts

    # SEO
    page_title: str | None = None
    meta_description: str | None = None
    website_url: str = ""  # For OG tags and structured data

    def __post_init__(self):
        if not self.services:
            self.services = [
                ServiceItem("Service One", "Professional service description here.", "star"),
                ServiceItem("Service Two", "Expert care and attention to detail.", "verified"),
                ServiceItem("Service Three", "Comprehensive solutions for your needs.", "auto_awesome"),
            ]
        if not self.page_title:
            self.page_title = f"{self.name} | Professional {self.niche.title()} Services"
        if not self.meta_description:
            self.meta_description = f"{self.name} - {self.tagline}. Call {self.phone}"
        if not self.hero_description:
            self.hero_description = self.tagline
        if not self.coverage_area:
            self.coverage_area = f"{self.city}, {self.state}".strip(", ") or self.full_address
        if not self.phone_raw:
            self.phone_raw = _digits_only(self.phone)

    @property
    def full_address(self) -> str:
        parts = [self.address_line1]
        if self.address_line2:
            parts.append(self.address_line2)
        parts.append(f"{self.city}, {self.state} {self.zip_code}")
        return ", ".join(parts)

    @property
    def full_address_html(self) -> str:
        parts = [self.address_line1]
        if self.address_line2:
            parts.append(self.address_line2)
        parts.append(f"{self.city}, {self.state} {self.zip_code}")
        line1 = ", ".join(parts[:2]) if len(parts) > 2 else parts[0]
        line2 = f"{self.city}, {self.state} {self.zip_code}"
        if len(parts) > 2:
            return f"{line1}<br/>{line2}"
        return line2

    @property
    def rating_display(self) -> str:
        return f"{self.rating:.1f}"

    @property
    def review_count_display(self) -> str:
        return f"{self.review_count}+"

    @property
    def hours_display(self) -> str:
        parts = []
        if self.hours.weekdays or self.hours.weekday_hours:
            parts.append(f"{self.hours.weekdays}: {self.hours.weekday_hours}".strip(": "))
        if self.hours.weekend_day or self.hours.weekend_hours:
            parts.append(f"{self.hours.weekend_day}: {self.hours.weekend_hours}".strip(": "))
        if self.hours.note:
            parts.append(self.hours.note)
        return " · ".join(part for part in parts if part)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["full_address"] = self.full_address
        d["full_address_html"] = self.full_address_html
        d["rating_display"] = self.rating_display
        d["review_count_display"] = self.review_count_display
        d["hours_display"] = self.hours_display
        return d

    @classmethod
    def from_dict(cls, data: dict) -> BusinessData:
        hours_data = data.pop("hours", None)
        services_data = data.pop("services", None)
        hours = HoursSchedule.from_dict(hours_data) if hours_data else HoursSchedule()
        services = [ServiceItem.from_dict(s) for s in services_data] if services_data else []
        # Filter to known fields
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(hours=hours, services=services, **filtered)

    @classmethod
    def from_json(cls, path: str) -> BusinessData:
        with open(path, "r") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def to_json(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


# JSON schema for validation reference
BUSINESS_DATA_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "BusinessData",
    "type": "object",
    "required": ["name", "niche", "phone"],
    "properties": {
        "name": {"type": "string", "description": "Business name"},
        "tagline": {"type": "string", "description": "Business tagline"},
        "niche": {"type": "string", "description": "Business niche/industry"},
        "phone": {"type": "string", "description": "Display phone number"},
        "phone_raw": {"type": "string", "description": "Digits-only phone for tel: links"},
        "address_line1": {"type": "string"},
        "address_line2": {"type": "string"},
        "city": {"type": "string"},
        "state": {"type": "string"},
        "zip_code": {"type": "string"},
        "rating": {"type": "number", "minimum": 0, "maximum": 5},
        "review_count": {"type": "integer", "minimum": 0},
        "trust_badge": {"type": "string"},
        "hours": {
            "type": "object",
            "properties": {
                "weekdays": {"type": "string"},
                "weekday_hours": {"type": "string"},
                "weekend_day": {"type": "string"},
                "weekend_hours": {"type": "string"},
                "note": {"type": "string"},
            },
        },
        "services": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "description", "icon"],
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "icon": {"type": "string"},
                    "tag": {"type": "string"},
                },
            },
        },
        "cta_headline": {"type": "string"},
        "cta_subtext": {"type": "string"},
        "cta_button_label": {"type": "string"},
        "page_title": {"type": "string"},
        "meta_description": {"type": "string"},
    },
}
