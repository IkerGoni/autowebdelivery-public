"""Image Generation Fallback - Generate placeholder images when real photos unavailable.

Integrates with image generation tools to create contextual placeholder images
based on business niche and local context.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.shared.ssrf_validator import is_safe_url

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ImageGenerationRequest:
    """Request for generating a placeholder image."""
    
    business_name: str
    niche: str
    city: str
    state: str = ""
    style: str = "professional"  # professional, modern, clean, warm
    aspect_ratio: str = "16:9"  # 16:9, 4:3, 1:1
    
    def to_prompt(self) -> str:
        """Convert request to image generation prompt."""
        # Build descriptive prompt
        location_context = f"{self.city}, {self.state}" if self.state else self.city
        
        prompt_parts = [
            f"Professional business photo for {self.niche} in {location_context}.",
            f"Style: {self.style}, clean, high-quality.",
            "No text, no logos, no people.",
            "Photorealistic, well-lit, modern aesthetic.",
        ]
        
        # Add niche-specific details
        niche_lower = self.niche.lower()
        if "detail" in niche_lower or "car wash" in niche_lower:
            prompt_parts.append("Show clean vehicle exterior, water droplets, professional equipment.")
        elif "restaurant" in niche_lower or "food" in niche_lower:
            prompt_parts.append("Show appetizing food presentation, clean kitchen or dining area.")
        elif "salon" in niche_lower or "barber" in niche_lower:
            prompt_parts.append("Show modern salon interior, styling chairs, professional equipment.")
        elif "landscap" in niche_lower or "lawn" in niche_lower:
            prompt_parts.append("Show manicured lawn, landscaping tools, outdoor greenery.")
        elif "plumb" in niche_lower:
            prompt_parts.append("Show professional plumbing tools, clean pipes, organized workspace.")
        elif "electrical" in niche_lower or "electric" in niche_lower:
            prompt_parts.append("Show electrical panels, wiring, professional tools, safety equipment.")
        elif "hvac" in niche_lower:
            prompt_parts.append("Show HVAC unit, air conditioning, climate control equipment.")
        elif "paint" in niche_lower:
            prompt_parts.append("Show paint samples, brushes, freshly painted walls, color swatches.")
        elif "roofing" in niche_lower or "roof" in niche_lower:
            prompt_parts.append("Show roof shingles, roofing materials, professional equipment.")
        elif "clean" in niche_lower:
            prompt_parts.append("Show cleaning supplies, spotless surfaces, professional equipment.")
        else:
            prompt_parts.append("Show professional business environment, organized workspace.")
        
        return " ".join(prompt_parts)
    
    def get_cache_key(self) -> str:
        """Generate cache key for this request."""
        key_string = f"{self.business_name}|{self.niche}|{self.city}|{self.style}|{self.aspect_ratio}"
        return hashlib.md5(key_string.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Image availability checker
# ---------------------------------------------------------------------------

def has_sufficient_images(enrichment_data: dict[str, Any], min_images: int = 3) -> bool:
    """Check if enrichment data has sufficient real images."""
    photos = enrichment_data.get("photos", [])
    
    # Filter out invalid/placeholder URLs
    valid_photos = [
        p for p in photos
        if p and isinstance(p, str) and p.startswith("http")
    ]
    
    return len(valid_photos) >= min_images


def get_image_urls_from_enrichment(enrichment_data: dict[str, Any]) -> list[str]:
    """Extract valid image URLs from enrichment data.

    R0-03 (U-14): these URLs originate from scraped pages and land in run
    artifacts consumed by fetchers and the browser. Each URL must pass the
    SSRF guard (public addresses only) before being handed on.
    """
    photos = enrichment_data.get("photos", [])

    valid_urls = []
    for url in photos:
        if url and isinstance(url, str) and url.startswith("http"):
            # Skip known placeholder patterns
            if any(skip in url.lower() for skip in [
                "placeholder", "dummy", "example.com", "localhost"
            ]):
                continue
            if not is_safe_url(url):
                logger.warning("Dropped image URL failing SSRF guard: %s", url)
                continue
            valid_urls.append(url)

    return valid_urls


# ---------------------------------------------------------------------------
# Prompt generation
# ---------------------------------------------------------------------------

def generate_image_prompt(
    business_name: str,
    niche: str,
    city: str,
    state: str = "",
    style: str = "professional"
) -> str:
    """Generate descriptive prompt for image generation.
    
    Args:
        business_name: Name of the business
        niche: Business niche/category
        city: City location
        state: State (optional)
        style: Image style (professional, modern, clean, warm)
    
    Returns:
        Detailed prompt string for image generation
    """
    request = ImageGenerationRequest(
        business_name=business_name,
        niche=niche,
        city=city,
        state=state,
        style=style
    )
    
    return request.to_prompt()


# ---------------------------------------------------------------------------
# Fallback image generation integration
# ---------------------------------------------------------------------------

def generate_fallback_images(
    enrichment_data: dict[str, Any],
    output_dir: str | Path,
    image_generator: Any = None,
    max_images: int = 3
) -> list[str]:
    """Generate fallback images when real photos are unavailable.
    
    Args:
        enrichment_data: Business enrichment data
        output_dir: Directory to save generated images
        image_generator: Image generation tool/function (optional)
        max_images: Maximum number of images to generate
    
    Returns:
        List of generated image file paths
    """
    # Check if fallback needed
    if has_sufficient_images(enrichment_data):
        logger.info("Sufficient images available, skipping fallback generation")
        return []
    
    business_name = enrichment_data.get("business_name", "Business")
    niche = enrichment_data.get("niche", "local business")
    city = enrichment_data.get("city", "")
    state = enrichment_data.get("state", "")
    
    if not city:
        logger.warning("No city provided, cannot generate contextual images")
        return []
    
    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    generated_paths = []
    
    # Generate multiple variations
    styles = ["professional", "modern", "clean"][:max_images]
    
    for idx, style in enumerate(styles):
        try:
            request = ImageGenerationRequest(
                business_name=business_name,
                niche=niche,
                city=city,
                state=state,
                style=style
            )
            
            prompt = request.to_prompt()
            cache_key = request.get_cache_key()
            
            # Generate filename
            safe_name = re.sub(r'[^a-z0-9]+', '-', business_name.lower())[:50]
            filename = f"{safe_name}-{style}-{cache_key[:8]}.png"
            output_file = output_path / filename
            
            # If image_generator provided, use it
            if image_generator:
                logger.info(f"Generating image {idx+1}/{len(styles)}: {style}")
                
                # Call image generator (interface may vary)
                # This is a placeholder for actual integration
                if callable(image_generator):
                    result = image_generator(
                        prompt=prompt,
                        output_path=str(output_file),
                        aspect_ratio=request.aspect_ratio
                    )
                    
                    if result and output_file.exists():
                        generated_paths.append(str(output_file))
                        logger.info(f"Generated: {output_file}")
            else:
                # No generator available - log the prompt for manual generation
                logger.info(f"Image generation prompt {idx+1}: {prompt}")
                logger.info(f"Would save to: {output_file}")
        
        except Exception as e:
            logger.error(f"Failed to generate image {idx+1}: {e}")
            continue
    
    return generated_paths


# ---------------------------------------------------------------------------
# Enrichment integration
# ---------------------------------------------------------------------------

def add_fallback_images_to_enrichment(
    enrichment_data: dict[str, Any],
    generated_image_paths: list[str]
) -> dict[str, Any]:
    """Add generated fallback images to enrichment data.
    
    Args:
        enrichment_data: Business enrichment data
        generated_image_paths: List of generated image file paths
    
    Returns:
        Updated enrichment data with fallback images added
    """
    if not generated_image_paths:
        return enrichment_data
    
    # Add to photos list
    existing_photos = enrichment_data.get("photos", [])
    enrichment_data["photos"] = existing_photos + generated_image_paths
    
    # Mark as having fallback images
    enrichment_data.setdefault("metadata", {})["has_fallback_images"] = True
    enrichment_data["metadata"]["fallback_image_count"] = len(generated_image_paths)
    
    return enrichment_data


def should_generate_fallback_images(enrichment_data: dict[str, Any]) -> bool:
    """Determine if fallback image generation is needed.
    
    Args:
        enrichment_data: Business enrichment data
    
    Returns:
        True if fallback images should be generated
    """
    # Check if already has fallback images
    if enrichment_data.get("metadata", {}).get("has_fallback_images"):
        return False
    
    # Check if has sufficient real images
    if has_sufficient_images(enrichment_data, min_images=3):
        return False
    
    # Check if has necessary data for generation
    return bool(enrichment_data.get("city"))
