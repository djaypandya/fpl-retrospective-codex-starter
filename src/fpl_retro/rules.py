"""Candidate rule feature helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd


ID_COLUMNS = [
    "gameweek",
    "player_id",
    "web_name",
    "team_name",
    "position",
    "position_short",
]

PLAYER_FEATURE_COLUMNS = [
    "price",
    "total_points_roll3_mean_prior",
    "total_points_roll5_mean_prior",
    "points_season_to_date_prior",
    "points_per_90_prior",
    "minutes_roll3_mean_prior",
    "minutes_roll5_mean_prior",
    "minutes_season_to_date_prior",
    "start_rate_prior",
    "appearance_rate_prior",
    "sixty_plus_rate_prior",
    "goals_scored_roll5_sum_prior",
    "assists_roll5_sum_prior",
    "expected_goals_roll5_mean_prior",
    "expected_assists_roll5_mean_prior",
    "expected_goal_involvements_roll5_mean_prior",
    "xgi_season_to_date_prior",
    "goals_per_90_prior",
    "assists_per_90_prior",
    "xg_per_90_prior",
    "xa_per_90_prior",
    "xgi_per_90_prior",
    "clean_sheets_roll5_sum_prior",
    "goals_conceded_roll5_sum_prior",
    "goals_conceded_per_90_prior",
    "expected_goals_conceded_per_90_prior",
    "saves_roll5_sum_prior",
    "penalties_saved_roll5_sum_prior",
    "saves_per_90_prior",
    "bonus_roll5_sum_prior",
    "bps_roll5_mean_prior",
    "bps_per_90_prior",
    "bonus_per_90_prior",
    "defensive_contribution_roll5_sum_prior",
    "defensive_contribution_threshold_rate_prior",
    "defensive_contribution_per_90_prior",
    "cbi_per_90_prior",
    "recoveries_per_90_prior",
    "tackles_per_90_prior",
    "yellow_cards_roll5_sum_prior",
    "red_cards_roll5_sum_prior",
    "own_goals_roll5_sum_prior",
    "penalties_missed_roll5_sum_prior",
    "prior_gameweeks_count",
]

TEAM_FEATURE_COLUMNS = [
    "fixtures_played_season_to_date_prior",
    "goals_for_per_fixture_prior",
    "goals_against_per_fixture_prior",
    "clean_sheet_rate_prior",
    "points_per_fixture_prior",
    "goals_for_roll5_mean_prior",
    "goals_against_roll5_mean_prior",
    "clean_sheets_roll5_mean_prior",
    "league_points_roll5_mean_prior",
]

FIXTURE_FEATURE_PREFIXES = (
    "fixture_count_next",
    "fpl_difficulty_mean_next",
    "fpl_difficulty_max_next",
    "home_fixture_count_next",
    "away_fixture_count_next",
    "blank_gameweeks_next",
    "double_gameweeks_next",
    "blank_next",
    "double_next",
    "opponent_goals_for_per_fixture_prior_mean_next",
    "opponent_goals_against_per_fixture_prior_mean_next",
    "opponent_clean_sheet_rate_prior_mean_next",
    "opponent_points_per_fixture_prior_mean_next",
)

OUTCOME_WINDOWS = [1, 3, 5]

MIN_RULE_SAMPLE_SIZE = 30


def _available(columns: list[str], df: pd.DataFrame) -> list[str]:
    """Return columns that are present in a dataframe."""

    return [column for column in columns if column in df.columns]


def _mean_of_columns(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    """Average available numeric columns row-wise."""

    available_columns = _available(columns, df)
    if not available_columns:
        return pd.Series(np.nan, index=df.index, dtype="float64")
    numeric = df[available_columns].apply(pd.to_numeric, errors="coerce")
    return numeric.mean(axis=1)


def _price_band(price: pd.Series) -> pd.Series:
    """Create broad FPL price bands from displayed player prices."""

    return pd.cut(
        pd.to_numeric(price, errors="coerce"),
        bins=[0, 4.5, 6.0, 8.0, np.inf],
        labels=["budget", "mid_price", "expensive", "premium"],
        right=False,
    ).astype("string")


def _add_future_outcomes(features: pd.DataFrame) -> pd.DataFrame:
    """Add future outcome windows from current gameweek onward."""

    output = features.sort_values(["player_id", "gameweek"]).copy()
    grouped = output.groupby("player_id", sort=False)
    additions: dict[str, pd.Series] = {}

    for window in OUTCOME_WINDOWS:
        for source, stem in [
            ("total_points", "points"),
            ("minutes", "minutes"),
            ("starts", "starts"),
        ]:
            if source not in output.columns:
                continue
            additions[f"outcome_{stem}_next{window}"] = grouped[source].transform(
                lambda series: series.iloc[::-1].rolling(window=window, min_periods=1).sum().iloc[::-1]
            )
        additions[f"outcome_gameweeks_available_next{window}"] = grouped["gameweek"].transform(
            lambda series: pd.Series(1, index=series.index)
            .iloc[::-1]
            .rolling(window=window, min_periods=1)
            .sum()
            .iloc[::-1]
        )

    return pd.concat([output, pd.DataFrame(additions, index=output.index)], axis=1)


def _add_route_features(features: pd.DataFrame) -> pd.DataFrame:
    """Add position-aware scoring route features using pre-GW inputs only."""

    output = features.copy()
    route_columns = {
        "feature_route_attacking_score": [
            "feature_player_goals_scored_roll5_sum_prior",
            "feature_player_assists_roll5_sum_prior",
            "feature_player_expected_goal_involvements_roll5_mean_prior",
            "feature_player_xgi_per_90_prior",
        ],
        "feature_route_clean_sheet_score": [
            "feature_player_clean_sheets_roll5_sum_prior",
            "feature_team_clean_sheet_rate_prior",
            "feature_fixture_opponent_goals_for_per_fixture_prior_mean_next3",
        ],
        "feature_route_defensive_contribution_score": [
            "feature_player_defensive_contribution_roll5_sum_prior",
            "feature_player_defensive_contribution_threshold_rate_prior",
            "feature_player_defensive_contribution_per_90_prior",
            "feature_player_cbi_per_90_prior",
            "feature_player_recoveries_per_90_prior",
            "feature_player_tackles_per_90_prior",
        ],
        "feature_route_goalkeeper_save_score": [
            "feature_player_saves_roll5_sum_prior",
            "feature_player_saves_per_90_prior",
            "feature_player_penalties_saved_roll5_sum_prior",
        ],
        "feature_route_bps_bonus_score": [
            "feature_player_bps_roll5_mean_prior",
            "feature_player_bonus_roll5_sum_prior",
            "feature_player_bps_per_90_prior",
            "feature_player_bonus_per_90_prior",
        ],
        "feature_route_discipline_risk_score": [
            "feature_player_yellow_cards_roll5_sum_prior",
            "feature_player_red_cards_roll5_sum_prior",
            "feature_player_own_goals_roll5_sum_prior",
            "feature_player_penalties_missed_roll5_sum_prior",
        ],
        "feature_route_availability_score": [
            "feature_player_minutes_roll5_mean_prior",
            "feature_player_start_rate_prior",
            "feature_player_appearance_rate_prior",
            "feature_player_sixty_plus_rate_prior",
        ],
    }
    for output_column, source_columns in route_columns.items():
        output[output_column] = _mean_of_columns(output, source_columns)

    position_route_weights = {
        "GKP": {
            "feature_route_goalkeeper_save_score": 0.30,
            "feature_route_clean_sheet_score": 0.25,
            "feature_route_bps_bonus_score": 0.20,
            "feature_route_availability_score": 0.20,
            "feature_route_discipline_risk_score": -0.05,
        },
        "DEF": {
            "feature_route_clean_sheet_score": 0.30,
            "feature_route_defensive_contribution_score": 0.25,
            "feature_route_attacking_score": 0.20,
            "feature_route_bps_bonus_score": 0.15,
            "feature_route_availability_score": 0.15,
            "feature_route_discipline_risk_score": -0.05,
        },
        "MID": {
            "feature_route_attacking_score": 0.35,
            "feature_route_defensive_contribution_score": 0.20,
            "feature_route_bps_bonus_score": 0.20,
            "feature_route_availability_score": 0.20,
            "feature_route_clean_sheet_score": 0.10,
            "feature_route_discipline_risk_score": -0.05,
        },
        "FWD": {
            "feature_route_attacking_score": 0.45,
            "feature_route_bps_bonus_score": 0.20,
            "feature_route_availability_score": 0.20,
            "feature_route_defensive_contribution_score": 0.10,
            "feature_route_discipline_risk_score": -0.05,
        },
    }
    weighted_scores = pd.Series(np.nan, index=output.index, dtype="float64")
    for position, weights in position_route_weights.items():
        mask = output["position_short"].eq(position)
        if not mask.any():
            continue
        score = pd.Series(0.0, index=output.index)
        weight_total = 0.0
        for column, weight in weights.items():
            if column in output.columns:
                score = score + output[column].fillna(0) * weight
                weight_total += abs(weight)
        if weight_total:
            weighted_scores.loc[mask] = score.loc[mask] / weight_total
    output["feature_position_relevant_route_score"] = weighted_scores

    return output


def _prior_sample_ownership(manager_picks_df: pd.DataFrame) -> pd.DataFrame:
    """Infer previous-gameweek ownership from cached manager picks."""

    required_columns = {"manager_id", "event", "element"}
    missing_columns = required_columns - set(manager_picks_df.columns)
    if missing_columns:
        raise ValueError(f"missing manager picks columns: {sorted(missing_columns)}")

    picks = manager_picks_df[list(required_columns)].dropna(subset=["manager_id", "event", "element"]).copy()
    picks["manager_id"] = picks["manager_id"].astype(int)
    picks["event"] = picks["event"].astype(int)
    picks["element"] = picks["element"].astype(int)

    ownership = (
        picks.groupby(["event", "element"], as_index=False)["manager_id"]
        .nunique()
        .rename(
            columns={
                "event": "prior_event",
                "element": "player_id",
                "manager_id": "feature_prior_sample_owner_count",
            }
        )
    )
    manager_counts = (
        picks.groupby("event", as_index=False)["manager_id"]
        .nunique()
        .rename(
            columns={
                "event": "prior_event",
                "manager_id": "feature_prior_sample_manager_count",
            }
        )
    )
    ownership = ownership.merge(manager_counts, on="prior_event", how="left", validate="many_to_one")
    ownership["gameweek"] = ownership["prior_event"] + 1
    ownership["feature_prior_sample_ownership_percent"] = (
        ownership["feature_prior_sample_owner_count"]
        / ownership["feature_prior_sample_manager_count"]
        * 100
    )
    return ownership[
        [
            "player_id",
            "gameweek",
            "feature_prior_sample_owner_count",
            "feature_prior_sample_manager_count",
            "feature_prior_sample_ownership_percent",
        ]
    ]


def build_candidate_rule_features(
    player_gw_features_df: pd.DataFrame,
    team_strength_df: pd.DataFrame,
    fixture_difficulty_df: pd.DataFrame,
    manager_picks_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build one leakage-safe candidate rule row per player-gameweek."""

    required_player_columns = {"gameweek", "player_id", "team_name", "position_short", "total_points"}
    missing_player_columns = required_player_columns - set(player_gw_features_df.columns)
    if missing_player_columns:
        raise ValueError(f"missing player feature columns: {sorted(missing_player_columns)}")

    output = player_gw_features_df.copy()
    output["gameweek"] = output["gameweek"].astype(int)

    team_columns = ["team_name", "gameweek", *_available(TEAM_FEATURE_COLUMNS, team_strength_df)]
    output = output.merge(
        team_strength_df[team_columns],
        on=["team_name", "gameweek"],
        how="left",
        validate="many_to_one",
        suffixes=("", "_team"),
    )

    fixture_columns = [
        column
        for column in fixture_difficulty_df.columns
        if column in {"team_name", "gameweek"}
        or any(column.startswith(prefix) for prefix in FIXTURE_FEATURE_PREFIXES)
    ]
    output = output.merge(
        fixture_difficulty_df[fixture_columns],
        on=["team_name", "gameweek"],
        how="left",
        validate="many_to_one",
        suffixes=("", "_fixture"),
    )

    feature_frames = [
        output[_available(ID_COLUMNS, output)],
        output[_available(PLAYER_FEATURE_COLUMNS, output)].add_prefix("feature_player_"),
        output[_available(TEAM_FEATURE_COLUMNS, output)].add_prefix("feature_team_"),
    ]
    fixture_feature_columns = [
        column
        for column in output.columns
        if any(column.startswith(prefix) for prefix in FIXTURE_FEATURE_PREFIXES)
    ]
    if fixture_feature_columns:
        feature_frames.append(output[fixture_feature_columns].add_prefix("feature_fixture_"))

    candidate = pd.concat(feature_frames, axis=1)
    candidate["feature_price_band"] = _price_band(candidate["feature_player_price"])
    candidate["feature_position"] = candidate["position_short"]
    for band in ["budget", "mid_price", "expensive", "premium"]:
        candidate[f"feature_price_band_{band}"] = candidate["feature_price_band"].eq(band).astype(int)

    if manager_picks_df is not None and not manager_picks_df.empty:
        ownership = _prior_sample_ownership(manager_picks_df)
        candidate = candidate.merge(ownership, on=["player_id", "gameweek"], how="left", validate="one_to_one")
        candidate["feature_prior_sample_manager_count"] = candidate.groupby("gameweek")[
            "feature_prior_sample_manager_count"
        ].transform("max")
        has_prior_sample = candidate["feature_prior_sample_manager_count"].notna()
        candidate.loc[has_prior_sample, "feature_prior_sample_owner_count"] = candidate.loc[
            has_prior_sample, "feature_prior_sample_owner_count"
        ].fillna(0)
        candidate.loc[has_prior_sample, "feature_prior_sample_ownership_percent"] = candidate.loc[
            has_prior_sample, "feature_prior_sample_ownership_percent"
        ].fillna(0)
        candidate["feature_ownership_percent_prior"] = candidate["feature_prior_sample_ownership_percent"]
        candidate["feature_ownership_available"] = candidate["feature_ownership_percent_prior"].notna()
        candidate["feature_ownership_source"] = np.where(
            candidate["feature_ownership_available"],
            "prior_top_sample_picks",
            "unavailable",
        )
    else:
        candidate["feature_prior_sample_owner_count"] = np.nan
        candidate["feature_prior_sample_manager_count"] = np.nan
        candidate["feature_prior_sample_ownership_percent"] = np.nan
        candidate["feature_ownership_percent_prior"] = np.nan
        candidate["feature_ownership_available"] = False
        candidate["feature_ownership_source"] = "unavailable"

    candidate = _add_route_features(candidate)

    source_outcomes = output[["player_id", "gameweek", "total_points", "minutes", "starts"]].copy()
    future_outcomes = _add_future_outcomes(source_outcomes).drop(columns=["total_points", "minutes", "starts"])
    candidate = candidate.merge(future_outcomes, on=["player_id", "gameweek"], how="left", validate="one_to_one")

    feature_columns = [column for column in candidate.columns if column.startswith("feature_")]
    outcome_columns = [column for column in candidate.columns if column.startswith("outcome_")]
    candidate["feature_column_count"] = len(feature_columns)
    candidate["outcome_column_count"] = len(outcome_columns)

    return candidate.sort_values(["gameweek", "team_name", "player_id"]).reset_index(drop=True)


