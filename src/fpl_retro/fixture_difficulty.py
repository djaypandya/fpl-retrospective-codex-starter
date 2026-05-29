"""Fixture difficulty feature helpers."""

from __future__ import annotations

import pandas as pd


OUTLOOK_WINDOWS = [1, 3, 5]

OPPONENT_STRENGTH_COLUMNS = [
    "goals_for_per_fixture_prior",
    "goals_against_per_fixture_prior",
    "clean_sheet_rate_prior",
    "points_per_fixture_prior",
    "home_goals_for_per_home_fixture_prior",
    "home_goals_against_per_home_fixture_prior",
    "home_clean_sheet_rate_prior",
    "away_goals_for_per_away_fixture_prior",
    "away_goals_against_per_away_fixture_prior",
    "away_clean_sheet_rate_prior",
]


def _fixture_team_rows(fixtures: pd.DataFrame) -> pd.DataFrame:
    """Convert fixtures into one future-opponent row per team fixture."""

    required_columns = {
        "event",
        "id",
        "team_h",
        "team_a",
        "team_h_name",
        "team_a_name",
        "team_h_short_name",
        "team_a_short_name",
        "team_h_difficulty",
        "team_a_difficulty",
    }
    missing_columns = required_columns - set(fixtures.columns)
    if missing_columns:
        raise ValueError(f"missing fixture columns: {sorted(missing_columns)}")

    home = pd.DataFrame(
        {
            "fixture_gameweek": fixtures["event"].astype(int),
            "fixture_id": fixtures["id"].astype(int),
            "team_id": fixtures["team_h"].astype(int),
            "team_name": fixtures["team_h_name"],
            "team_short_name": fixtures["team_h_short_name"],
            "opponent_id": fixtures["team_a"].astype(int),
            "opponent_name": fixtures["team_a_name"],
            "opponent_short_name": fixtures["team_a_short_name"],
            "is_home": True,
            "fpl_difficulty": fixtures["team_h_difficulty"].astype(float),
        }
    )
    away = pd.DataFrame(
        {
            "fixture_gameweek": fixtures["event"].astype(int),
            "fixture_id": fixtures["id"].astype(int),
            "team_id": fixtures["team_a"].astype(int),
            "team_name": fixtures["team_a_name"],
            "team_short_name": fixtures["team_a_short_name"],
            "opponent_id": fixtures["team_h"].astype(int),
            "opponent_name": fixtures["team_h_name"],
            "opponent_short_name": fixtures["team_h_short_name"],
            "is_home": False,
            "fpl_difficulty": fixtures["team_a_difficulty"].astype(float),
        }
    )
    return pd.concat([home, away], ignore_index=True).sort_values(
        ["team_id", "fixture_gameweek", "fixture_id"]
    )


def _join_opponent_strength(fixture_rows: pd.DataFrame, team_strength: pd.DataFrame) -> pd.DataFrame:
    """Attach opponent prior strength for the gameweek the fixture is played."""

    required_strength_columns = {"team_id", "gameweek", *OPPONENT_STRENGTH_COLUMNS}
    missing_columns = required_strength_columns - set(team_strength.columns)
    if missing_columns:
        raise ValueError(f"missing team strength columns: {sorted(missing_columns)}")

    opponent_strength = team_strength[["team_id", "gameweek", *OPPONENT_STRENGTH_COLUMNS]].rename(
        columns={
            "team_id": "opponent_id",
            "gameweek": "fixture_gameweek",
            **{column: f"opponent_{column}" for column in OPPONENT_STRENGTH_COLUMNS},
        }
    )
    return fixture_rows.merge(
        opponent_strength,
        on=["opponent_id", "fixture_gameweek"],
        how="left",
        validate="many_to_one",
    )


