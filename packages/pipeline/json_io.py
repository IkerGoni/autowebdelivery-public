"""JSON file I/O utilities per pipeline_data_contract.md."""

import json
from pathlib import Path
from typing import Any


def read_json(path: str) -> dict[str, Any]:
    """Read JSON file and return as dict."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, data: dict[str, Any]) -> str:
    """Write dict to JSON file. Returns absolute path."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return str(Path(path).resolve())


def read_result(path: str) -> dict[str, Any]:
    """Read result.json from workspace. Raises if not found."""
    result_path = Path(path) / "result.json"
    if not result_path.exists():
        raise FileNotFoundError(f"result.json not found at {result_path}")
    return read_json(str(result_path))


def write_result(result_path: str, result: dict[str, Any]) -> str:
    """Write result.json. Returns absolute path."""
    path = Path(result_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return write_json(str(path), result)