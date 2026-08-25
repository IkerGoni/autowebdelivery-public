"""Premium generation helpers for Autowebdelivery."""

from packages.generation.html_sanitizer import (
    SanitizationFinding,
    SanitizationResult,
    SanitizationRule,
    sanitize_html,
    write_sanitized_html,
    write_sanitizer_report,
)
from packages.generation.stitch_adapter import (
    CommandResult,
    McporterStitchClient,
    McpStitchClient,
    StitchAdapter,
    StitchGenerationRequest,
    StitchGenerationResult,
)
from packages.generation.stitch_prompt_builder import (
    PremiumStitchPrompt,
    StitchPromptInput,
    build_premium_stitch_prompt,
)

__all__ = [
    "CommandResult",
    "McpStitchClient",
    "McporterStitchClient",
    "PremiumStitchPrompt",
    "SanitizationFinding",
    "SanitizationResult",
    "SanitizationRule",
    "StitchAdapter",
    "StitchGenerationRequest",
    "StitchGenerationResult",
    "StitchPromptInput",
    "build_premium_stitch_prompt",
    "sanitize_html",
    "write_sanitized_html",
    "write_sanitizer_report",
]
