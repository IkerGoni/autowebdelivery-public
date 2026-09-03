"""Vercel deployer wrapper for deploying generated sites to Vercel."""

from __future__ import annotations

import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

def deploy_to_vercel(
    site_path: str,
    *,
    project_name: str | None = None,
    token: str | None = None,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    """Deploy site to Vercel using the Vercel CLI.
    
    Args:
        site_path: Path containing the site directory (e.g. 05_sites/{slug})
        project_name: Custom project name for Vercel
        token: Vercel authorization token (reads VERCEL_TOKEN from env if None)
        timeout_seconds: Timeout for CLI execution
        
    Returns:
        dict containing deployment record fields
    """
    now = datetime.now(timezone.utc).isoformat()
    site_dir = Path(site_path) / "site"
    
    if not site_dir.exists():
        return {
            "preview_url": "",
            "deployment_status": "failed",
            "provider": "vercel",
            "http_status": 0,
            "error": f"site directory does not exist: {site_dir}",
            "deployed_at": now,
        }
        
    if not (site_dir / "index.html").exists():
        return {
            "preview_url": "",
            "deployment_status": "failed",
            "provider": "vercel",
            "http_status": 0,
            "error": f"index.html missing in site directory: {site_dir}",
            "deployed_at": now,
        }
        
    # Build CLI command — the auth token NEVER goes into argv (visible in `ps`
    # output and shell history); it is passed to the CLI via the environment.
    cmd = ["vercel", "deploy", "--yes", "--prod"]
    if project_name:
        cmd.extend(["--name", project_name])

    # Read VERCEL_TOKEN env if token not passed
    token = token or os.environ.get("VERCEL_TOKEN")
    run_env = os.environ.copy()
    if token:
        run_env["VERCEL_TOKEN"] = token

    logger.info(f"Deploying {site_dir} to Vercel via CLI...")

    try:
        res = subprocess.run(
            cmd,
            cwd=str(site_dir),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            env=run_env,
        )
        
        if res.returncode != 0:
            err = res.stderr.strip() or res.stdout.strip()
            logger.error(f"Vercel deployment failed: {err}")
            return {
                "preview_url": "",
                "deployment_status": "failed",
                "provider": "vercel",
                "http_status": 0,
                "error": err,
                "deployed_at": now,
            }
            
        url = res.stdout.strip()
        if not url.startswith("https://"):
            url = f"https://{url}"
            
        logger.info(f"Vercel deployment live: {url}")
        return {
            "preview_url": url,
            "deployment_status": "live",
            "provider": "vercel",
            "http_status": 200,
            "error": "",
            "deployed_at": now,
        }
        
    except subprocess.TimeoutExpired:
        return {
            "preview_url": "",
            "deployment_status": "failed",
            "provider": "vercel",
            "http_status": 0,
            "error": "Vercel deploy timed out",
            "deployed_at": now,
        }
    except (OSError, subprocess.SubprocessError) as e:
        return {
            "preview_url": "",
            "deployment_status": "failed",
            "provider": "vercel",
            "http_status": 0,
            "error": str(e),
            "deployed_at": now,
        }