def validate_candidate_rule_features(candidate_rule_features: pd.DataFrame) -> dict[str, object]:
    """Run lightweight validation checks for the candidate rule table."""

    required_route_columns = {
        "feature_route_attacking_score",
        "feature_route_clean_sheet_score",
        "feature_route_defensive_contribution_score",
        "feature_route_goalkeeper_save_score",
        "feature_route_bps_bonus_score",
        "feature_route_discipline_risk_score",
        "feature_route_availability_score",
        "feature_position_relevant_route_score",
    }
    required_outcomes = {f"outcome_points_next{window}" for window in OUTCOME_WINDOWS}
    missing_routes = sorted(required_route_columns - set(candidate_rule_features.columns))
    missing_outcomes = sorted(required_outcomes - set(candidate_rule_features.columns))

    feature_columns = [column for column in candidate_rule_features.columns if column.startswith("feature_")]
    forbidden_exact_features = {
        "feature_total_points",
        "feature_minutes",
        "feature_starts",
        "feature_player_total_points",
        "feature_player_minutes",
        "feature_player_starts",
    }
    leaked_features = sorted(forbidden_exact_features & set(feature_columns))
    duplicated_keys = int(candidate_rule_features.duplicated(["player_id", "gameweek"]).sum())

    return {
        "rows": int(len(candidate_rule_features)),
        "columns": int(candidate_rule_features.shape[1]),
        "feature_columns": int(len(feature_columns)),
        "outcome_columns": int(
            len([column for column in candidate_rule_features.columns if column.startswith("outcome_")])
        ),
        "missing_route_columns": missing_routes,
        "missing_outcome_columns": missing_outcomes,
        "leaked_feature_columns": leaked_features,
        "duplicated_player_gameweeks": duplicated_keys,
        "ownership_available": bool(candidate_rule_features["feature_ownership_available"].any()),
        "ownership_source_values": sorted(candidate_rule_features["feature_ownership_source"].dropna().unique()),
    }


