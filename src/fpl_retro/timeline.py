"""Season timeline helpers for the focal manager."""

from __future__ import annotations

import pandas as pd


def _require_columns(df: pd.DataFrame, required_columns: set[str], name: str) -> None:
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"missing {name} columns: {sorted(missing_columns)}")


def _normalise_player_lookup(players_df: pd.DataFrame) -> pd.DataFrame:
    """Return player names keyed by FPL element ID."""

    _require_columns(players_df, {"id", "web_name"}, "players")
    return (
        players_df[["id", "web_name"]]
        .rename(columns={"id": "player_id", "web_name": "player_name"})
        .assign(player_id=lambda df: df["player_id"].astype(int))
        .drop_duplicates("player_id")
    )


def _build_chip_summary(chips_df: pd.DataFrame, manager_id: int) -> pd.DataFrame:
    """Aggregate chip usage to one row per gameweek."""

    if chips_df.empty:
        return pd.DataFrame(columns=["event", "chip_count", "chip_names", "chip_name"])
    _require_columns(chips_df, {"manager_id", "event", "name"}, "chips")
    chips = chips_df[chips_df["manager_id"].astype(int).eq(int(manager_id))].copy()
    if chips.empty:
        return pd.DataFrame(columns=["event", "chip_count", "chip_names", "chip_name"])

    summary = (
        chips.sort_values(["event", "time"] if "time" in chips.columns else ["event"])
        .groupby("event")
        .agg(
            chip_count=("name", "size"),
            chip_names=("name", lambda values: ", ".join(values.astype(str))),
        )
        .reset_index()
    )
    summary["chip_name"] = summary["chip_names"]
    return summary


def _build_transfer_summary(
    transfers_df: pd.DataFrame,
    players_df: pd.DataFrame,
    manager_id: int,
) -> pd.DataFrame:
    """Aggregate transfer rows to one row per gameweek."""

    if transfers_df.empty:
        return pd.DataFrame(
            columns=[
                "event",
                "transfer_count_actual",
                "transfer_in_names",
                "transfer_out_names",
                "transfer_moves",
            ]
        )
    _require_columns(
        transfers_df,
        {"manager_id", "event", "element_in", "element_out"},
        "transfers",
    )
    player_lookup = _normalise_player_lookup(players_df)
    transfers = transfers_df[transfers_df["manager_id"].astype(int).eq(int(manager_id))].copy()
    if transfers.empty:
        return pd.DataFrame(
            columns=[
                "event",
                "transfer_count_actual",
                "transfer_in_names",
                "transfer_out_names",
                "transfer_moves",
            ]
        )

    transfers["element_in"] = transfers["element_in"].astype(int)
    transfers["element_out"] = transfers["element_out"].astype(int)
    transfers = transfers.merge(
        player_lookup.rename(columns={"player_id": "element_in", "player_name": "player_in_name"}),
        on="element_in",
        how="left",
    ).merge(
        player_lookup.rename(columns={"player_id": "element_out", "player_name": "player_out_name"}),
        on="element_out",
        how="left",
    )
    transfers["player_in_name"] = transfers["player_in_name"].fillna(transfers["element_in"].astype(str))
    transfers["player_out_name"] = transfers["player_out_name"].fillna(transfers["element_out"].astype(str))
    transfers["transfer_move"] = transfers["player_out_name"] + " -> " + transfers["player_in_name"]
    sort_columns = ["event", "time"] if "time" in transfers.columns else ["event"]
    transfers = transfers.sort_values(sort_columns)

    return (
        transfers.groupby("event")
        .agg(
            transfer_count_actual=("element_in", "size"),
            transfer_in_names=("player_in_name", lambda values: ", ".join(values.astype(str))),
            transfer_out_names=("player_out_name", lambda values: ", ".join(values.astype(str))),
            transfer_moves=("transfer_move", lambda values: "; ".join(values.astype(str))),
        )
        .reset_index()
    )


