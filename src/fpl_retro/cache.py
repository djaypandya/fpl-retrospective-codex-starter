"""JSON cache helpers for FPL API responses."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(cache_path: str | Path) -> Any:
    """Load cached JSON from disk."""
    path = Path(cache_path)
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(data: Any, cache_path: str | Path) -> Path:
    """Save JSON data to disk and return the resolved cache path."""
    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, sort_keys=True)
    return path


def cache_exists(cache_path: str | Path | None) -> bool:
    """Return True when a non-empty cache path exists."""
    return cache_path is not None and Path(cache_path).exists()
