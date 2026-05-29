"""Transfer outcome evaluation helpers."""

from __future__ import annotations

import pandas as pd


HORIZONS = {
    "1gw": 1,
    "3gw": 3,
    "5gw": 5,
}

PLAYER_PROCESS_COLUMNS = [
    "price",
    "total_points_roll3_mean_prior",
    "total_points_roll5_mean_prior",
    "points_season_to_date_prior",
    "minutes_roll3_mean_prior",
    "minutes_roll5_mean_prior",
    "start_rate_prior",
    "appearance_rate_prior",
    "sixty_plus_rate_prior",
    "expected_goal_involvements_roll3_mean_prior",
    "expected_goal_involvements_roll5_mean_prior",
    "xgi_season_to_date_prior",
    "goals_scored_roll5_sum_prior",
    "assists_roll5_sum_prior",
    "clean_sheets_roll5_sum_prior",
    "goals_conceded_roll5_sum_prior",
    "defensive_contribution_roll5_sum_prior",
    "defensive_contribution_threshold_rate_prior",
    "bonus_roll5_sum_prior",
    "bps_roll5_mean_prior",
    "points_per_90_prior",
    "xgi_per_90_prior",
    "defensive_contribution_per_90_prior",
    "saves_per_90_prior",
    "goals_conceded_per_90_prior",
]

TEAM_PROCESS_COLUMNS = [
    "fixtures_played_season_to_date_prior",
    "goals_for_per_fixture_prior",
    "goals_against_per_fixture_prior",
    "clean_sheet_rate_prior",
    "points_per_fixture_prior",
    "goal_difference_roll5_sum_prior",
]

FIXTURE_PROCESS_COLUMNS = [
    "fixture_count_next1",
    "fpl_difficulty_mean_next1",
    "blank_next1",
    "double_next1",
    "fixture_count_next3",
    "fpl_difficulty_mean_next3",
    "blank_next3",
    "double_next3",
    "fixture_count_next5",
    "fpl_difficulty_mean_next5",
    "blank_next5",
    "double_next5",
    "opponent_points_per_fixture_prior_mean_next3",
    "opponent_goals_for_per_fixture_prior_mean_next3",
    "opponent_goals_against_per_fixture_prior_mean_next3",
    "opponent_clean_sheet_rate_prior_mean_next3",
]

TRANSFER_DECISION_LABEL_KEYS = {
    "good_process_good_outcome",
    "good_process_bad_outcome",
    "bad_process_good_outcome",
    "bad_process_bad_outcome",
}


def _require_columns(df: pd.DataFrame, required_columns: set[str], name: str) -> None:
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"missing {name} columns: {sorted(missing_columns)}")


def _player_lookup(players_df: pd.DataFrame) -> pd.DataFrame:
    """Return static player metadata keyed by player ID."""

    _require_columns(players_df, {"id", "web_name", "team_name", "position_short"}, "players")
    columns = [
        column
        for column in ["id", "web_name", "team_name", "team_short_name", "position", "position_short"]
        if column in players_df.columns
    ]
    return (
        players_df[columns]
        .rename(columns={"id": "player_id"})
        .assign(player_id=lambda df: df["player_id"].astype(int))
        .drop_duplicates("player_id")
    )


def _points_lookup(player_gw_features_df: pd.DataFrame) -> pd.DataFrame:
    """Return player actual points by gameweek."""

    _require_columns(player_gw_features_df, {"player_id", "gameweek", "total_points"}, "player gameweek features")
    points = player_gw_features_df[["player_id", "gameweek", "total_points"]].copy()
    points["player_id"] = points["player_id"].astype(int)
    points["gameweek"] = points["gameweek"].astype(int)
    points["total_points"] = pd.to_numeric(points["total_points"], errors="coerce").fillna(0)
    return points


def _future_points(points: pd.DataFrame, player_id: int, start_gameweek: int, horizon: int | None) -> float:
    """Return player points from start gameweek over a fixed horizon or rest of season."""

    if horizon is None:
        mask = (points["player_id"].eq(int(player_id))) & (points["gameweek"].ge(int(start_gameweek)))
    else:
        end_gameweek = int(start_gameweek) + int(horizon) - 1
        mask = (
            points["player_id"].eq(int(player_id))
            & points["gameweek"].between(int(start_gameweek), int(end_gameweek))
        )
    return float(points.loc[mask, "total_points"].sum())


