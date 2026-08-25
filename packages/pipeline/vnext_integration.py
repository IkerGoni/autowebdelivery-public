"""VNEXT-11 — vNext phase integration helpers.

Lightweight adapter functions that wire vNext modules into the pipeline runner
behind feature flags.  Each helper reads upstream artifacts from the run
directory, calls the corresponding vNext module, and writes output artifacts
back.  When a flag is disabled the helper is a no-op.

Flags are read from ``input_config["vnext_flags"]``.  When the key is absent
all flags default to ``False`` — fully backward-compatible.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from packages.pipeline.json_io import read_json, write_json

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Flag helpers
# ---------------------------------------------------------------------------

_VNEXT_FLAG_DEFAULTS: dict[str, bool] = {
    "use_business_profile_contract": False,
    "use_market_profile_contract": False,
    "use_brand_reconstruction_contract": False,
    "use_creative_spec": False,
    "use_stitch_compiler": False,
    "use_structured_evaluation_report": False,
    "use_sales_package_contract": False,
    "use_learning_record_contract": False,
    "use_competitor_intelligence": False,
    "use_patch_phase": False,
    "use_overpass_enrichment": False,
    "use_gmaps_enrichment": False,
    "use_social_enrichment": False,
    "use_image_fallback": False,
}


def get_vnext_flags(config: dict[str, Any]) -> dict[str, bool]:
    """Return a resolved dict of vnext flags from *config*.

    Missing keys default to ``False``.
    """
    raw = config.get("vnext_flags", {})
    return {k: raw.get(k, v) for k, v in _VNEXT_FLAG_DEFAULTS.items()}


# ---------------------------------------------------------------------------
# Directory layout helpers
# ---------------------------------------------------------------------------

def _runs(workspace: str, run_id: str) -> Path:
    return Path(workspace) / "runs" / run_id


def _read_selected_leads(workspace: str, run_id: str) -> list[dict[str, Any]]:
    """Read selected_for_preview.json; return [] on missing/corrupt."""
    path = _runs(workspace, run_id) / "04_briefs" / "selected_for_preview.json"
    if path.exists():
        try:
            return read_json(str(path))
        except Exception:
            pass
    return []


def _read_config(workspace: str, run_id: str) -> dict[str, Any]:
    """Read input_config.json for the run."""
    path = _runs(workspace, run_id) / "config" / "input_config.json"
    if path.exists():
        try:
            return read_json(str(path))
        except Exception:
            pass
    return {}


# ---------------------------------------------------------------------------
# Post-Phase 03: VNEXT-02 market profile per selected lead
# ---------------------------------------------------------------------------

def run_vnext_post_phase_03(
    run_id: str,
    workspace: str,
    selected_leads: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[str]:
    """Run VNEXT-02 market_profile generation if flag enabled.

    Returns list of written artifact paths.
    """
    flags = get_vnext_flags(config)
    if not flags.get("use_market_profile_contract"):
        return []

    from packages.intelligence.market_profile import (
        build_market_profile,
        write_market_profile,
    )

    output_dir = _runs(workspace, run_id) / "04_briefs"
    written: list[str] = []
    for lead in selected_leads:
        slug = lead.get("business_slug", "unknown")
        try:
            profile = build_market_profile(lead, config, run_id=run_id)
            path = write_market_profile(profile, str(output_dir), slug)
            written.append(path)
            logger.info("VNEXT-02: wrote market_profile for %s", slug)
        except Exception as exc:
            logger.warning("VNEXT-02: failed for %s: %s", slug, exc)
    return written


# ---------------------------------------------------------------------------
# Post-Phase 03: VNEXT-10 competitor intelligence (Phase 2 placeholder)
# ---------------------------------------------------------------------------


def run_vnext_post_phase_03_competitor_intel(
    run_id: str,
    workspace: str,
    selected_leads: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[str]:
    """Run VNEXT-10 competitor intelligence if flag enabled.

    Returns list of written artifact paths.
    """
    flags = get_vnext_flags(config)
    if not flags.get("use_competitor_intelligence"):
        return []

    from packages.intelligence.competitor_intelligence import (
        build_competitor_profile,
        write_competitor_profile,
    )

    output_dir = _runs(workspace, run_id) / "04_briefs"
    written: list[str] = []

    for lead in selected_leads:
        slug = lead.get("business_slug", "unknown")

        bp: dict[str, Any] = {}
        bp_path = output_dir / slug / "business_profile.json"
        if bp_path.exists():
            try:
                bp = read_json(str(bp_path))
            except Exception:
                pass

        category = lead.get("category") or bp.get("overview", {}).get("industry") or "Unknown"
        area = lead.get("area") or bp.get("location", {}).get("region") or "Unknown"

        try:
            profile = build_competitor_profile(
                category=category,
                area=area,
                config=config,
                run_id=run_id,
            )
            path = write_competitor_profile(profile, str(output_dir), slug)
            written.append(path)
            logger.info("VNEXT-10: wrote competitor_profile for %s", slug)
        except Exception as exc:
            logger.warning("VNEXT-10: failed for %s: %s", slug, exc)

    return written


# ---------------------------------------------------------------------------
# Post-Phase 03: VNEXT-13 Overpass enrichment (OSM tags enrichment for leads)
# ---------------------------------------------------------------------------


def run_vnext_post_phase_03_overpass_enrichment(
    run_id: str,
    workspace: str,
    selected_leads: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[str]:
    """Run VNEXT-13 Overpass enrichment if flag enabled.

    Uses the Overpass API to fetch OSM tags (opening_hours, amenities, etc.) for
    each lead based on business name and area. Enriches lead data with OSM-specific
    metadata without modifying the original discovery source behavior.

    Returns list of written artifact paths.
    """
    flags = get_vnext_flags(config)
    if not flags.get("use_overpass_enrichment"):
        return []

    from packages.discovery.overpass_fetcher import OverpassClient

    enrichment_dir = _runs(workspace, run_id) / "04_5_enrichment"
    written: list[str] = []

    client = OverpassClient()

    for lead in selected_leads:
        slug = lead.get("business_slug", "unknown")
        business_name = (
            lead.get("business_name")
            or lead.get("company_name")
            or lead.get("title")
            or slug
        )
        # Use area from config or lead
        area = config.get("area") or lead.get("area") or lead.get("city", "")
        if not area:
            continue

        # Infer niche from category for Overpass query
        category = lead.get("category", "")
        niche = category if category else config.get("niche", "")

        try:
            # Fetch OSM data for this business/category in area
            results = client.discover(niche, area, max_results=10)
            if results:
                from packages.discovery.overpass_fetcher import overpass_to_raw_place_dicts
                enriched_data = overpass_to_raw_place_dicts(results, niche, area)

                # Find matching business by name
                matching = [
                    r for r in enriched_data
                    if r.get("business_name", "").lower() == business_name.lower()
                ]

                # Write enrichment artifact
                out_dir = enrichment_dir / slug
                out_dir.mkdir(parents=True, exist_ok=True)

                # Build enrichment payload with OSM tags
                osm_tags = {}
                if matching:
                    osm_tags = {
                        "osm_type": matching[0].get("place_id", "").replace("osm_", "").split("_")[0] if matching[0].get("place_id") else "",
                        "osm_tags": {"category": matching[0].get("category", ""), "hours": matching[0].get("hours", "")},
                        "enrichment_source": "overpass",
                    }
                elif results:
                    # Use first result's tags as generic enrichment
                    osm_tags = {
                        "osm_tags": {"category": results[0].tags.get("amenity", "") or results[0].tags.get("shop", ""), "hours": results[0].tags.get("opening_hours", "")},
                        "enrichment_source": "overpass",
                    }

                artifact_path = str(out_dir / "overpass_enrichment.json")
                write_json(artifact_path, osm_tags)
                written.append(artifact_path)

                # Inject OSM tags into lead payload
                lead["osm_enrichment"] = osm_tags

                logger.info("VNEXT-13: enriched %s with OSM tags", slug)
        except Exception as exc:
            logger.warning("VNEXT-13: failed for %s: %s", slug, exc)

    return written


# ---------------------------------------------------------------------------
# Post-Phase 04.5: VNEXT-03 brand reconstruction + VNEXT-04 creative spec
# ---------------------------------------------------------------------------

def run_vnext_post_phase_04_5(
    run_id: str,
    workspace: str,
    selected_leads: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[str]:
    """Run VNEXT-03 brand_profile and VNEXT-04 creative_spec if flags enabled.

    Returns list of written artifact paths.
    """
    flags = get_vnext_flags(config)
    written: list[str] = []

    # We need business_profile (VNEXT-01) per lead if it exists, otherwise build on-the-fly
    from packages.intelligence.business_profile import (
        build_business_profile,
        write_business_profile,
    )

    briefs_dir = _runs(workspace, run_id) / "04_briefs"
    enrichment_dir = _runs(workspace, run_id) / "04_5_enrichment"

    for lead in selected_leads:
        slug = lead.get("business_slug", "unknown")

        # ── Read enrichment artifacts if they exist ──
        overpass_enrichment: dict[str, Any] | None = None
        gmaps_enrichment: dict[str, Any] | None = None
        social_enrichment: dict[str, Any] | None = None

        slug_dir = enrichment_dir / slug
        if slug_dir.exists():
            # Overpass enrichment (VNEXT-13)
            op_path = slug_dir / "overpass_enrichment.json"
            if op_path.exists():
                try:
                    overpass_enrichment = read_json(str(op_path))
                except Exception:
                    pass

            # Google Maps enrichment (VNEXT-14)
            gm_path = slug_dir / "gmaps_enrichment.json"
            if gm_path.exists():
                try:
                    gmaps_enrichment = read_json(str(gm_path))
                except Exception:
                    pass

            # Social enrichment (VNEXT-15)
            soc_path = slug_dir / "social_enrichment.json"
            if soc_path.exists():
                try:
                    social_enrichment = read_json(str(soc_path))
                except Exception:
                    pass

        # Build/write business_profile if the flag is on
        bp: dict[str, Any] = {}
        bp_path = briefs_dir / slug / "business_profile.json"
        if flags.get("use_business_profile_contract"):
            try:
                if bp_path.exists():
                    bp = read_json(str(bp_path))
                else:
                    bp = build_business_profile(
                        lead, config, run_id=run_id,
                        overpass_enrichment=overpass_enrichment,
                        gmaps_enrichment=gmaps_enrichment,
                        social_enrichment=social_enrichment,
                    )
                    write_business_profile(bp, str(briefs_dir), slug)
                    written.append(str(bp_path))
                    logger.info("VNEXT-01: wrote business_profile for %s", slug)
            except Exception as exc:
                logger.warning("VNEXT-01: failed for %s: %s", slug, exc)

        # VNEXT-02 market_profile — read only if flag enabled
        mp: dict[str, Any] = {}
        if flags.get("use_market_profile_contract"):
            mp_path = briefs_dir / slug / "market_profile.json"
            if mp_path.exists():
                try:
                    mp = read_json(str(mp_path))
                except Exception:
                    pass

        # VNEXT-03 brand reconstruction
        brand_profile: dict[str, Any] = {}
        if flags.get("use_brand_reconstruction_contract"):
            from packages.intelligence.brand_reconstruction import (
                build_brand_profile,
                write_brand_profile,
            )
            try:
                brand_profile = build_brand_profile(bp, mp, config, run_id=run_id)
                write_brand_profile(brand_profile, str(briefs_dir), slug)
                written.append(str(briefs_dir / slug / "brand_profile.json"))
                logger.info("VNEXT-03: wrote brand_profile for %s", slug)
            except Exception as exc:
                logger.warning("VNEXT-03: failed for %s: %s", slug, exc)

        # VNEXT-10 competitor_profile — read if available
        competitor_profile: dict[str, Any] | None = None
        if flags.get("use_competitor_intelligence"):
            cp_path = briefs_dir / slug / "competitor_profile.json"
            if cp_path.exists():
                try:
                    competitor_profile = read_json(str(cp_path))
                except Exception:
                    pass

        # VNEXT-04 creative spec
        if flags.get("use_creative_spec") and bp and brand_profile:
            from packages.creative.creative_spec_builder import (
                build_creative_spec,
                write_creative_spec,
            )
            try:
                spec = build_creative_spec(
                    bp, mp, brand_profile, config,
                    run_id=run_id,
                    competitor_profile=competitor_profile,
                )
                write_creative_spec(spec, str(briefs_dir), slug)
                written.append(str(briefs_dir / slug / "creative_spec.json"))
                logger.info("VNEXT-04: wrote creative_spec for %s", slug)
            except Exception as exc:
                logger.warning("VNEXT-04: failed for %s: %s", slug, exc)

    return written


# ---------------------------------------------------------------------------
# Post-Phase 04.5: VNEXT-14 Google Maps enrichment per lead
# ---------------------------------------------------------------------------


def run_vnext_post_phase_04_5_gmaps_enrichment(
    run_id: str,
    workspace: str,
    selected_leads: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[str]:
    """Run VNEXT-14 Google Maps enrichment if flag enabled.

    Extracts review text and extended GMB metadata from the Google Maps
    enricher and injects them into each lead's temporary payload as a
    ``gmaps_enrichment`` key.

    Returns list of written artifact paths.
    """
    flags = get_vnext_flags(config)
    if not flags.get("use_gmaps_enrichment"):
        return []

    from packages.enrichment.google_maps_enricher import (
        run_enrichment,
    )


    enrichment_dir = _runs(workspace, run_id) / "04_5_enrichment"
    written: list[str] = []

    for lead in selected_leads:
        slug = lead.get("business_slug", "unknown")
        business_name = (
            lead.get("business_name")
            or lead.get("company_name")
            or lead.get("title")
            or slug
        )
        # Try to get city/area from lead fields
        city = lead.get("city") or lead.get("area") or lead.get("location", "")

        try:
            # Read pre-fetched facts / maps page text if the enrichment_cache exists
            brief_dir = _runs(workspace, run_id) / "04_briefs" / slug
            facts_md = brief_dir / "FACTS.md"
            maps_url: str | None = None
            page_text: str | None = None

            if facts_md.exists():
                facts_text = facts_md.read_text(encoding="utf-8")
                # Try to extract maps_url from facts
                for line in facts_text.splitlines():
                    if line.lower().startswith("maps_url") or line.lower().startswith("- maps_url"):
                        parts = line.split(":", 1)
                        if len(parts) > 1:
                            maps_url = parts[1].strip()
                    if line.lower().startswith("city") or line.lower().startswith("- city"):
                        parts = line.split(":", 1)
                        if len(parts) > 1:
                            city = parts[1].strip()

            # Also check enrichment_cache for pre-extracted page content
            cache_dir = brief_dir / "enrichment_cache"
            if cache_dir.exists():
                page_text_path = cache_dir / "gmaps_page.txt"
                if page_text_path.exists():
                    page_text = page_text_path.read_text(encoding="utf-8")

            enrichment = run_enrichment(
                business_name=business_name,
                city=city,
                maps_url=maps_url,
                page_text=page_text,
            )

            # Write enrichment artifact
            slug.replace(" ", "_").replace("/", "_")  # sanitize
            out_dir = enrichment_dir / slug
            out_dir.mkdir(parents=True, exist_ok=True)
            artifact_path = str(out_dir / "gmaps_enrichment.json")
            write_json(artifact_path, enrichment.to_dict())
            written.append(artifact_path)

            # Build enrichment_sources.json for safety validation (per fact_safety_rules.md)
            now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            sources: list[dict[str, Any]] = []
            
            # Record source provenance for each enriched field
            if enrichment.source_url:
                sources.append({
                    "source_id": f"{slug}:gmaps_main",
                    "name": "Google Maps Business Profile",
                    "type": "google_maps_api",
                    "url": enrichment.source_url,
                    "accessed_at": now,
                    "reliability_score": 0.95,
                    "facts_sourced": ["rating", "review_count", "hours", "services"],
                })
            
            if enrichment.review_snippets:
                sources.append({
                    "source_id": f"{slug}:gmaps_reviews",
                    "name": "Google Maps Reviews",
                    "type": "public_directory",
                    "url": enrichment.source_url or f"https://www.google.com/maps/search/{business_name}",
                    "accessed_at": now,
                    "reliability_score": 0.90,
                    "facts_sourced": ["review_snippets"],
                })
            
            if sources:
                enrichment_sources = {
                    "schema_version": "1.0.0",
                    "run_id": run_id,
                    "business_slug": slug,
                    "sources": sources,
                    "created_at": now,
                    "updated_at": now,
                }
                sources_path = str(out_dir / "enrichment_sources.json")
                write_json(sources_path, enrichment_sources)
                written.append(sources_path)

            # Inject enrichment data into the lead payload
            lead["gmaps_enrichment"] = enrichment.to_dict()

            logger.info(
                "VNEXT-14: enriched %s (rating=%.1f, reviews=%d, snippets=%d)",
                slug,
                enrichment.rating,
                enrichment.review_count,
                len(enrichment.review_snippets),
            )
        except Exception as exc:
            logger.warning("VNEXT-14: failed for %s: %s", slug, exc)

    return written


# ---------------------------------------------------------------------------
# Post-Phase 04.5: VNEXT-15 Social scraper enrichment per lead
# ---------------------------------------------------------------------------


def run_vnext_post_phase_04_5_social_enrichment(
    run_id: str,
    workspace: str,
    selected_leads: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[str]:
    """Run VNEXT-15 social scraper enrichment if flag enabled.

    Extracts Facebook Open Graph metadata and Instagram profile data for
    each lead whose website_raw/website points to a social platform.
    Respects robots.txt and rate limiting (5 req/min).  Gracefully
    handles fetch failures — enrichment is best-effort.

    Returns list of written artifact paths.
    """
    flags = get_vnext_flags(config)
    if not flags.get("use_social_enrichment"):
        return []

    from packages.enrichment.social_scraper import (
        detect_social_platform,
        merge_social_data_into_enrichment,
        scrape_social_profile,
    )

    enrichment_dir = _runs(workspace, run_id) / "04_5_enrichment"
    written: list[str] = []

    for lead in selected_leads:
        slug = lead.get("business_slug", "unknown")
        # Try website_raw first, fall back to website
        url = (
            lead.get("website_raw")
            or lead.get("website")
            or ""
        )
        if not url:
            logger.debug("VNEXT-15: no URL for %s, skipping", slug)
            continue

        platform = detect_social_platform(url)
        if not platform:
            logger.debug("VNEXT-15: URL %s is not a known social platform, skipping", url)
            continue

        try:
            profile = scrape_social_profile(url, respect_robots=True)

            if profile is None:
                logger.info("VNEXT-15: no profile data for %s (%s)", slug, url)
                continue

            # Build enrichment payload
            enrichment_payload: dict[str, Any] = {
                "platform": platform,
                "username": profile.username,
                "profile_url": profile.profile_url,
                "about_text": profile.about_text,
                "follower_count": profile.follower_count,
                "following_count": profile.following_count,
                "post_count": profile.post_count,
                "is_verified": profile.is_verified,
                "business_category": profile.business_category,
                "photos": profile.photos,
                "contact_info": profile.contact_info,
                "enrichment_source": "social_scraper",
                "social_type": "facebook_og" if platform == "facebook" else "instagram_profile",
            }

            # Merge into lead's enrichment data if gmaps enrichment already exists
            existing = lead.get("gmaps_enrichment", {})
            if existing:
                merged = merge_social_data_into_enrichment(existing, profile)
                lead["gmaps_enrichment"] = merged
            else:
                # Attach social enrichment as its own key
                lead.setdefault("social_enrichment", {})
                lead["social_enrichment"] = enrichment_payload

            # Write artifact
            out_dir = enrichment_dir / slug
            out_dir.mkdir(parents=True, exist_ok=True)
            artifact_path = str(out_dir / "social_enrichment.json")
            write_json(artifact_path, enrichment_payload)
            written.append(artifact_path)

            logger.info(
                "VNEXT-15: enriched %s via %s (platform=%s, followers=%s)",
                slug, url, platform, profile.follower_count,
            )
        except Exception as exc:
            logger.warning("VNEXT-15: failed for %s (%s): %s", slug, url, exc)

    return written


# ---------------------------------------------------------------------------
# Post-Phase 04.5: VNEXT-17 Image generation fallback
# ---------------------------------------------------------------------------


def run_vnext_post_phase_04_5_image_fallback(
    run_id: str,
    workspace: str,
    selected_leads: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[str]:
    """Run VNEXT-17 image fallback generation if flag enabled.

    After Google Maps and social enrichment have run, checks each lead for
    sufficient real photos.  When fewer than ``min_images`` are available,
    generates descriptive prompts for AI image generation and attaches them
    as ``fallback_image_prompts`` on the lead payload.  Also writes a
    ``fallback_image_prompts.json`` artifact per lead.

    The prompts can be consumed by any image generation tool (DALL-E,
    Stable Diffusion, Midjourney, etc.) — the module is decoupled from the
    specific generator.

    Returns list of written artifact paths.
    """
    flags = get_vnext_flags(config)
    if not flags.get("use_image_fallback"):
        return []

    from packages.enrichment.image_fallback import (
        generate_image_prompt,
        has_sufficient_images,
    )

    enrichment_dir = _runs(workspace, run_id) / "04_5_enrichment"
    written: list[str] = []

    for lead in selected_leads:
        slug = lead.get("business_slug", "unknown")

        # Collect enrichment payload from gmaps + social-media steps
        enrichment_payload: dict[str, Any] = {
            "business_name": lead.get("business_name") or lead.get("company_name") or slug,
            "niche": lead.get("category") or config.get("niche", ""),
            "city": lead.get("city") or lead.get("area") or "",
            "state": lead.get("state", ""),
        }

        # Merge in photos collected by earlier enrichment steps
        gmaps = lead.get("gmaps_enrichment", {})
        social = lead.get("social_enrichment", {})

        existing_photos: list[str] = []
        if isinstance(gmaps, dict):
            existing_photos.extend(gmaps.get("photos", []))
        if isinstance(social, dict):
            existing_photos.extend(social.get("photos", []))
        enrichment_payload["photos"] = existing_photos

        # Check if fallback is needed
        if has_sufficient_images(enrichment_payload, min_images=3):
            logger.debug("VNEXT-17: %s has sufficient images, skipping", slug)
            continue

        if not enrichment_payload["city"]:
            logger.debug("VNEXT-17: %s has no city, skipping fallback", slug)
            continue

        try:
            # Generate fallback prompts / placeholders
            output_dir = enrichment_dir / slug
            output_dir.mkdir(parents=True, exist_ok=True)

            # generate_fallback_images with no image_generator -> logs prompts
            # and returns empty list.  We collect the prompts explicitly.
            prompts = [
                generate_image_prompt(
                    business_name=enrichment_payload["business_name"],
                    niche=enrichment_payload["niche"],
                    city=enrichment_payload["city"],
                    state=enrichment_payload["state"],
                    style=style,
                )
                for style in ["professional", "modern", "clean"][:3]
            ]

            fallback_data = {
                "business_slug": slug,
                "has_real_photos": len(existing_photos),
                "fallback_prompts": prompts,
                "prompt_count": len(prompts),
            }

            artifact_path = str(output_dir / "fallback_image_prompts.json")
            write_json(artifact_path, fallback_data)
            written.append(artifact_path)

            # Attach to lead payload so downstream phases can consume
            lead.setdefault("fallback_image_prompts", prompts)

            logger.info(
                "VNEXT-17: generated %d fallback prompts for %s",
                len(prompts), slug,
            )
        except Exception as exc:
            logger.warning("VNEXT-17: failed for %s: %s", slug, exc)

    return written


# ---------------------------------------------------------------------------
# Post-Phase 06: VNEXT-06 structured evaluation
# ---------------------------------------------------------------------------


def run_vnext_post_phase_06(
    run_id: str,
    workspace: str,
    selected_leads: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[str]:
    """Run VNEXT-06 structured evaluation if flag enabled.

    Returns list of written artifact paths.
    """
    flags = get_vnext_flags(config)
    if not flags.get("use_structured_evaluation_report"):
        return []

    from packages.evaluation.website_evaluator import (
        evaluate_website,
        write_evaluation_report,
    )

    sites_dir = _runs(workspace, run_id) / "05_sites"
    written: list[str] = []

    for lead in selected_leads:
        slug = lead.get("business_slug", "unknown")
        html_path = sites_dir / slug / "site" / "index.html"
        if not html_path.exists():
            logger.warning("VNEXT-06: no site HTML for %s, skipping", slug)
            continue

        try:
            html_content = html_path.read_text(encoding="utf-8")

            # Read creative_spec ONLY if use_creative_spec flag is enabled
            creative_spec = None
            if flags.get("use_creative_spec"):
                cs_path = _runs(workspace, run_id) / "04_briefs" / slug / "creative_spec.json"
                if cs_path.exists():
                    try:
                        creative_spec = read_json(str(cs_path))
                    except Exception:
                        pass

            report = evaluate_website(
                html_content,
                creative_spec=creative_spec,
                config=config,
                run_id=run_id,
                business_slug=slug,
            )
            eval_dir = sites_dir / slug
            write_evaluation_report(report, str(eval_dir))
            written.append(str(eval_dir / "evaluation_report.json"))
            logger.info("VNEXT-06: wrote evaluation_report for %s", slug)
        except Exception as exc:
            logger.warning("VNEXT-06: failed for %s: %s", slug, exc)

    return written


# ---------------------------------------------------------------------------
# Post-Phase 06: VNEXT-07 patch plan (Phase 2 placeholder)
# ---------------------------------------------------------------------------


def run_vnext_post_phase_06_patch_plan(
    run_id: str,
    workspace: str,
    selected_leads: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[str]:
    """Run VNEXT-07 patch plan if flag enabled.

    When patches are applied, also re-evaluates the patched HTML
    (single evaluate-patch-evaluate cycle — no infinite loop) and logs the
    score delta.  Returns list of written artifact paths.
    """
    flags = get_vnext_flags(config)
    if not flags.get("use_patch_phase"):
        return []

    from packages.evaluation.website_evaluator import (
        evaluate_website,
        write_evaluation_report,
    )
    from packages.patching.html_patch_engine import apply_html_patches
    from packages.patching.patch_plan import build_patch_plan, write_patch_plan

    sites_dir = _runs(workspace, run_id) / "05_sites"
    briefs_dir = _runs(workspace, run_id) / "04_briefs"
    written: list[str] = []

    for lead in selected_leads:
        slug = lead.get("business_slug", "unknown")
        html_path = sites_dir / slug / "site" / "index.html"
        eval_report_path = sites_dir / slug / "evaluation_report.json"
        cs_path = briefs_dir / slug / "creative_spec.json"

        if not html_path.exists():
            logger.warning("VNEXT-07: no site HTML for %s, skipping", slug)
            continue

        try:
            html_content = html_path.read_text(encoding="utf-8")

            # Read evaluation report (optional — build_patch_plan uses it)
            evaluation_report: dict[str, Any] | None = None
            if eval_report_path.exists():
                try:
                    evaluation_report = read_json(str(eval_report_path))
                except Exception:
                    pass

            # Read creative_spec ONLY if use_creative_spec flag is ON
            creative_spec: dict[str, Any] | None = None
            if flags.get("use_creative_spec") and cs_path.exists():
                try:
                    creative_spec = read_json(str(cs_path))
                except Exception:
                    pass

            # Build patch plan
            # Inject site_html into evaluation_report for patch planner to inspect
            eval_report_for_plan: dict[str, Any] = dict(evaluation_report or {})
            if html_content:
                eval_report_for_plan["_site_html"] = html_content

            plan = build_patch_plan(
                eval_report_for_plan,
                creative_spec=creative_spec,
                run_id=run_id,
                business_slug=slug,
            )
            plan_path = write_patch_plan(plan, str(sites_dir), slug)
            written.append(plan_path)

            patches = plan.get("patches", [])
            if not patches:
                logger.info("VNEXT-07: no patches for %s", slug)
                continue

            # Apply patches to HTML
            patched_html = apply_html_patches(html_content, patches)
            patched_path = sites_dir / slug / "site" / "index_patched.html"
            patched_path.parent.mkdir(parents=True, exist_ok=True)
            patched_path.write_text(patched_html, encoding="utf-8")
            written.append(str(patched_path))
            logger.info(
                "VNEXT-07: applied %d patches for %s",
                len(patches), slug,
            )

            # Task 2.4: Re-evaluate patched HTML (single cycle only)
            pre_score: float | None = None
            if evaluation_report is not None:
                pre_score = evaluation_report.get("overall_score")

            re_eval = evaluate_website(
                patched_html,
                creative_spec=creative_spec,
                config=config,
                run_id=run_id,
                business_slug=slug,
            )

            post_score: float = re_eval.get("overall_score", 0)
            delta: float = (post_score - pre_score) if pre_score is not None else 0

            # Write re-evaluation report
            re_eval_path = write_evaluation_report(
                re_eval, str(sites_dir / slug / "post_patch_eval"),
            )
            written.append(str(re_eval_path))

            # Store delta in metadata sidecar
            meta: dict[str, Any] = {
                "business_slug": slug,
                "pre_patch_eval": str(eval_report_path),
                "post_patch_eval": str(re_eval_path),
                "pre_score": pre_score,
                "post_score": post_score,
                "delta": delta,
                "num_patches": len(patches),
            }
            meta_path = sites_dir / slug / "patch_eval_meta.json"
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            import json
            meta_path.write_text(
                json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            written.append(str(meta_path))

            if delta > 0:
                logger.info(
                    "VNEXT-07: score improved by +%.1f for %s",
                    delta, slug,
                )
            elif delta < 0:
                logger.warning(
                    "VNEXT-07: score dropped by %.1f for %s",
                    delta, slug,
                )
            else:
                logger.info("VNEXT-07: score unchanged for %s", slug)

        except Exception as exc:
            logger.warning("VNEXT-07: failed for %s: %s", slug, exc)

    return written


# ---------------------------------------------------------------------------
# Post-Phase 08: VNEXT-08 sales package
# ---------------------------------------------------------------------------

def run_vnext_post_phase_08(
    run_id: str,
    workspace: str,
    selected_leads: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[str]:
    """Run VNEXT-08 sales_package generation if flag enabled.

    Returns list of written artifact paths.
    """
    flags = get_vnext_flags(config)
    if not flags.get("use_sales_package_contract"):
        return []

    from packages.sales.sales_package import build_sales_package, write_sales_package

    briefs_dir = _runs(workspace, run_id) / "04_briefs"
    sites_dir = _runs(workspace, run_id) / "05_sites"
    deploy_dir = _runs(workspace, run_id) / "07_deployments"
    output_dir = _runs(workspace, run_id) / "08_outreach"
    written: list[str] = []

    for lead in selected_leads:
        slug = lead.get("business_slug", "unknown")

        # Collect upstream artifacts (all optional)
        bp: dict | None = None
        bp_path = briefs_dir / slug / "business_profile.json"
        if bp_path.exists():
            try:
                bp = read_json(str(bp_path))
            except Exception:
                pass

        mp: dict | None = None
        mp_path = briefs_dir / slug / "market_profile.json"
        if mp_path.exists():
            try:
                mp = read_json(str(mp_path))
            except Exception:
                pass

        cs: dict | None = None
        cs_path = briefs_dir / slug / "creative_spec.json"
        if cs_path.exists():
            try:
                cs = read_json(str(cs_path))
            except Exception:
                pass

        er: dict | None = None
        er_path = sites_dir / slug / "evaluation_report.json"
        if er_path.exists():
            try:
                er = read_json(str(er_path))
            except Exception:
                pass

        # Get preview_url from deployment manifest
        preview_url = ""
        dep_record = deploy_dir / slug / "deployment_record.json"
        if dep_record.exists():
            try:
                dep = read_json(str(dep_record))
                preview_url = dep.get("preview_url", "")
            except Exception:
                pass

        # Get screenshots info
        screenshots: dict | None = None
        render_path = sites_dir / slug / "render_capture.json"
        if render_path.exists():
            try:
                screenshots = read_json(str(render_path))
            except Exception:
                pass

        try:
            pkg = build_sales_package(
                business_profile=bp or {},
                market_profile=mp,
                creative_spec=cs,
                evaluation_report=er,
                config=config,
                run_id=run_id,
                preview_url=preview_url,
                screenshots=screenshots,
            )
            path = write_sales_package(pkg, str(output_dir), slug)
            written.append(path)
            logger.info("VNEXT-08: wrote sales_package for %s", slug)
        except Exception as exc:
            logger.warning("VNEXT-08: failed for %s: %s", slug, exc)

    return written


# ---------------------------------------------------------------------------
# Post-Phase 09: VNEXT-09 learning record
# ---------------------------------------------------------------------------

def run_vnext_post_phase_09(
    run_id: str,
    workspace: str,
    selected_leads: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[str]:
    """Run VNEXT-09 learning_record generation if flag enabled.

    Returns list of written artifact paths.
    """
    flags = get_vnext_flags(config)
    if not flags.get("use_learning_record_contract"):
        return []

    from packages.learning.learning_record import build_learning_record, write_learning_record

    briefs_dir = _runs(workspace, run_id) / "04_briefs"
    sites_dir = _runs(workspace, run_id) / "05_sites"
    outreach_dir = _runs(workspace, run_id) / "08_outreach"
    output_dir = _runs(workspace, run_id) / "09_review"
    written: list[str] = []

    for lead in selected_leads:
        slug = lead.get("business_slug", "unknown")

        # Collect upstream artifacts (all optional)
        bp: dict | None = None
        bp_path = briefs_dir / slug / "business_profile.json"
        if bp_path.exists():
            try:
                bp = read_json(str(bp_path))
            except Exception:
                pass

        mp: dict | None = None
        mp_path = briefs_dir / slug / "market_profile.json"
        if mp_path.exists():
            try:
                mp = read_json(str(mp_path))
            except Exception:
                pass

        cs: dict | None = None
        cs_path = briefs_dir / slug / "creative_spec.json"
        if cs_path.exists():
            try:
                cs = read_json(str(cs_path))
            except Exception:
                pass

        er: dict | None = None
        er_path = sites_dir / slug / "evaluation_report.json"
        if er_path.exists():
            try:
                er = read_json(str(er_path))
            except Exception:
                pass

        sp: dict | None = None
        sp_path = outreach_dir / slug / "sales_package.json"
        if sp_path.exists():
            try:
                sp = read_json(str(sp_path))
            except Exception:
                pass

        prompt_contract: dict | None = None
        pc_path = sites_dir / slug / "stitch_prompt_contract.json"
        if pc_path.exists():
            try:
                prompt_contract = read_json(str(pc_path))
            except Exception:
                pass

        try:
            record = build_learning_record(
                business_profile=bp,
                market_profile=mp,
                creative_spec=cs,
                evaluation_report=er,
                sales_package=sp,
                prompt_contract=prompt_contract,
                config=config,
                run_id=run_id,
                business_slug=slug,
            )
            path = write_learning_record(record, str(output_dir), slug)
            written.append(path)
            logger.info("VNEXT-09: wrote learning_record for %s", slug)
        except Exception as exc:
            logger.warning("VNEXT-09: failed for %s: %s", slug, exc)

    return written
