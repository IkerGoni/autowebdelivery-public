"""Premium Stitch generation adapter with design systems, variants, and iterative refinement."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from packages.generation.html_sanitizer import (
    sanitize_html,
    write_sanitized_html,
    write_sanitizer_report,
)
from packages.generation.stitch_adapter import (
    StitchAdapter,
    StitchClient,
    StitchGenerationRequest,
    StitchGenerationResult,
    _extract_id,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Design system configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DesignSystemConfig:
    """Configuration for a Stitch design system."""
    display_name: str
    color_mode: str = "LIGHT"          # LIGHT | DARK
    headline_font: str = "INTER"
    body_font: str = "INTER"
    roundness: str = "ROUND_EIGHT"     # ROUND_FOUR | ROUND_EIGHT | ROUND_TWELVE | ROUND_FULL
    custom_color: str = "#2563EB"      # primary color seed
    color_variant: str = "TONAL_SPOT"  # MONOCHROME | NEUTRAL | TONAL_SPOT | VIBRANT | EXPRESSIVE
    design_md: str | None = None       # optional markdown design instructions


# Pre-built design system presets mapped to visual profile presets
DESIGN_SYSTEM_PRESETS: dict[str, DesignSystemConfig] = {
    "clinical_trust": DesignSystemConfig(
        display_name="Clinical Trust",
        color_mode="LIGHT",
        headline_font="INTER",
        body_font="INTER",
        roundness="ROUND_EIGHT",
        custom_color="#0EA5E9",
        color_variant="TONAL_SPOT",
        design_md=(
            "Clean, medical-grade design. White backgrounds, blue accents, "
            "high contrast for accessibility. Professional typography with Inter. "
            "Rounded corners (8px) for approachability. Emphasize trust signals."
        ),
    ),
    "warm_editorial": DesignSystemConfig(
        display_name="Warm Editorial",
        color_mode="LIGHT",
        headline_font="PLAYFAIR_DISPLAY",
        body_font="LORA",
        roundness="ROUND_TWELVE",
        custom_color="#D97706",
        color_variant="WARM" if "WARM" else "VIBRANT",
        design_md=(
            "Warm, editorial design for beauty/hospitality. Serif headlines, "
            "warm amber/gold accents, generous whitespace. Rounded corners (12px). "
            "Elegant, inviting feel with rich typography."
        ),
    ),
    "industrial_reliable": DesignSystemConfig(
        display_name="Industrial Reliable",
        color_mode="LIGHT",
        headline_font="ROBOTO_FLEX",
        body_font="PUBLIC_SANS",
        roundness="ROUND_FOUR",
        custom_color="#DC2626",
        color_variant="NEUTRAL",
        design_md=(
            "Industrial, reliable design for trades/repair. Bold sans-serif fonts, "
            "red/dark accents, strong contrast. Minimal rounding (4px). "
            "Emphasize durability, expertise, and directness."
        ),
    ),
    "fresh_utility": DesignSystemConfig(
        display_name="Fresh Utility",
        color_mode="LIGHT",
        headline_font="MANROPE",
        body_font="DM_SANS",
        roundness="ROUND_TWELVE",
        custom_color="#059669",
        color_variant="TONAL_SPOT",
        design_md=(
            "Fresh, clean design for home services/eco. Modern sans-serif fonts, "
            "green accents, airy layouts. Rounded corners (12px). "
            "Emphasize cleanliness, eco-friendliness, and reliability."
        ),
    ),
}


# ---------------------------------------------------------------------------
# Premium generation result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PremiumGenerationResult:
    """Result from premium Stitch generation with refinement loop."""
    status: str                          # done | failed | hard_blocked
    run_id: str
    business_slug: str
    project_id: str | None
    screen_id: str | None
    design_system_id: str | None
    html_path: str | None
    iterations: int                      # number of generation attempts
    visual_quality_score: int | None     # 0-100 if scored
    sanitizer_findings: int
    hard_block: bool
    outputs_created: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Premium Stitch Adapter
# ---------------------------------------------------------------------------

class PremiumStitchAdapter:
    """Premium Stitch adapter with design systems, variants, and iterative refinement.

    Wraps the base StitchAdapter and adds:
    - Design system creation/application from visual profile presets
    - Variant generation for A/B testing
    - Iterative refinement loop (generate → sanitize → score → regenerate if needed)
    - Post-processing of Stitch HTML (clean orphan elements, inject verified facts)
    """

    def __init__(
        self,
        client: StitchClient,
        *,
        max_iterations: int = 3,
        min_quality_score: int = 60,
        enable_variants: bool = False,
        variant_count: int = 2,
    ):
        self.base_adapter = StitchAdapter(client)
        self.client = client
        self.max_iterations = max_iterations
        self.min_quality_score = min_quality_score
        self.enable_variants = enable_variants
        self.variant_count = variant_count

    def generate_premium(
        self,
        *,
        run_id: str,
        record_id: str,
        business_slug: str,
        business_name: str,
        prompt: str,
        prompt_contract: dict[str, Any],
        output_dir: Path,
        project_title: str,
        project_id: str | None = None,
        visual_profile: dict[str, Any] | None = None,
        verified_facts: dict[str, str] | None = None,
        device_type: str = "MOBILE",
        model_id: str = "GEMINI_3_PRO",
    ) -> PremiumGenerationResult:
        """Generate premium site with design system and iterative refinement."""
        visual_profile = visual_profile or {}
        verified_facts = verified_facts or {}
        output_dir.mkdir(parents=True, exist_ok=True)

        # --- Step 1: Create/apply design system ---
        design_system_id = self._ensure_design_system(
            project_id=project_id,
            visual_profile=visual_profile,
        )

        # --- Step 2: Iterative generation loop ---
        best_result: StitchGenerationResult | None = None
        best_score = 0
        iterations = 0

        for iteration in range(1, self.max_iterations + 1):
            iterations = iteration
            request = StitchGenerationRequest(
                run_id=run_id,
                record_id=record_id,
                business_slug=business_slug,
                business_name=business_name,
                prompt=prompt,
                prompt_contract=prompt_contract,
                output_dir=output_dir,
                project_title=project_title,
                project_id=project_id,
                design_system=design_system_id,
                device_type=device_type,
                model_id=model_id,
                adapter_mode="premium",
            )

            result = self.base_adapter.generate(request)
            if result.status == "failed":
                return PremiumGenerationResult(
                    status="failed",
                    run_id=run_id,
                    business_slug=business_slug,
                    project_id=project_id,
                    screen_id=None,
                    design_system_id=design_system_id,
                    html_path=None,
                    iterations=iterations,
                    visual_quality_score=None,
                    sanitizer_findings=0,
                    hard_block=False,
                    errors=result.errors,
                )

            # --- Step 3: Sanitize ---
            html_path = result.html_path
            if not html_path:
                # Try fallback
                candidates = [output_dir / "index.html", output_dir / "site" / "index.html"]
                for c in candidates:
                    if c.exists():
                        html_path = str(c)
                        break

            if not html_path:
                return PremiumGenerationResult(
                    status="failed",
                    run_id=run_id,
                    business_slug=business_slug,
                    project_id=project_id,
                    screen_id=result.screen_id,
                    design_system_id=design_system_id,
                    html_path=None,
                    iterations=iterations,
                    visual_quality_score=None,
                    sanitizer_findings=0,
                    hard_block=False,
                    errors=["No HTML found in Stitch download"],
                )

            raw_html = Path(html_path).read_text(encoding="utf-8")
            san_result = sanitize_html(raw_html, verified_facts=verified_facts)

            if san_result.hard_block:
                return PremiumGenerationResult(
                    status="hard_blocked",
                    run_id=run_id,
                    business_slug=business_slug,
                    project_id=project_id,
                    screen_id=result.screen_id,
                    design_system_id=design_system_id,
                    html_path=None,
                    iterations=iterations,
                    visual_quality_score=None,
                    sanitizer_findings=len(san_result.findings),
                    hard_block=True,
                    errors=[f"Sanitizer hard block: {san_result.hard_block_reasons}"],
                )

            # --- Step 4: Score ---
            score = self._compute_quick_quality_score(san_result, raw_html)

            if score > best_score:
                best_score = score
                best_result = result

            logger.info(
                "Iteration %d/%d: score=%d, findings=%d",
                iteration, self.max_iterations, score, len(san_result.findings),
            )

            if score >= self.min_quality_score:
                break

        if best_result is None:
            return PremiumGenerationResult(
                status="failed",
                run_id=run_id,
                business_slug=business_slug,
                project_id=project_id,
                screen_id=None,
                design_system_id=design_system_id,
                html_path=None,
                iterations=iterations,
                visual_quality_score=best_score,
                sanitizer_findings=0,
                hard_block=False,
                errors=["All iterations failed"],
            )

        # --- Step 5: Write final output ---
        final_html_path = best_result.html_path
        if final_html_path:
            raw_html = Path(final_html_path).read_text(encoding="utf-8")
            san_result = sanitize_html(raw_html, verified_facts=verified_facts)
            site_dir = output_dir / "site"
            site_dir.mkdir(parents=True, exist_ok=True)
            write_sanitized_html(san_result, site_dir / "index.html")
            write_sanitizer_report(san_result, output_dir)
        else:
            san_result = sanitize_html("", verified_facts=verified_facts)

        outputs = self._write_metadata(
            output_dir=output_dir,
            run_id=run_id,
            business_slug=business_slug,
            design_system_id=design_system_id,
            iterations=iterations,
            visual_quality_score=best_score,
            sanitizer_findings=len(san_result.findings),
        )

        return PremiumGenerationResult(
            status="done",
            run_id=run_id,
            business_slug=business_slug,
            project_id=project_id,
            screen_id=best_result.screen_id,
            design_system_id=design_system_id,
            html_path=str(site_dir / "index.html") if final_html_path else None,
            iterations=iterations,
            visual_quality_score=best_score,
            sanitizer_findings=len(san_result.findings),
            hard_block=False,
            outputs_created=outputs,
            metadata={
                "design_system_id": design_system_id,
                "iterations": iterations,
                "visual_quality_score": best_score,
                "min_quality_score": self.min_quality_score,
            },
        )

    def _ensure_design_system(
        self,
        project_id: str | None,
        visual_profile: dict[str, Any],
    ) -> str | None:
        """Create or return design system ID based on visual profile preset."""
        preset_id = (visual_profile.get("preset_id") or "").lower()
        config = DESIGN_SYSTEM_PRESETS.get(preset_id)
        if config is None:
            return None

        if project_id is None:
            return None

        try:
            # Try to create design system via Stitch MCP
            ds_payload = self._call_create_design_system(
                project_id=project_id,
                config=config,
            )
            ds_id = _extract_id(ds_payload, ("asset_id", "assetId", "id", "name"))
            if ds_id:
                logger.info("Created design system %s for project %s", ds_id, project_id)
                return f"assets/{ds_id}"
        except Exception as exc:
            logger.warning("Design system creation failed, continuing without: %s", exc)

        return None

    def _call_create_design_system(
        self,
        project_id: str,
        config: DesignSystemConfig,
    ) -> dict[str, Any]:
        """Call Stitch MCP to create a design system."""
        # Check if client has direct create_design_system method
        if hasattr(self.client, "create_design_system"):
            return self.client.create_design_system(
                project_id=project_id,
                display_name=config.display_name,
                color_mode=config.color_mode,
                headline_font=config.headline_font,
                body_font=config.body_font,
                roundness=config.roundness,
                custom_color=config.custom_color,
                color_variant=config.color_variant,
                design_md=config.design_md,
            )

        # Fallback: try via MCP tool call if client supports it
        if hasattr(self.client, "_rpc"):
            return self.client._rpc(
                "tools/call",
                {
                    "name": "create_design_system",
                    "arguments": {
                        "projectId": project_id,
                        "designSystem": {
                            "displayName": config.display_name,
                            "theme": {
                                "colorMode": config.color_mode,
                                "headlineFont": config.headline_font,
                                "bodyFont": config.body_font,
                                "roundness": config.roundness,
                                "customColor": config.custom_color,
                                "colorVariant": config.color_variant,
                                "designMd": config.design_md,
                            },
                        },
                    },
                },
            )

        raise RuntimeError("Client does not support design system creation")

    def _compute_quick_quality_score(
        self,
        san_result: Any,
        raw_html: str,
    ) -> int:
        """Compute quick quality score from sanitizer results and HTML analysis."""
        score = 100

        # Sanitizer findings penalty
        score -= len(san_result.findings) * 5

        # Content quality signals
        text_content = self._extract_text_from_html(raw_html)
        word_count = len(text_content.split()) if text_content else 0

        if word_count < 50:
            score -= 20
        elif word_count < 100:
            score -= 10

        # Structure signals
        has_h1 = "<h1" in raw_html.lower()
        has_cta = any(kw in raw_html.lower() for kw in ("tel:", "call", "contact", "btn"))
        has_sections = any(kw in raw_html.lower() for kw in ("<section", "<main", "<article"))

        if not has_h1:
            score -= 15
        if not has_cta:
            score -= 20
        if not has_sections:
            score -= 10

        return max(0, min(100, score))

    def _extract_text_from_html(self, html: str) -> str:
        """Extract visible text from HTML (simple regex-based)."""
        import re
        text = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _write_metadata(
        self,
        output_dir: Path,
        run_id: str,
        business_slug: str,
        design_system_id: str | None,
        iterations: int,
        visual_quality_score: int,
        sanitizer_findings: int,
    ) -> list[str]:
        """Write premium generation metadata."""
        outputs: list[str] = []
        metadata = {
            "run_id": run_id,
            "business_slug": business_slug,
            "generation_mode": "premium_stitch_v2",
            "design_system_id": design_system_id,
            "iterations": iterations,
            "visual_quality_score": visual_quality_score,
            "sanitizer_findings": sanitizer_findings,
        }
        meta_path = output_dir / "premium_generation_metadata.json"
        meta_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
        outputs.append(str(meta_path))
        return outputs