def build_transfer_outcome_review(
    *,
    manager_transfers_df: pd.DataFrame,
    player_gw_features_df: pd.DataFrame,
    players_df: pd.DataFrame,
    my_timeline_df: pd.DataFrame,
    manager_id: int,
) -> pd.DataFrame:
    """Build transfer-in versus transfer-out point deltas over multiple horizons."""

    _require_columns(
        manager_transfers_df,
        {"manager_id", "event", "element_in", "element_out", "element_in_cost", "element_out_cost"},
        "manager transfers",
    )
    _require_columns(
        my_timeline_df,
        {"event", "event_transfers", "event_transfers_cost", "chip_name", "transfer_count_actual"},
        "my timeline",
    )

    transfers = manager_transfers_df[manager_transfers_df["manager_id"].astype(int).eq(int(manager_id))].copy()
    if transfers.empty:
        raise ValueError(f"manager_id {int(manager_id)} not found in manager transfers")

    transfers["event"] = transfers["event"].astype(int)
    transfers["element_in"] = transfers["element_in"].astype(int)
    transfers["element_out"] = transfers["element_out"].astype(int)
    transfers = transfers.sort_values(["event", "time"] if "time" in transfers.columns else ["event"]).reset_index(
        drop=True
    )
    transfers.insert(0, "transfer_sequence", range(1, len(transfers) + 1))

    player_lookup = _player_lookup(players_df)
    points = _points_lookup(player_gw_features_df)
    max_gameweek = int(points["gameweek"].max())

    transfers = transfers.merge(
        player_lookup.add_prefix("in_").rename(columns={"in_player_id": "element_in"}),
        on="element_in",
        how="left",
        validate="many_to_one",
    ).merge(
        player_lookup.add_prefix("out_").rename(columns={"out_player_id": "element_out"}),
        on="element_out",
        how="left",
        validate="many_to_one",
    )

    timeline_columns = [
        "event",
        "event_transfers",
        "event_transfers_cost",
        "chip_name",
        "transfer_count_actual",
    ]
    transfers = transfers.merge(
        my_timeline_df[timeline_columns],
        on="event",
        how="left",
        validate="many_to_one",
    )
    transfers["chip_name"] = transfers["chip_name"].fillna("")
    transfers["is_chip_week"] = transfers["chip_name"].ne("")
    transfers["hit_cost_allocated"] = 0.0
    counted_mask = transfers["event_transfers"].fillna(0).gt(0)
    transfers.loc[counted_mask, "hit_cost_allocated"] = (
        transfers.loc[counted_mask, "event_transfers_cost"]
        / transfers.loc[counted_mask, "event_transfers"]
    )
    transfers["hit_allocation_assumption"] = (
        "event_transfers_cost evenly allocated across official counted transfers; chip-week raw transfers get 0"
    )
    transfers["remaining_gws_including_event"] = max_gameweek - transfers["event"] + 1

    for label, horizon in HORIZONS.items():
        transfers[f"points_in_{label}"] = transfers.apply(
            lambda row: _future_points(points, row["element_in"], row["event"], horizon),
            axis=1,
        )
        transfers[f"points_out_{label}"] = transfers.apply(
            lambda row: _future_points(points, row["element_out"], row["event"], horizon),
            axis=1,
        )
        transfers[f"net_points_{label}"] = transfers[f"points_in_{label}"] - transfers[f"points_out_{label}"]
        transfers[f"net_points_after_hit_{label}"] = transfers[f"net_points_{label}"] - transfers[
            "hit_cost_allocated"
        ]

    transfers["points_in_ros"] = transfers.apply(
        lambda row: _future_points(points, row["element_in"], row["event"], None),
        axis=1,
    )
    transfers["points_out_ros"] = transfers.apply(
        lambda row: _future_points(points, row["element_out"], row["event"], None),
        axis=1,
    )
    transfers["net_points_ros"] = transfers["points_in_ros"] - transfers["points_out_ros"]
    transfers["net_points_after_hit_ros"] = transfers["net_points_ros"] - transfers["hit_cost_allocated"]

    transfers["element_in_cost_value"] = transfers["element_in_cost"] / 10
    transfers["element_out_cost_value"] = transfers["element_out_cost"] / 10

    front_columns = [
        "transfer_sequence",
        "manager_id",
        "event",
        "time",
        "chip_name",
        "is_chip_week",
        "event_transfers",
        "transfer_count_actual",
        "event_transfers_cost",
        "hit_cost_allocated",
        "hit_allocation_assumption",
        "element_in",
        "in_web_name",
        "in_team_name",
        "in_position_short",
        "element_in_cost_value",
        "element_out",
        "out_web_name",
        "out_team_name",
        "out_position_short",
        "element_out_cost_value",
        "points_in_1gw",
        "points_out_1gw",
        "net_points_1gw",
        "net_points_after_hit_1gw",
        "points_in_3gw",
        "points_out_3gw",
        "net_points_3gw",
        "net_points_after_hit_3gw",
        "points_in_5gw",
        "points_out_5gw",
        "net_points_5gw",
        "net_points_after_hit_5gw",
        "points_in_ros",
        "points_out_ros",
        "net_points_ros",
        "net_points_after_hit_ros",
    ]
    ordered_columns = [column for column in front_columns if column in transfers.columns]
    ordered_columns.extend([column for column in transfers.columns if column not in ordered_columns])
    return transfers[ordered_columns].reset_index(drop=True)


