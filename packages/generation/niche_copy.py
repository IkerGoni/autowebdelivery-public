"""Niche-specific copy generator — persuasive, human, non-AI-sounding.

Produces copy slots that read like a real business wrote them, not a template.
Each niche has its own voice, value propositions, and CTA language.

Used by:
- Phase 05 template generation (fallback when no Stitch)
- Phase 04.5 copy_inputs enrichment (improves deterministic copy)
- Stitch prompt builder (as structured guidance for LLM)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CopySlots:
    """Copy slots for a single business page."""
    hero_tagline: str
    hero_supporting_line: str
    overview_intro: str
    overview_support_block_1: str
    overview_support_block_2: str
    trust_intro: str
    location_intro: str
    cta_body: str
    footer_note: str


@dataclass(frozen=True)
class NicheCopyProfile:
    """Voice and content profile for a niche."""
    voice: str  # e.g. "confident-direct", "warm-professional"
    value_props: list[str]  # what this niche cares about most
    cta_style: str  # e.g. "direct-action", "soft-invite"
    tone_words: list[str]  # words that fit the voice
    avoid_words: list[str]  # words that sound AI/corporate


# ---------------------------------------------------------------------------
# Niche profiles
# ---------------------------------------------------------------------------

_MOBILE_DETAILING = NicheCopyProfile(
    voice="confident-direct",
    value_props=[
        "we come to you — no driving, no waiting",
        "showroom results at your door",
        "protect your investment",
        "professional-grade products",
        "save hours every week",
    ],
    cta_style="direct-action",
    tone_words=["precision", "detail", "care", "results", "professional", "quality"],
    avoid_words=["premier", "cutting-edge", "state-of-the-art", "unparalleled", "testimonials"],
)

_DENTAL = NicheCopyProfile(
    voice="warm-professional",
    value_props=[
        "gentle care you can trust",
        "modern treatments, comfortable experience",
        "your smile, our priority",
        "family-friendly environment",
        "transparent about options and costs",
    ],
    cta_style="soft-invite",
    tone_words=["care", "comfort", "health", "smile", "trust", "experience"],
    avoid_words=["best", "cheapest", "guaranteed", "#1", "award-winning"],
)

_SALON_BEAUTY = NicheCopyProfile(
    voice="warm-editorial",
    value_props=[
        "look and feel your best",
        "personalized attention",
        "trends and timeless style",
        "relaxing experience",
        "skilled professionals",
    ],
    cta_style="soft-invite",
    tone_words=["beautiful", "style", "relax", "transform", "expert", "care"],
    avoid_words=["cheap", "fast", "guaranteed", "best", "premier"],
)

_AUTO_REPAIR = NicheCopyProfile(
    voice="straight-talking",
    value_props=[
        "honest diagnostics, fair pricing",
        "get back on the road fast",
        "experienced technicians",
        "no surprises on the bill",
        "quality parts, quality work",
    ],
    cta_style="direct-action",
    tone_words=["honest", "reliable", "experienced", "quality", "fair", "trusted"],
    avoid_words=["premier", "elite", "cutting-edge", "unbeatable", "guaranteed"],
)

_CLEANING = NicheCopyProfile(
    voice="friendly-efficient",
    value_props=[
        "come home to a clean space",
        "reliable, on-time service",
        "eco-friendly products available",
        "flexible scheduling",
        "attention to detail",
    ],
    cta_style="direct-action",
    tone_words=["clean", "fresh", "reliable", "thorough", "friendly", "care"],
    avoid_words=["premier", "elite", "best", "guaranteed", "unparalleled"],
)

_RESTAURANT = NicheCopyProfile(
    voice="warm-inviting",
    value_props=[
        "fresh ingredients, real flavors",
        "a place to gather and enjoy",
        "local favorites, made daily",
        "something for everyone",
        "warm hospitality",
    ],
    cta_style="soft-invite",
    tone_words=["fresh", "flavor", "welcome", "local", "crafted", "enjoy"],
    avoid_words=["premier", "finest", "best", "world-class", "award-winning"],
)

# ---------------------------------------------------------------------------
# Category → profile mapping
# ---------------------------------------------------------------------------

_NICHE_PROFILES: dict[str, NicheCopyProfile] = {
    "mobile_detailing": _MOBILE_DETAILING,
    "auto_detailing": _MOBILE_DETAILING,
    "car_detailing": _MOBILE_DETAILING,
    "dental": _DENTAL,
    "dentist": _DENTAL,
    "clinic": _DENTAL,
    "medical": _DENTAL,
    "wellness": _DENTAL,
    "salon": _SALON_BEAUTY,
    "beauty": _SALON_BEAUTY,
    "spa": _SALON_BEAUTY,
    "barber": _SALON_BEAUTY,
    "auto_repair": _AUTO_REPAIR,
    "mechanic": _AUTO_REPAIR,
    "repair": _AUTO_REPAIR,
    "cleaning": _CLEANING,
    "house_cleaning": _CLEANING,
    "restaurant": _RESTAURANT,
    "cafe": _RESTAURANT,
    "food": _RESTAURANT,
}

_DEFAULT_PROFILE = NicheCopyProfile(
    voice="professional-clear",
    value_props=[
        "quality service you can count on",
        "focused on what matters to you",
        "local and accessible",
        "clear communication",
    ],
    cta_style="direct-action",
    tone_words=["quality", "local", "reliable", "professional"],
    avoid_words=["premier", "best", "guaranteed", "#1", "elite"],
)


def _detect_niche_profile(category: str, niche: str = "") -> NicheCopyProfile:
    """Find the best niche profile for a category/niche."""
    text = f"{category} {niche}".lower()
    for key, profile in _NICHE_PROFILES.items():
        if key in text:
            return profile
    return _DEFAULT_PROFILE


def _build_rating_line(rating: str, review_count: str) -> str:
    """Build a trust line from rating + reviews — factual only."""
    if rating and review_count:
        return f"Rated {rating} on Google from {review_count} reviews"
    if rating:
        return f"Rated {rating} on Google"
    return None


def _generate_copy_slots(
    business_name: str,
    category: str,
    address: str = "",
    phone: str = "",
    hours: str = "",
    rating: str = "",
    review_count: str = "",
    niche: str = "",
    maps_url: str = "",
) -> CopySlots:
    """Generate persuasive, niche-specific copy slots.

    Only uses verified facts. No invented claims.
    """
    profile = _detect_niche_profile(category, niche)

    # Hero — name + what they do, clear and direct
    hero_tagline = business_name or "Local Business"
    if category:
        hero_tagline = f"{business_name}"

    # Supporting — the trust signal if we have it
    rating_line = _build_rating_line(rating, review_count)
    if rating_line:
        hero_supporting_line = rating_line
    elif category:
        hero_supporting_line = f"{category} — {address}" if address else category
    else:
        hero_supporting_line = "Serving the local community"

    # Overview — lead with value, not "we are a business that..."
    vp = profile.value_props
    if profile.voice == "confident-direct":
        overview_intro = (
            f"{business_name} brings professional {category.lower()} service to your location. "
            f"No driving, no waiting — {vp[0]}."
        )
        overview_support_block_1 = f"{vp[1].capitalize()}. Every job done with care and attention to detail."
        overview_support_block_2 = f"{vp[2].capitalize()}. We use professional-grade products for lasting results."
    elif profile.voice == "warm-professional":
        overview_intro = (
            f"At {business_name}, your comfort and health come first. "
            f"{vp[0].capitalize()}."
        )
        overview_support_block_1 = f"{vp[1].capitalize()}. We take time to explain your options."
        overview_support_block_2 = f"{vp[2].capitalize()}. Our team is here for you and your family."
    elif profile.voice == "warm-editorial":
        overview_intro = (
            f"{business_name} is where style meets care. "
            f"{vp[0].capitalize()}."
        )
        overview_support_block_1 = f"{vp[1].capitalize()}. Every visit is tailored to you."
        overview_support_block_2 = f"{vp[2].capitalize()}. Leave feeling your best."
    elif profile.voice == "straight-talking":
        overview_intro = (
            f"{business_name} does honest {category.lower()} work at fair prices. "
            f"{vp[0].capitalize()}."
        )
        overview_support_block_1 = f"{vp[1].capitalize()}. We explain what needs fixing before we start."
        overview_support_block_2 = f"{vp[2].capitalize()}. No hidden charges, no surprises."
    elif profile.voice == "friendly-efficient":
        overview_intro = (
            f"{business_name} makes {category.lower()} easy. "
            f"{vp[0].capitalize()}."
        )
        overview_support_block_1 = f"{vp[1].capitalize()}. We show up on time, every time."
        overview_support_block_2 = f"{vp[2].capitalize()}. Your space, treated with respect."
    elif profile.voice == "warm-inviting":
        overview_intro = (
            f"{business_name} is your spot for {category.lower()}. "
            f"{vp[0].capitalize()}."
        )
        overview_support_block_1 = f"{vp[1].capitalize()}. Come as you are."
        overview_support_block_2 = f"{vp[2].capitalize()}. Made fresh, served with care."
    else:
        overview_intro = (
            f"{business_name} provides {category.lower()} services in the area. "
            f"{vp[0].capitalize()}."
        )
        overview_support_block_1 = f"{vp[1].capitalize()}."
        overview_support_block_2 = f"{vp[2].capitalize()}."

    # Trust — factual only
    if rating_line:
        trust_intro = f"{rating_line}. We let our work speak for itself."
    else:
        trust_intro = f"{business_name} is committed to quality {category.lower()} service."

    # Location
    if address:
        location_intro = f"Find us at {address}."
        if hours:
            location_intro += " Open during listed hours — check below for details."
    elif hours:
        location_intro = "Check hours below and reach out when it works for you."
    else:
        location_intro = "Contact us for location and availability."

    # CTA
    if profile.cta_style == "direct-action":
        if phone:
            cta_body = f"Ready to get started? Call {phone} or reach out below."
        else:
            cta_body = "Ready to get started? Reach out using the contact options below."
    else:
        if phone:
            cta_body = f"We'd love to hear from you. Call {phone} or use the contact options below."
        else:
            cta_body = "We'd love to hear from you. Use the contact options below to get in touch."

    # Footer
    footer_note = f"Page prepared for {business_name}."

    return CopySlots(
        hero_tagline=hero_tagline,
        hero_supporting_line=hero_supporting_line,
        overview_intro=overview_intro,
        overview_support_block_1=overview_support_block_1,
        overview_support_block_2=overview_support_block_2,
        trust_intro=trust_intro,
        location_intro=location_intro,
        cta_body=cta_body,
        footer_note=footer_note,
    )


def copy_slots_to_dict(slots: CopySlots) -> dict[str, str]:
    """Convert CopySlots to dict for JSON/template use."""
    return {
        "hero_tagline": slots.hero_tagline,
        "hero_supporting_line": slots.hero_supporting_line,
        "overview_intro": slots.overview_intro,
        "overview_support_block_1": slots.overview_support_block_1,
        "overview_support_block_2": slots.overview_support_block_2,
        "trust_intro": slots.trust_intro,
        "location_intro": slots.location_intro,
        "cta_body": slots.cta_body,
        "footer_note": slots.footer_note,
    }


def generate_copy_from_facts(facts: dict[str, Any], niche: str = "") -> CopySlots:
    """Generate copy slots from a FACTS.md dict."""
    return _generate_copy_slots(
        business_name=facts.get("business_name", ""),
        category=facts.get("category", ""),
        address=facts.get("address", ""),
        phone=facts.get("phone", ""),
        hours=facts.get("hours", ""),
        rating=facts.get("rating", ""),
        review_count=facts.get("review_count", ""),
        niche=niche,
        maps_url=facts.get("maps_url", ""),
    )
