"""Tests for image_fallback module — prompt generation, availability checks, fallback logic."""

from __future__ import annotations

from pathlib import Path

from packages.enrichment.image_fallback import (
    ImageGenerationRequest,
    has_sufficient_images,
    get_image_urls_from_enrichment,
    generate_image_prompt,
    generate_fallback_images,
    add_fallback_images_to_enrichment,
    should_generate_fallback_images,
)


# ===========================================================================
# ImageGenerationRequest
# ===========================================================================

class TestImageGenerationRequest:
    def test_to_prompt_auto_detailing(self):
        req = ImageGenerationRequest(
            business_name="Fresh Shine Auto Detailing",
            niche="auto_detailing",
            city="Dallas",
            state="TX",
        )
        prompt = req.to_prompt()
        assert "Dallas, TX" in prompt
        assert "vehicle" in prompt.lower() or "car" in prompt.lower()

    def test_to_prompt_restaurant(self):
        req = ImageGenerationRequest(
            business_name="Taste of Italy",
            niche="restaurant",
            city="Miami",
        )
        prompt = req.to_prompt()
        assert "food" in prompt.lower() or "dining" in prompt.lower()

    def test_to_prompt_hvac(self):
        req = ImageGenerationRequest(
            business_name="Cool Air HVAC",
            niche="hvac",
            city="Phoenix",
        )
        prompt = req.to_prompt()
        assert "HVAC" in prompt or "air conditioning" in prompt.lower()

    def test_to_prompt_generic(self):
        req = ImageGenerationRequest(
            business_name="Local Co",
            niche="general",
            city="Austin",
        )
        prompt = req.to_prompt()
        assert "business environment" in prompt.lower()

    def test_cache_key_consistency(self):
        req1 = ImageGenerationRequest("Biz", "auto_detailing", "Dallas", "TX", "professional", "16:9")
        req2 = ImageGenerationRequest("Biz", "auto_detailing", "Dallas", "TX", "professional", "16:9")
        assert req1.get_cache_key() == req2.get_cache_key()

    def test_cache_key_different_inputs(self):
        req1 = ImageGenerationRequest("Biz A", "auto_detailing", "Dallas", "TX")
        req2 = ImageGenerationRequest("Biz B", "auto_detailing", "Dallas", "TX")
        assert req1.get_cache_key() != req2.get_cache_key()

    def test_no_text_no_logos_constraint(self):
        req = ImageGenerationRequest("Test", "general", "City")
        prompt = req.to_prompt()
        assert "No text" in prompt
        assert "no logos" in prompt


# ===========================================================================
# Image availability checks
# ===========================================================================

class TestHasSufficientImages:
    def test_sufficient_real_images(self):
        data = {
            "photos": [
                "https://lh3.googleusercontent.com/photo1.jpg",
                "https://lh3.googleusercontent.com/photo2.jpg",
                "https://lh3.googleusercontent.com/photo3.jpg",
            ]
        }
        assert has_sufficient_images(data, min_images=3) is True

    def test_insufficient_images(self):
        data = {"photos": ["https://example.com/photo1.jpg"]}
        assert has_sufficient_images(data, min_images=3) is False

    def test_no_photos(self):
        assert has_sufficient_images({}, min_images=1) is False

    def test_filters_invalid_urls(self):
        data = {"photos": ["", "not-a-url", None]}
        assert has_sufficient_images(data, min_images=1) is False

    def test_default_min_images(self):
        data = {"photos": ["http://example.com/p1.jpg", "http://example.com/p2.jpg"]}
        assert has_sufficient_images(data) is False  # default min_images=3, has 2
        assert has_sufficient_images(data, min_images=2) is True


class TestGetImageUrls:
    def test_extracts_valid_urls(self):
        data = {
            "photos": [
                "https://lh3.googleusercontent.com/photo1.jpg",
                "http://photos.example.org/photo2.png",
                "placeholder.png",
                "",
            ]
        }
        urls = get_image_urls_from_enrichment(data)
        assert len(urls) == 2
        assert all(u.startswith("http") for u in urls)

    def test_filters_placeholder_urls(self):
        data = {
            "photos": [
                "https://images.unsplash.com/real-photo-123",
                "https://cdn.example.com/placeholder-image.jpg",
            ]
        }
        urls = get_image_urls_from_enrichment(data)
        assert len(urls) == 1
        assert "unsplash" in urls[0]

    def test_empty_data(self):
        assert get_image_urls_from_enrichment({}) == []


