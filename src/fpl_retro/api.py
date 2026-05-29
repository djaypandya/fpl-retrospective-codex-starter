"""FPL API helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from .cache import cache_exists, load_json, save_json


DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_HEADERS = {
    "User-Agent": "fpl-retrospective-codex-starter/0.1",
    "Accept": "application/json",
}


def fetch_json(
    url: str,
    cache_path: str | Path | None = None,
    force_refresh: bool = False,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> Any:
    """Fetch JSON from a URL, using a local cache when available.

    If ``cache_path`` exists and ``force_refresh`` is False, cached JSON is
    returned without making a network request. HTTP errors and invalid JSON
    propagate to the caller so notebook checks fail loudly.
    """
    if cache_exists(cache_path) and not force_refresh:
        return load_json(cache_path)  # type: ignore[arg-type]

    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    data = response.json()

    if cache_path is not None:
        save_json(data, cache_path)

    return data
