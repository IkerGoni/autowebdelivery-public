"""CLI entry point for running the Autowebdelivery pipeline."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so `from pipeline.X` imports work
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.shared.logging_config import setup_logging


def _build_stitch_client(api_key: str | None) -> object | None:
    """Create an HttpStitchClient if an API key is available."""
    if not api_key:
        return None
    from packages.generation.stitch_adapter import HttpStitchClient
    return HttpStitchClient(api_key=api_key)


def main() -> None:
    # Import after sys.path fix
    from packages.pipeline.run_pipeline import run_full_pipeline

    parser = argparse.ArgumentParser(description="Autowebdelivery End-to-End Pipeline")
    parser.add_argument("--niche", required=True, help="Niche/category (e.g. 'auto detailing')")
    parser.add_argument("--area", required=True, help="Target city/area (e.g. 'Frisco TX')")
    parser.add_argument("--country", default="US", help="ISO country code (default: US)")
    parser.add_argument("--generation-mode", default="stitch", choices=["stitch", "modular", "template", "auto"],
                        help="Site generation path (default: stitch)")
    parser.add_argument("--production", action="store_true",
                        help="Production mode: removes watermarks/test markers (modular mode)")
    parser.add_argument("--stitch-api-key", default=None,
                        help="Stitch MCP API key (or set STITCH_API_KEY env var)")
    parser.add_argument("--stitch-model", default="GEMINI_3_1_PRO",
                        choices=["GEMINI_3_1_PRO", "GEMINI_3_FLASH", "GEMINI_3_PRO"],
                        help="Stitch generation model (default: GEMINI_3_1_PRO)")
    parser.add_argument("--deploy-provider", default="local_only", choices=["local_only", "vercel", "nginx_local"],
                        help="Deployment provider (default: local_only)")
    parser.add_argument("--discovery-source", default="fixture",
                        choices=["fixture", "overpass", "csv_file", "maps_api", "maps_search"],
                        help="Lead discovery source (default: fixture)")
    parser.add_argument("--max-sites", type=int, default=5, help="Max preview sites to generate (default: 5)")
    parser.add_argument("--price-offer", default="$499 one-time", help="Offer price to pitch")
    parser.add_argument("--dry-run", action="store_true", help="Skip deployment and outreach steps")
    parser.add_argument("--verbose", action="store_true", help="Print debug logging")
    parser.add_argument("--json-logs", action="store_true",
                        help="Emit one-line JSON logs (each with ts, level, run_id, phase)")

    args = parser.parse_args()

    # Resolve Stitch API key: CLI arg > env var
    stitch_api_key = args.stitch_api_key or os.environ.get("STITCH_API_KEY")
    stitch_client = _build_stitch_client(stitch_api_key)

    logger = logging.getLogger(__name__)
    if stitch_client is not None:
        logger.info("Stitch MCP client initialized (HTTP JSON-RPC)")
    elif args.generation_mode == "stitch":
        logger.warning("generation_mode=stitch but no STITCH_API_KEY — will fail at Phase 05")

    # Configure logging (human-readable console by default; --json-logs for JSON lines)
    setup_logging(verbose=args.verbose, json_logs=args.json_logs)

    summary = run_full_pipeline(
        niche=args.niche,
        area=args.area,
        country=args.country,
        stitch_client=stitch_client,
        model_id=args.stitch_model,
        generation_mode=args.generation_mode,
        deploy_provider=args.deploy_provider,
        discovery_source=args.discovery_source,
        max_preview_sites=args.max_sites,
        price_offer=args.price_offer,
        dry_run=args.dry_run,
        production_mode=args.production,
    )

    print("\n" + "="*40)
    print("PIPELINE RUN SUMMARY")
    print("="*40)
    print(json.dumps(summary, indent=2))
    print("="*40)


if __name__ == "__main__":
    main()
