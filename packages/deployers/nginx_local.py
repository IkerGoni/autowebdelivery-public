"""Nginx-local deployer for serving generated sites via HTTP.

Assumes nginx is already configured to serve the runs/ directory
under /sites/ on a configured port.  This deployer only verifies
that the static site exists and constructs the correct HTTP URL.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def deploy_nginx_local(site_path: str) -> dict[str, Any]:
    """Verify local static site and return HTTP preview URL.

    The URL points at the nginx reverse-mapped location:
        http://{HOST}:{PORT}/sites/{run_id}/05_sites/{slug}/

    where:
      - HOST comes from env ``SITE_HOST`` (default ``192.0.2.1`` — Tailscale IP of rs host)
      - PORT comes from env ``SITE_PORT`` (default ``8081``)
      - ``site_path`` is the absolute or relative path to the site
        directory (e.g. ``runs/run_xxx/05_sites/business-slug/``).

    The default Tailscale-only host assumes nginx is bound to the
    tailnet interface on the rs host, keeping previews off the public
    internet until the operator is ready to ship.

    Args:
        site_path: Path to the site directory.

    Returns:
        Dict with preview_url, deployment_status, provider, http_status, error.
    """
    host = os.environ.get("SITE_HOST", "192.0.2.1")
    port = os.environ.get("SITE_PORT", "8081")
    root = Path(site_path)

    if not root.exists():
        return {
            "preview_url": "",
            "deployment_status": "failed",
            "provider": "nginx_local",
            "http_status": 0,
            "error": f"Site path not found: {site_path}",
        }

    # Support both site/index.html (stitch/preview) and index.html (modular)
    index_path = root / "site" / "index.html"
    if not index_path.exists():
        index_path = root / "index.html"

    if not index_path.exists():
        return {
            "preview_url": "",
            "deployment_status": "failed",
            "provider": "nginx_local",
            "http_status": 0,
            "error": f"Site entrypoint not found: {index_path}",
        }

    # Derive the URL path from the site_path.
    # site_path looks like: runs/{run_id}/05_sites/{slug}
    # or an absolute path ending with runs/{run_id}/05_sites/{slug}
    parts = Path(site_path).parts
    try:
        runs_idx = list(parts).index("runs")
        relative = "/".join(parts[runs_idx:])  # runs/run_id/05_sites/slug
    except ValueError:
        # Fallback: use the directory name as slug
        relative = f"sites/{root.name}"

    preview_url = f"http://{host}:{port}/sites/{relative}/"

    return {
        "preview_url": preview_url,
        "deployment_status": "live",
        "provider": "nginx_local",
        "http_status": 200,
        "error": "",
    }
