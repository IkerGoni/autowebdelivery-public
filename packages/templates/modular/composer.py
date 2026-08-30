"""TemplateComposer - Reassembles sections with injected business data.

Supports:
  - Composing full pages from a single family (desktop + mobile)
  - Mixin system: swap individual sections between families
  - {{mustache}} placeholder rendering
"""

from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path
from urllib.parse import quote

from .models import BusinessData

MODULE_DIR = Path(__file__).parent
SECTIONS_DIR = MODULE_DIR / "sections"
CONFIG_DIR = MODULE_DIR / "config"


class TemplateComposer:
    """Composes HTML pages from modular sections with data injection."""

    def __init__(
        self,
        sections_dir: Path | None = None,
        config_dir: Path | None = None,
    ):
        self.sections_dir = sections_dir or SECTIONS_DIR
        self.config_dir = config_dir or CONFIG_DIR

    def _variant_to_suffix(self, variant: str) -> str:
        """Map variant name to section suffix."""
        return "" if variant == "desktop" else f"_{variant}"

    def _load_section(self, family: str, section_name: str) -> str | None:
        """Load a section HTML template from disk.

        Supports two naming conventions:
        - Flat: {section}.html (desktop) / {section}_mobile.html (mobile)
        - Subdirectory: {variant}/{section}.html
        """
        # Convention 1: flat files with _mobile suffix
        flat_path = self.sections_dir / family / f"{section_name}.html"
        if flat_path.exists():
            return flat_path.read_text(encoding="utf-8")

        mobile_path = self.sections_dir / family / f"{section_name}_mobile.html"
        if mobile_path.exists():
            return mobile_path.read_text(encoding="utf-8")

        # Convention 2: subdirectories (e.g. mobile_v2/, desktop_v2/)
        for variant in ("desktop_v2", "mobile_v2"):
            suffix = f"_{variant}"
            if section_name.endswith(suffix):
                base = section_name[: -len(suffix)]
                subdir_path = self.sections_dir / family / variant / f"{base}.html"
                if subdir_path.exists():
                    return subdir_path.read_text(encoding="utf-8")

        return None

    def _load_config(self, family: str) -> dict:
        """Load family config from disk."""
        path = self.config_dir / f"{family}.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _render_mustache(self, template: str, data: dict) -> str:
        """Simple mustache-style template rendering.

        Supports:
          {{key}}         - simple key replacement
          {{key.subkey}}  - nested dict access
          {{#list}}...{{/list}} - list iteration (limited)
        """
        result = template

        # Handle {{#list}}...{{/list}} blocks for services
        # Or {{#key}}...{{/key}} for truthy string values.
        list_pattern = re.compile(r"\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}", re.DOTALL)
        for match in list_pattern.finditer(result):
            list_key = match.group(1)
            inner_template = match.group(2)
            value = data.get(list_key)

            if value is None or value == "":
                replacement = ""
            elif isinstance(value, list):
                rendered_items = []
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        item_rendered = inner_template
                        for key, val in item.items():
                            item_rendered = item_rendered.replace(f"{{{{{key}}}}}", str(val))
                            item_rendered = item_rendered.replace("{{idx}}", str(i))
                        rendered_items.append(item_rendered)
                replacement = "".join(rendered_items)
            elif isinstance(value, str):
                replacement = inner_template.replace(f"{{{{{list_key}}}}}", value)
            else:
                replacement = ""

            result = result.replace(match.group(0), replacement)

        # Handle simple {{key}} replacements
        def replace_simple(match):
            key = match.group(1).strip()
            # Support dotted access
            parts = key.split(".")
            value = data
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part, match.group(0))
                else:
                    return match.group(0)
            return str(value) if value is not None else match.group(0)

        result = re.sub(r"\{\{([^#/}][^}]*?)\}\}", replace_simple, result)

        return result

    def _build_services_list(self, business: BusinessData) -> str:
        """Render fallback services list HTML for templates using {{services_list}}."""
        cards = []
        for service in business.services:
            tag_html = (
                f'<span class="inline-flex items-center rounded-full bg-primary-container/15 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-primary">{service.tag}</span>'
                if service.tag else ""
            )
            cards.append(
                "\n".join([
                    '<article class="rounded-2xl border border-outline/20 bg-surface-container-lowest p-6 shadow-sm">',
                    '  <div class="flex items-start gap-4">',
                    f'    <span class="material-symbols-outlined text-primary text-3xl">{service.icon}</span>',
                    '    <div class="flex-1 space-y-2">',
                    f'      <h4 class="text-lg font-semibold text-on-surface">{service.name}</h4>',
                    f'      <p class="text-sm leading-6 text-on-surface-variant">{service.description}</p>',
                    f'      {tag_html}' if tag_html else '',
                    '    </div>',
                    '  </div>',
                    '</article>',
                ]).replace('\n\n', '\n')
            )
        return "\n".join(cards)

    def _build_data_dict(self, business: BusinessData) -> dict:
        """Convert BusinessData to flat dict suitable for template rendering.

        Returns a dict with the following hours-related keys:
        - `hours`: Flat display string (e.g. "Mon - Fri: 8:00 AM - 5:00 PM · Sat - Sun: Closed")
          for backward compatibility with existing templates.
        - `hours_weekdays`: Weekday label (e.g. "Mon - Fri")
        - `hours_weekday_hours`: Weekday hours (e.g. "8:00 AM - 5:00 PM")
        - `hours_weekend_day`: Weekend day label (e.g. "Sat - Sun")
        - `hours_weekend_hours`: Weekend hours (e.g. "Closed")
        - `hours_note`: Optional note (e.g. "Emergency appointments available")
        """
        d = business.to_dict()

        # Add service-specific convenience keys
        for i, service in enumerate(business.services):
            prefix = f"service{i + 1}"
            d[f"{prefix}_name"] = service.name
            d[f"{prefix}_description"] = service.description
            d[f"{prefix}_icon"] = service.icon
            d[f"{prefix}_tag"] = service.tag or ""

        d["name"] = business.name
        d["address"] = business.full_address
        d["hours"] = business.hours_display
        # Per-day hours variables for templates that need structured schedule rendering.
        # These supplement the flat `hours` string (which remains for backward compatibility).
        d["hours_weekdays"] = business.hours.weekdays
        d["hours_weekday_hours"] = business.hours.weekday_hours
        d["hours_weekend_day"] = business.hours.weekend_day
        d["hours_weekend_hours"] = business.hours.weekend_hours
        d["hours_note"] = business.hours.note or ""
        d["coverage_area"] = business.coverage_area or business.full_address
        d["cta_copy"] = business.cta_button_label
        d["cta_primary"] = business.cta_button_label
        d["cta_secondary"] = business.cta_secondary_label
        d["hero_description"] = business.hero_description or business.tagline
        d["hero_image_url"] = business.hero_image_url
        d["hero_image_alt"] = business.hero_image_alt
        d["services_list"] = self._build_services_list(business)

        d["website_url"] = business.website_url

        # Address query for Google Maps embed (URL-encoded full address)
        d["address_query"] = quote(business.full_address)

        # Booking CTA data
        d["booking_url"] = business.booking_url or ""
        d["booking_label"] = "Book Online"
        d["has_booking"] = [{}] if business.booking_url else []

        # Reviews/testimonials data
        review_items = []
        for sample in business.review_samples[:3]:
            review_items.append({"text": sample})
        d["review_items"] = review_items
        d["has_reviews"] = [{}] if review_items else []
        d["rating"] = business.rating_display
        d["review_count"] = business.review_count_display

        return d

    def _render_meta_description(self, meta_description: str | None) -> str:
        """Render optional meta description tag."""
        if not meta_description:
            return ""
        return f'<meta content="{escape(meta_description, quote=True)}" name="description"/>'

    def _render_og_tags(self, business: BusinessData) -> str:
        """Render Open Graph and Twitter Card meta tags."""
        title = escape(business.page_title or "", quote=True)
        description = escape(business.meta_description or "", quote=True)
        url = escape(business.website_url or "", quote=True)
        lines = [
            # Open Graph
            f'<meta property="og:title" content="{title}"/>',
            f'<meta property="og:description" content="{description}"/>',
            '<meta property="og:type" content="website"/>',
            f'<meta property="og:url" content="{url}"/>',
            '<meta property="og:locale" content="en_US"/>',
            # Twitter Card
            '<meta name="twitter:card" content="summary"/>',
            f'<meta name="twitter:title" content="{title}"/>',
            f'<meta name="twitter:description" content="{description}"/>',
        ]
        return "\n".join(lines)

    def _render_json_ld(self, business: BusinessData) -> str:
        """Render JSON-LD LocalBusiness structured data."""
        ld = {
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": business.name,
            "telephone": business.phone,
            "address": {
                "@type": "PostalAddress",
                "streetAddress": business.address_line1,
                "addressLocality": business.city,
                "addressRegion": business.state,
                "postalCode": business.zip_code,
            },
            "aggregateRating": {
                "@type": "AggregateRating",
                "ratingValue": business.rating,
                "reviewCount": business.review_count,
            },
        }
        return f'<script type="application/ld+json">\n{json.dumps(ld, indent=2)}\n</script>'

    def _build_document_shell(
        self,
        family: str,
        config: dict,
        business: BusinessData,
        body_content: str,
    ) -> str:
        """Build the complete HTML document with head, tailwind config, fonts, etc."""
        config_data = self._load_config(family)

        # Build font links
        font_links = config_data.get("font_links", [])
        font_links_html = "\n".join(font_links)
        # Remove duplicates
        font_links_html = "\n".join(dict.fromkeys(font_links_html.split("\n")))

        # Build tailwind config
        tailwind_raw = config_data.get("tailwind_config_raw", "")
        if tailwind_raw:
            tw_script = f'<script id="tailwind-config">\n{tailwind_raw}\n</script>'
        else:
            tw_script = ""

        # Build styles
        styles = config_data.get("styles", "")
        if styles:
            styles_html = f"<style>\n{styles}\n</style>"
        else:
            styles_html = ""

        meta_description_html = self._render_meta_description(business.meta_description)
        og_tags_html = self._render_og_tags(business)
        json_ld_html = self._render_json_ld(business)

        return f"""<!DOCTYPE html>

<html class="light" lang="en">
<head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>{business.page_title}</title>
{meta_description_html}
{og_tags_html}
{json_ld_html}
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
{font_links_html}
{tw_script}
{styles_html}
</head>
<body class="bg-background text-on-surface">
{body_content}
</body>
</html>"""

    def compose(
        self,
        family: str,
        business: BusinessData,
        variant: str = "desktop",
        mixins: dict[str, str] | None = None,
    ) -> str:
        """Compose a complete HTML page.

        Args:
            family: Template family name (e.g. "clinical-trust")
            business: BusinessData instance with business information
            variant: "desktop" or "mobile"
            mixins: Optional dict mapping section_name -> source_family
                    e.g. {"hero": "warm-editorial"} to use warm-editorial's hero

        Returns:
            Complete HTML string
        """
        mixins = mixins or {}
        suffix = self._variant_to_suffix(variant)
        data = self._build_data_dict(business)
        config = self._load_config(family)

        # Compose sections
        section_order = ["header", "hero", "services", "trust", "reviews", "location", "cta", "footer"]
        body_parts = []

        for section_name in section_order:
            # Check if mixin overrides this section
            source_family = mixins.get(section_name, family)
            key = f"{section_name}{suffix}"
            template = self._load_section(source_family, key)

            if template is None:
                # Fallback to primary family
                template = self._load_section(family, key)

            if template is None:
                # Fallback to common family for shared sections (e.g. reviews)
                template = self._load_section("common", key)

            if template:
                # Render with data
                rendered = self._render_mustache(template, data)
                body_parts.append(f"<!-- {section_name.title()} Section -->\n{rendered}")

        body_content = "\n\n".join(body_parts)

        return self._build_document_shell(family, config, business, body_content)

    def compose_desktop(
        self,
        family: str,
        business: BusinessData,
        mixins: dict[str, str] | None = None,
    ) -> str:
        """Compose desktop variant."""
        return self.compose(family, business, "desktop", mixins)

    def compose_mobile(
        self,
        family: str,
        business: BusinessData,
        mixins: dict[str, str] | None = None,
    ) -> str:
        """Compose mobile variant."""
        return self.compose(family, business, "mobile", mixins)

    def compose_both(
        self,
        family: str,
        business: BusinessData,
        mixins: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Compose both desktop and mobile variants.

        Returns dict with "desktop" and "mobile" keys.
        """
        return {
            "desktop": self.compose_desktop(family, business, mixins),
            "mobile": self.compose_mobile(family, business, mixins),
        }

    def list_available_families(self) -> list[str]:
        """List available template families."""
        if not self.sections_dir.exists():
            return []

        families = []
        for d in self.sections_dir.iterdir():
            if not d.is_dir():
                continue
            has_flat_header = (d / "header.html").exists()
            has_nested_header = any(
                (d / variant / "header.html").exists()
                for variant in ("desktop_v2", "mobile_v2")
            )
            if has_flat_header or has_nested_header:
                families.append(d.name)

        return sorted(families)

    def list_available_sections(self, family: str) -> list[str]:
        """List available sections for a family."""
        family_dir = self.sections_dir / family
        if not family_dir.exists():
            return []

        sections = {p.stem for p in family_dir.glob("*.html")}

        for variant in ("desktop_v2", "mobile_v2"):
            variant_dir = family_dir / variant
            if not variant_dir.exists():
                continue
            for path in variant_dir.glob("*.html"):
                sections.add(f"{path.stem}_{variant}")

        return sorted(sections)


def compose_page(
    family: str,
    data_path: str,
    output_dir: str,
    mixins: dict[str, str] | None = None,
) -> list[str]:
    """High-level compose function: read data JSON, generate pages.

    Returns list of created file paths.
    """
    business = BusinessData.from_json(data_path)
    composer = TemplateComposer()

    pages = composer.compose_both(family, business, mixins)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    created = []
    for variant, html in pages.items():
        filename = "index.html" if variant == "desktop" else "mobile.html"
        path = output / filename
        path.write_text(html, encoding="utf-8")
        created.append(str(path))

    return created
