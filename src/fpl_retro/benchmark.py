"""Benchmark summary helpers."""

from __future__ import annotations

import math

import pandas as pd


POSITION_LABELS = {
    1: "GKP",
    2: "DEF",
    3: "MID",
    4: "FWD",
}


def _require_columns(df: pd.DataFrame, required_columns: set[str], name: str) -> None:
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"missing {name} columns: {sorted(missing_columns)}")


def _empty_manager_summary(manager_ids: pd.Series) -> pd.DataFrame:
    return pd.DataFrame({"manager_id": manager_ids.astype(int).drop_duplicates().sort_values()})


def _mode_text(values: pd.Series) -> str:
    clean_values = values.dropna().astype(str)
    if clean_values.empty:
        return ""
    counts = clean_values.value_counts()
    return str(counts.index[0])


def _history_summary(manager_history_df: pd.DataFrame) -> pd.DataFrame:
    _require_columns(
        manager_history_df,
        {
            "manager_id",
            "event",
            "points",
            "total_points",
            "overall_rank",
            "rank",
            "points_on_bench",
            "event_transfers",
            "event_transfers_cost",
            "bank",
            "value",
        },
        "manager history",
    )
    history = manager_history_df.copy()
    history["manager_id"] = history["manager_id"].astype(int)
    history["event"] = history["event"].astype(int)
    history = history.sort_values(["manager_id", "event"])
    final_rows = history.groupby("manager_id", as_index=False).tail(1)
    final_rows = final_rows.rename(
        columns={
            "event": "last_event",
            "points": "final_event_points",
            "total_points": "final_total_points",
            "overall_rank": "final_overall_rank",
            "rank": "final_gameweek_rank",
            "bank": "final_bank_raw",
            "value": "final_squad_value_raw",
        }
    )

    summary = history.groupby("manager_id").agg(
        gameweeks=("event", "nunique"),
        season_points=("points", "sum"),
        average_gameweek_points=("points", "mean"),
        points_on_bench_total=("points_on_bench", "sum"),
        points_on_bench_mean=("points_on_bench", "mean"),
        official_transfers_total=("event_transfers", "sum"),
        transfer_hit_cost_total=("event_transfers_cost", "sum"),
        transfer_weeks=("event_transfers", lambda values: int((pd.to_numeric(values, errors="coerce") > 0).sum())),
        hit_weeks=("event_transfers_cost", lambda values: int((pd.to_numeric(values, errors="coerce") > 0).sum())),
        average_bank_raw=("bank", "mean"),
        average_squad_value_raw=("value", "mean"),
    )
    summary = summary.reset_index()
    final_columns = [
        "manager_id",
        "last_event",
        "final_event_points",
        "final_total_points",
        "final_overall_rank",
        "final_gameweek_rank",
        "final_bank_raw",
        "final_squad_value_raw",
    ]
    summary = summary.merge(final_rows[final_columns], on="manager_id", how="left", validate="one_to_one")
    summary["final_bank"] = summary["final_bank_raw"] / 10
    summary["final_squad_value"] = summary["final_squad_value_raw"] / 10
    summary["average_bank"] = summary["average_bank_raw"] / 10
    summary["average_squad_value"] = summary["average_squad_value_raw"] / 10
    return summary.drop(columns=["final_bank_raw", "final_squad_value_raw", "average_bank_raw", "average_squad_value_raw"])


def _transfer_summary(manager_transfers_df: pd.DataFrame, manager_ids: pd.Series) -> pd.DataFrame:
    if manager_transfers_df.empty:
        summary = _empty_manager_summary(manager_ids)
        summary["raw_transfer_rows"] = 0
        summary["raw_transfer_gameweeks"] = 0
        return summary
    _require_columns(manager_transfers_df, {"manager_id", "event", "element_in", "element_out"}, "manager transfers")
    transfers = manager_transfers_df.copy()
    transfers["manager_id"] = transfers["manager_id"].astype(int)
    transfers["event"] = transfers["event"].astype(int)
    return (
        transfers.groupby("manager_id")
        .agg(
            raw_transfer_rows=("element_in", "size"),
            raw_transfer_gameweeks=("event", "nunique"),
        )
        .reset_index()
    )


def _chip_summary(manager_chips_df: pd.DataFrame, manager_ids: pd.Series) -> pd.DataFrame:
    if manager_chips_df.empty:
        summary = _empty_manager_summary(manager_ids)
        summary["chip_count"] = 0
        summary["chip_names"] = ""
        return summary
    _require_columns(manager_chips_df, {"manager_id", "name"}, "manager chips")
    chips = manager_chips_df.copy()
    chips["manager_id"] = chips["manager_id"].astype(int)
    return (
        chips.groupby("manager_id")
        .agg(
            chip_count=("name", "size"),
            chip_names=("name", lambda values: ", ".join(sorted(values.dropna().astype(str).unique()))),
        )
        .reset_index()
    )