def _position_gameweek_quantile(df: pd.DataFrame, column: str, quantile: float) -> pd.Series:
    """Return a same-position, same-gameweek quantile for a feature column."""

    if column not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype="float64")
    return df.groupby(["gameweek", "position_short"])[column].transform(lambda values: values.quantile(quantile))


def _confidence_label(sample_size: int, mean_uplift_next3: float, mean_uplift_next5: float) -> str:
    """Assign a simple confidence label based on sample size and consistency."""

    if pd.isna(mean_uplift_next3) or pd.isna(mean_uplift_next5):
        return "Low"
    same_direction = (mean_uplift_next3 >= 0 and mean_uplift_next5 >= 0) or (
        mean_uplift_next3 <= 0 and mean_uplift_next5 <= 0
    )
    if sample_size >= 500 and same_direction and abs(mean_uplift_next5) >= 0.5:
        return "High"
    if sample_size >= 150 and same_direction and abs(mean_uplift_next5) >= 0.2:
        return "Medium"
    return "Low"


def _add_position_baselines(df: pd.DataFrame) -> pd.DataFrame:
    """Add same-position, same-gameweek outcome baselines."""

    output = df.copy()
    for window in OUTCOME_WINDOWS:
        outcome_column = f"outcome_points_next{window}"
        baseline_column = f"baseline_position_points_next{window}"
        uplift_column = f"uplift_vs_position_baseline_next{window}"
        output[baseline_column] = output.groupby(["gameweek", "position_short"])[outcome_column].transform("mean")
        output[uplift_column] = output[outcome_column] - output[baseline_column]
    return output


def add_player_selection_rule_flags(candidate_rule_features: pd.DataFrame) -> pd.DataFrame:
    """Add transparent binary player-selection rule flags."""

    output = candidate_rule_features.copy()
    q75_columns = [
        "feature_player_total_points_roll5_mean_prior",
        "feature_player_expected_goal_involvements_roll5_mean_prior",
        "feature_position_relevant_route_score",
        "feature_route_attacking_score",
        "feature_route_clean_sheet_score",
        "feature_route_defensive_contribution_score",
        "feature_route_goalkeeper_save_score",
        "feature_route_bps_bonus_score",
        "feature_ownership_percent_prior",
        "feature_team_points_per_fixture_prior",
    ]
    q25_columns = ["feature_route_discipline_risk_score"]
    for column in q75_columns:
        output[f"threshold_q75_{column}"] = _position_gameweek_quantile(output, column, 0.75)
    for column in q25_columns:
        output[f"threshold_q25_{column}"] = _position_gameweek_quantile(output, column, 0.25)

    output["rule_secure_minutes"] = (
        (output["feature_player_minutes_roll5_mean_prior"] >= 60)
        & (output["feature_player_start_rate_prior"] >= 0.70)
    )
    output["rule_strong_recent_points"] = (
        output["feature_player_total_points_roll5_mean_prior"]
        >= output["threshold_q75_feature_player_total_points_roll5_mean_prior"]
    )
    output["rule_strong_xgi_proxy"] = (
        output["feature_player_expected_goal_involvements_roll5_mean_prior"]
        >= output["threshold_q75_feature_player_expected_goal_involvements_roll5_mean_prior"]
    )
    output["rule_strong_position_route_score"] = (
        output["feature_position_relevant_route_score"]
        >= output["threshold_q75_feature_position_relevant_route_score"]
    )
    output["rule_good_fixture_next3"] = (
        (output["feature_fixture_fixture_count_next3"] >= 3)
        & (output["feature_fixture_blank_next3"] == 0)
        & (output["feature_fixture_fpl_difficulty_mean_next3"] <= 3.0)
    )
    output["rule_double_next3"] = output["feature_fixture_double_next3"] == 1
    output["rule_popular_in_top_sample"] = (
        output["feature_ownership_available"]
        & (
            output["feature_ownership_percent_prior"]
            >= output["threshold_q75_feature_ownership_percent_prior"]
        )
    )
    output["rule_strong_team"] = (
        output["feature_team_points_per_fixture_prior"]
        >= output["threshold_q75_feature_team_points_per_fixture_prior"]
    )
    output["rule_budget_minutes"] = (
        output["feature_price_band"].eq("budget") & output["rule_secure_minutes"]
    )
    output["rule_premium_secure_route"] = (
        output["feature_price_band"].eq("premium")
        & output["rule_secure_minutes"]
        & output["rule_strong_position_route_score"]
    )
    output["rule_attacking_route_high"] = (
        output["feature_position"].isin(["DEF", "MID", "FWD"])
        & (
            output["feature_route_attacking_score"]
            >= output["threshold_q75_feature_route_attacking_score"]
        )
    )
    output["rule_clean_sheet_route_high"] = (
        output["feature_position"].isin(["GKP", "DEF"])
        & (
            output["feature_route_clean_sheet_score"]
            >= output["threshold_q75_feature_route_clean_sheet_score"]
        )
    )
    output["rule_defensive_contribution_route_high"] = (
        output["feature_position"].isin(["DEF", "MID", "FWD"])
        & (
            output["feature_route_defensive_contribution_score"]
            >= output["threshold_q75_feature_route_defensive_contribution_score"]
        )
    )
    output["rule_goalkeeper_save_route_high"] = (
        output["feature_position"].eq("GKP")
        & (
            output["feature_route_goalkeeper_save_score"]
            >= output["threshold_q75_feature_route_goalkeeper_save_score"]
        )
    )
    output["rule_bps_bonus_route_high"] = (
        output["feature_route_bps_bonus_score"]
        >= output["threshold_q75_feature_route_bps_bonus_score"]
    )
    output["rule_low_discipline_risk"] = (
        output["feature_route_discipline_risk_score"]
        <= output["threshold_q25_feature_route_discipline_risk_score"]
    )

    rule_columns = [column for column in output.columns if column.startswith("rule_")]
    output[rule_columns] = output[rule_columns].fillna(False).astype(bool)
    return output


