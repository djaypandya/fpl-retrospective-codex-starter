"""Team strength feature helpers."""

from __future__ import annotations

import pandas as pd


ROLLING_WINDOWS = [3, 5]


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Divide two series and return null where the denominator is zero."""

    denominator = denominator.where(denominator != 0)
    return numerator / denominator


def _fixture_team_rows(fixtures: pd.DataFrame) -> pd.DataFrame:
    """Convert completed fixtures into one team-perspective row per team-match."""

    required_columns = {
        "event",
        "finished",
        "id",
        "team_h",
        "team_a",
        "team_h_score",
        "team_a_score",
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

    completed = fixtures[fixtures["finished"]].copy()
    if completed.empty:
        raise ValueError("no completed fixtures available for team strength")

    home = pd.DataFrame(
        {
            "gameweek": completed["event"].astype(int),
            "fixture_id": completed["id"].astype(int),
            "team_id": completed["team_h"].astype(int),
            "team_name": completed["team_h_name"],
            "team_short_name": completed["team_h_short_name"],
            "opponent_id": completed["team_a"].astype(int),
            "opponent_name": completed["team_a_name"],
            "opponent_short_name": completed["team_a_short_name"],
            "was_home": True,
            "goals_for": completed["team_h_score"].astype(int),
            "goals_against": completed["team_a_score"].astype(int),
            "fixture_difficulty": completed["team_h_difficulty"].astype(int),
        }
    )
    away = pd.DataFrame(
        {
            "gameweek": completed["event"].astype(int),
            "fixture_id": completed["id"].astype(int),
            "team_id": completed["team_a"].astype(int),
            "team_name": completed["team_a_name"],
            "team_short_name": completed["team_a_short_name"],
            "opponent_id": completed["team_h"].astype(int),
            "opponent_name": completed["team_h_name"],
            "opponent_short_name": completed["team_h_short_name"],
            "was_home": False,
            "goals_for": completed["team_a_score"].astype(int),
            "goals_against": completed["team_h_score"].astype(int),
            "fixture_difficulty": completed["team_a_difficulty"].astype(int),
        }
    )
    team_rows = pd.concat([home, away], ignore_index=True)
    team_rows["goal_difference"] = team_rows["goals_for"] - team_rows["goals_against"]
    team_rows["clean_sheets"] = (team_rows["goals_against"] == 0).astype(int)
    team_rows["wins"] = (team_rows["goals_for"] > team_rows["goals_against"]).astype(int)
    team_rows["draws"] = (team_rows["goals_for"] == team_rows["goals_against"]).astype(int)
    team_rows["losses"] = (team_rows["goals_for"] < team_rows["goals_against"]).astype(int)
    team_rows["league_points"] = team_rows["wins"] * 3 + team_rows["draws"]
    team_rows["home_matches"] = team_rows["was_home"].astype(int)
    team_rows["away_matches"] = (~team_rows["was_home"]).astype(int)
    team_rows["home_goals_for"] = team_rows["goals_for"].where(team_rows["was_home"], 0)
    team_rows["home_goals_against"] = team_rows["goals_against"].where(team_rows["was_home"], 0)
    team_rows["home_clean_sheets"] = team_rows["clean_sheets"].where(team_rows["was_home"], 0)
    team_rows["away_goals_for"] = team_rows["goals_for"].where(~team_rows["was_home"], 0)
    team_rows["away_goals_against"] = team_rows["goals_against"].where(~team_rows["was_home"], 0)
    team_rows["away_clean_sheets"] = team_rows["clean_sheets"].where(~team_rows["was_home"], 0)

    return team_rows.sort_values(["team_id", "gameweek", "fixture_id"]).reset_index(drop=True)


def _team_gameweek_actuals(fixtures: pd.DataFrame) -> pd.DataFrame:
    """Aggregate team-match rows to one actual row per team-gameweek."""

    team_rows = _fixture_team_rows(fixtures)
    aggregations = {
        "team_name": "last",
        "team_short_name": "last",
        "fixture_id": "count",
        "goals_for": "sum",
        "goals_against": "sum",
        "goal_difference": "sum",
        "clean_sheets": "sum",
        "wins": "sum",
        "draws": "sum",
        "losses": "sum",
        "league_points": "sum",
        "fixture_difficulty": "mean",
        "home_matches": "sum",
        "home_goals_for": "sum",
        "home_goals_against": "sum",
        "home_clean_sheets": "sum",
        "away_matches": "sum",
        "away_goals_for": "sum",
        "away_goals_against": "sum",
        "away_clean_sheets": "sum",
    }
    actuals = (
        team_rows.groupby(["team_id", "gameweek"], as_index=False)
        .agg(aggregations)
        .rename(columns={"fixture_id": "fixtures_played"})
    )
    actuals["had_fixture"] = 1
    actuals["double_gameweek"] = (actuals["fixtures_played"] > 1).astype(int)
    return actuals


def _add_prior_rolling_features(
    df: pd.DataFrame,
    *,
    group_column: str,
    value_columns: list[str],
    windows: list[int],
) -> pd.DataFrame:
    """Add prior-only rolling sums and means for available value columns."""

    output = df.copy()
    grouped = output.groupby(group_column, sort=False)
    new_columns = {}

    for column in value_columns:
        if column not in output.columns:
            continue
        shifted = grouped[column].shift(1)
        for window in windows:
            rolling = shifted.groupby(output[group_column])
            new_columns[f"{column}_roll{window}_sum_prior"] = rolling.transform(
                lambda series: series.rolling(window=window, min_periods=1).sum()
            )
            new_columns[f"{column}_roll{window}_mean_prior"] = rolling.transform(
                lambda series: series.rolling(window=window, min_periods=1).mean()
            )

    if new_columns:
        output = pd.concat([output, pd.DataFrame(new_columns, index=output.index)], axis=1)
    return output


def build_team_strength(fixtures_df: pd.DataFrame) -> pd.DataFrame:
    """Build leakage-safe team strength rows, one team per gameweek."""

    actuals = _team_gameweek_actuals(fixtures_df)
    teams = (
        actuals[["team_id", "team_name", "team_short_name"]]
        .drop_duplicates("team_id")
        .sort_values("team_id")
        .reset_index(drop=True)
    )
    gameweeks = pd.DataFrame(
        {"gameweek": range(int(fixtures_df["event"].min()), int(fixtures_df["event"].max()) + 1)}
    )
    grid = teams.merge(gameweeks, how="cross")
    team_strength = grid.merge(actuals, on=["team_id", "team_name", "team_short_name", "gameweek"], how="left")

    fill_zero_columns = [
        "fixtures_played",
        "goals_for",
        "goals_against",
        "goal_difference",
        "clean_sheets",
        "wins",
        "draws",
        "losses",
        "league_points",
        "home_matches",
        "home_goals_for",
        "home_goals_against",
        "home_clean_sheets",
        "away_matches",
        "away_goals_for",
        "away_goals_against",
        "away_clean_sheets",
        "had_fixture",
        "double_gameweek",
    ]
    for column in fill_zero_columns:
        team_strength[column] = team_strength[column].fillna(0).astype(int)

    team_strength["fixture_difficulty"] = team_strength["fixture_difficulty"].astype(float)
    team_strength = team_strength.sort_values(["team_id", "gameweek"]).reset_index(drop=True)

    rolling_columns = [
        "fixtures_played",
        "goals_for",
        "goals_against",
        "goal_difference",
        "clean_sheets",
        "wins",
        "draws",
        "losses",
        "league_points",
        "home_matches",
        "home_goals_for",
        "home_goals_against",
        "home_clean_sheets",
        "away_matches",
        "away_goals_for",
        "away_goals_against",
        "away_clean_sheets",
    ]
    team_strength = _add_prior_rolling_features(
        team_strength,
        group_column="team_id",
        value_columns=rolling_columns,
        windows=ROLLING_WINDOWS,
    )

    grouped = team_strength.groupby("team_id", sort=False)
    cumulative_columns = {}
    for column in rolling_columns:
        cumulative_columns[f"{column}_season_to_date_prior"] = grouped[column].cumsum() - team_strength[column]
    cumulative_columns["prior_gameweeks_count"] = grouped.cumcount()
    team_strength = pd.concat([team_strength, pd.DataFrame(cumulative_columns, index=team_strength.index)], axis=1)

    team_strength["goals_for_per_fixture_prior"] = _safe_divide(
        team_strength["goals_for_season_to_date_prior"],
        team_strength["fixtures_played_season_to_date_prior"],
    )
    team_strength["goals_against_per_fixture_prior"] = _safe_divide(
        team_strength["goals_against_season_to_date_prior"],
        team_strength["fixtures_played_season_to_date_prior"],
    )
    team_strength["clean_sheet_rate_prior"] = _safe_divide(
        team_strength["clean_sheets_season_to_date_prior"],
        team_strength["fixtures_played_season_to_date_prior"],
    )
    team_strength["points_per_fixture_prior"] = _safe_divide(
        team_strength["league_points_season_to_date_prior"],
        team_strength["fixtures_played_season_to_date_prior"],
    )
    team_strength["home_goals_for_per_home_fixture_prior"] = _safe_divide(
        team_strength["home_goals_for_season_to_date_prior"],
        team_strength["home_matches_season_to_date_prior"],
    )
    team_strength["home_goals_against_per_home_fixture_prior"] = _safe_divide(
        team_strength["home_goals_against_season_to_date_prior"],
        team_strength["home_matches_season_to_date_prior"],
    )
    team_strength["home_clean_sheet_rate_prior"] = _safe_divide(
        team_strength["home_clean_sheets_season_to_date_prior"],
        team_strength["home_matches_season_to_date_prior"],
    )
    team_strength["away_goals_for_per_away_fixture_prior"] = _safe_divide(
        team_strength["away_goals_for_season_to_date_prior"],
        team_strength["away_matches_season_to_date_prior"],
    )
    team_strength["away_goals_against_per_away_fixture_prior"] = _safe_divide(
        team_strength["away_goals_against_season_to_date_prior"],
        team_strength["away_matches_season_to_date_prior"],
    )
    team_strength["away_clean_sheet_rate_prior"] = _safe_divide(
        team_strength["away_clean_sheets_season_to_date_prior"],
        team_strength["away_matches_season_to_date_prior"],
    )
    team_strength["xg_like_available"] = False

    return team_strength.sort_values(["gameweek", "team_id"]).reset_index(drop=True)