def _available_columns(df: pd.DataFrame, requested_columns: list[str]) -> list[str]:
    return [column for column in requested_columns if column in df.columns]


def _prefixed_lookup(
    df: pd.DataFrame,
    *,
    key_columns: list[str],
    value_columns: list[str],
    prefix: str,
) -> pd.DataFrame:
    columns = key_columns + _available_columns(df, value_columns)
    lookup = df[columns].copy()
    rename_columns = {column: f"{prefix}{column}" for column in columns if column not in key_columns}
    return lookup.rename(columns=rename_columns).drop_duplicates(key_columns)


def _add_difference_columns(
    df: pd.DataFrame,
    *,
    feature_names: list[str],
    in_prefix: str,
    out_prefix: str,
    diff_prefix: str,
) -> pd.DataFrame:
    for feature_name in feature_names:
        in_column = f"{in_prefix}{feature_name}"
        out_column = f"{out_prefix}{feature_name}"
        if in_column in df.columns and out_column in df.columns:
            df[f"{diff_prefix}{feature_name}"] = pd.to_numeric(df[in_column], errors="coerce") - pd.to_numeric(
                df[out_column], errors="coerce"
            )
    return df


def build_transfer_process_features(
    *,
    transfer_outcomes_df: pd.DataFrame,
    player_gw_features_df: pd.DataFrame,
    team_strength_df: pd.DataFrame,
    fixture_difficulty_df: pd.DataFrame,
) -> pd.DataFrame:
    """Add leakage-safe pre-gameweek context for each transfer-in/out pair."""

    _require_columns(
        transfer_outcomes_df,
        {"transfer_sequence", "event", "element_in", "element_out", "in_team_name", "out_team_name"},
        "transfer outcomes",
    )
    _require_columns(player_gw_features_df, {"gameweek", "player_id"}, "player gameweek features")
    _require_columns(team_strength_df, {"gameweek", "team_name"}, "team strength")
    _require_columns(fixture_difficulty_df, {"gameweek", "team_name"}, "fixture difficulty")

    transfers = transfer_outcomes_df.copy()
    transfers["event"] = transfers["event"].astype(int)
    transfers["element_in"] = transfers["element_in"].astype(int)
    transfers["element_out"] = transfers["element_out"].astype(int)

    player_features = player_gw_features_df.copy()
    player_features["gameweek"] = player_features["gameweek"].astype(int)
    player_features["player_id"] = player_features["player_id"].astype(int)

    in_player_lookup = _prefixed_lookup(
        player_features,
        key_columns=["gameweek", "player_id"],
        value_columns=PLAYER_PROCESS_COLUMNS,
        prefix="in_player_",
    ).rename(columns={"gameweek": "event", "player_id": "element_in"})
    out_player_lookup = _prefixed_lookup(
        player_features,
        key_columns=["gameweek", "player_id"],
        value_columns=PLAYER_PROCESS_COLUMNS,
        prefix="out_player_",
    ).rename(columns={"gameweek": "event", "player_id": "element_out"})

    transfers = transfers.merge(in_player_lookup, on=["event", "element_in"], how="left", validate="many_to_one")
    transfers = transfers.merge(out_player_lookup, on=["event", "element_out"], how="left", validate="many_to_one")

    team_strength = team_strength_df.copy()
    team_strength["gameweek"] = team_strength["gameweek"].astype(int)
    in_team_lookup = _prefixed_lookup(
        team_strength,
        key_columns=["gameweek", "team_name"],
        value_columns=TEAM_PROCESS_COLUMNS,
        prefix="in_team_",
    ).rename(columns={"gameweek": "event", "team_name": "in_team_name"})
    out_team_lookup = _prefixed_lookup(
        team_strength,
        key_columns=["gameweek", "team_name"],
        value_columns=TEAM_PROCESS_COLUMNS,
        prefix="out_team_",
    ).rename(columns={"gameweek": "event", "team_name": "out_team_name"})

    transfers = transfers.merge(in_team_lookup, on=["event", "in_team_name"], how="left", validate="many_to_one")
    transfers = transfers.merge(out_team_lookup, on=["event", "out_team_name"], how="left", validate="many_to_one")

    fixtures = fixture_difficulty_df.copy()
    fixtures["gameweek"] = fixtures["gameweek"].astype(int)
    in_fixture_lookup = _prefixed_lookup(
        fixtures,
        key_columns=["gameweek", "team_name"],
        value_columns=FIXTURE_PROCESS_COLUMNS,
        prefix="in_fixture_",
    ).rename(columns={"gameweek": "event", "team_name": "in_team_name"})
    out_fixture_lookup = _prefixed_lookup(
        fixtures,
        key_columns=["gameweek", "team_name"],
        value_columns=FIXTURE_PROCESS_COLUMNS,
        prefix="out_fixture_",
    ).rename(columns={"gameweek": "event", "team_name": "out_team_name"})

    transfers = transfers.merge(in_fixture_lookup, on=["event", "in_team_name"], how="left", validate="many_to_one")
    transfers = transfers.merge(out_fixture_lookup, on=["event", "out_team_name"], how="left", validate="many_to_one")

    transfers = _add_difference_columns(
        transfers,
        feature_names=_available_columns(player_features, PLAYER_PROCESS_COLUMNS),
        in_prefix="in_player_",
        out_prefix="out_player_",
        diff_prefix="diff_player_",
    )
    transfers = _add_difference_columns(
        transfers,
        feature_names=_available_columns(team_strength, TEAM_PROCESS_COLUMNS),
        in_prefix="in_team_",
        out_prefix="out_team_",
        diff_prefix="diff_team_",
    )
    transfers = _add_difference_columns(
        transfers,
        feature_names=_available_columns(fixtures, FIXTURE_PROCESS_COLUMNS),
        in_prefix="in_fixture_",
        out_prefix="out_fixture_",
        diff_prefix="diff_fixture_",
    )

    transfers["process_feature_note"] = (
        "player and team process columns use prior-only features for the transfer gameweek; "
        "fixture columns describe upcoming fixtures from that gameweek"
    )
    return transfers.reset_index(drop=True)