PLAYER_SELECTION_RULES = [
    ("rule_secure_minutes", "Secure minutes", "availability", {"GKP", "DEF", "MID", "FWD"}),
    ("rule_strong_recent_points", "Strong recent points", "form", {"GKP", "DEF", "MID", "FWD"}),
    ("rule_strong_xgi_proxy", "Strong xGI proxy", "attacking", {"DEF", "MID", "FWD"}),
    (
        "rule_strong_position_route_score",
        "Strong position-relevant route score",
        "position_route",
        {"GKP", "DEF", "MID", "FWD"},
    ),
    ("rule_good_fixture_next3", "Good next-3 fixture run", "fixtures", {"GKP", "DEF", "MID", "FWD"}),
    ("rule_double_next3", "Double gameweek in next 3", "fixtures", {"GKP", "DEF", "MID", "FWD"}),
    ("rule_popular_in_top_sample", "Popular in top sample", "ownership", {"GKP", "DEF", "MID", "FWD"}),
    ("rule_strong_team", "Strong prior team", "team_strength", {"GKP", "DEF", "MID", "FWD"}),
    ("rule_budget_minutes", "Budget player with secure minutes", "price", {"GKP", "DEF", "MID", "FWD"}),
    ("rule_premium_secure_route", "Premium with secure route score", "price", {"GKP", "DEF", "MID", "FWD"}),
    ("rule_attacking_route_high", "High attacking route score", "attacking", {"DEF", "MID", "FWD"}),
    ("rule_clean_sheet_route_high", "High clean-sheet route score", "clean_sheet", {"GKP", "DEF"}),
    (
        "rule_defensive_contribution_route_high",
        "High defensive-contribution route score",
        "defensive_contribution",
        {"DEF", "MID", "FWD"},
    ),
    ("rule_goalkeeper_save_route_high", "High goalkeeper-save route score", "goalkeeper_save", {"GKP"}),
    ("rule_bps_bonus_route_high", "High BPS/bonus route score", "bps_bonus", {"GKP", "DEF", "MID", "FWD"}),
    ("rule_low_discipline_risk", "Low discipline risk", "discipline", {"GKP", "DEF", "MID", "FWD"}),
]


def build_player_selection_rule_results(candidate_rule_features: pd.DataFrame) -> pd.DataFrame:
    """Evaluate transparent player-selection rules by position."""

    required_columns = {
        "gameweek",
        "player_id",
        "position_short",
        *{f"outcome_points_next{window}" for window in OUTCOME_WINDOWS},
    }
    missing_columns = required_columns - set(candidate_rule_features.columns)
    if missing_columns:
        raise ValueError(f"missing candidate rule columns: {sorted(missing_columns)}")

    flagged = _add_position_baselines(add_player_selection_rule_flags(candidate_rule_features))
    results = []
    for rule_id, rule_name, route_family, allowed_positions in PLAYER_SELECTION_RULES:
        if rule_id not in flagged.columns:
            continue
        for position in sorted(allowed_positions):
            position_rows = flagged[flagged["position_short"].eq(position)]
            rule_rows = position_rows[position_rows[rule_id]]
            sample_size = int(len(rule_rows))
            baseline_size = int(len(position_rows))
            if sample_size < MIN_RULE_SAMPLE_SIZE:
                continue

            row = {
                "rule_id": rule_id,
                "rule_name": rule_name,
                "route_family": route_family,
                "position_short": position,
                "sample_size": sample_size,
                "position_baseline_sample_size": baseline_size,
                "flagged_share_of_position_rows": sample_size / baseline_size if baseline_size else np.nan,
            }
            for window in OUTCOME_WINDOWS:
                outcome_column = f"outcome_points_next{window}"
                baseline_column = f"baseline_position_points_next{window}"
                uplift_column = f"uplift_vs_position_baseline_next{window}"
                row[f"mean_points_next{window}"] = rule_rows[outcome_column].mean()
                row[f"median_points_next{window}"] = rule_rows[outcome_column].median()
                row[f"position_baseline_mean_points_next{window}"] = position_rows[outcome_column].mean()
                row[f"mean_position_gameweek_baseline_next{window}"] = rule_rows[baseline_column].mean()
                row[f"mean_uplift_vs_position_baseline_next{window}"] = rule_rows[uplift_column].mean()
            row["confidence"] = _confidence_label(
                sample_size,
                row["mean_uplift_vs_position_baseline_next3"],
                row["mean_uplift_vs_position_baseline_next5"],
            )
            results.append(row)

    output = pd.DataFrame(results)
    if output.empty:
        return output

    return output.sort_values(
        ["confidence", "mean_uplift_vs_position_baseline_next5", "sample_size"],
        ascending=[True, False, False],
    ).reset_index(drop=True)


def validate_player_selection_rule_results(rule_results: pd.DataFrame) -> dict[str, object]:
    """Run lightweight validation checks for player-selection rule results."""

    required_columns = {
        "rule_id",
        "route_family",
        "position_short",
        "sample_size",
        "confidence",
        "mean_uplift_vs_position_baseline_next1",
        "mean_uplift_vs_position_baseline_next3",
        "mean_uplift_vs_position_baseline_next5",
    }
    missing_columns = sorted(required_columns - set(rule_results.columns))
    duplicate_rules = (
        int(rule_results.duplicated(["rule_id", "position_short"]).sum()) if not rule_results.empty else 0
    )
    return {
        "rows": int(len(rule_results)),
        "rules": int(rule_results["rule_id"].nunique()) if "rule_id" in rule_results else 0,
        "positions": sorted(rule_results["position_short"].dropna().unique()) if "position_short" in rule_results else [],
        "route_families": sorted(rule_results["route_family"].dropna().unique())
        if "route_family" in rule_results
        else [],
        "missing_columns": missing_columns,
        "duplicate_rule_position_rows": duplicate_rules,
        "min_sample_size": int(rule_results["sample_size"].min()) if "sample_size" in rule_results and not rule_results.empty else 0,
        "confidence_values": sorted(rule_results["confidence"].dropna().unique()) if "confidence" in rule_results else [],
    }


TRANSFER_CONTEXT_COLUMNS = [
    "player_id",
    "gameweek",
    "feature_team_points_per_fixture_prior",
    "feature_position_relevant_route_score",
    "feature_route_attacking_score",
    "feature_route_clean_sheet_score",
    "feature_route_defensive_contribution_score",
    "feature_route_goalkeeper_save_score",
    "feature_route_bps_bonus_score",
    "feature_route_availability_score",
    "outcome_points_next1",
    "outcome_points_next3",
    "outcome_points_next5",
]


def _transfer_context(candidate_rule_features: pd.DataFrame, prefix: str) -> pd.DataFrame:
    """Return candidate feature context with a transfer side prefix."""

    columns = _available(TRANSFER_CONTEXT_COLUMNS, candidate_rule_features)
    context = candidate_rule_features[columns].copy()
    return context.rename(
        columns={
            "player_id": f"{prefix}_element",
            "gameweek": "event",
            **{
                column: f"{prefix}_{column}"
                for column in columns
                if column not in {"player_id", "gameweek"}
            },
        }
    )