def _build_pick_summary(
    picks_df: pd.DataFrame,
    player_gw_features_df: pd.DataFrame,
    manager_id: int,
) -> pd.DataFrame:
    """Aggregate captain, vice-captain, and bench points to one row per gameweek."""

    _require_columns(
        picks_df,
        {"manager_id", "event", "element", "is_captain", "is_vice_captain", "multiplier", "position"},
        "picks",
    )
    _require_columns(
        player_gw_features_df,
        {"player_id", "gameweek", "total_points"},
        "player gameweek features",
    )

    picks = picks_df[picks_df["manager_id"].astype(int).eq(int(manager_id))].copy()
    if picks.empty:
        return pd.DataFrame(columns=["event"])

    picks["element"] = picks["element"].astype(int)
    picks["event"] = picks["event"].astype(int)
    picks["position"] = picks["position"].astype(int)
    picks["multiplier"] = picks["multiplier"].astype(int)
    player_points = player_gw_features_df[["player_id", "gameweek", "total_points"]].rename(
        columns={"player_id": "element", "gameweek": "event", "total_points": "player_total_points"}
    )
    picks = picks.merge(player_points, on=["element", "event"], how="left", validate="many_to_one")
    picks["player_total_points"] = picks["player_total_points"].fillna(0).astype(int)
    picks["pick_points_after_multiplier"] = picks["player_total_points"] * picks["multiplier"]

    captain = picks[picks["is_captain"]].copy()
    captain_summary = captain[
        ["event", "element", "web_name", "team_name", "player_total_points", "multiplier", "pick_points_after_multiplier"]
    ].rename(
        columns={
            "element": "captain_player_id",
            "web_name": "captain_name",
            "team_name": "captain_team_name",
            "player_total_points": "captain_base_points",
            "multiplier": "captain_multiplier",
            "pick_points_after_multiplier": "captain_points",
        }
    )

    vice = picks[picks["is_vice_captain"]].copy()
    vice_summary = vice[["event", "element", "web_name", "team_name", "player_total_points"]].rename(
        columns={
            "element": "vice_captain_player_id",
            "web_name": "vice_captain_name",
            "team_name": "vice_captain_team_name",
            "player_total_points": "vice_captain_base_points",
        }
    )

    pick_counts = picks.groupby("event").agg(
        pick_count=("element", "size"),
        starter_count=("position", lambda values: int((values <= 11).sum())),
        bench_count=("position", lambda values: int((values > 11).sum())),
    )
    bench_points = picks[picks["position"] > 11].groupby("event")["player_total_points"].sum()
    starter_points = picks[picks["position"] <= 11].groupby("event")["pick_points_after_multiplier"].sum()
    pick_counts["bench_raw_points"] = bench_points
    pick_counts["starting_xi_points_after_multiplier"] = starter_points
    pick_counts = pick_counts.fillna(0).astype(int).reset_index()

    return (
        pick_counts.merge(captain_summary, on="event", how="left", validate="one_to_one")
        .merge(vice_summary, on="event", how="left", validate="one_to_one")
        .sort_values("event")
        .reset_index(drop=True)
    )


def build_my_gameweek_timeline(
    *,
    manager_history_df: pd.DataFrame,
    manager_chips_df: pd.DataFrame,
    manager_transfers_df: pd.DataFrame,
    manager_picks_df: pd.DataFrame,
    player_gw_features_df: pd.DataFrame,
    players_df: pd.DataFrame,
    manager_id: int,
) -> pd.DataFrame:
    """Build one timeline row per gameweek for the focal manager."""

    _require_columns(
        manager_history_df,
        {
            "manager_id",
            "event",
            "points",
            "points_on_bench",
            "total_points",
            "overall_rank",
            "rank",
            "event_transfers",
            "event_transfers_cost",
            "bank",
            "value",
        },
        "manager history",
    )

    timeline = manager_history_df[manager_history_df["manager_id"].astype(int).eq(int(manager_id))].copy()
    if timeline.empty:
        raise ValueError(f"manager_id {int(manager_id)} not found in manager history")

    timeline["event"] = timeline["event"].astype(int)
    timeline = timeline.sort_values("event").reset_index(drop=True)

    chips = _build_chip_summary(manager_chips_df, manager_id)
    transfers = _build_transfer_summary(manager_transfers_df, players_df, manager_id)
    picks = _build_pick_summary(manager_picks_df, player_gw_features_df, manager_id)

    timeline = (
        timeline.merge(chips, on="event", how="left", validate="one_to_one")
        .merge(transfers, on="event", how="left", validate="one_to_one")
        .merge(picks, on="event", how="left", validate="one_to_one")
    )

    fill_zero_columns = [
        "chip_count",
        "transfer_count_actual",
        "bench_raw_points",
        "starting_xi_points_after_multiplier",
    ]
    for column in fill_zero_columns:
        if column in timeline.columns:
            timeline[column] = timeline[column].fillna(0).astype(int)

    fill_text_columns = ["chip_names", "chip_name", "transfer_in_names", "transfer_out_names", "transfer_moves"]
    for column in fill_text_columns:
        if column in timeline.columns:
            timeline[column] = timeline[column].fillna("")

    timeline["overall_rank_previous"] = timeline["overall_rank"].shift(1)
    timeline["overall_rank_delta"] = timeline["overall_rank"] - timeline["overall_rank_previous"]
    timeline["overall_rank_movement"] = timeline["overall_rank_previous"] - timeline["overall_rank"]
    timeline["gameweek_rank_previous"] = timeline["rank"].shift(1)
    timeline["gameweek_rank_delta"] = timeline["rank"] - timeline["gameweek_rank_previous"]
    timeline["gameweek_rank_movement"] = timeline["gameweek_rank_previous"] - timeline["rank"]
    timeline["team_value"] = timeline["value"] / 10
    timeline["bank_value"] = timeline["bank"] / 10

    front_columns = [
        "manager_id",
        "event",
        "points",
        "total_points",
        "overall_rank",
        "overall_rank_previous",
        "overall_rank_delta",
        "overall_rank_movement",
        "rank",
        "gameweek_rank_previous",
        "gameweek_rank_delta",
        "gameweek_rank_movement",
        "points_on_bench",
        "bench_raw_points",
        "event_transfers",
        "transfer_count_actual",
        "event_transfers_cost",
        "chip_name",
        "captain_name",
        "captain_team_name",
        "captain_base_points",
        "captain_multiplier",
        "captain_points",
        "vice_captain_name",
        "vice_captain_team_name",
        "vice_captain_base_points",
        "transfer_moves",
        "transfer_in_names",
        "transfer_out_names",
        "bank_value",
        "team_value",
    ]
    ordered_columns = [column for column in front_columns if column in timeline.columns]
    ordered_columns.extend([column for column in timeline.columns if column not in ordered_columns])
    return timeline[ordered_columns].sort_values("event").reset_index(drop=True)
