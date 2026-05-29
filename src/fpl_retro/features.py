"""Feature engineering helpers."""

from __future__ import annotations

import pandas as pd


ROLLING_WINDOWS = [3, 5]

ROLLING_SCORING_COLUMNS = [
    "total_points",
    "minutes",
    "starts",
    "goals_scored",
    "assists",
    "clean_sheets",
    "goals_conceded",
    "saves",
    "penalties_saved",
    "penalties_missed",
    "yellow_cards",
    "red_cards",
    "own_goals",
    "bonus",
    "bps",
    "defensive_contribution",
    "clearances_blocks_interceptions",
    "recoveries",
    "tackles",
    "expected_goals",
    "expected_assists",
    "expected_goal_involvements",
    "expected_goals_conceded",
    "creativity",
    "ict_index",
    "influence",
    "threat",
]

SEASON_TO_DATE_COLUMNS = [
    "total_points",
    "minutes",
    "starts",
    "goals_scored",
    "assists",
    "clean_sheets",
    "goals_conceded",
    "saves",
    "penalties_saved",
    "penalties_missed",
    "yellow_cards",
    "red_cards",
    "own_goals",
    "bonus",
    "bps",
    "defensive_contribution",
    "clearances_blocks_interceptions",
    "recoveries",
    "tackles",
    "expected_goals",
    "expected_assists",
    "expected_goal_involvements",
    "expected_goals_conceded",
]