def _aggregate_window(
    fixtures_with_strength: pd.DataFrame,
    *,
    teams: pd.DataFrame,
    decision_gameweek: int,
    max_gameweek: int,
    window: int,
) -> pd.DataFrame:
    """Aggregate future fixtures for one decision gameweek and horizon."""

    end_gameweek = min(decision_gameweek + window - 1, max_gameweek)
    gameweeks = pd.DataFrame({"fixture_gameweek": range(decision_gameweek, end_gameweek + 1)})
    window_fixtures = fixtures_with_strength[
        fixtures_with_strength["fixture_gameweek"].between(decision_gameweek, end_gameweek)
    ].copy()
    fixture_counts = (
        window_fixtures.groupby(["team_id", "fixture_gameweek"]).size().rename("fixture_count").reset_index()
    )
    team_gameweeks = teams[["team_id"]].merge(gameweeks, how="cross").merge(
        fixture_counts, on=["team_id", "fixture_gameweek"], how="left"
    )
    team_gameweeks["fixture_count"] = team_gameweeks["fixture_count"].fillna(0).astype(int)
    schedule_summary = team_gameweeks.groupby("team_id", as_index=False).agg(
        **{
            f"blank_gameweeks_next{window}": ("fixture_count", lambda values: int((values == 0).sum())),
            f"double_gameweeks_next{window}": ("fixture_count", lambda values: int((values > 1).sum())),
        }
    )

    aggregations = {
        "fixture_id": "count",
        "fpl_difficulty": ["sum", "mean", "max"],
        "is_home": "sum",
    }
    for column in OPPONENT_STRENGTH_COLUMNS:
        aggregations[f"opponent_{column}"] = "mean"

    if window_fixtures.empty:
        summary = teams[["team_id"]].copy()
        summary[f"fixture_count_next{window}"] = 0
    else:
        summary = window_fixtures.groupby("team_id").agg(aggregations)
        summary.columns = [
            "_".join(part for part in column if part).replace("fixture_id_count", f"fixture_count_next{window}")
            for column in summary.columns.to_flat_index()
        ]
        summary = summary.reset_index()
        summary = teams[["team_id"]].merge(summary, on="team_id", how="left")

    summary = summary.merge(schedule_summary, on="team_id", how="left", validate="one_to_one")
    summary[f"gameweeks_available_next{window}"] = end_gameweek - decision_gameweek + 1
    summary[f"fixture_count_next{window}"] = summary[f"fixture_count_next{window}"].fillna(0).astype(int)
    summary[f"blank_next{window}"] = (summary[f"blank_gameweeks_next{window}"] > 0).astype(int)
    summary[f"double_next{window}"] = (summary[f"double_gameweeks_next{window}"] > 0).astype(int)

    rename_columns = {
        "fpl_difficulty_sum": f"fpl_difficulty_sum_next{window}",
        "fpl_difficulty_mean": f"fpl_difficulty_mean_next{window}",
        "fpl_difficulty_max": f"fpl_difficulty_max_next{window}",
        "is_home_sum": f"home_fixture_count_next{window}",
    }
    for column in OPPONENT_STRENGTH_COLUMNS:
        rename_columns[f"opponent_{column}_mean"] = f"opponent_{column}_mean_next{window}"
    summary = summary.rename(columns=rename_columns)

    summary[f"home_fixture_count_next{window}"] = (
        summary[f"home_fixture_count_next{window}"].fillna(0).astype(int)
    )
    summary[f"away_fixture_count_next{window}"] = (
        summary[f"fixture_count_next{window}"] - summary[f"home_fixture_count_next{window}"]
    )

    return summary


def build_fixture_difficulty(fixtures_df: pd.DataFrame, team_strength_df: pd.DataFrame) -> pd.DataFrame:
    """Build fixture outlook features, one team per decision gameweek."""

    fixture_rows = _fixture_team_rows(fixtures_df)
    fixtures_with_strength = _join_opponent_strength(fixture_rows, team_strength_df)
    teams = (
        team_strength_df[["team_id", "team_name", "team_short_name"]]
        .drop_duplicates("team_id")
        .sort_values("team_id")
        .reset_index(drop=True)
    )
    min_gameweek = int(fixtures_df["event"].min())
    max_gameweek = int(fixtures_df["event"].max())
    grid = teams.merge(pd.DataFrame({"gameweek": range(min_gameweek, max_gameweek + 1)}), how="cross")

    output = grid.copy()
    for window in OUTLOOK_WINDOWS:
        window_frames = []
        for decision_gameweek in range(min_gameweek, max_gameweek + 1):
            summary = _aggregate_window(
                fixtures_with_strength,
                teams=teams,
                decision_gameweek=decision_gameweek,
                max_gameweek=max_gameweek,
                window=window,
            )
            summary["gameweek"] = decision_gameweek
            window_frames.append(summary)
        window_output = pd.concat(window_frames, ignore_index=True)
        output = output.merge(window_output, on=["team_id", "gameweek"], how="left", validate="one_to_one")

    return output.sort_values(["gameweek", "team_id"]).reset_index(drop=True)