def enrich_transfer_rule_rows(
    manager_transfer_enriched_df: pd.DataFrame,
    candidate_rule_features_df: pd.DataFrame,
) -> pd.DataFrame:
    """Attach future outcomes and route context to transfer rows."""

    required_columns = {
        "manager_id",
        "event",
        "in_element",
        "out_element",
        "transfer_group_id",
        "event_transfers",
        "event_transfers_cost",
        "transfer_value_delta",
        "in_position_short",
    }
    missing_columns = required_columns - set(manager_transfer_enriched_df.columns)
    if missing_columns:
        raise ValueError(f"missing transfer columns: {sorted(missing_columns)}")

    transfers = manager_transfer_enriched_df.copy()
    for column in ["manager_id", "event", "in_element", "out_element"]:
        transfers[column] = pd.to_numeric(transfers[column], errors="coerce").astype("Int64")
    transfers = transfers.dropna(subset=["manager_id", "event", "in_element", "out_element"]).copy()
    for column in ["manager_id", "event", "in_element", "out_element"]:
        transfers[column] = transfers[column].astype(int)

    transfers = transfers.merge(
        _transfer_context(candidate_rule_features_df, "in"),
        on=["in_element", "event"],
        how="left",
        validate="many_to_one",
    ).merge(
        _transfer_context(candidate_rule_features_df, "out"),
        on=["out_element", "event"],
        how="left",
        validate="many_to_one",
    )

    counted_transfers = pd.to_numeric(transfers["event_transfers"], errors="coerce").fillna(0)
    hit_cost = pd.to_numeric(transfers["event_transfers_cost"], errors="coerce").fillna(0)
    transfers["allocated_hit_cost"] = np.where(counted_transfers.gt(0), hit_cost / counted_transfers, 0.0)

    for window in OUTCOME_WINDOWS:
        in_column = f"in_outcome_points_next{window}"
        out_column = f"out_outcome_points_next{window}"
        gross_column = f"gross_transfer_gain_next{window}"
        net_column = f"net_transfer_gain_next{window}"
        transfers[gross_column] = pd.to_numeric(transfers[in_column], errors="coerce") - pd.to_numeric(
            transfers[out_column],
            errors="coerce",
        )
        transfers[net_column] = transfers[gross_column] - transfers["allocated_hit_cost"]

    transfers["route_score_delta"] = (
        transfers["in_feature_position_relevant_route_score"]
        - transfers["out_feature_position_relevant_route_score"]
    )
    transfers["team_strength_delta"] = (
        transfers["in_feature_team_points_per_fixture_prior"]
        - transfers["out_feature_team_points_per_fixture_prior"]
    )
    transfers["attacking_route_delta"] = (
        transfers["in_feature_route_attacking_score"] - transfers["out_feature_route_attacking_score"]
    )
    transfers["clean_sheet_route_delta"] = (
        transfers["in_feature_route_clean_sheet_score"] - transfers["out_feature_route_clean_sheet_score"]
    )
    transfers["defensive_contribution_route_delta"] = (
        transfers["in_feature_route_defensive_contribution_score"]
        - transfers["out_feature_route_defensive_contribution_score"]
    )
    transfers["goalkeeper_save_route_delta"] = (
        transfers["in_feature_route_goalkeeper_save_score"] - transfers["out_feature_route_goalkeeper_save_score"]
    )
    transfers["bps_bonus_route_delta"] = (
        transfers["in_feature_route_bps_bonus_score"] - transfers["out_feature_route_bps_bonus_score"]
    )
    transfers["availability_route_delta"] = (
        transfers["in_feature_route_availability_score"] - transfers["out_feature_route_availability_score"]
    )

    package_size = transfers.groupby("transfer_group_id")["in_element"].transform("size")
    package_value_delta = transfers.groupby("transfer_group_id")["transfer_value_delta"].transform("sum")
    package_fixture_improvement_rate = transfers.groupby("transfer_group_id")[
        "targeted_fixture_improvement_next3"
    ].transform(lambda values: pd.Series(values).fillna(False).astype(bool).mean())
    transfers["package_transfer_rows"] = package_size
    transfers["package_value_delta"] = package_value_delta
    transfers["package_fixture_improvement_rate_next3"] = package_fixture_improvement_rate
    transfers["is_multi_transfer_package"] = transfers["package_transfer_rows"].gt(1)
    transfers["is_hit_package"] = pd.to_numeric(transfers["event_transfers_cost"], errors="coerce").fillna(0).gt(0)
    transfers["released_budget_package"] = transfers["package_value_delta"].lt(-0.5)
    transfers["spent_budget_package"] = transfers["package_value_delta"].gt(0.5)
    transfers["possible_funding_leg"] = (
        transfers["is_multi_transfer_package"]
        & pd.to_numeric(transfers["transfer_value_delta"], errors="coerce").lt(-0.5)
        & transfers["package_value_delta"].ge(-0.5)
    )
    return transfers


def _add_transfer_rule_flags(transfers: pd.DataFrame) -> pd.DataFrame:
    """Add individual transfer-leg rule flags."""

    output = transfers.copy()
    output["rule_fixture_improvement_next3"] = output["targeted_fixture_improvement_next3"].fillna(False).astype(bool)
    output["rule_avoids_blank_next3"] = (
        pd.to_numeric(output["in_blank_next3"], errors="coerce").fillna(0).eq(0)
        & pd.to_numeric(output["out_blank_next3"], errors="coerce").fillna(0).eq(1)
    )
    output["rule_targets_double_next3"] = pd.to_numeric(output["in_double_next3"], errors="coerce").fillna(0).eq(1)
    output["rule_minutes_upgrade"] = (
        pd.to_numeric(output["in_minutes_roll5_mean_prior"], errors="coerce")
        - pd.to_numeric(output["out_minutes_roll5_mean_prior"], errors="coerce")
    ).ge(15)
    output["rule_form_upgrade"] = (
        pd.to_numeric(output["in_points_roll5_mean_prior"], errors="coerce")
        - pd.to_numeric(output["out_points_roll5_mean_prior"], errors="coerce")
    ).ge(1)
    output["rule_xgi_upgrade"] = (
        pd.to_numeric(output["in_xgi_per_90_prior"], errors="coerce")
        - pd.to_numeric(output["out_xgi_per_90_prior"], errors="coerce")
    ).ge(0.10)
    output["rule_team_strength_upgrade"] = pd.to_numeric(output["team_strength_delta"], errors="coerce").ge(0.25)
    output["rule_position_route_upgrade"] = pd.to_numeric(output["route_score_delta"], errors="coerce").ge(0.50)
    output["rule_transfer_out_low_minutes"] = pd.to_numeric(
        output["out_minutes_roll5_mean_prior"],
        errors="coerce",
    ).lt(45)
    output["rule_transfer_out_poor_form"] = pd.to_numeric(
        output["out_points_roll5_mean_prior"],
        errors="coerce",
    ).lt(2)
    output["rule_budget_releasing_leg"] = pd.to_numeric(
        output["transfer_value_delta"],
        errors="coerce",
    ).lt(-0.5)
    output["rule_possible_funding_leg"] = output["possible_funding_leg"].fillna(False).astype(bool)
    output["rule_hit_transfer_leg"] = output["is_hit_transfer_week"].fillna(False).astype(bool)
    output["rule_attacking_route_upgrade"] = (
        output["in_position_short"].isin(["DEF", "MID", "FWD"])
        & pd.to_numeric(output["attacking_route_delta"], errors="coerce").ge(0.50)
    )
    output["rule_clean_sheet_route_upgrade"] = (
        output["in_position_short"].isin(["GKP", "DEF"])
        & pd.to_numeric(output["clean_sheet_route_delta"], errors="coerce").ge(0.50)
    )
    output["rule_defensive_contribution_route_upgrade"] = (
        output["in_position_short"].isin(["DEF", "MID", "FWD"])
        & pd.to_numeric(output["defensive_contribution_route_delta"], errors="coerce").ge(0.50)
    )
    output["rule_goalkeeper_save_route_upgrade"] = (
        output["in_position_short"].eq("GKP")
        & pd.to_numeric(output["goalkeeper_save_route_delta"], errors="coerce").ge(0.50)
    )
    output["rule_bps_bonus_route_upgrade"] = pd.to_numeric(output["bps_bonus_route_delta"], errors="coerce").ge(0.50)
    return output


