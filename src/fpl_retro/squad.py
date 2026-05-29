"""Squad reconstruction helpers for the focal manager."""

from __future__ import annotations

import pandas as pd


def _require_columns(df: pd.DataFrame, required_columns: set[str], name: str) -> None:
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"missing {name} columns: {sorted(missing_columns)}")


def _team_lookup(teams_df: pd.DataFrame) -> pd.DataFrame:
    """Return team IDs keyed by team short name."""

    _require_columns(teams_df, {"id", "short_name", "name"}, "teams")
    return (
        teams_df[["id", "short_name", "name"]]
        .rename(columns={"id": "team_id", "short_name": "team_short_name", "name": "team_lookup_name"})
        .assign(team_id=lambda df: df["team_id"].astype(int))
        .drop_duplicates("team_short_name")
    )


def _player_feature_columns(player_gw_features_df: pd.DataFrame) -> list[str]:
    """Select current outcome and prior-only player columns for squad reconstruction."""

    identity_columns = [
        "player_id",
        "gameweek",
        "web_name",
        "team_name",
        "position",
        "position_short",
        "price",
        "team_short_name",
    ]
    current_outcome_columns = [
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
    prior_columns = [column for column in player_gw_features_df.columns if column.endswith("_prior")]
    selected = identity_columns + current_outcome_columns + prior_columns
    return [column for column in selected if column in player_gw_features_df.columns]


def _prefix_feature_columns(
    df: pd.DataFrame,
    *,
    key_columns: set[str],
    prefix: str,
) -> pd.DataFrame:
    """Prefix non-key columns for clear feature provenance."""

    rename_map = {column: f"{prefix}{column}" for column in df.columns if column not in key_columns}
    return df.rename(columns=rename_map)


def build_my_squad_gameweek(
    *,
    manager_picks_df: pd.DataFrame,
    player_gw_features_df: pd.DataFrame,
    team_strength_df: pd.DataFrame,
    fixture_difficulty_df: pd.DataFrame,
    teams_df: pd.DataFrame,
    manager_id: int,
) -> pd.DataFrame:
    """Build one row per player per gameweek for the focal manager squad."""

    _require_columns(
        manager_picks_df,
        {"manager_id", "event", "element", "position", "multiplier", "is_captain", "is_vice_captain"},
        "manager picks",
    )
    _require_columns(player_gw_features_df, {"player_id", "gameweek", "total_points"}, "player features")
    _require_columns(team_strength_df, {"team_id", "gameweek"}, "team strength")
    _require_columns(fixture_difficulty_df, {"team_id", "gameweek"}, "fixture difficulty")

    squad = manager_picks_df[manager_picks_df["manager_id"].astype(int).eq(int(manager_id))].copy()
    if squad.empty:
        raise ValueError(f"manager_id {int(manager_id)} not found in manager picks")

    squad["manager_id"] = squad["manager_id"].astype(int)
    squad["event"] = squad["event"].astype(int)
    squad["element"] = squad["element"].astype(int)
    squad["position"] = squad["position"].astype(int)
    squad["multiplier"] = squad["multiplier"].astype(int)
    squad["is_starter"] = squad["position"] <= 11
    squad["is_bench"] = ~squad["is_starter"]
    squad["squad_position"] = squad["position"]

    player_features = player_gw_features_df[_player_feature_columns(player_gw_features_df)].rename(
        columns={"player_id": "element", "gameweek": "event"}
    )
    player_features["element"] = player_features["element"].astype(int)
    player_features["event"] = player_features["event"].astype(int)
    player_features = player_features.merge(_team_lookup(teams_df), on="team_short_name", how="left")
    player_features = _prefix_feature_columns(
        player_features,
        key_columns={"element", "event", "team_id"},
        prefix="player_",
    )

    squad = squad.merge(player_features, on=["element", "event"], how="left", validate="many_to_one")
    squad["actual_points"] = squad["player_total_points"]
    squad["points_after_multiplier"] = squad["actual_points"] * squad["multiplier"]

    team_prior_columns = [
        "team_id",
        "gameweek",
        *[column for column in team_strength_df.columns if column.endswith("_prior")],
        "xg_like_available",
    ]
    team_features = team_strength_df[[column for column in team_prior_columns if column in team_strength_df.columns]]
    team_features = _prefix_feature_columns(
        team_features.rename(columns={"gameweek": "event"}),
        key_columns={"team_id", "event"},
        prefix="team_",
    )
    squad = squad.merge(team_features, on=["team_id", "event"], how="left", validate="many_to_one")

    fixture_features = _prefix_feature_columns(
        fixture_difficulty_df.rename(columns={"gameweek": "event"}),
        key_columns={"team_id", "event"},
        prefix="fixture_",
    )
    squad = squad.merge(fixture_features, on=["team_id", "event"], how="left", validate="many_to_one")

    front_columns = [
        "manager_id",
        "event",
        "element",
        "player_web_name",
        "player_team_name",
        "player_team_short_name",
        "team_id",
        "player_position",
        "player_position_short",
        "squad_position",
        "is_starter",
        "is_bench",
        "is_captain",
        "is_vice_captain",
        "multiplier",
        "actual_points",
        "points_after_multiplier",
        "player_minutes",
        "player_price",
    ]
    ordered_columns = [column for column in front_columns if column in squad.columns]
    ordered_columns.extend([column for column in squad.columns if column not in ordered_columns])
    return squad[ordered_columns].sort_values(["event", "squad_position"]).reset_index(drop=True)