def _numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    """Return a numeric column, or zeros when the column is unavailable."""

    if column not in df.columns:
        return pd.Series(0, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").fillna(0)


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Divide two series and return null where the denominator is zero."""

    denominator = denominator.where(denominator != 0)
    return numerator / denominator


def add_prior_rolling_features(
    df: pd.DataFrame,
    *,
    group_column: str,
    value_columns: list[str],
    windows: list[int],
) -> pd.DataFrame:
    """Add prior-only rolling means and sums for each value column."""

    output = df.copy()
    grouped = output.groupby(group_column, sort=False)
    new_columns = {}

    for column in value_columns:
        if column not in output.columns:
            continue
        shifted = grouped[column].shift(1)
        for window in windows:
            new_columns[f"{column}_roll{window}_mean_prior"] = shifted.groupby(output[group_column]).transform(
                lambda series: series.rolling(window=window, min_periods=1).mean()
            )
            new_columns[f"{column}_roll{window}_sum_prior"] = shifted.groupby(output[group_column]).transform(
                lambda series: series.rolling(window=window, min_periods=1).sum()
            )

    if new_columns:
        output = pd.concat([output, pd.DataFrame(new_columns, index=output.index)], axis=1)

    return output


def _add_prior_season_totals(
    features: pd.DataFrame,
    *,
    group_column: str,
    value_columns: list[str],
) -> pd.DataFrame:
    """Add season-to-date prior totals for available value columns."""

    output = features.copy()
    grouped = output.groupby(group_column, sort=False)
    new_columns = {}
    rename_map = {
        "total_points": "points_season_to_date_prior",
        "expected_goal_involvements": "xgi_season_to_date_prior",
    }

    for column in value_columns:
        if column not in output.columns:
            continue
        prior_column = rename_map.get(column, f"{column}_season_to_date_prior")
        new_columns[prior_column] = grouped[column].cumsum() - output[column]

    if new_columns:
        output = pd.concat([output, pd.DataFrame(new_columns, index=output.index)], axis=1)

    return output


def _add_role_and_efficiency_features(features: pd.DataFrame) -> pd.DataFrame:
    """Add prior-only role stability, defensive threshold, and per-90 features."""

    output = features.copy()
    grouped = output.groupby("player_id", sort=False)
    role_columns = {
        "prior_gameweeks_count": grouped.cumcount(),
        "sixty_plus_minutes": (output["minutes"] >= 60).astype(int),
        "started_gameweek": (output["starts"] > 0).astype(int),
    }
    output = pd.concat([output, pd.DataFrame(role_columns, index=output.index)], axis=1)
    grouped = output.groupby("player_id", sort=False)
    output = pd.concat(
        [
            output,
            pd.DataFrame(
                {
                    "sixty_plus_season_to_date_prior": (
                        grouped["sixty_plus_minutes"].cumsum() - output["sixty_plus_minutes"]
                    ),
                    "appearances_season_to_date_prior": (
                        (output["minutes"] > 0).astype(int).groupby(output["player_id"]).cumsum()
                        - (output["minutes"] > 0).astype(int)
                    ),
                    "started_gameweeks_season_to_date_prior": (
                        grouped["started_gameweek"].cumsum() - output["started_gameweek"]
                    ),
                },
                index=output.index,
            ),
        ],
        axis=1,
    )

    rate_columns = {}
    rate_columns["start_rate_prior"] = _safe_divide(
        output["started_gameweeks_season_to_date_prior"], output["prior_gameweeks_count"]
    )
    rate_columns["appearance_rate_prior"] = _safe_divide(
        output["appearances_season_to_date_prior"], output["prior_gameweeks_count"]
    )
    rate_columns["sixty_plus_rate_prior"] = _safe_divide(
        output["sixty_plus_season_to_date_prior"], output["prior_gameweeks_count"]
    )
    output = pd.concat([output, pd.DataFrame(rate_columns, index=output.index)], axis=1)

    defender_actions = output["clearances_blocks_interceptions"] + output["tackles"]
    outfield_actions = defender_actions + output["recoveries"]
    threshold_met = pd.Series(0, index=output.index, dtype="int64")
    threshold_met.loc[output["position_short"] == "DEF"] = (defender_actions >= 10).astype(int)
    threshold_met.loc[output["position_short"].isin(["MID", "FWD"])] = (outfield_actions >= 12).astype(int)
    output = pd.concat(
        [
            output,
            pd.DataFrame({"defensive_contribution_threshold_met": threshold_met}, index=output.index),
        ],
        axis=1,
    )
    output = add_prior_rolling_features(
        output,
        group_column="player_id",
        value_columns=["defensive_contribution_threshold_met", "sixty_plus_minutes"],
        windows=ROLLING_WINDOWS,
    )
    grouped = output.groupby("player_id", sort=False)
    threshold_season_to_date_prior = (
        grouped["defensive_contribution_threshold_met"].cumsum()
        - output["defensive_contribution_threshold_met"]
    )

    per_90_sources = {
        "points_per_90_prior": "points_season_to_date_prior",
        "goals_per_90_prior": "goals_scored_season_to_date_prior",
        "assists_per_90_prior": "assists_season_to_date_prior",
        "xg_per_90_prior": "expected_goals_season_to_date_prior",
        "xa_per_90_prior": "expected_assists_season_to_date_prior",
        "xgi_per_90_prior": "xgi_season_to_date_prior",
        "bps_per_90_prior": "bps_season_to_date_prior",
        "bonus_per_90_prior": "bonus_season_to_date_prior",
        "defensive_contribution_per_90_prior": "defensive_contribution_season_to_date_prior",
        "cbi_per_90_prior": "clearances_blocks_interceptions_season_to_date_prior",
        "recoveries_per_90_prior": "recoveries_season_to_date_prior",
        "tackles_per_90_prior": "tackles_season_to_date_prior",
        "saves_per_90_prior": "saves_season_to_date_prior",
        "goals_conceded_per_90_prior": "goals_conceded_season_to_date_prior",
        "expected_goals_conceded_per_90_prior": "expected_goals_conceded_season_to_date_prior",
    }
    minutes_prior = output["minutes_season_to_date_prior"]
    derived_columns = {
        "defensive_contribution_threshold_season_to_date_prior": threshold_season_to_date_prior,
        "defensive_contribution_threshold_rate_prior": _safe_divide(
            threshold_season_to_date_prior,
            output["prior_gameweeks_count"],
        ),
    }
    for output_column, source_column in per_90_sources.items():
        if source_column in output.columns:
            derived_columns[output_column] = _safe_divide(output[source_column] * 90, minutes_prior)

    output = pd.concat([output, pd.DataFrame(derived_columns, index=output.index)], axis=1)
    return output.drop(columns=["sixty_plus_minutes", "started_gameweek"])


def build_player_gw_features(gw_live_df: pd.DataFrame) -> pd.DataFrame:
    """Build one player-gameweek table with leakage-safe historical features."""

    required_columns = {"player_id", "gameweek", "total_points", "minutes"}
    missing_columns = required_columns - set(gw_live_df.columns)
    if missing_columns:
        raise ValueError(f"missing gameweek live columns: {sorted(missing_columns)}")

    features = gw_live_df.copy()
    features["player_id"] = features["player_id"].astype(int)
    features["gameweek"] = features["gameweek"].astype(int)
    features = features.sort_values(["player_id", "gameweek"]).reset_index(drop=True)

    numeric_columns = set(ROLLING_SCORING_COLUMNS + SEASON_TO_DATE_COLUMNS)
    for column in numeric_columns:
        if column in features.columns:
            features[column] = pd.to_numeric(features[column], errors="coerce").fillna(0)

    rolling_columns = [column for column in ROLLING_SCORING_COLUMNS if column in features.columns]
    features = add_prior_rolling_features(
        features,
        group_column="player_id",
        value_columns=rolling_columns,
        windows=ROLLING_WINDOWS,
    )

    season_to_date_columns = [column for column in SEASON_TO_DATE_COLUMNS if column in features.columns]
    features = _add_prior_season_totals(
        features,
        group_column="player_id",
        value_columns=season_to_date_columns,
    )
    features = _add_role_and_efficiency_features(features)

    return features.sort_values(["gameweek", "player_id"]).reset_index(drop=True)