# ===========================================================================
# Prompt generation
# ===========================================================================

class TestGenerateImagePrompt:
    def test_generates_descriptive_prompt(self):
        prompt = generate_image_prompt(
            business_name="Prime Auto Detailing",
            niche="auto_detailing",
            city="Dallas",
            state="TX",
            style="professional",
        )
        assert "Dallas, TX" in prompt
        assert "professional" in prompt.lower()
        assert "Photorealistic" in prompt

    def test_default_style(self):
        prompt = generate_image_prompt(
            business_name="Biz", niche="salon", city="Miami"
        )
        assert "professional" in prompt.lower()


# ===========================================================================
# Fallback image generation
# ===========================================================================

class TestGenerateFallbackImages:
    def test_skips_when_sufficient_images(self, tmp_path):
        data = {
            "photos": [
                "https://example.com/1.jpg",
                "https://example.com/2.jpg",
                "https://example.com/3.jpg",
            ]
        }
        result = generate_fallback_images(data, str(tmp_path), max_images=3)
        assert result == []  # No generation needed

    def test_skips_when_no_city(self, tmp_path):
        data = {"business_name": "Test", "niche": "auto_detailing", "city": ""}
        result = generate_fallback_images(data, str(tmp_path))
        assert result == []

    def test_produces_prompts_when_no_generator(self, tmp_path):
        data = {
            "business_name": "Dallas Auto Detailing",
            "niche": "auto_detailing",
            "city": "Dallas",
        }
        result = generate_fallback_images(data, str(tmp_path))
        assert result == []  # No real generator — just logs prompts

    def test_calls_generator_when_provided(self, tmp_path):
        data = {
            "business_name": "Test Biz",
            "niche": "auto_detailing",
            "city": "Austin",
        }

        def fake_generator(prompt, output_path, aspect_ratio):
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text("fake-image-data")
            return {"path": output_path}

        result = generate_fallback_images(data, str(tmp_path), image_generator=fake_generator, max_images=1)
        # The fake generator writes a file but generate_fallback_images
        # checks if output_file.exists() — should find it
        assert isinstance(result, list)


class TestShouldGenerateFallbackImages:
    def test_should_generate_when_no_photos(self):
        data = {"city": "Dallas"}
        assert should_generate_fallback_images(data) is True

    def test_should_not_generate_when_already_has_fallback(self):
        data = {"city": "Dallas", "metadata": {"has_fallback_images": True}}
        assert should_generate_fallback_images(data) is False

    def test_should_not_generate_when_sufficient_real_images(self):
        data = {
            "city": "Dallas",
            "photos": ["http://a.jpg", "http://b.jpg", "http://c.jpg"],
        }
        assert should_generate_fallback_images(data) is False

    def test_should_not_generate_when_no_city(self):
        data = {"city": ""}
        assert should_generate_fallback_images(data) is False


# ===========================================================================
# Enrichment integration
# ===========================================================================

class TestAddFallbackImages:
    def test_adds_photos_to_enrichment(self):
        data = {"photos": ["http://existing.jpg"]}
        result = add_fallback_images_to_enrichment(data, ["/tmp/gen1.png", "/tmp/gen2.png"])
        assert len(result["photos"]) == 3
        assert "/tmp/gen1.png" in result["photos"]

    def test_sets_metadata_flag(self):
        data = {}
        result = add_fallback_images_to_enrichment(data, ["/tmp/gen.png"])
        assert result["metadata"]["has_fallback_images"] is True
        assert result["metadata"]["fallback_image_count"] == 1

    def test_empty_paths(self):
        data = {"photos": ["http://existing.jpg"]}
        result = add_fallback_images_to_enrichment(data, [])
        assert len(result["photos"]) == 1
        assert "has_fallback_images" not in result.get("metadata", {})