TRANSFER_ROW_RULES = [
    ("rule_fixture_improvement_next3", "Bought better fixtures next 3", "fixture", {"GKP", "DEF", "MID", "FWD"}),
    ("rule_avoids_blank_next3", "Sold a blank for a player with fixtures", "fixture", {"GKP", "DEF", "MID", "FWD"}),
    ("rule_targets_double_next3", "Bought a double-gameweek player", "fixture", {"GKP", "DEF", "MID", "FWD"}),
    ("rule_minutes_upgrade", "Minutes upgrade", "minutes", {"GKP", "DEF", "MID", "FWD"}),
    ("rule_form_upgrade", "Recent-points upgrade", "form", {"GKP", "DEF", "MID", "FWD"}),
    ("rule_xgi_upgrade", "xGI upgrade", "xgi", {"DEF", "MID", "FWD"}),
    ("rule_team_strength_upgrade", "Team-strength upgrade", "team_strength", {"GKP", "DEF", "MID", "FWD"}),
    ("rule_position_route_upgrade", "Position-route upgrade", "position_route", {"GKP", "DEF", "MID", "FWD"}),
    ("rule_transfer_out_low_minutes", "Sold low-minutes player", "transfer_out", {"GKP", "DEF", "MID", "FWD"}),
    ("rule_transfer_out_poor_form", "Sold poor-form player", "transfer_out", {"GKP", "DEF", "MID", "FWD"}),
    ("rule_budget_releasing_leg", "Released budget", "funding_leg", {"GKP", "DEF", "MID", "FWD"}),
    ("rule_possible_funding_leg", "Possible funding leg", "funding_leg", {"GKP", "DEF", "MID", "FWD"}),
    ("rule_hit_transfer_leg", "Transfer leg in hit week", "hit", {"GKP", "DEF", "MID", "FWD"}),
    ("rule_attacking_route_upgrade", "Attacking-route upgrade", "attacking", {"DEF", "MID", "FWD"}),
    ("rule_clean_sheet_route_upgrade", "Clean-sheet-route upgrade", "clean_sheet", {"GKP", "DEF"}),
    (
        "rule_defensive_contribution_route_upgrade",
        "Defensive-contribution-route upgrade",
        "defensive_contribution",
        {"DEF", "MID", "FWD"},
    ),
    ("rule_goalkeeper_save_route_upgrade", "Goalkeeper-save-route upgrade", "goalkeeper_save", {"GKP"}),
    ("rule_bps_bonus_route_upgrade", "BPS/bonus-route upgrade", "bps_bonus", {"GKP", "DEF", "MID", "FWD"}),
]


PACKAGE_RULES = [
    ("package_is_multi_transfer", "Multi-transfer package", "transfer_package"),
    ("package_is_hit", "Package included a hit", "hit"),
    ("package_released_budget", "Package released budget", "funding_leg"),
    ("package_spent_budget", "Package spent budget", "funding_leg"),
    ("package_fixture_improvement_majority", "Majority fixture-improvement package", "fixture"),
]


def _transfer_confidence(sample_size: int, gain_next3: float, gain_next5: float) -> str:
    return _confidence_label(sample_size, gain_next3, gain_next5)


def _baseline_by_position(transfers: pd.DataFrame, position: str, window: int) -> float:
    column = f"net_transfer_gain_next{window}"
    return pd.to_numeric(transfers.loc[transfers["in_position_short"].eq(position), column], errors="coerce").mean()


def _package_summary(transfers: pd.DataFrame) -> pd.DataFrame:
    """Aggregate transfer rows once per manager-gameweek package."""

    aggregations = {
        "manager_id": "first",
        "event": "first",
        "in_element": "size",
        "event_transfers": "max",
        "event_transfers_cost": "max",
        "transfer_value_delta": "sum",
        "targeted_fixture_improvement_next3": lambda values: pd.Series(values).fillna(False).astype(bool).mean(),
        "is_multi_transfer_package": "max",
        "is_hit_package": "max",
        "released_budget_package": "max",
        "spent_budget_package": "max",
    }
    for window in OUTCOME_WINDOWS:
        aggregations[f"gross_transfer_gain_next{window}"] = "sum"

    packages = transfers.groupby("transfer_group_id").agg(aggregations).reset_index()
    packages = packages.rename(
        columns={
            "in_element": "package_transfer_rows",
            "transfer_value_delta": "package_value_delta",
            "targeted_fixture_improvement_next3": "package_fixture_improvement_rate_next3",
        }
    )
    for window in OUTCOME_WINDOWS:
        packages[f"net_package_gain_next{window}"] = (
            packages[f"gross_transfer_gain_next{window}"]
            - pd.to_numeric(packages["event_transfers_cost"], errors="coerce").fillna(0)
        )
    packages["package_is_multi_transfer"] = packages["is_multi_transfer_package"].fillna(False).astype(bool)
    packages["package_is_hit"] = packages["is_hit_package"].fillna(False).astype(bool)
    packages["package_released_budget"] = packages["released_budget_package"].fillna(False).astype(bool)
    packages["package_spent_budget"] = packages["spent_budget_package"].fillna(False).astype(bool)
    packages["package_fixture_improvement_majority"] = packages["package_fixture_improvement_rate_next3"].ge(0.5)
    return packages


