"""Local-only deployer for MVP preview sites.

No network deploy. Verifies local static site and returns file URL.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def deploy_local_site(site_path: str) -> dict[str, Any]:
    """Verify local static site and return local preview URL."""
    root = Path(site_path)
    
    if not root.exists():
        return {
            "preview_url": "",
            "deployment_status": "failed",
            "provider": "local_only",
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
            "provider": "local_only",
            "http_status": 0,
            "error": f"Site entrypoint not found: {index_path}",
        }

    return {
        "preview_url": index_path.resolve().as_uri(),
        "deployment_status": "live",
        "provider": "local_only",
        "http_status": 200,
        "error": "",
    }
