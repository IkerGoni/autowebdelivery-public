"""
Shared artifact I/O utilities.

Provides a single `read_artifact()` / `write_artifact()` pair that handles
path construction, directory creation, and JSON serialization.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_artifact(
    filename: str,
    business_slug: str,
    *,
    base_dir: str | Path = ".",
) -> dict[str, Any] | None:
    """Read a JSON artifact file.

    Parameters
    ----------
    filename:
        Artifact filename (e.g. ``"business_profile.json"``).
    business_slug:
        Business slug subdirectory.
    base_dir:
        Root directory. Defaults to current directory.

    Returns
    -------
    dict or None
        Parsed JSON dict, or None if the file does not exist or cannot be
        decoded.
    """
    path = Path(base_dir) / business_slug / filename
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def write_artifact(
    data: dict[str, Any],
    filename: str,
    business_slug: str,
    *,
    base_dir: str | Path = ".",
) -> str:
    """Write a JSON artifact file.

    Creates parent directories as needed.

    Parameters
    ----------
    data:
        JSON-serializable dict.
    filename:
        Artifact filename (e.g. ``"business_profile.json"``).
    business_slug:
        Business slug subdirectory.
    base_dir:
        Root directory. Defaults to current directory.

    Returns
    -------
    str
        Absolute path of the written file.
    """
    path = Path(base_dir) / business_slug / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return str(path.resolve())
