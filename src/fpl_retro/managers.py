"""Manager-level FPL data collection helpers."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pandas as pd

from .api import fetch_json
from .cache import cache_exists


FPL_BASE_URL = "https://fantasy.premierleague.com/api"
FAILURE_COLUMNS = ["manager_id", "endpoint", "url", "error_type", "error"]
PICKS_FAILURE_COLUMNS = ["manager_id", "event", "endpoint", "url", "error_type", "error"]


def manager_history_url(manager_id: int) -> str:
    """Return the FPL manager history endpoint URL."""

    return f"{FPL_BASE_URL}/entry/{int(manager_id)}/history/"


def manager_transfers_url(manager_id: int) -> str:
    """Return the FPL manager transfers endpoint URL."""

    return f"{FPL_BASE_URL}/entry/{int(manager_id)}/transfers/"


def manager_picks_url(manager_id: int, event: int) -> str:
    """Return the FPL manager gameweek picks endpoint URL."""

    return f"{FPL_BASE_URL}/entry/{int(manager_id)}/event/{int(event)}/picks/"


def build_manager_list(sample_managers: pd.DataFrame, my_team_id: int) -> pd.DataFrame:
    """Return focal manager plus sampled comparison managers."""

    if "manager_id" not in sample_managers.columns:
        raise ValueError("sample_managers must include manager_id")

    comparison = sample_managers[["manager_id"]].copy()
    comparison["manager_id"] = comparison["manager_id"].astype(int)
    comparison["manager_group"] = "sample"

    focal = pd.DataFrame(
        [{"manager_id": int(my_team_id), "manager_group": "focal"}],
    )

    manager_list = pd.concat([focal, comparison], ignore_index=True)
    manager_list = manager_list.drop_duplicates(subset=["manager_id"], keep="first")
    return manager_list.sort_values(["manager_group", "manager_id"]).reset_index(drop=True)


def fetch_manager_history_and_transfers(
    manager_id: int,
    *,
    raw_manager_dir: str | Path,
    force_refresh: bool = False,
    request_sleep_seconds: float = 0.0,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]] | None, list[dict[str, Any]]]:
    """Fetch one manager's history and transfers, returning failures separately."""

    raw_dir = Path(raw_manager_dir)
    history_cache = raw_dir / "history" / f"manager_{int(manager_id)}.json"
    transfers_cache = raw_dir / "transfers" / f"manager_{int(manager_id)}.json"
    failures: list[dict[str, Any]] = []

    history_payload: dict[str, Any] | None = None
    transfers_payload: list[dict[str, Any]] | None = None

    history_missing = not cache_exists(history_cache)
    try:
        history_payload = fetch_json(
            manager_history_url(manager_id),
            cache_path=history_cache,
            force_refresh=force_refresh,
        )
    except Exception as exc:  # noqa: BLE001 - record failures without stopping the whole batch.
        failures.append(
            {
                "manager_id": int(manager_id),
                "endpoint": "history",
                "url": manager_history_url(manager_id),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )

    if history_missing and request_sleep_seconds:
        time.sleep(request_sleep_seconds)

    transfers_missing = not cache_exists(transfers_cache)
    try:
        transfers_payload = fetch_json(
            manager_transfers_url(manager_id),
            cache_path=transfers_cache,
            force_refresh=force_refresh,
        )
    except Exception as exc:  # noqa: BLE001 - record failures without stopping the whole batch.
        failures.append(
            {
                "manager_id": int(manager_id),
                "endpoint": "transfers",
                "url": manager_transfers_url(manager_id),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )

    if transfers_missing and request_sleep_seconds:
        time.sleep(request_sleep_seconds)

    return history_payload, transfers_payload, failures


def normalise_manager_history(history_payload: dict[str, Any] | None, manager_id: int) -> pd.DataFrame:
    """Normalise the current-season rows from a manager history response."""

    rows = [] if history_payload is None else history_payload.get("current", [])
    history_df = pd.DataFrame(rows)
    if history_df.empty:
        return pd.DataFrame(columns=["manager_id"])
    history_df.insert(0, "manager_id", int(manager_id))
    return history_df


def normalise_manager_chips(history_payload: dict[str, Any] | None, manager_id: int) -> pd.DataFrame:
    """Normalise chip rows from a manager history response."""

    rows = [] if history_payload is None else history_payload.get("chips", [])
    chips_df = pd.DataFrame(rows)
    if chips_df.empty:
        return pd.DataFrame(columns=["manager_id"])
    chips_df.insert(0, "manager_id", int(manager_id))
    return chips_df


def normalise_manager_transfers(transfers_payload: list[dict[str, Any]] | None, manager_id: int) -> pd.DataFrame:
    """Normalise transfer rows from a manager transfers response."""

    rows = [] if transfers_payload is None else transfers_payload
    transfers_df = pd.DataFrame(rows)
    if transfers_df.empty:
        return pd.DataFrame(columns=["manager_id"])
    transfers_df.insert(0, "manager_id", int(manager_id))
    return transfers_df


def collect_manager_history_and_transfers(
    manager_ids: list[int],
    *,
    raw_manager_dir: str | Path,
    force_refresh: bool = False,
    request_sleep_seconds: float = 0.0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Collect and normalise manager histories, chips, transfers, and failures."""

    history_frames = []
    chips_frames = []
    transfers_frames = []
    failure_rows = []

    for manager_id in manager_ids:
        history_payload, transfers_payload, failures = fetch_manager_history_and_transfers(
            int(manager_id),
            raw_manager_dir=raw_manager_dir,
            force_refresh=force_refresh,
            request_sleep_seconds=request_sleep_seconds,
        )
        history_frames.append(normalise_manager_history(history_payload, int(manager_id)))
        chips_frames.append(normalise_manager_chips(history_payload, int(manager_id)))
        transfers_frames.append(normalise_manager_transfers(transfers_payload, int(manager_id)))
        failure_rows.extend(failures)

    history_df = pd.concat(history_frames, ignore_index=True) if history_frames else pd.DataFrame()
    chips_df = pd.concat(chips_frames, ignore_index=True) if chips_frames else pd.DataFrame()
    transfers_df = pd.concat(transfers_frames, ignore_index=True) if transfers_frames else pd.DataFrame()
    failures_df = pd.DataFrame(failure_rows, columns=FAILURE_COLUMNS)

    return history_df, chips_df, transfers_df, failures_df


def fetch_manager_picks(
    manager_id: int,
    event: int,
    *,
    raw_manager_dir: str | Path,
    force_refresh: bool = False,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Fetch one manager-gameweek picks payload and return a failure row if needed."""

    raw_dir = Path(raw_manager_dir)
    picks_cache = raw_dir / "picks" / f"manager_{int(manager_id)}" / f"event_{int(event):02d}.json"
    url = manager_picks_url(manager_id, event)

    try:
        return fetch_json(url, cache_path=picks_cache, force_refresh=force_refresh), None
    except Exception as exc:  # noqa: BLE001 - record failures without stopping the whole batch.
        return None, {
            "manager_id": int(manager_id),
            "event": int(event),
            "endpoint": "picks",
            "url": url,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def normalise_manager_picks(picks_payload: dict[str, Any] | None, manager_id: int, event: int) -> pd.DataFrame:
    """Normalise pick rows from one manager-gameweek payload."""

    rows = [] if picks_payload is None else picks_payload.get("picks", [])
    picks_df = pd.DataFrame(rows)
    if picks_df.empty:
        return pd.DataFrame(columns=["manager_id", "event"])
    picks_df.insert(0, "event", int(event))
    picks_df.insert(0, "manager_id", int(manager_id))
    return picks_df


def normalise_entry_history(picks_payload: dict[str, Any] | None, manager_id: int, event: int) -> pd.DataFrame:
    """Normalise entry-history metadata from one manager-gameweek picks payload."""

    row = {} if picks_payload is None else picks_payload.get("entry_history", {})
    entry_history_df = pd.DataFrame([row]) if row else pd.DataFrame()
    if entry_history_df.empty:
        return pd.DataFrame(columns=["manager_id", "event"])
    entry_history_df["event"] = int(event)
    entry_history_df["manager_id"] = int(manager_id)
    front_columns = ["manager_id", "event"]
    entry_history_df = entry_history_df[
        front_columns + [column for column in entry_history_df.columns if column not in front_columns]
    ]
    return entry_history_df


def normalise_automatic_subs(picks_payload: dict[str, Any] | None, manager_id: int, event: int) -> pd.DataFrame:
    """Normalise automatic substitution rows from one manager-gameweek payload."""

    rows = [] if picks_payload is None else picks_payload.get("automatic_subs", [])
    automatic_subs_df = pd.DataFrame(rows)
    if automatic_subs_df.empty:
        return pd.DataFrame(columns=["manager_id", "event"])
    automatic_subs_df["event"] = int(event)
    automatic_subs_df["manager_id"] = int(manager_id)
    front_columns = ["manager_id", "event"]
    automatic_subs_df = automatic_subs_df[
        front_columns + [column for column in automatic_subs_df.columns if column not in front_columns]
    ]
    return automatic_subs_df


def collect_manager_picks(
    manager_ids: list[int],
    events: list[int],
    *,
    raw_manager_dir: str | Path,
    force_refresh: bool = False,
    request_sleep_seconds: float = 0.0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Collect and normalise manager picks, entry history, automatic subs, and failures."""

    picks_frames = []
    entry_history_frames = []
    automatic_sub_frames = []
    failure_rows = []

    for manager_id in manager_ids:
        for event in events:
            payload, failure = fetch_manager_picks(
                int(manager_id),
                int(event),
                raw_manager_dir=raw_manager_dir,
                force_refresh=force_refresh,
            )
            if failure is not None:
                failure_rows.append(failure)
            picks_frames.append(normalise_manager_picks(payload, int(manager_id), int(event)))
            entry_history_frames.append(normalise_entry_history(payload, int(manager_id), int(event)))
            automatic_sub_frames.append(normalise_automatic_subs(payload, int(manager_id), int(event)))

            if request_sleep_seconds:
                time.sleep(request_sleep_seconds)

    picks_df = pd.concat(picks_frames, ignore_index=True) if picks_frames else pd.DataFrame()
    entry_history_df = (
        pd.concat(entry_history_frames, ignore_index=True) if entry_history_frames else pd.DataFrame()
    )
    automatic_subs_df = (
        pd.concat(automatic_sub_frames, ignore_index=True) if automatic_sub_frames else pd.DataFrame()
    )
    failures_df = pd.DataFrame(failure_rows, columns=PICKS_FAILURE_COLUMNS)

    return picks_df, entry_history_df, automatic_subs_df, failures_df