def build_transfer_rule_results(
    manager_transfer_enriched_df: pd.DataFrame,
    candidate_rule_features_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Evaluate transfer-style rules for individual legs and packages."""

    enriched = _add_transfer_rule_flags(enrich_transfer_rule_rows(manager_transfer_enriched_df, candidate_rule_features_df))
    rows: list[dict[str, object]] = []

    for rule_id, rule_name, route_family, allowed_positions in TRANSFER_ROW_RULES:
        if rule_id not in enriched.columns:
            continue
        for position in sorted(allowed_positions):
            position_rows = enriched[enriched["in_position_short"].eq(position)]
            rule_rows = position_rows[enriched.loc[position_rows.index, rule_id].fillna(False).astype(bool)]
            sample_size = int(len(rule_rows))
            if sample_size < MIN_RULE_SAMPLE_SIZE:
                continue
            row: dict[str, object] = {
                "rule_level": "individual_transfer_leg",
                "rule_id": rule_id,
                "rule_name": rule_name,
                "route_family": route_family,
                "position_short": position,
                "sample_size": sample_size,
                "baseline_sample_size": int(len(position_rows)),
                "flagged_share": sample_size / len(position_rows) if len(position_rows) else np.nan,
                "package_count": int(rule_rows["transfer_group_id"].nunique()),
                "counting_note": "Individual rows count transfer legs; package_count counts distinct manager-gameweek packages.",
            }
            for window in OUTCOME_WINDOWS:
                net_column = f"net_transfer_gain_next{window}"
                row[f"mean_net_gain_next{window}"] = pd.to_numeric(rule_rows[net_column], errors="coerce").mean()
                row[f"median_net_gain_next{window}"] = pd.to_numeric(rule_rows[net_column], errors="coerce").median()
                baseline = _baseline_by_position(enriched, position, window)
                row[f"baseline_mean_net_gain_next{window}"] = baseline
                row[f"mean_uplift_vs_baseline_next{window}"] = row[f"mean_net_gain_next{window}"] - baseline
            row["confidence"] = _transfer_confidence(
                sample_size,
                row["mean_uplift_vs_baseline_next3"],
                row["mean_uplift_vs_baseline_next5"],
            )
            rows.append(row)

    packages = _package_summary(enriched)
    for rule_id, rule_name, route_family in PACKAGE_RULES:
        package_rows = packages[packages[rule_id].fillna(False).astype(bool)]
        sample_size = int(len(package_rows))
        if sample_size < MIN_RULE_SAMPLE_SIZE:
            continue
        row = {
            "rule_level": "transfer_package",
            "rule_id": rule_id,
            "rule_name": rule_name,
            "route_family": route_family,
            "position_short": "ALL",
            "sample_size": sample_size,
            "baseline_sample_size": int(len(packages)),
            "flagged_share": sample_size / len(packages) if len(packages) else np.nan,
            "package_count": sample_size,
            "counting_note": "Package rows count each manager-gameweek transfer package once.",
        }
        for window in OUTCOME_WINDOWS:
            net_column = f"net_package_gain_next{window}"
            row[f"mean_net_gain_next{window}"] = pd.to_numeric(package_rows[net_column], errors="coerce").mean()
            row[f"median_net_gain_next{window}"] = pd.to_numeric(package_rows[net_column], errors="coerce").median()
            baseline = pd.to_numeric(packages[net_column], errors="coerce").mean()
            row[f"baseline_mean_net_gain_next{window}"] = baseline
            row[f"mean_uplift_vs_baseline_next{window}"] = row[f"mean_net_gain_next{window}"] - baseline
        row["confidence"] = _transfer_confidence(
            sample_size,
            row["mean_uplift_vs_baseline_next3"],
            row["mean_uplift_vs_baseline_next5"],
        )
        rows.append(row)

    results = pd.DataFrame(rows)
    if not results.empty:
        results = results.sort_values(
            ["rule_level", "confidence", "mean_uplift_vs_baseline_next5", "sample_size"],
            ascending=[True, True, False, False],
        ).reset_index(drop=True)
    return enriched, packages, results


def validate_transfer_rule_results(rule_results: pd.DataFrame, package_rows: pd.DataFrame) -> dict[str, object]:
    """Run lightweight validation checks for transfer rule results."""

    required_columns = {
        "rule_level",
        "rule_id",
        "route_family",
        "sample_size",
        "package_count",
        "confidence",
        "mean_net_gain_next1",
        "median_net_gain_next1",
        "mean_net_gain_next3",
        "median_net_gain_next3",
        "mean_net_gain_next5",
        "median_net_gain_next5",
    }
    missing_columns = sorted(required_columns - set(rule_results.columns))
    duplicate_rows = (
        int(rule_results.duplicated(["rule_level", "rule_id", "position_short"]).sum()) if not rule_results.empty else 0
    )
    return {
        "rows": int(len(rule_results)),
        "rules": int(rule_results["rule_id"].nunique()) if "rule_id" in rule_results else 0,
        "rule_levels": sorted(rule_results["rule_level"].dropna().unique()) if "rule_level" in rule_results else [],
        "route_families": sorted(rule_results["route_family"].dropna().unique())
        if "route_family" in rule_results
        else [],
        "missing_columns": missing_columns,
        "duplicate_rule_rows": duplicate_rows,
        "min_sample_size": int(rule_results["sample_size"].min()) if "sample_size" in rule_results and not rule_results.empty else 0,
        "confidence_values": sorted(rule_results["confidence"].dropna().unique()) if "confidence" in rule_results else [],
        "package_rows": int(len(package_rows)),
        "duplicate_package_ids": int(package_rows["transfer_group_id"].duplicated().sum()) if not package_rows.empty else 0,
    }


RULEBOOK_REQUIRED_COLUMNS = {
    "rule_id",
    "rule_scope",
    "rule_text",
    "confidence",
    "evidence_summary",
    "when_to_use",
    "when_to_ignore",
    "my_season_note",
    "overfitting_risk",
    "applies_to_position",
    "route_family",
    "source_rule_level",
}


def _fmt_points(value: object) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value):+.1f}"


def _support_label(uplift_next5: float, confidence: str) -> str:
    if pd.isna(uplift_next5):
        return "uncertain"
    if confidence == "Low":
        return "watchlist"
    if uplift_next5 >= 1:
        return "supported"
    if uplift_next5 <= -1:
        return "avoid"
    return "context-dependent"


def _risk_label(confidence: str, sample_size: int, route_family: str) -> str:
    if confidence == "Low":
        return "High: weak or inconsistent evidence."
    if sample_size < 500:
        return "Medium: useful signal, but sample size is modest."
    if route_family in {"fixture", "transfer_package", "funding_leg", "hit"}:
        return "Medium: depends heavily on surrounding squad context."
    return "Low: broad sample and consistent directional evidence, but still retrospective."


def _player_when_to_use(row: pd.Series) -> str:
    family = row["route_family"]
    position = row["position_short"]
    if family == "availability":
        return f"Use for {position} picks when you need reliable starters and can sacrifice some ceiling."
    if family == "attacking":
        return f"Use for {position} picks when role, minutes, and fixtures also support the attacking signal."
    if family == "clean_sheet":
        return "Use for GKP/DEF picks when team strength and upcoming fixtures point to clean-sheet upside."
    if family == "defensive_contribution":
        return "Use for DEF/MID/FWD picks whose points can come from defensive contribution, not just goals."
    if family == "goalkeeper_save":
        return "Use for goalkeepers with saves plus reasonable fixture context, especially outside elite clean-sheet teams."
    if family == "bps_bonus":
        return "Use as a tie-breaker when minutes and scoring-route evidence are already acceptable."
    if family == "ownership":
        return "Use as a market-confirmation signal from strong managers, not as a standalone reason to buy."
    if family == "fixtures":
        return "Use when the player also has minutes security and a scoring route for their position."
    if family == "price":
        return "Use when the player role fits the budget slot you need rather than chasing price alone."
    return f"Use for {position} picks when the rule is backed by current-season prior evidence."


def _player_when_to_ignore(row: pd.Series) -> str:
    family = row["route_family"]
    if family == "availability":
        return "Ignore if injury news, suspension risk, or rotation context has changed since the historical window."
    if family == "attacking":
        return "Ignore if the player is losing minutes or the apparent xGI role is fixture-driven noise."
    if family == "clean_sheet":
        return "Ignore if the defender or keeper lacks starts, or if clean-sheet odds hide poor attacking/bonus upside."
    if family == "defensive_contribution":
        return "Ignore if defensive contribution came from an unusual match state unlikely to repeat."
    if family == "goalkeeper_save":
        return "Ignore if save volume comes with high goals-conceded risk and no bonus path."
    if family == "ownership":
        return "Ignore when ownership is stale, bandwagon-driven, or conflicts with your squad structure."
    return "Ignore if the signal conflicts with minutes, role, fixture, or squad-structure context."


def _transfer_when_to_use(row: pd.Series) -> str:
    family = row["route_family"]
    level = row["rule_level"]
    if level == "transfer_package":
        return "Use when assessing the whole gameweek transfer plan, not each leg in isolation."
    if family == "transfer_out":
        return "Use when the outgoing player has lost minutes, role, or practical squad value."
    if family == "funding_leg":
        return "Use only when the downgrade funds a stronger package elsewhere."
    if family == "hit":
        return "Use only when the expected package gain clearly exceeds the points hit."
    if family == "fixture":
        return "Use when fixtures improve without sacrificing minutes or position-specific scoring routes."
    if family in {"attacking", "clean_sheet", "defensive_contribution", "goalkeeper_save", "bps_bonus", "position_route"}:
        return "Use when the incoming player improves the scoring route that matters for their position."
    return "Use when the transfer improves multiple pre-decision signals, not just one metric."


def _transfer_when_to_ignore(row: pd.Series) -> str:
    family = row["route_family"]
    level = row["rule_level"]
    if level == "transfer_package":
        return "Ignore as an individual-player rule; judge the package by the combined squad effect."
    if family == "funding_leg":
        return "Ignore if the released budget is not clearly used to improve another position."
    if family == "hit":
        return "Ignore for marginal upgrades or short horizons where the hit dominates."
    if family == "fixture":
        return "Ignore if the fixture swing hides weak minutes, weak role, or a blank soon after."
    return "Ignore if the move is driven by one signal while other process signals deteriorate."


def _summarise_my_transfer_rule(row: pd.Series, enriched: pd.DataFrame, packages: pd.DataFrame) -> str:
    if enriched.empty:
        return "My-transfer support not available."
    rule_id = row["rule_id"]
    if row["rule_level"] == "transfer_package":
        if rule_id not in packages.columns:
            return "My package support not available for this rule."
        my_rows = packages[packages["manager_id"].astype(int).eq(816200)]
        matched = my_rows[my_rows[rule_id].fillna(False).astype(bool)]
        if matched.empty:
            return "My season had no matching package examples."
        return (
            f"My matching packages: {len(matched)}; "
            f"mean 5GW net package gain {_fmt_points(matched['net_package_gain_next5'].mean())} pts."
        )
    if rule_id not in enriched.columns:
        return "My transfer-leg support not available for this rule."
    my_rows = enriched[enriched["manager_id"].astype(int).eq(816200)]
    if row["position_short"] != "ALL":
        my_rows = my_rows[my_rows["in_position_short"].eq(row["position_short"])]
    matched = my_rows[my_rows[rule_id].fillna(False).astype(bool)]
    if matched.empty:
        return "My season had no matching transfer-leg examples."
    return (
        f"My matching transfer legs: {len(matched)}; "
        f"mean 5GW net gain {_fmt_points(matched['net_transfer_gain_next5'].mean())} pts."
    )


def _summarise_my_player_context(
    row: pd.Series,
    adoption_timing_df: pd.DataFrame,
    captaincy_review_df: pd.DataFrame,
    benching_summary_df: pd.DataFrame,
) -> str:
    notes = []
    if row["route_family"] in {"form", "position_route", "ownership"} and not adoption_timing_df.empty:
        late = int(adoption_timing_df["adoption_timing_category"].isin(["late", "never_owned"]).sum())
        missed = pd.to_numeric(
            adoption_timing_df["estimated_points_after_sample_median_before_my_adoption"],
            errors="coerce",
        ).sum()
        notes.append(f"key-player adoption had {late} late/never-owned cases costing about {missed:.0f} pts after sample median")
    if row["route_family"] in {"availability", "position_route"} and not benching_summary_df.empty:
        questionable = int(pd.to_numeric(benching_summary_df["questionable_benchings"], errors="coerce").sum())
        notes.append(f"bench review found {questionable} questionable benchings")
    if row["route_family"] in {"attacking", "position_route", "fixtures"} and not captaincy_review_df.empty:
        missed = pd.to_numeric(captaincy_review_df["delta_vs_recommended_candidate_extra"], errors="coerce").sum()
        notes.append(f"captaincy was {missed:.0f} pts vs the pre-GW candidate benchmark")
    if not notes:
        return "My season support should be checked in the final report; no direct matching decision review exists for this rule."
    return "; ".join(notes) + "."


def build_next_season_rulebook(
    player_rule_results_df: pd.DataFrame,
    transfer_rule_results_df: pd.DataFrame,
    transfer_rule_enriched_df: pd.DataFrame,
    transfer_rule_packages_df: pd.DataFrame,
    my_transfer_group_decision_labels_df: pd.DataFrame,
    adoption_timing_df: pd.DataFrame,
    captaincy_review_df: pd.DataFrame,
    benching_summary_df: pd.DataFrame,
    *,
    max_player_rules: int | None = None,
    max_transfer_rules: int | None = None,
) -> pd.DataFrame:
    """Convert rule result tables into practical next-season rulebook rows."""

    player_rules = player_rule_results_df.copy()
    transfer_rules = transfer_rule_results_df.copy()
    if not player_rules.empty:
        player_rules["abs_uplift_next5"] = player_rules["mean_uplift_vs_position_baseline_next5"].abs()
        player_rules = player_rules.sort_values(
            ["confidence", "mean_uplift_vs_position_baseline_next5", "sample_size"],
            ascending=[True, False, False],
        )
        if max_player_rules is not None:
            player_rules = player_rules.head(max_player_rules)
    if not transfer_rules.empty:
        transfer_rules["abs_uplift_next5"] = transfer_rules["mean_uplift_vs_baseline_next5"].abs()
        transfer_rules = transfer_rules.sort_values(
            ["confidence", "mean_uplift_vs_baseline_next5", "sample_size"],
            ascending=[True, False, False],
        )
        if max_transfer_rules is not None:
            transfer_rules = transfer_rules.head(max_transfer_rules)

    rows: list[dict[str, object]] = []
    for _, row in player_rules.iterrows():
        position = row["position_short"]
        uplift5 = row["mean_uplift_vs_position_baseline_next5"]
        signal = _support_label(uplift5, row["confidence"])
        rows.append(
            {
                "rule_id": f"selection_{row['rule_id']}_{position}",
                "source_rule_id": row["rule_id"],
                "rule_scope": "player_selection",
                "source_rule_level": "player_selection",
                "applies_to_position": position,
                "route_family": row["route_family"],
                "rule_text": f"For {position}, prefer players matching '{row['rule_name']}' when the squad slot needs that scoring route.",
                "evidence_summary": (
                    f"{int(row['sample_size'])} player-GW examples; 5GW uplift vs same-position baseline "
                    f"{_fmt_points(uplift5)} pts; 3GW uplift "
                    f"{_fmt_points(row['mean_uplift_vs_position_baseline_next3'])} pts."
                ),
                "confidence": row["confidence"],
                "recommendation_strength": signal,
                "when_to_use": _player_when_to_use(row),
                "when_to_ignore": _player_when_to_ignore(row),
                "my_season_note": _summarise_my_player_context(
                    row,
                    adoption_timing_df,
                    captaincy_review_df,
                    benching_summary_df,
                ),
                "overfitting_risk": _risk_label(row["confidence"], int(row["sample_size"]), row["route_family"]),
                "sample_size": int(row["sample_size"]),
                "primary_metric_5gw": float(uplift5),
                "metric_name": "mean_uplift_vs_position_baseline_next5",
            }
        )

    for _, row in transfer_rules.iterrows():
        position = row["position_short"]
        uplift5 = row["mean_uplift_vs_baseline_next5"]
        signal = _support_label(uplift5, row["confidence"])
        scope = "transfer_package" if row["rule_level"] == "transfer_package" else "individual_transfer_leg"
        rows.append(
            {
                "rule_id": f"{scope}_{row['rule_id']}_{position}",
                "source_rule_id": row["rule_id"],
                "rule_scope": scope,
                "source_rule_level": row["rule_level"],
                "applies_to_position": position,
                "route_family": row["route_family"],
                "rule_text": f"For {scope.replace('_', ' ')}, apply '{row['rule_name']}' only with matching squad context.",
                "evidence_summary": (
                    f"{int(row['sample_size'])} examples; 5GW net gain uplift vs baseline "
                    f"{_fmt_points(uplift5)} pts; median 5GW net gain "
                    f"{_fmt_points(row['median_net_gain_next5'])} pts."
                ),
                "confidence": row["confidence"],
                "recommendation_strength": signal,
                "when_to_use": _transfer_when_to_use(row),
                "when_to_ignore": _transfer_when_to_ignore(row),
                "my_season_note": _summarise_my_transfer_rule(row, transfer_rule_enriched_df, transfer_rule_packages_df),
                "overfitting_risk": _risk_label(row["confidence"], int(row["sample_size"]), row["route_family"]),
                "sample_size": int(row["sample_size"]),
                "primary_metric_5gw": float(uplift5),
                "metric_name": "mean_uplift_vs_baseline_next5",
            }
        )

    rulebook = pd.DataFrame(rows)
    if rulebook.empty:
        return rulebook

    if not my_transfer_group_decision_labels_df.empty:
        group_counts = my_transfer_group_decision_labels_df["group_decision_quality_label"].value_counts().to_dict()
        summary = "; ".join(f"{key}: {value}" for key, value in sorted(group_counts.items()))
        mask = rulebook["rule_scope"].eq("transfer_package")
        rulebook.loc[mask, "my_season_note"] = rulebook.loc[mask, "my_season_note"] + (
            " My transfer package labels: " + summary + "."
        )

    return rulebook.sort_values(
        ["confidence", "recommendation_strength", "rule_scope", "primary_metric_5gw"],
        ascending=[True, True, True, False],
    ).reset_index(drop=True)


def validate_next_season_rulebook(rulebook: pd.DataFrame) -> dict[str, object]:
    """Run lightweight validation checks for the next-season rulebook."""

    missing_columns = sorted(RULEBOOK_REQUIRED_COLUMNS - set(rulebook.columns))
    duplicate_ids = int(rulebook["rule_id"].duplicated().sum()) if "rule_id" in rulebook else 0
    low_confidence_rows = rulebook[rulebook["confidence"].eq("Low")] if "confidence" in rulebook else pd.DataFrame()
    low_confidence_labelled = (
        bool(low_confidence_rows["overfitting_risk"].str.contains("weak|High", case=False, na=False).all())
        if not low_confidence_rows.empty and "overfitting_risk" in low_confidence_rows
        else True
    )
    return {
        "rows": int(len(rulebook)),
        "missing_columns": missing_columns,
        "duplicate_rule_ids": duplicate_ids,
        "rule_scopes": sorted(rulebook["rule_scope"].dropna().unique()) if "rule_scope" in rulebook else [],
        "confidence_values": sorted(rulebook["confidence"].dropna().unique()) if "confidence" in rulebook else [],
        "low_confidence_rows": int(len(low_confidence_rows)),
        "low_confidence_labelled": low_confidence_labelled,
        "empty_rule_text_rows": int(rulebook["rule_text"].isna().sum()) if "rule_text" in rulebook else 0,
    }