def _threshold_score(series: pd.Series, *, positive_threshold: float, negative_threshold: float) -> pd.Series:
    score = pd.Series(0, index=series.index, dtype="int64")
    numeric = pd.to_numeric(series, errors="coerce")
    score.loc[numeric.ge(positive_threshold)] = 1
    score.loc[numeric.le(negative_threshold)] = -1
    return score


def classify_transfer_decisions(
    transfer_process_df: pd.DataFrame,
    *,
    decision_quality_labels: dict[str, str],
) -> pd.DataFrame:
    """Classify transfer decisions using transparent process and outcome rules."""

    _require_columns(
        transfer_process_df,
        {
            "transfer_sequence",
            "net_points_after_hit_5gw",
            "diff_player_total_points_roll5_mean_prior",
            "diff_player_minutes_roll5_mean_prior",
            "diff_player_xgi_per_90_prior",
            "diff_player_clean_sheets_roll5_sum_prior",
            "diff_player_goals_conceded_per_90_prior",
            "diff_player_defensive_contribution_per_90_prior",
            "diff_player_bps_roll5_mean_prior",
            "diff_player_saves_per_90_prior",
            "diff_team_points_per_fixture_prior",
            "diff_fixture_fpl_difficulty_mean_next3",
            "diff_fixture_blank_next3",
            "diff_fixture_double_next3",
            "in_position_short",
        },
        "transfer process features",
    )
    missing_label_keys = TRANSFER_DECISION_LABEL_KEYS - set(decision_quality_labels)
    if missing_label_keys:
        raise ValueError(f"missing decision quality label keys: {sorted(missing_label_keys)}")

    decisions = transfer_process_df.copy()
    decisions["process_form_score"] = _threshold_score(
        decisions["diff_player_total_points_roll5_mean_prior"],
        positive_threshold=1.0,
        negative_threshold=-1.0,
    )
    decisions["process_minutes_score"] = _threshold_score(
        decisions["diff_player_minutes_roll5_mean_prior"],
        positive_threshold=15.0,
        negative_threshold=-15.0,
    )
    decisions["process_xgi_score"] = _threshold_score(
        decisions["diff_player_xgi_per_90_prior"],
        positive_threshold=0.10,
        negative_threshold=-0.10,
    )
    decisions["process_clean_sheet_score"] = _threshold_score(
        decisions["diff_player_clean_sheets_roll5_sum_prior"],
        positive_threshold=1.0,
        negative_threshold=-1.0,
    )
    decisions["process_goals_conceded_score"] = _threshold_score(
        -decisions["diff_player_goals_conceded_per_90_prior"],
        positive_threshold=0.25,
        negative_threshold=-0.25,
    )
    decisions["process_defensive_contribution_score"] = _threshold_score(
        decisions["diff_player_defensive_contribution_per_90_prior"],
        positive_threshold=0.75,
        negative_threshold=-0.75,
    )
    decisions["process_bps_score"] = _threshold_score(
        decisions["diff_player_bps_roll5_mean_prior"],
        positive_threshold=5.0,
        negative_threshold=-5.0,
    )
    decisions["process_saves_score"] = _threshold_score(
        decisions["diff_player_saves_per_90_prior"],
        positive_threshold=1.0,
        negative_threshold=-1.0,
    )
    decisions["process_position_route_score"] = 0
    goalkeeper_mask = decisions["in_position_short"].eq("GKP")
    defender_mask = decisions["in_position_short"].eq("DEF")
    midfielder_mask = decisions["in_position_short"].eq("MID")
    forward_mask = decisions["in_position_short"].eq("FWD")
    decisions.loc[goalkeeper_mask, "process_position_route_score"] = decisions.loc[
        goalkeeper_mask,
        ["process_saves_score", "process_clean_sheet_score", "process_goals_conceded_score", "process_bps_score"],
    ].sum(axis=1)
    decisions.loc[defender_mask, "process_position_route_score"] = decisions.loc[
        defender_mask,
        [
            "process_clean_sheet_score",
            "process_goals_conceded_score",
            "process_defensive_contribution_score",
            "process_bps_score",
        ],
    ].sum(axis=1)
    decisions.loc[midfielder_mask | forward_mask, "process_position_route_score"] = decisions.loc[
        midfielder_mask | forward_mask,
        ["process_defensive_contribution_score", "process_bps_score"],
    ].sum(axis=1)
    decisions["process_position_route_score"] = decisions["process_position_route_score"].clip(lower=-3, upper=3)
    decisions["process_team_score"] = _threshold_score(
        decisions["diff_team_points_per_fixture_prior"],
        positive_threshold=0.30,
        negative_threshold=-0.30,
    )
    decisions["process_fixture_score"] = _threshold_score(
        -decisions["diff_fixture_fpl_difficulty_mean_next3"],
        positive_threshold=0.25,
        negative_threshold=-0.25,
    )
    decisions["process_blank_score"] = _threshold_score(
        -decisions["diff_fixture_blank_next3"],
        positive_threshold=1.0,
        negative_threshold=-1.0,
    )
    decisions["process_double_score"] = _threshold_score(
        decisions["diff_fixture_double_next3"],
        positive_threshold=1.0,
        negative_threshold=-1.0,
    )

    score_columns = [
        "process_form_score",
        "process_minutes_score",
        "process_xgi_score",
        "process_position_route_score",
        "process_team_score",
        "process_fixture_score",
        "process_blank_score",
        "process_double_score",
    ]
    decisions["process_score"] = decisions[score_columns].sum(axis=1)
    decisions["good_process"] = decisions["process_score"].ge(1)
    decisions["outcome_score"] = pd.to_numeric(decisions["net_points_after_hit_5gw"], errors="coerce")
    decisions["outcome_correct"] = decisions["outcome_score"].ge(0)

    decisions["decision_quality_key"] = "bad_process_bad_outcome"
    decisions.loc[decisions["good_process"] & decisions["outcome_correct"], "decision_quality_key"] = (
        "good_process_good_outcome"
    )
    decisions.loc[decisions["good_process"] & ~decisions["outcome_correct"], "decision_quality_key"] = (
        "good_process_bad_outcome"
    )
    decisions.loc[~decisions["good_process"] & decisions["outcome_correct"], "decision_quality_key"] = (
        "bad_process_good_outcome"
    )
    decisions["decision_quality_label"] = decisions["decision_quality_key"].map(decision_quality_labels)

    absolute_process = decisions["process_score"].abs()
    absolute_outcome = decisions["outcome_score"].abs()
    decisions["decision_confidence"] = "Low"
    decisions.loc[absolute_process.ge(2) | absolute_outcome.ge(5), "decision_confidence"] = "Medium"
    decisions.loc[absolute_process.ge(3) & absolute_outcome.ge(8), "decision_confidence"] = "High"
    decisions["classification_note"] = (
        "process_score uses prior player/team features, position-aware scoring routes, and upcoming fixtures; "
        "outcome_score is net_points_after_hit_5gw"
    )

    front_columns = [
        "transfer_sequence",
        "manager_id",
        "event",
        "time",
        "chip_name",
        "is_chip_week",
        "element_in",
        "in_web_name",
        "in_position_short",
        "element_out",
        "out_web_name",
        "out_position_short",
        "process_score",
        "good_process",
        "outcome_score",
        "outcome_correct",
        "decision_quality_key",
        "decision_quality_label",
        "decision_confidence",
        "classification_note",
    ]
    ordered_columns = [column for column in front_columns if column in decisions.columns]
    ordered_columns.extend([column for column in decisions.columns if column not in ordered_columns])
    return decisions[ordered_columns].reset_index(drop=True)