def _pick_summary(manager_picks_df: pd.DataFrame, manager_ids: pd.Series) -> pd.DataFrame:
    if manager_picks_df.empty:
        summary = _empty_manager_summary(manager_ids)
        summary["captain_unique_count"] = 0
        summary["captain_changes"] = 0
        summary["most_common_captain"] = ""
        summary["most_common_formation"] = ""
        summary["avg_starters_gkp"] = 0.0
        summary["avg_starters_def"] = 0.0
        summary["avg_starters_mid"] = 0.0
        summary["avg_starters_fwd"] = 0.0
        return summary
    _require_columns(
        manager_picks_df,
        {"manager_id", "event", "element", "element_type", "is_captain", "position", "web_name"},
        "manager picks",
    )
    picks = manager_picks_df.copy()
    picks["manager_id"] = picks["manager_id"].astype(int)
    picks["event"] = picks["event"].astype(int)
    picks["element"] = picks["element"].astype(int)
    picks["element_type"] = picks["element_type"].astype(int)
    picks["position"] = picks["position"].astype(int)
    picks["is_starter"] = picks["position"].le(11)

    captains = picks[picks["is_captain"].astype(bool)].sort_values(["manager_id", "event"])
    captain_summary = captains.groupby("manager_id").agg(
        captain_unique_count=("element", "nunique"),
        most_common_captain=("web_name", _mode_text),
    )
    captain_changes = captains.groupby("manager_id")["element"].apply(lambda values: int(values.ne(values.shift()).sum() - 1))
    captain_summary["captain_changes"] = captain_changes.clip(lower=0)
    captain_summary = captain_summary.reset_index()

    starters = picks[picks["is_starter"]].copy()
    starters["position_short"] = starters["element_type"].map(POSITION_LABELS).fillna("UNK")
    counts = (
        starters.groupby(["manager_id", "event", "position_short"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    for position in ["GKP", "DEF", "MID", "FWD"]:
        if position not in counts.columns:
            counts[position] = 0
    counts["formation"] = (
        counts["DEF"].astype(int).astype(str)
        + "-"
        + counts["MID"].astype(int).astype(str)
        + "-"
        + counts["FWD"].astype(int).astype(str)
    )
    formation_summary = counts.groupby("manager_id").agg(
        most_common_formation=("formation", _mode_text),
        avg_starters_gkp=("GKP", "mean"),
        avg_starters_def=("DEF", "mean"),
        avg_starters_mid=("MID", "mean"),
        avg_starters_fwd=("FWD", "mean"),
    )
    return captain_summary.merge(formation_summary.reset_index(), on="manager_id", how="outer")


def _sample_summary(top_n_sample_managers_df: pd.DataFrame, manager_ids: pd.Series, my_team_id: int) -> pd.DataFrame:
    if top_n_sample_managers_df.empty:
        summary = _empty_manager_summary(manager_ids)
        summary["rank_band"] = ""
        summary["sample_overall_rank"] = pd.NA
        summary["is_me"] = summary["manager_id"].eq(int(my_team_id))
        return summary
    _require_columns(top_n_sample_managers_df, {"manager_id", "overall_rank", "rank_band"}, "top-N sample managers")
    sample = top_n_sample_managers_df[["manager_id", "overall_rank", "rank_band"]].copy()
    sample["manager_id"] = sample["manager_id"].astype(int)
    sample = sample.rename(columns={"overall_rank": "sample_overall_rank"}).drop_duplicates("manager_id")
    summary = _empty_manager_summary(manager_ids).merge(sample, on="manager_id", how="left", validate="one_to_one")
    summary["rank_band"] = summary["rank_band"].fillna("")
    summary.loc[summary["manager_id"].eq(int(my_team_id)), "rank_band"] = "me"
    summary["is_me"] = summary["manager_id"].eq(int(my_team_id))
    return summary


def _my_transfer_label_summary(my_transfer_decision_labels_df: pd.DataFrame, my_team_id: int) -> pd.DataFrame:
    row: dict[str, object] = {"manager_id": int(my_team_id)}
    if my_transfer_decision_labels_df.empty:
        return pd.DataFrame([row])
    decisions = my_transfer_decision_labels_df.copy()
    if "manager_id" in decisions.columns:
        decisions = decisions[decisions["manager_id"].astype(int).eq(int(my_team_id))]
    row["my_labeled_transfer_rows"] = len(decisions)
    if "possible_funding_leg" in decisions.columns:
        row["my_possible_funding_leg_count"] = int(decisions["possible_funding_leg"].fillna(False).astype(bool).sum())
    if "decision_quality_label" in decisions.columns:
        for label, count in decisions["decision_quality_label"].fillna("Unlabelled").value_counts().items():
            key = str(label).lower().replace(" ", "_").replace(",", "")
            row[f"my_transfer_label_{key}_count"] = int(count)
    if "in_position_short" in decisions.columns:
        for position, count in decisions["in_position_short"].fillna("UNK").value_counts().items():
            row[f"my_transfer_in_{str(position).lower()}_count"] = int(count)
    return pd.DataFrame([row])


def _my_transfer_group_summary(my_transfer_group_decision_labels_df: pd.DataFrame, my_team_id: int) -> pd.DataFrame:
    row: dict[str, object] = {"manager_id": int(my_team_id)}
    if my_transfer_group_decision_labels_df.empty:
        return pd.DataFrame([row])
    groups = my_transfer_group_decision_labels_df.copy()
    if "manager_id" in groups.columns:
        groups = groups[groups["manager_id"].astype(int).eq(int(my_team_id))]
    row["my_transfer_group_count"] = len(groups)
    if "group_transfer_count" in groups.columns:
        row["my_multi_transfer_group_count"] = int((pd.to_numeric(groups["group_transfer_count"], errors="coerce") > 1).sum())
    if "transfer_group_type" in groups.columns:
        for group_type, count in groups["transfer_group_type"].fillna("unknown").value_counts().items():
            key = str(group_type).lower().replace(" ", "_").replace("-", "_")
            row[f"my_transfer_group_type_{key}_count"] = int(count)
    if "group_decision_quality_label" in groups.columns:
        for label, count in groups["group_decision_quality_label"].fillna("Unlabelled").value_counts().items():
            key = str(label).lower().replace(" ", "_").replace(",", "")
            row[f"my_transfer_group_label_{key}_count"] = int(count)
    if "group_net_points_after_hit_5gw" in groups.columns:
        row["my_transfer_group_net_points_after_hit_5gw_total"] = float(
            pd.to_numeric(groups["group_net_points_after_hit_5gw"], errors="coerce").fillna(0).sum()
        )
    return pd.DataFrame([row])


def _my_decision_output_summary(
    my_captaincy_review_df: pd.DataFrame,
    my_benching_gameweek_summary_df: pd.DataFrame,
    my_team_id: int,
) -> pd.DataFrame:
    row: dict[str, object] = {"manager_id": int(my_team_id)}
    if not my_captaincy_review_df.empty:
        captaincy = my_captaincy_review_df.copy()
        row["my_captain_delta_vs_best_starter_total"] = float(
            pd.to_numeric(captaincy.get("delta_vs_best_starter_extra", 0), errors="coerce").fillna(0).sum()
        )
        row["my_captain_delta_vs_recommended_total"] = float(
            pd.to_numeric(captaincy.get("delta_vs_recommended_candidate_extra", 0), errors="coerce").fillna(0).sum()
        )
        if "captain_was_recommended_candidate" in captaincy.columns:
            row["my_captain_recommended_match_rate"] = float(
                captaincy["captain_was_recommended_candidate"].fillna(False).astype(bool).mean()
            )
    if not my_benching_gameweek_summary_df.empty:
        benching = my_benching_gameweek_summary_df.copy()
        row["my_bench_regret_points_total"] = float(
            pd.to_numeric(benching.get("bench_regret_points", 0), errors="coerce").fillna(0).sum()
        )
        row["my_questionable_benchings_total"] = int(
            pd.to_numeric(benching.get("questionable_benchings", 0), errors="coerce").fillna(0).sum()
        )
        row["my_high_regret_benchings_total"] = int(
            pd.to_numeric(benching.get("high_regret_benchings", 0), errors="coerce").fillna(0).sum()
        )
    return pd.DataFrame([row])


def build_manager_behaviour_summary(
    *,
    manager_history_df: pd.DataFrame,
    manager_transfers_df: pd.DataFrame,
    manager_chips_df: pd.DataFrame,
    manager_picks_df: pd.DataFrame,
    top_n_sample_managers_df: pd.DataFrame,
    my_team_id: int,
    my_transfer_decision_labels_df: pd.DataFrame | None = None,
    my_transfer_group_decision_labels_df: pd.DataFrame | None = None,
    my_captaincy_review_df: pd.DataFrame | None = None,
    my_benching_gameweek_summary_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build one season-level behaviour summary row per manager."""

    history = _history_summary(manager_history_df)
    manager_ids = history["manager_id"]
    summary = history.merge(_sample_summary(top_n_sample_managers_df, manager_ids, my_team_id), on="manager_id")
    summary = summary.merge(_transfer_summary(manager_transfers_df, manager_ids), on="manager_id", how="left")
    summary = summary.merge(_chip_summary(manager_chips_df, manager_ids), on="manager_id", how="left")
    summary = summary.merge(_pick_summary(manager_picks_df, manager_ids), on="manager_id", how="left")

    transfer_decisions = (
        my_transfer_decision_labels_df if my_transfer_decision_labels_df is not None else pd.DataFrame()
    )
    transfer_groups = (
        my_transfer_group_decision_labels_df
        if my_transfer_group_decision_labels_df is not None
        else pd.DataFrame()
    )
    captaincy_review = my_captaincy_review_df if my_captaincy_review_df is not None else pd.DataFrame()
    benching_summary = (
        my_benching_gameweek_summary_df if my_benching_gameweek_summary_df is not None else pd.DataFrame()
    )

    my_tables = [
        _my_transfer_label_summary(transfer_decisions, my_team_id),
        _my_transfer_group_summary(transfer_groups, my_team_id),
        _my_decision_output_summary(
            captaincy_review,
            benching_summary,
            my_team_id,
        ),
    ]
    for table in my_tables:
        summary = summary.merge(table, on="manager_id", how="left")

    numeric_fill_columns = [
        column
        for column in summary.columns
        if column
        not in {
            "rank_band",
            "chip_names",
            "most_common_captain",
            "most_common_formation",
        }
    ]
    for column in numeric_fill_columns:
        if column != "sample_overall_rank" and pd.api.types.is_numeric_dtype(summary[column]):
            summary[column] = summary[column].fillna(0)
    for column in ["chip_names", "most_common_captain", "most_common_formation"]:
        if column in summary.columns:
            summary[column] = summary[column].fillna("")

    front_columns = [
        "manager_id",
        "is_me",
        "rank_band",
        "sample_overall_rank",
        "final_overall_rank",
        "final_total_points",
        "gameweeks",
        "average_gameweek_points",
        "official_transfers_total",
        "raw_transfer_rows",
        "transfer_hit_cost_total",
        "points_on_bench_total",
        "points_on_bench_mean",
        "chip_count",
        "chip_names",
        "captain_unique_count",
        "captain_changes",
        "most_common_captain",
        "most_common_formation",
        "final_squad_value",
        "final_bank",
    ]
    ordered_columns = [column for column in front_columns if column in summary.columns]
    ordered_columns.extend([column for column in summary.columns if column not in ordered_columns])
    return summary[ordered_columns].sort_values(["is_me", "final_total_points"], ascending=[False, False]).reset_index(
        drop=True
    )


def _key_player_pool(
    player_gw_features_df: pd.DataFrame,
    *,
    top_n: int,
    min_per_position: int,
) -> pd.DataFrame:
    _require_columns(
        player_gw_features_df,
        {
            "player_id",
            "gameweek",
            "web_name",
            "team_name",
            "position_short",
            "total_points",
            "goals_scored",
            "assists",
            "clean_sheets",
            "saves",
            "bonus",
            "bps",
            "defensive_contribution",
            "clearances_blocks_interceptions",
            "recoveries",
            "expected_goal_involvements",
        },
        "player gameweek features",
    )
    features = player_gw_features_df.copy()
    features["player_id"] = features["player_id"].astype(int)
    features["gameweek"] = features["gameweek"].astype(int)

    player_summary = (
        features.groupby("player_id")
        .agg(
            player_name=("web_name", "last"),
            team_name=("team_name", "last"),
            position_short=("position_short", "last"),
            season_points=("total_points", "sum"),
            played_gameweeks=("minutes", lambda values: int((pd.to_numeric(values, errors="coerce") > 0).sum())),
            goals=("goals_scored", "sum"),
            assists=("assists", "sum"),
            clean_sheets=("clean_sheets", "sum"),
            saves=("saves", "sum"),
            bonus=("bonus", "sum"),
            bps=("bps", "sum"),
            defensive_contribution=("defensive_contribution", "sum"),
            clearances_blocks_interceptions=("clearances_blocks_interceptions", "sum"),
            recoveries=("recoveries", "sum"),
            expected_goal_involvements=("expected_goal_involvements", "sum"),
        )
        .reset_index()
    )
    player_summary["overall_points_rank"] = player_summary["season_points"].rank(
        method="first",
        ascending=False,
    )
    player_summary["position_points_rank"] = player_summary.groupby("position_short")["season_points"].rank(
        method="first",
        ascending=False,
    )

    key_mask = (player_summary["overall_points_rank"] <= top_n) | (
        player_summary["position_points_rank"] <= min_per_position
    )
    key_players = player_summary[key_mask].copy()
    return key_players.sort_values(["season_points", "player_id"], ascending=[False, True]).reset_index(drop=True)


def _route_summary(row: pd.Series) -> str:
    position = row["position_short"]
    if position == "GKP":
        return (
            f"GKP route: {int(row['clean_sheets'])} clean sheets, {int(row['saves'])} saves, "
            f"{int(row['bonus'])} bonus"
        )
    if position == "DEF":
        return (
            f"DEF route: {int(row['clean_sheets'])} clean sheets, "
            f"{int(row['defensive_contribution'])} defensive contribution points, "
            f"{int(row['goals'])} goals, {int(row['assists'])} assists"
        )
    if position == "MID":
        return (
            f"MID route: {int(row['goals'])} goals, {int(row['assists'])} assists, "
            f"{int(row['defensive_contribution'])} defensive contribution points"
        )
    return (
        f"FWD route: {int(row['goals'])} goals, {int(row['assists'])} assists, "
        f"{float(row['expected_goal_involvements']):.1f} xGI"
    )


def _first_owned_table(manager_picks_df: pd.DataFrame, manager_ids: pd.Series) -> pd.DataFrame:
    _require_columns(manager_picks_df, {"manager_id", "event", "element"}, "manager picks")
    picks = manager_picks_df.copy()
    valid_manager_ids = set(manager_ids.astype(int))
    picks["manager_id"] = picks["manager_id"].astype(int)
    picks = picks[picks["manager_id"].isin(valid_manager_ids)]
    picks["event"] = picks["event"].astype(int)
    picks["player_id"] = picks["element"].astype(int)
    return (
        picks.groupby(["manager_id", "player_id"], as_index=False)
        .agg(first_owned_gw=("event", "min"))
        .sort_values(["manager_id", "player_id"])
        .reset_index(drop=True)
    )


def _points_between(
    player_gw_features_df: pd.DataFrame,
    player_id: int,
    start_event: int | None,
    end_event_exclusive: int,
) -> float:
    if start_event is None:
        return 0.0
    features = player_gw_features_df[
        player_gw_features_df["player_id"].astype(int).eq(int(player_id))
        & player_gw_features_df["gameweek"].astype(int).ge(int(start_event))
        & player_gw_features_df["gameweek"].astype(int).lt(int(end_event_exclusive))
    ]
    return float(pd.to_numeric(features["total_points"], errors="coerce").fillna(0).sum())


def build_player_adoption_timing(
    *,
    manager_picks_df: pd.DataFrame,
    player_gw_features_df: pd.DataFrame,
    top_n_sample_managers_df: pd.DataFrame,
    my_team_id: int,
    top_n_key_players: int = 30,
    min_key_players_per_position: int = 5,
) -> pd.DataFrame:
    """Compare first ownership timing for key players against sampled managers."""

    _require_columns(top_n_sample_managers_df, {"manager_id"}, "top-N sample managers")
    key_players = _key_player_pool(
        player_gw_features_df,
        top_n=top_n_key_players,
        min_per_position=min_key_players_per_position,
    )
    sample_manager_ids = top_n_sample_managers_df["manager_id"].astype(int).drop_duplicates()
    all_manager_ids = pd.concat([sample_manager_ids, pd.Series([int(my_team_id)])], ignore_index=True).drop_duplicates()
    first_owned = _first_owned_table(manager_picks_df, all_manager_ids)

    sample_first_owned = first_owned[first_owned["manager_id"].isin(set(sample_manager_ids))]
    my_first_owned = first_owned[first_owned["manager_id"].eq(int(my_team_id))][["player_id", "first_owned_gw"]].rename(
        columns={"first_owned_gw": "my_first_owned_gw"}
    )

    sample_stats = (
        sample_first_owned.groupby("player_id")
        .agg(
            sample_managers_owned=("manager_id", "nunique"),
            sample_median_first_owned_gw=("first_owned_gw", "median"),
            sample_p25_first_owned_gw=("first_owned_gw", lambda values: float(values.quantile(0.25))),
            sample_p75_first_owned_gw=("first_owned_gw", lambda values: float(values.quantile(0.75))),
            sample_earliest_first_owned_gw=("first_owned_gw", "min"),
        )
        .reset_index()
    )
    sample_stats["sample_total_managers"] = int(sample_manager_ids.nunique())
    sample_stats["sample_adoption_rate"] = sample_stats["sample_managers_owned"] / sample_stats["sample_total_managers"]

    review = key_players.merge(sample_stats, on="player_id", how="left").merge(
        my_first_owned,
        on="player_id",
        how="left",
    )
    review["sample_managers_owned"] = review["sample_managers_owned"].fillna(0).astype(int)
    review["sample_total_managers"] = review["sample_total_managers"].fillna(int(sample_manager_ids.nunique())).astype(int)
    review["sample_adoption_rate"] = review["sample_adoption_rate"].fillna(0.0)
    review["my_owned"] = review["my_first_owned_gw"].notna()
    review["my_adoption_delay_vs_sample_median"] = review["my_first_owned_gw"] - review["sample_median_first_owned_gw"]

    missed_points = []
    median_ceiling_events = []
    delay_categories = []
    for _, row in review.iterrows():
        median_gw = row["sample_median_first_owned_gw"]
        if pd.isna(median_gw):
            median_ceiling_events.append(pd.NA)
            missed_points.append(0.0)
            delay_categories.append("not_adopted_by_sample")
            continue

        median_event = int(math.ceil(float(median_gw)))
        median_ceiling_events.append(median_event)
        my_first = row["my_first_owned_gw"]
        if pd.isna(my_first):
            end_event = int(player_gw_features_df["gameweek"].max()) + 1
            missed_points.append(_points_between(player_gw_features_df, int(row["player_id"]), median_event, end_event))
            delay_categories.append("never_owned")
        elif float(my_first) > float(median_gw):
            missed_points.append(_points_between(player_gw_features_df, int(row["player_id"]), median_event, int(my_first)))
            delay_categories.append("late")
        elif float(my_first) < float(median_gw):
            missed_points.append(0.0)
            delay_categories.append("early")
        else:
            missed_points.append(0.0)
            delay_categories.append("same_as_sample_median")

    review["sample_median_first_owned_gw_ceiling"] = median_ceiling_events
    review["estimated_points_after_sample_median_before_my_adoption"] = missed_points
    review["adoption_timing_category"] = delay_categories
    review["scoring_route_context"] = review.apply(_route_summary, axis=1)
    review["key_player_selection_note"] = (
        f"Key players are top {top_n_key_players} by season points plus the top "
        f"{min_key_players_per_position} per position."
    )
    front_columns = [
        "player_id",
        "player_name",
        "team_name",
        "position_short",
        "season_points",
        "overall_points_rank",
        "position_points_rank",
        "sample_managers_owned",
        "sample_total_managers",
        "sample_adoption_rate",
        "sample_median_first_owned_gw",
        "sample_median_first_owned_gw_ceiling",
        "sample_p25_first_owned_gw",
        "sample_p75_first_owned_gw",
        "my_owned",
        "my_first_owned_gw",
        "my_adoption_delay_vs_sample_median",
        "adoption_timing_category",
        "estimated_points_after_sample_median_before_my_adoption",
        "scoring_route_context",
    ]
    ordered_columns = [column for column in front_columns if column in review.columns]
    ordered_columns.extend([column for column in review.columns if column not in ordered_columns])
    return review[ordered_columns].sort_values(
        ["estimated_points_after_sample_median_before_my_adoption", "season_points"],
        ascending=[False, False],
    ).reset_index(drop=True)


def _price_band(price: pd.Series) -> pd.Series:
    price_numeric = pd.to_numeric(price, errors="coerce").fillna(0.0)
    return pd.cut(
        price_numeric,
        bins=[-0.01, 5.99, 8.99, 99.0],
        labels=["budget", "mid", "premium"],
    ).astype(str)


def _build_structure_gameweeks(
    manager_picks_df: pd.DataFrame,
    players_df: pd.DataFrame,
    team_strength_df: pd.DataFrame,
    fixture_difficulty_df: pd.DataFrame,
) -> pd.DataFrame:
    _require_columns(
        manager_picks_df,
        {"manager_id", "event", "element", "element_type", "position"},
        "manager picks",
    )
    _require_columns(players_df, {"id", "price", "team_name", "position_short"}, "players")
    _require_columns(
        team_strength_df,
        {"team_name", "gameweek", "points_per_fixture_prior"},
        "team strength",
    )
    _require_columns(
        fixture_difficulty_df,
        {"team_name", "gameweek", "fpl_difficulty_mean_next3"},
        "fixture difficulty",
    )

    picks = manager_picks_df.copy()
    picks["manager_id"] = picks["manager_id"].astype(int)
    picks["event"] = picks["event"].astype(int)
    picks["element"] = picks["element"].astype(int)
    picks["position"] = picks["position"].astype(int)
    picks["is_starter"] = picks["position"].le(11)
    picks["is_bench"] = ~picks["is_starter"]

    player_lookup = players_df[["id", "price", "position_short"]].rename(columns={"id": "element"})
    player_lookup["element"] = player_lookup["element"].astype(int)
    picks = picks.merge(player_lookup, on="element", how="left", validate="many_to_one")
    picks["price"] = pd.to_numeric(picks["price"], errors="coerce").fillna(0.0)
    picks["price_band"] = _price_band(picks["price"])
    picks["position_short"] = picks["position_short"].fillna(picks["element_type"].map(POSITION_LABELS))

    strength = team_strength_df[["team_name", "gameweek", "points_per_fixture_prior"]].copy()
    strength["gameweek"] = strength["gameweek"].astype(int)
    strength["team_strength_rank_prior"] = strength.groupby("gameweek")["points_per_fixture_prior"].rank(
        method="min",
        ascending=False,
    )
    strength["is_prior_top6_team"] = strength["team_strength_rank_prior"].le(6)
    picks = picks.merge(
        strength.rename(columns={"gameweek": "event"}),
        on=["team_name", "event"],
        how="left",
        validate="many_to_one",
    )

    fixtures = fixture_difficulty_df[["team_name", "gameweek", "fpl_difficulty_mean_next3"]].copy()
    fixtures["gameweek"] = fixtures["gameweek"].astype(int)
    fixtures["has_good_next3_fixtures"] = pd.to_numeric(
        fixtures["fpl_difficulty_mean_next3"],
        errors="coerce",
    ).le(3.0)
    picks = picks.merge(
        fixtures.rename(columns={"gameweek": "event"}),
        on=["team_name", "event"],
        how="left",
        validate="many_to_one",
    )

    rows: list[dict[str, object]] = []
    for (manager_id, event), group in picks.groupby(["manager_id", "event"], sort=True):
        starter = group[group["is_starter"]]
        bench = group[group["is_bench"]]
        row: dict[str, object] = {
            "manager_id": int(manager_id),
            "event": int(event),
            "squad_players": int(len(group)),
            "starter_players": int(len(starter)),
            "bench_players": int(len(bench)),
            "squad_value_proxy": float(group["price"].sum()),
            "starter_value_proxy": float(starter["price"].sum()),
            "bench_value_proxy": float(bench["price"].sum()),
            "bench_value_share_proxy": float(bench["price"].sum() / group["price"].sum()) if group["price"].sum() else 0.0,
            "prior_top6_team_players": int(group["is_prior_top6_team"].fillna(False).sum()),
            "good_next3_fixture_players": int(group["has_good_next3_fixtures"].fillna(False).sum()),
            "starter_prior_top6_team_players": int(starter["is_prior_top6_team"].fillna(False).sum()),
            "starter_good_next3_fixture_players": int(starter["has_good_next3_fixtures"].fillna(False).sum()),
        }
        for position in ["GKP", "DEF", "MID", "FWD"]:
            row[f"squad_{position.lower()}_count"] = int(group["position_short"].eq(position).sum())
            row[f"starter_{position.lower()}_count"] = int(starter["position_short"].eq(position).sum())
            row[f"{position.lower()}_value_proxy"] = float(group.loc[group["position_short"].eq(position), "price"].sum())
        for band in ["budget", "mid", "premium"]:
            row[f"{band}_players"] = int(group["price_band"].eq(band).sum())
            row[f"starter_{band}_players"] = int(starter["price_band"].eq(band).sum())
            row[f"{band}_value_proxy"] = float(group.loc[group["price_band"].eq(band), "price"].sum())
        rows.append(row)

    return pd.DataFrame(rows).sort_values(["manager_id", "event"]).reset_index(drop=True)


def _add_sample_percentiles(summary: pd.DataFrame, metric_columns: list[str], my_team_id: int) -> pd.DataFrame:
    result = summary.copy()
    sample = result[~result["manager_id"].astype(int).eq(int(my_team_id))]
    for column in metric_columns:
        values = pd.to_numeric(sample[column], errors="coerce").dropna()
        if values.empty:
            result[f"{column}_sample_percentile"] = pd.NA
            continue
        result[f"{column}_sample_percentile"] = pd.to_numeric(result[column], errors="coerce").apply(
            lambda value: float((values <= value).mean()) if pd.notna(value) else pd.NA
        )
    return result


def _my_structural_transfer_summary(
    structure_gameweeks: pd.DataFrame,
    my_transfer_group_decision_labels_df: pd.DataFrame,
    my_team_id: int,
) -> pd.DataFrame:
    row: dict[str, object] = {
        "manager_id": int(my_team_id),
        "my_transfer_group_structure_event_count": 0,
        "my_transfer_groups_with_position_change_count": 0,
        "my_transfer_groups_with_position_value_change_count": 0,
        "my_transfer_groups_with_budget_mix_change_count": 0,
        "my_transfer_groups_with_exposure_change_count": 0,
        "my_transfer_groups_with_value_change_count": 0,
        "my_transfer_group_max_abs_position_count_delta": 0.0,
        "my_transfer_group_max_abs_position_value_delta": 0.0,
        "my_transfer_group_max_abs_budget_mix_delta": 0.0,
        "my_transfer_group_max_abs_exposure_delta": 0.0,
        "my_transfer_group_max_abs_squad_value_delta": 0.0,
    }
    if my_transfer_group_decision_labels_df.empty:
        return pd.DataFrame([row])
    if "event" not in my_transfer_group_decision_labels_df.columns:
        return pd.DataFrame([row])

    my_structure = structure_gameweeks[structure_gameweeks["manager_id"].astype(int).eq(int(my_team_id))].copy()
    if my_structure.empty:
        return pd.DataFrame([row])
    my_structure = my_structure.set_index("event")
    position_columns = ["squad_gkp_count", "squad_def_count", "squad_mid_count", "squad_fwd_count"]
    position_value_columns = ["gkp_value_proxy", "def_value_proxy", "mid_value_proxy", "fwd_value_proxy"]
    budget_mix_columns = ["budget_players", "mid_players", "premium_players"]
    exposure_columns = ["prior_top6_team_players", "good_next3_fixture_players"]
    value_column = "squad_value_proxy"

    groups = my_transfer_group_decision_labels_df.copy()
    if "manager_id" in groups.columns:
        groups = groups[groups["manager_id"].astype(int).eq(int(my_team_id))]

    position_change_count = 0
    position_value_change_count = 0
    budget_mix_change_count = 0
    exposure_change_count = 0
    value_change_count = 0
    max_position_delta = 0.0
    max_position_value_delta = 0.0
    max_budget_mix_delta = 0.0
    max_exposure_delta = 0.0
    max_value_delta = 0.0
    event_count = 0
    for event in sorted(groups["event"].dropna().astype(int).unique()):
        if event <= 1 or event not in my_structure.index or event - 1 not in my_structure.index:
            continue
        before = my_structure.loc[event - 1]
        after = my_structure.loc[event]
        position_delta = float((after[position_columns] - before[position_columns]).abs().sum())
        position_value_delta = float((after[position_value_columns] - before[position_value_columns]).abs().sum())
        budget_mix_delta = float((after[budget_mix_columns] - before[budget_mix_columns]).abs().sum())
        exposure_delta = float((after[exposure_columns] - before[exposure_columns]).abs().sum())
        value_delta = float(abs(after[value_column] - before[value_column]))
        event_count += 1
        position_change_count += int(position_delta > 0)
        position_value_change_count += int(position_value_delta >= 0.5)
        budget_mix_change_count += int(budget_mix_delta > 0)
        exposure_change_count += int(exposure_delta > 0)
        value_change_count += int(value_delta >= 0.5)
        max_position_delta = max(max_position_delta, position_delta)
        max_position_value_delta = max(max_position_value_delta, position_value_delta)
        max_budget_mix_delta = max(max_budget_mix_delta, budget_mix_delta)
        max_exposure_delta = max(max_exposure_delta, exposure_delta)
        max_value_delta = max(max_value_delta, value_delta)

    row["my_transfer_group_structure_event_count"] = event_count
    row["my_transfer_groups_with_position_change_count"] = position_change_count
    row["my_transfer_groups_with_position_value_change_count"] = position_value_change_count
    row["my_transfer_groups_with_budget_mix_change_count"] = budget_mix_change_count
    row["my_transfer_groups_with_exposure_change_count"] = exposure_change_count
    row["my_transfer_groups_with_value_change_count"] = value_change_count
    row["my_transfer_group_max_abs_position_count_delta"] = max_position_delta
    row["my_transfer_group_max_abs_position_value_delta"] = max_position_value_delta
    row["my_transfer_group_max_abs_budget_mix_delta"] = max_budget_mix_delta
    row["my_transfer_group_max_abs_exposure_delta"] = max_exposure_delta
    row["my_transfer_group_max_abs_squad_value_delta"] = max_value_delta
    return pd.DataFrame([row])


def build_squad_structure_benchmark(
    *,
    manager_picks_df: pd.DataFrame,
    players_df: pd.DataFrame,
    team_strength_df: pd.DataFrame,
    fixture_difficulty_df: pd.DataFrame,
    top_n_sample_managers_df: pd.DataFrame,
    my_team_id: int,
    my_transfer_group_decision_labels_df: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build gameweek and season squad-structure benchmarks."""

    _require_columns(top_n_sample_managers_df, {"manager_id", "rank_band"}, "top-N sample managers")
    structure_gw = _build_structure_gameweeks(
        manager_picks_df=manager_picks_df,
        players_df=players_df,
        team_strength_df=team_strength_df,
        fixture_difficulty_df=fixture_difficulty_df,
    )

    metric_columns = [
        column
        for column in structure_gw.columns
        if column not in {"manager_id", "event"} and pd.api.types.is_numeric_dtype(structure_gw[column])
    ]
    season_summary = structure_gw.groupby("manager_id")[metric_columns].mean().reset_index()
    season_summary = season_summary.rename(columns={column: f"avg_{column}" for column in metric_columns})
    event_counts = structure_gw.groupby("manager_id").agg(gameweeks=("event", "nunique")).reset_index()
    season_summary = season_summary.merge(event_counts, on="manager_id", how="left", validate="one_to_one")

    sample = top_n_sample_managers_df[["manager_id", "rank_band", "overall_rank"]].copy()
    sample["manager_id"] = sample["manager_id"].astype(int)
    sample = sample.rename(columns={"overall_rank": "sample_overall_rank"}).drop_duplicates("manager_id")
    season_summary = season_summary.merge(sample, on="manager_id", how="left")
    season_summary["rank_band"] = season_summary["rank_band"].fillna("")
    season_summary.loc[season_summary["manager_id"].astype(int).eq(int(my_team_id)), "rank_band"] = "me"
    season_summary["is_me"] = season_summary["manager_id"].astype(int).eq(int(my_team_id))
    season_summary["value_proxy_note"] = (
        "Budget and bench-spend fields use the player price column from processed players metadata as a "
        "consistent squad-structure proxy; manager picks do not include per-gameweek purchase/selling prices."
    )

    percentile_metrics = [
        "avg_bench_value_proxy",
        "avg_bench_value_share_proxy",
        "avg_premium_players",
        "avg_prior_top6_team_players",
        "avg_good_next3_fixture_players",
        "avg_starter_good_next3_fixture_players",
        "avg_squad_def_count",
        "avg_squad_mid_count",
        "avg_squad_fwd_count",
    ]
    season_summary = _add_sample_percentiles(season_summary, percentile_metrics, my_team_id)

    transfer_groups = (
        my_transfer_group_decision_labels_df
        if my_transfer_group_decision_labels_df is not None
        else pd.DataFrame()
    )
    season_summary = season_summary.merge(
        _my_structural_transfer_summary(structure_gw, transfer_groups, my_team_id),
        on="manager_id",
        how="left",
    )
    for column in season_summary.columns:
        if column.startswith("my_transfer_group_") or column.startswith("my_transfer_groups_"):
            season_summary[column] = pd.to_numeric(season_summary[column], errors="coerce").fillna(0)

    front_columns = [
        "manager_id",
        "is_me",
        "rank_band",
        "sample_overall_rank",
        "gameweeks",
        "avg_squad_value_proxy",
        "avg_starter_value_proxy",
        "avg_bench_value_proxy",
        "avg_bench_value_share_proxy",
        "avg_squad_gkp_count",
        "avg_squad_def_count",
        "avg_squad_mid_count",
        "avg_squad_fwd_count",
        "avg_premium_players",
        "avg_mid_players",
        "avg_budget_players",
        "avg_prior_top6_team_players",
        "avg_good_next3_fixture_players",
        "avg_starter_good_next3_fixture_players",
    ]
    ordered_columns = [column for column in front_columns if column in season_summary.columns]
    ordered_columns.extend([column for column in season_summary.columns if column not in ordered_columns])
    season_summary = season_summary[ordered_columns].sort_values(
        ["is_me", "sample_overall_rank"],
        ascending=[False, True],
    ).reset_index(drop=True)
    return structure_gw, season_summary


def _player_transfer_lookup(player_gw_features_df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    columns = [
        "gameweek",
        "player_id",
        "web_name",
        "team_name",
        "position_short",
        "price",
        "total_points_roll5_mean_prior",
        "minutes_roll5_mean_prior",
        "points_season_to_date_prior",
        "xgi_per_90_prior",
        "clean_sheets_roll5_sum_prior",
        "defensive_contribution_per_90_prior",
        "saves_per_90_prior",
    ]
    available_columns = [column for column in columns if column in player_gw_features_df.columns]
    lookup = player_gw_features_df[available_columns].copy()
    lookup["gameweek"] = lookup["gameweek"].astype(int)
    lookup["player_id"] = lookup["player_id"].astype(int)
    rename = {
        "gameweek": "event",
        "player_id": f"{prefix}_element",
        "web_name": f"{prefix}_player_name",
        "team_name": f"{prefix}_team_name",
        "position_short": f"{prefix}_position_short",
        "price": f"{prefix}_price",
        "total_points_roll5_mean_prior": f"{prefix}_points_roll5_mean_prior",
        "minutes_roll5_mean_prior": f"{prefix}_minutes_roll5_mean_prior",
        "points_season_to_date_prior": f"{prefix}_points_season_to_date_prior",
        "xgi_per_90_prior": f"{prefix}_xgi_per_90_prior",
        "clean_sheets_roll5_sum_prior": f"{prefix}_clean_sheets_roll5_sum_prior",
        "defensive_contribution_per_90_prior": f"{prefix}_defensive_contribution_per_90_prior",
        "saves_per_90_prior": f"{prefix}_saves_per_90_prior",
    }
    return lookup.rename(columns={key: value for key, value in rename.items() if key in lookup.columns})


def _fixture_transfer_lookup(fixture_difficulty_df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    columns = [
        "gameweek",
        "team_name",
        "fpl_difficulty_mean_next3",
        "fpl_difficulty_mean_next5",
        "blank_next3",
        "double_next3",
    ]
    available_columns = [column for column in columns if column in fixture_difficulty_df.columns]
    lookup = fixture_difficulty_df[available_columns].copy()
    lookup["gameweek"] = lookup["gameweek"].astype(int)
    rename = {
        "gameweek": "event",
        "team_name": f"{prefix}_team_name",
        "fpl_difficulty_mean_next3": f"{prefix}_fixture_difficulty_mean_next3",
        "fpl_difficulty_mean_next5": f"{prefix}_fixture_difficulty_mean_next5",
        "blank_next3": f"{prefix}_blank_next3",
        "double_next3": f"{prefix}_double_next3",
    }
    return lookup.rename(columns={key: value for key, value in rename.items() if key in lookup.columns})


def build_transfer_behaviour_benchmark(
    *,
    manager_transfers_df: pd.DataFrame,
    manager_history_df: pd.DataFrame,
    player_gw_features_df: pd.DataFrame,
    fixture_difficulty_df: pd.DataFrame,
    top_n_sample_managers_df: pd.DataFrame,
    my_team_id: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare transfer behaviour for the focal manager against the sampled managers."""

    _require_columns(
        manager_transfers_df,
        {"manager_id", "event", "element_in", "element_in_cost", "element_out", "element_out_cost"},
        "manager transfers",
    )
    _require_columns(
        manager_history_df,
        {"manager_id", "event", "event_transfers", "event_transfers_cost"},
        "manager history",
    )
    _require_columns(top_n_sample_managers_df, {"manager_id", "rank_band", "overall_rank"}, "top-N sample managers")

    transfers = manager_transfers_df.copy()
    transfers["manager_id"] = transfers["manager_id"].astype(int)
    transfers["event"] = transfers["event"].astype(int)
    transfers["element_in"] = transfers["element_in"].astype(int)
    transfers["element_out"] = transfers["element_out"].astype(int)
    transfers = transfers.rename(columns={"element_in": "in_element", "element_out": "out_element"})

    manager_ids = set(top_n_sample_managers_df["manager_id"].astype(int)) | {int(my_team_id)}
    transfers = transfers[transfers["manager_id"].isin(manager_ids)].copy()
    transfers = transfers.sort_values(["manager_id", "event", "time"] if "time" in transfers.columns else ["manager_id", "event"])
    transfers["transfer_row_sequence"] = transfers.groupby("manager_id").cumcount() + 1
    transfers["transfer_group_id"] = (
        transfers["manager_id"].astype(str) + "_gw" + transfers["event"].astype(str).str.zfill(2)
    )

    history = manager_history_df[["manager_id", "event", "event_transfers", "event_transfers_cost"]].copy()
    history["manager_id"] = history["manager_id"].astype(int)
    history["event"] = history["event"].astype(int)
    transfers = transfers.merge(history, on=["manager_id", "event"], how="left", validate="many_to_one")
    transfers["event_transfers"] = pd.to_numeric(transfers["event_transfers"], errors="coerce").fillna(0)
    transfers["event_transfers_cost"] = pd.to_numeric(transfers["event_transfers_cost"], errors="coerce").fillna(0)
    transfers["is_hit_transfer_week"] = transfers["event_transfers_cost"].gt(0)

    transfers = transfers.merge(
        _player_transfer_lookup(player_gw_features_df, "in"),
        on=["event", "in_element"],
        how="left",
        validate="many_to_one",
    ).merge(
        _player_transfer_lookup(player_gw_features_df, "out"),
        on=["event", "out_element"],
        how="left",
        validate="many_to_one",
    )
    transfers = transfers.merge(
        _fixture_transfer_lookup(fixture_difficulty_df, "in"),
        on=["event", "in_team_name"],
        how="left",
        validate="many_to_one",
    ).merge(
        _fixture_transfer_lookup(fixture_difficulty_df, "out"),
        on=["event", "out_team_name"],
        how="left",
        validate="many_to_one",
    )

    transfers["transfer_value_delta"] = (
        pd.to_numeric(transfers["element_in_cost"], errors="coerce")
        - pd.to_numeric(transfers["element_out_cost"], errors="coerce")
    ) / 10
    transfers["fixture_difficulty_swing_next3"] = (
        pd.to_numeric(transfers["out_fixture_difficulty_mean_next3"], errors="coerce")
        - pd.to_numeric(transfers["in_fixture_difficulty_mean_next3"], errors="coerce")
    )
    transfers["targeted_fixture_improvement_next3"] = transfers["fixture_difficulty_swing_next3"].gt(0)
    transfers["transfer_season_phase"] = pd.cut(
        transfers["event"],
        bins=[0, 12, 25, 38],
        labels=["early", "middle", "late"],
        include_lowest=True,
    ).astype(str)

    position_columns = []
    for position in ["GKP", "DEF", "MID", "FWD"]:
        column = f"in_position_{position.lower()}_transfer"
        transfers[column] = transfers["in_position_short"].eq(position).astype(int)
        position_columns.append(column)

    package_summary = (
        transfers.groupby(["manager_id", "event", "transfer_group_id"])
        .agg(
            package_transfer_rows=("in_element", "size"),
            package_event_transfers=("event_transfers", "max"),
            package_hit_cost=("event_transfers_cost", "max"),
            package_value_delta=("transfer_value_delta", "sum"),
            package_fixture_swing_next3=("fixture_difficulty_swing_next3", "mean"),
        )
        .reset_index()
    )
    package_summary["is_multi_transfer_package"] = package_summary["package_transfer_rows"].gt(1)
    package_summary["is_hit_package"] = package_summary["package_hit_cost"].gt(0)
    package_summary["released_budget_package"] = package_summary["package_value_delta"].lt(-0.5)
    package_summary["spent_budget_package"] = package_summary["package_value_delta"].gt(0.5)

    transfer_agg = transfers.groupby("manager_id").agg(
        transfer_row_count=("in_element", "size"),
        transfer_gameweeks=("event", "nunique"),
        first_transfer_gw=("event", "min"),
        last_transfer_gw=("event", "max"),
        avg_transfer_gw=("event", "mean"),
        hit_transfer_rows=("is_hit_transfer_week", "sum"),
        avg_transfer_value_delta=("transfer_value_delta", "mean"),
        total_transfer_value_delta=("transfer_value_delta", "sum"),
        avg_fixture_difficulty_swing_next3=("fixture_difficulty_swing_next3", "mean"),
        fixture_improvement_transfer_rate=("targeted_fixture_improvement_next3", "mean"),
        avg_in_price=("in_price", "mean"),
        avg_out_price=("out_price", "mean"),
        avg_in_points_roll5_mean_prior=("in_points_roll5_mean_prior", "mean"),
        avg_out_points_roll5_mean_prior=("out_points_roll5_mean_prior", "mean"),
        avg_in_minutes_roll5_mean_prior=("in_minutes_roll5_mean_prior", "mean"),
        avg_in_xgi_per_90_prior=("in_xgi_per_90_prior", "mean"),
        avg_in_clean_sheets_roll5_sum_prior=("in_clean_sheets_roll5_sum_prior", "mean"),
        avg_in_defensive_contribution_per_90_prior=("in_defensive_contribution_per_90_prior", "mean"),
        avg_in_saves_per_90_prior=("in_saves_per_90_prior", "mean"),
    )
    for column in position_columns:
        transfer_agg[column.replace("in_position_", "transfer_in_").replace("_transfer", "_count")] = (
            transfers.groupby("manager_id")[column].sum()
        )

    phase_counts = transfers.pivot_table(
        index="manager_id",
        columns="transfer_season_phase",
        values="in_element",
        aggfunc="count",
        fill_value=0,
    )
    for phase in ["early", "middle", "late"]:
        if phase not in phase_counts.columns:
            phase_counts[phase] = 0
    phase_counts = phase_counts.rename(columns={phase: f"{phase}_transfer_rows" for phase in ["early", "middle", "late"]})

    package_agg = package_summary.groupby("manager_id").agg(
        transfer_package_count=("transfer_group_id", "size"),
        multi_transfer_package_count=("is_multi_transfer_package", "sum"),
        hit_package_count=("is_hit_package", "sum"),
        avg_package_size=("package_transfer_rows", "mean"),
        avg_package_value_delta=("package_value_delta", "mean"),
        released_budget_package_count=("released_budget_package", "sum"),
        spent_budget_package_count=("spent_budget_package", "sum"),
        avg_package_fixture_swing_next3=("package_fixture_swing_next3", "mean"),
    )

    benchmark = transfer_agg.join(phase_counts, how="left").join(package_agg, how="left").reset_index()
    all_managers = (
        pd.concat([top_n_sample_managers_df["manager_id"].astype(int), pd.Series([int(my_team_id)])], ignore_index=True)
        .drop_duplicates()
        .to_frame(name="manager_id")
    )
    benchmark = all_managers.merge(benchmark, on="manager_id", how="left")
    numeric_columns = [column for column in benchmark.columns if column != "manager_id"]
    for column in numeric_columns:
        if pd.api.types.is_numeric_dtype(benchmark[column]):
            benchmark[column] = benchmark[column].fillna(0)

    sample = top_n_sample_managers_df[["manager_id", "rank_band", "overall_rank"]].copy()
    sample["manager_id"] = sample["manager_id"].astype(int)
    sample = sample.rename(columns={"overall_rank": "sample_overall_rank"}).drop_duplicates("manager_id")
    benchmark = benchmark.merge(sample, on="manager_id", how="left", validate="one_to_one")
    benchmark["rank_band"] = benchmark["rank_band"].fillna("")
    benchmark.loc[benchmark["manager_id"].eq(int(my_team_id)), "rank_band"] = "me"
    benchmark["is_me"] = benchmark["manager_id"].eq(int(my_team_id))

    percentile_metrics = [
        "transfer_row_count",
        "transfer_gameweeks",
        "hit_transfer_rows",
        "transfer_package_count",
        "multi_transfer_package_count",
        "avg_package_size",
        "fixture_improvement_transfer_rate",
        "avg_fixture_difficulty_swing_next3",
        "avg_in_xgi_per_90_prior",
        "avg_in_defensive_contribution_per_90_prior",
        "avg_in_saves_per_90_prior",
        "transfer_in_def_count",
        "transfer_in_mid_count",
        "transfer_in_fwd_count",
    ]
    benchmark = _add_sample_percentiles(benchmark, percentile_metrics, my_team_id)
    benchmark["individual_package_counting_note"] = (
        "transfer_row_count counts individual transfer legs; transfer_package_count counts manager-gameweek packages."
    )
    benchmark["position_profile_note"] = (
        "Position profile fields keep attacking, clean-sheet, defensive-contribution and goalkeeper-save routes separate."
    )

    front_columns = [
        "manager_id",
        "is_me",
        "rank_band",
        "sample_overall_rank",
        "transfer_row_count",
        "transfer_gameweeks",
        "transfer_package_count",
        "multi_transfer_package_count",
        "hit_transfer_rows",
        "hit_package_count",
        "avg_package_size",
        "avg_transfer_gw",
        "early_transfer_rows",
        "middle_transfer_rows",
        "late_transfer_rows",
        "fixture_improvement_transfer_rate",
        "avg_fixture_difficulty_swing_next3",
        "avg_transfer_value_delta",
        "released_budget_package_count",
        "spent_budget_package_count",
        "transfer_in_gkp_count",
        "transfer_in_def_count",
        "transfer_in_mid_count",
        "transfer_in_fwd_count",
        "avg_in_xgi_per_90_prior",
        "avg_in_clean_sheets_roll5_sum_prior",
        "avg_in_defensive_contribution_per_90_prior",
        "avg_in_saves_per_90_prior",
    ]
    ordered_columns = [column for column in front_columns if column in benchmark.columns]
    ordered_columns.extend([column for column in benchmark.columns if column not in ordered_columns])
    benchmark = benchmark[ordered_columns].sort_values(["is_me", "sample_overall_rank"], ascending=[False, True])
    return transfers.reset_index(drop=True), benchmark.reset_index(drop=True)
