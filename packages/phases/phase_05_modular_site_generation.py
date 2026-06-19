"""Phase 05 — modular template site generation.

Generates preview sites using the modular template system with production-quality output.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from packages.shared.provenance import _safe_str

logger = logging.getLogger(__name__)

PHASE_NAME = "phase_05_modular_site_generation"
PHASE_SLUG = "05_sites"
PHASE_04_SLUG = "04_briefs"
PHASE_04_5_SLUG = "04_5_enrichment"

try:
    from pipeline.json_io import read_json, write_json
    from pipeline.result_envelope import ResultEnvelope
except ModuleNotFoundError:  # pragma: no cover - CLI fallback
    from packages.pipeline.json_io import read_json, write_json
    from packages.pipeline.result_envelope import ResultEnvelope

try:
    from templates.modular.composer import TemplateComposer
    from templates.modular.models import BusinessData, ServiceItem, HoursSchedule
    from generation.html_sanitizer import sanitize_html, write_sanitizer_report, write_sanitized_html
    from phases.phase_05_preview_site_generation import write_screenshot_png
except ModuleNotFoundError:  # pragma: no cover
    from packages.templates.modular.composer import TemplateComposer
    from packages.templates.modular.models import BusinessData, ServiceItem, HoursSchedule
    from packages.generation.html_sanitizer import sanitize_html, write_sanitizer_report, write_sanitized_html
    from packages.phases.phase_05_preview_site_generation import write_screenshot_png


def _parse_facts_md(path: Path) -> dict[str, str]:
    """Parse FACTS.md into dict."""
    facts: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("- ") or ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        facts[key.strip()] = value.strip()
    return facts


def _map_category_to_family(category: str, niche: str) -> str:
    """Map business category/niche to template family."""
    category_lower = category.lower()
    niche_lower = niche.lower()
    
    # Clinical/medical niches
    if any(term in category_lower or term in niche_lower for term in ["dental", "dentist", "clinic", "medical", "doctor", "health"]):
        return "clinical-trust"
    
    # Beauty/spa niches
    if any(term in category_lower or term in niche_lower for term in ["beauty", "salon", "spa", "hair", "nail", "massage"]):
        return "warm-editorial"
    
    # Automotive/mechanical niches
    if any(term in category_lower or term in niche_lower for term in ["auto", "car", "mechanic", "repair", "garage", "detailing"]):
        return "industrial-reliable"
    
    # Cleaning/home services
    if any(term in category_lower or term in niche_lower for term in ["clean", "maid", "janitorial", "landscap", "lawn", "pool", "hvac"]):
        return "fresh-utility"
    
    # Default fallback
    return "clinical-trust"


def _parse_hours(hours_str: str) -> HoursSchedule:
    """Parse hours string into HoursSchedule object."""
    if not hours_str or hours_str.lower() in ["not available", "n/a", ""]:
        return HoursSchedule(
            weekdays="Mon - Fri",
            weekday_hours="9:00 AM - 5:00 PM",
            weekend_day="Weekend",
            weekend_hours="Closed"
        )
    
    # Simple parsing - can be enhanced
    return HoursSchedule(
        weekdays="Mon - Fri",
        weekday_hours=hours_str,
        weekend_day="Weekend",
        weekend_hours="By Appointment"
    )


def _extract_services_from_enrichment(enrichment_path: Path, business_name: str, category: str) -> list[ServiceItem]:
    """Extract services from enrichment data."""
    services = []
    
    if not enrichment_path.exists():
        # Return generic services based on category
        return _generate_generic_services(category)
    
    try:
        enrichment = read_json(str(enrichment_path))
        
        # Try to extract from enrichment
        if "services" in enrichment and enrichment["services"]:
            for svc in enrichment["services"][:3]:  # Max 3 services
                if isinstance(svc, dict):
                    services.append(ServiceItem(
                        name=svc.get("name", "Service"),
                        description=svc.get("description", "Professional service"),
                        icon=svc.get("icon", "star")
                    ))
                elif isinstance(svc, str):
                    services.append(ServiceItem(
                        name=svc,
                        description=f"Professional {svc.lower()} services",
                        icon="star"
                    ))
        
        # If no services extracted, return generic
        if not services:
            return _generate_generic_services(category)
            
        return services
        
    except Exception as e:
        logger.warning(f"Could not extract services from enrichment: {e}")
        return _generate_generic_services(category)


def _generate_generic_services(category: str) -> list[ServiceItem]:
    """Generate generic services based on category."""
    category_lower = category.lower()
    
    if "dental" in category_lower or "dentist" in category_lower:
        return [
            ServiceItem("General Dentistry", "Comprehensive oral health care including exams, cleanings, and preventative treatments.", "dentistry"),
            ServiceItem("Cosmetic Dentistry", "Enhance your smile with professional whitening, veneers, and aesthetic procedures.", "sentiment_very_satisfied"),
            ServiceItem("Emergency Care", "Same-day appointments available for dental emergencies and urgent care needs.", "emergency"),
        ]
    elif "beauty" in category_lower or "salon" in category_lower or "hair" in category_lower:
        return [
            ServiceItem("Hair Styling", "Expert cuts, coloring, and styling for all hair types and occasions.", "content_cut"),
            ServiceItem("Beauty Treatments", "Professional treatments including facials, waxing, and makeup services.", "face_retouching_natural"),
            ServiceItem("Special Occasions", "Bridal packages, event styling, and personalized beauty consultations.", "celebration"),
        ]
    elif "auto" in category_lower or "mechanic" in category_lower or "detailing" in category_lower:
        return [
            ServiceItem("Maintenance & Repair", "Complete automotive repair services including diagnostics and preventative maintenance.", "build"),
            ServiceItem("Detailing Services", "Professional interior and exterior detailing to restore your vehicle's appearance.", "local_car_wash"),
            ServiceItem("Specialized Services", "Advanced services including paint correction, ceramic coating, and custom work.", "verified"),
        ]
    elif "clean" in category_lower or "maid" in category_lower:
        return [
            ServiceItem("Residential Cleaning", "Thorough home cleaning services including deep cleaning and regular maintenance.", "home"),
            ServiceItem("Commercial Cleaning", "Professional office and commercial space cleaning with flexible scheduling.", "domain"),
            ServiceItem("Specialized Services", "Move-in/out cleaning, post-construction cleanup, and custom cleaning solutions.", "cleaning_services"),
        ]
    else:
        # Generic fallback
        return [
            ServiceItem("Professional Services", f"Expert {category} services tailored to your needs.", "star"),
            ServiceItem("Quality Workmanship", "Experienced team committed to delivering exceptional results.", "verified"),
            ServiceItem("Customer Satisfaction", "Dedicated to exceeding expectations with every project.", "thumb_up"),
        ]


def _build_business_data_from_facts(
    facts: dict[str, str],
    enrichment_path: Path,
    production_mode: bool = False
) -> BusinessData:
    """Build BusinessData object from FACTS.md and enrichment data."""
    
    business_name = _safe_str(facts.get("business_name", "Local Business"))
    category = _safe_str(facts.get("category", "Business"))
    niche = _safe_str(facts.get("niche", category))
    phone = _safe_str(facts.get("phone", "(555) 000-0000"))
    address = _safe_str(facts.get("address", "123 Main Street, City, ST 12345"))
    
    # Parse address components
    address_parts = [p.strip() for p in address.split(",")]
    address_line1 = address_parts[0] if len(address_parts) > 0 else "123 Main St"
    city = address_parts[1] if len(address_parts) > 1 else "City"
    state_zip = address_parts[2] if len(address_parts) > 2 else "ST 12345"
    state = state_zip.split()[0] if state_zip else "ST"
    zip_code = state_zip.split()[-1] if state_zip and len(state_zip.split()) > 1 else "12345"
    
    # Extract rating and reviews
    try:
        rating = float(facts.get("rating", "4.5"))
    except (ValueError, TypeError):
        rating = 4.5
    
    try:
        review_count = int(facts.get("review_count", "50"))
    except (ValueError, TypeError):
        review_count = 50
    
    # Parse hours
    hours_str = _safe_str(facts.get("hours", ""))
    hours = _parse_hours(hours_str)
    
    # Extract services
    services = _extract_services_from_enrichment(enrichment_path, business_name, category)
    
    # Build tagline
    tagline = f"Professional {category} services in {city}"
    
    # Production mode adjustments
    if production_mode:
        # Remove watermarks, test markers
        tagline = f"Your trusted {category.lower()} partner"
    
    return BusinessData(
        name=business_name,
        tagline=tagline,
        niche=niche.lower(),
        phone=phone,
        phone_raw="".join(ch for ch in phone if ch.isdigit()),
        address_line1=address_line1,
        address_line2="",
        city=city,
        state=state,
        zip_code=zip_code,
        rating=rating,
        review_count=review_count,
        trust_badge=f"{rating:.1f} Star Rated" if rating >= 4.0 else "Trusted Provider",
        hours=hours,
        services=services,
        cta_headline="Ready to get started?",
        cta_subtext=f"Contact {business_name} today to schedule your appointment.",
        cta_button_label="Call Now",
        cta_secondary_label="Get Directions",
        hero_description=tagline,
        coverage_area=f"{city}, {state}",
    )


def run_modular_phase_05(
    run_id: str,
    workspace: str,
    *,
    production_mode: bool = False,
    variant: str = "desktop",
) -> dict[str, Any]:
    """Run Phase 05 with modular template generation.
    
    Args:
        run_id: Pipeline run ID
        workspace: Workspace directory
        production_mode: If True, removes watermarks/test markers
        variant: Template variant (desktop, mobile, desktop_v2, mobile_v2)
        
    Returns:
        ResultEnvelope dictionary
    """
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    workspace_path = Path(workspace)
    run_path = workspace_path / "runs" / run_id
    briefs_path = run_path / PHASE_04_SLUG
    enrichment_dir = run_path / PHASE_04_5_SLUG
    output_dir = run_path / PHASE_SLUG
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Running modular Phase 05 for run_id={run_id}, production_mode={production_mode}")
    
    # Find all business brief directories
    if not briefs_path.exists():
        return ResultEnvelope.failed(
            phase=PHASE_NAME,
            run_id=run_id,
            errors=["Phase 04 briefs directory not found"]
        ).to_dict()
    
    business_dirs = [d for d in briefs_path.iterdir() if d.is_dir()]
    
    if not business_dirs:
        return ResultEnvelope.failed(
            phase=PHASE_NAME,
            run_id=run_id,
            errors=["No business briefs found"]
        ).to_dict()
    
    composer = TemplateComposer()
    sites_generated = []
    errors = []
    
    for biz_dir in business_dirs:
        business_slug = biz_dir.name
        facts_path = biz_dir / "FACTS.md"
        
        if not facts_path.exists():
            logger.warning(f"Skipping {business_slug} - no FACTS.md")
            errors.append(f"{business_slug}: FACTS.md not found")
            continue
        
        logger.info(f"Generating site for {business_slug}...")
        
        try:
            # Parse FACTS.md
            facts = _parse_facts_md(facts_path)
            
            # Determine template family
            category = _safe_str(facts.get("category", "business"))
            niche = _safe_str(facts.get("niche", category))
            family = _map_category_to_family(category, niche)
            
            logger.info(f"  Using template family: {family}")
            
            # Load enrichment data
            enrichment_path = enrichment_dir / business_slug / "enrichment.json"
            
            # Build business data
            business_data = _build_business_data_from_facts(
                facts,
                enrichment_path,
                production_mode=production_mode
            )
            
            # Compose HTML
            html = composer.compose(family, business_data, variant=variant)
            
            # Sanitize HTML
            sanitized = sanitize_html(html)
            
            # Create output directory for this business
            site_dir = output_dir / business_slug
            site_dir.mkdir(parents=True, exist_ok=True)
            
            # Write sanitizer report
            write_sanitizer_report(sanitized, site_dir)
            
            # Write sanitized HTML
            write_sanitized_html(sanitized, site_dir / "index.html")
            
            # Write original unsanitized HTML for comparison
            (site_dir / "index_unsanitized.html").write_text(html, encoding="utf-8")
            
            # Write build status
            build_status = {
                "phase": PHASE_NAME,
                "run_id": run_id,
                "business_slug": business_slug,
                "template_family": family,
                "variant": variant,
                "production_mode": production_mode,
                "generation_mode": "modular",
                "sanitizer_warnings": len(sanitized.findings),
                "sanitizer_hard_block": sanitized.hard_block,
            }
            write_json(str(site_dir / "build_status.json"), build_status)
            
            # Write synthetic screenshot placeholders (desktop + mobile)
            write_screenshot_png(
                site_dir / "screenshot_desktop.png",
                width=1280,
                height=800,
                business_name=business_data.name
            )
            write_screenshot_png(
                site_dir / "screenshot_mobile.png",
                width=390,
                height=844,
                business_name=business_data.name
            )
            
            sites_generated.append(business_slug)
            logger.info(f"  ✓ Generated site for {business_slug}")
            
        except Exception as e:
            logger.error(f"Failed to generate site for {business_slug}: {e}")
            errors.append(f"{business_slug}: {e}")
            continue
    
    if not sites_generated:
        return ResultEnvelope.failed(
            phase=PHASE_NAME,
            run_id=run_id,
            errors=errors or ["No sites generated"]
        ).to_dict()
    
    logger.info(f"Generated {len(sites_generated)} sites successfully")
    
    return ResultEnvelope.done(
        phase=PHASE_NAME,
        run_id=run_id,
        decisions=[
            f"Generated {len(sites_generated)} modular template sites",
            f"Template families used: {family}",
            f"Production mode: {production_mode}",
            f"Sites: {', '.join(sites_generated)}"
        ]
    ).to_dict()