def _assign_decision_quality(
    df: pd.DataFrame,
    *,
    process_column: str,
    outcome_column: str,
    key_column: str,
    label_column: str,
    decision_quality_labels: dict[str, str],
) -> pd.DataFrame:
    good_process = df[process_column].ge(1)
    good_outcome = df[outcome_column].ge(0)

    df[key_column] = "bad_process_bad_outcome"
    df.loc[good_process & good_outcome, key_column] = "good_process_good_outcome"
    df.loc[good_process & ~good_outcome, key_column] = "good_process_bad_outcome"
    df.loc[~good_process & good_outcome, key_column] = "bad_process_good_outcome"
    df[label_column] = df[key_column].map(decision_quality_labels)
    return df


def build_transfer_group_decision_labels(
    transfer_decisions_df: pd.DataFrame,
    *,
    decision_quality_labels: dict[str, str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Add gameweek transfer-package labels and funding-leg flags."""

    _require_columns(
        transfer_decisions_df,
        {
            "manager_id",
            "event",
            "transfer_sequence",
            "process_score",
            "outcome_score",
            "points_in_5gw",
            "points_out_5gw",
            "net_points_5gw",
            "net_points_after_hit_5gw",
            "hit_cost_allocated",
            "element_in_cost_value",
            "element_out_cost_value",
        },
        "transfer decision labels",
    )
    missing_label_keys = TRANSFER_DECISION_LABEL_KEYS - set(decision_quality_labels)
    if missing_label_keys:
        raise ValueError(f"missing decision quality label keys: {sorted(missing_label_keys)}")

    decisions = transfer_decisions_df.copy()
    decisions["transfer_group_id"] = (
        decisions["manager_id"].astype(int).astype(str) + "_gw" + decisions["event"].astype(int).astype(str).str.zfill(2)
    )
    decisions["transfer_value_delta"] = decisions["element_in_cost_value"] - decisions["element_out_cost_value"]

    group_index = ["transfer_group_id", "manager_id", "event"]
    groups = (
        decisions.groupby(group_index, as_index=False)
        .agg(
            group_transfer_count=("transfer_sequence", "size"),
            group_first_transfer_sequence=("transfer_sequence", "min"),
            group_last_transfer_sequence=("transfer_sequence", "max"),
            group_process_score=("process_score", "sum"),
            group_outcome_score=("outcome_score", "sum"),
            group_points_in_5gw=("points_in_5gw", "sum"),
            group_points_out_5gw=("points_out_5gw", "sum"),
            group_net_points_5gw=("net_points_5gw", "sum"),
            group_net_points_after_hit_5gw=("net_points_after_hit_5gw", "sum"),
            group_hit_cost_allocated=("hit_cost_allocated", "sum"),
            group_value_delta=("transfer_value_delta", "sum"),
        )
        .sort_values(["event", "group_first_transfer_sequence"])
        .reset_index(drop=True)
    )
    groups["group_good_process"] = groups["group_process_score"].ge(1)
    groups["group_outcome_correct"] = groups["group_outcome_score"].ge(0)
    groups = _assign_decision_quality(
        groups,
        process_column="group_process_score",
        outcome_column="group_outcome_score",
        key_column="group_decision_quality_key",
        label_column="group_decision_quality_label",
        decision_quality_labels=decision_quality_labels,
    )
    groups["transfer_group_type"] = "single_transfer"
    multi_group_mask = groups["group_transfer_count"].gt(1)
    groups.loc[multi_group_mask & groups["group_value_delta"].gt(0.5), "transfer_group_type"] = "package_spent_budget"
    groups.loc[multi_group_mask & groups["group_value_delta"].lt(-0.5), "transfer_group_type"] = "package_released_budget"
    groups.loc[multi_group_mask & groups["group_value_delta"].between(-0.5, 0.5), "transfer_group_type"] = (
        "package_restructure"
    )

    absolute_group_process = groups["group_process_score"].abs()
    absolute_group_outcome = groups["group_outcome_score"].abs()
    groups["group_decision_confidence"] = "Low"
    groups.loc[absolute_group_process.ge(2) | absolute_group_outcome.ge(5), "group_decision_confidence"] = "Medium"
    groups.loc[absolute_group_process.ge(4) & absolute_group_outcome.ge(12), "group_decision_confidence"] = "High"
    groups["group_classification_note"] = (
        "transfer_group_id groups all transfer rows for the same manager and gameweek; "
        "group scores sum individual process and 5GW hit-adjusted outcome scores"
    )

    group_join_columns = [
        "transfer_group_id",
        "group_transfer_count",
        "group_process_score",
        "group_good_process",
        "group_outcome_score",
        "group_outcome_correct",
        "group_decision_quality_key",
        "group_decision_quality_label",
        "group_decision_confidence",
        "transfer_group_type",
        "group_value_delta",
        "group_net_points_after_hit_5gw",
    ]
    decisions = decisions.merge(
        groups[group_join_columns],
        on="transfer_group_id",
        how="left",
        validate="many_to_one",
    )
    decisions["possible_funding_leg"] = (
        decisions["group_transfer_count"].gt(1)
        & decisions["transfer_value_delta"].lt(-0.5)
        & decisions["process_score"].lt(0)
        & (decisions["group_good_process"] | decisions["group_outcome_correct"])
    )
    decisions["individual_vs_group_note"] = "single-transfer group"
    decisions.loc[decisions["group_transfer_count"].gt(1), "individual_vs_group_note"] = "part of multi-transfer package"
    decisions.loc[decisions["possible_funding_leg"], "individual_vs_group_note"] = (
        "possible funding leg: individual downgrade inside non-negative group context"
    )

    front_columns = [
        "transfer_sequence",
        "transfer_group_id",
        "manager_id",
        "event",
        "time",
        "chip_name",
        "is_chip_week",
        "element_in",
        "in_web_name",
        "element_out",
        "out_web_name",
        "transfer_value_delta",
        "process_score",
        "outcome_score",
        "decision_quality_label",
        "group_transfer_count",
        "group_process_score",
        "group_outcome_score",
        "group_decision_quality_label",
        "transfer_group_type",
        "group_value_delta",
        "possible_funding_leg",
        "individual_vs_group_note",
    ]
    ordered_columns = [column for column in front_columns if column in decisions.columns]
    ordered_columns.extend([column for column in decisions.columns if column not in ordered_columns])
    return decisions[ordered_columns].reset_index(drop=True), groups.reset_index(drop=True)
