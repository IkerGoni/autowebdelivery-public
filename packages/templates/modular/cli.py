#!/usr/bin/env python3
"""CLI tool for composing modular templates.

Usage:
  # Generate a page from a family with business data
  python -m templates.modular.cli compose clinical-trust data.json -o output/

  # Generate with mixin overrides
  python -m templates.modular.cli compose clinical-trust data.json -o output/ --mixin hero=warm-editorial

  # Generate both desktop and mobile
  python -m templates.modular.cli compose clinical-trust data.json -o output/ --both

  # Parse all source templates (re-extract sections)
  python -m templates.modular.cli parse

  # List available families and sections
  python -m templates.modular.cli list

  # Generate a sample business data JSON
  python -m templates.modular.cli sample-data -o sample_business.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from templates.modular.parser import parse_all_families  # noqa: E402
from templates.modular.composer import TemplateComposer  # noqa: E402
from templates.modular.models import BusinessData, ServiceItem, HoursSchedule  # noqa: E402


def cmd_parse(args):
    """Parse all template families from stitch artifacts."""
    print("Parsing template families...")
    results = parse_all_families()
    total = 0
    for family, paths in results.items():
        print(f"  {family}: {len(paths)} files")
        total += len(paths)
    print(f"Total: {total} files created")


def cmd_compose(args):
    """Compose a page from a family + business data."""
    family = args.family
    data_path = args.data
    output_dir = args.output or f"./output/{family}"
    variant = "both" if args.both else args.variant

    # Parse mixins
    mixins = {}
    if args.mixin:
        for mixin_str in args.mixin:
            if "=" in mixin_str:
                section, source = mixin_str.split("=", 1)
                mixins[section] = source
            else:
                print(f"Invalid mixin format: {mixin_str}. Use section=family")
                sys.exit(1)

    # Load business data
    business = BusinessData.from_json(data_path)

    composer = TemplateComposer()

    if variant == "both":
        pages = composer.compose_both(family, business, mixins)
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        for v, html in pages.items():
            if v == "desktop":
                filename = "index.html"
            else:
                filename = f"{v}.html"
            path = out / filename
            path.write_text(html, encoding="utf-8")
            print(f"Created: {path}")

    else:
        html = composer.compose(family, business, variant, mixins)
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        if variant == "desktop" or variant == "desktop_v2":
            filename = "index.html"
        else:
            filename = f"{variant}.html"
        path = out / filename
        path.write_text(html, encoding="utf-8")
        print(f"Created: {path}")

    if mixins:
        print(f"Applied mixins: {mixins}")


def cmd_list(args):
    """List available families and sections."""
    composer = TemplateComposer()
    families = composer.list_available_families()

    if not families:
        print("No families found. Run 'parse' first to extract sections.")
        return

    for family in families:
        sections = composer.list_available_sections(family)
        print(f"\n{family}:")
        for section in sections:
            print(f"  {section}")


def cmd_sample_data(args):
    """Generate a sample business data JSON."""
    output = args.output or "sample_business.json"

    sample = BusinessData(
        name="Bright Smile Dental",
        tagline="Your trusted partner for reliable dental care",
        niche="dental",
        phone="(555) 234-5678",
        phone_raw="5552345678",
        address_line1="456 Tooth Avenue",
        address_line2="Medical Center, Suite 200",
        city="Springfield",
        state="IL",
        zip_code="62704",
        rating=4.8,
        review_count=150,
        trust_badge="Patient Choice Winner",
        hours=HoursSchedule(
            weekdays="Mon - Fri",
            weekday_hours="8:00 AM - 6:00 PM",
            weekend_day="Saturday",
            weekend_hours="9:00 AM - 2:00 PM",
            note="Emergency appointments available on Sundays",
        ),
        services=[
            ServiceItem(
                name="General Dentistry",
                description="Comprehensive oral health solutions including fillings, extractions, and preventative care for all ages.",
                icon="dentistry",
            ),
            ServiceItem(
                name="Dental Checkups",
                description="Regular dental examinations and professional cleanings to maintain your perfect smile.",
                icon="clinical_notes",
            ),
            ServiceItem(
                name="Cosmetic Dentistry",
                description="Enhance your natural beauty with advanced whitening, veneers, and aesthetic transformations.",
                icon="sentiment_very_satisfied",
            ),
        ],
        cta_headline="Ready for a brighter smile?",
        cta_subtext="Join over 1,000 satisfied patients. Book your appointment today.",
        cta_button_label="Call Now",
    )

    sample.to_json(output)
    print(f"Sample data written to: {output}")


def main():
    parser = argparse.ArgumentParser(
        description="Modular template composer for autowebdelivery"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # parse command
    parse_parser = subparsers.add_parser("parse", help="Parse all template families from stitch artifacts")
    parse_parser.set_defaults(func=cmd_parse)

    # compose command
    compose_parser = subparsers.add_parser("compose", help="Compose a page from family + data")
    compose_parser.add_argument("family", help="Template family name")
    compose_parser.add_argument("data", help="Path to business data JSON")
    compose_parser.add_argument("-o", "--output", help="Output directory")
    compose_parser.add_argument(
        "--variant",
        choices=["desktop", "mobile", "mobile_v2", "desktop_v2"],
        default="desktop",
        help="Page variant (default: desktop)",
    )
    compose_parser.add_argument(
        "--both",
        action="store_true",
        help="Generate both desktop and mobile variants",
    )
    compose_parser.add_argument(
        "--mixin",
        action="append",
        help="Mixin override: section=family (e.g. hero=warm-editorial)",
    )
    compose_parser.set_defaults(func=cmd_compose)

    # list command
    list_parser = subparsers.add_parser("list", help="List available families and sections")
    list_parser.set_defaults(func=cmd_list)

    # sample-data command
    sample_parser = subparsers.add_parser("sample-data", help="Generate sample business data JSON")
    sample_parser.add_argument("-o", "--output", help="Output file path")
    sample_parser.set_defaults(func=cmd_sample_data)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
