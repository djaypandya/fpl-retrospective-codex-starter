"""Decision evaluation helpers."""

from __future__ import annotations

import pandas as pd


def _require_columns(df: pd.DataFrame, required_columns: set[str], name: str) -> None:
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"missing {name} columns: {sorted(missing_columns)}")


def _numeric(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(0.0, index=df.index)
    return pd.to_numeric(df[column], errors="coerce").fillna(0.0)


def _rank_score(series: pd.Series, *, higher_is_better: bool = True) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").fillna(0.0)
    if numeric.nunique(dropna=False) <= 1:
        return pd.Series(0.5, index=series.index)
    return numeric.rank(pct=True, ascending=not higher_is_better)


def _position_route_score(squad: pd.DataFrame) -> pd.Series:
    """Return position-aware prior scoring-route strength for captain candidates."""

    position = squad["player_position_short"]
    score = pd.Series(0.0, index=squad.index)

    attacking_score = (
        0.45 * _rank_score(_numeric(squad, "player_xgi_per_90_prior"))
        + 0.20 * _rank_score(_numeric(squad, "player_goals_scored_roll5_sum_prior"))
        + 0.15 * _rank_score(_numeric(squad, "player_assists_roll5_sum_prior"))
        + 0.10 * _rank_score(_numeric(squad, "player_bps_per_90_prior"))
        + 0.10 * _rank_score(_numeric(squad, "player_bonus_per_90_prior"))
    )
    defender_score = (
        0.25 * _rank_score(_numeric(squad, "player_clean_sheets_roll5_sum_prior"))
        + 0.20 * _rank_score(_numeric(squad, "player_defensive_contribution_per_90_prior"))
        + 0.20 * _rank_score(_numeric(squad, "player_goals_conceded_per_90_prior"), higher_is_better=False)
        + 0.15 * _rank_score(_numeric(squad, "player_xgi_per_90_prior"))
        + 0.10 * _rank_score(_numeric(squad, "player_bps_per_90_prior"))
        + 0.10 * _rank_score(_numeric(squad, "player_bonus_per_90_prior"))
    )
    goalkeeper_score = (
        0.30 * _rank_score(_numeric(squad, "player_saves_per_90_prior"))
        + 0.25 * _rank_score(_numeric(squad, "player_clean_sheets_roll5_sum_prior"))
        + 0.20 * _rank_score(_numeric(squad, "player_goals_conceded_per_90_prior"), higher_is_better=False)
        + 0.15 * _rank_score(_numeric(squad, "player_bps_per_90_prior"))
        + 0.10 * _rank_score(_numeric(squad, "player_bonus_per_90_prior"))
    )

    score.loc[position.eq("GKP")] = goalkeeper_score.loc[position.eq("GKP")]
    score.loc[position.eq("DEF")] = defender_score.loc[position.eq("DEF")]
    score.loc[position.isin(["MID", "FWD"])] = attacking_score.loc[position.isin(["MID", "FWD"])]
    return score


def _add_captain_candidate_scores(squad: pd.DataFrame) -> pd.DataFrame:
    squad = squad.copy()
    squad["captain_form_score"] = squad.groupby("event")["player_total_points_roll5_mean_prior"].transform(
        _rank_score
    )
    squad["captain_security_score"] = (
        0.50 * squad.groupby("event")["player_minutes_roll5_mean_prior"].transform(_rank_score)
        + 0.25 * squad.groupby("event")["player_start_rate_prior"].transform(_rank_score)
        + 0.25 * squad.groupby("event")["player_sixty_plus_rate_prior"].transform(_rank_score)
    )
    squad["captain_ceiling_score"] = (
        0.30 * squad.groupby("event")["player_total_points_roll5_mean_prior"].transform(_rank_score)
        + 0.25 * squad.groupby("event")["player_xgi_per_90_prior"].transform(_rank_score)
        + 0.15 * squad.groupby("event")["player_goals_scored_roll5_sum_prior"].transform(_rank_score)
        + 0.10 * squad.groupby("event")["player_assists_roll5_sum_prior"].transform(_rank_score)
        + 0.10 * squad.groupby("event")["player_bps_per_90_prior"].transform(_rank_score)
        + 0.10 * squad.groupby("event")["player_bonus_per_90_prior"].transform(_rank_score)
    )
    squad["captain_position_route_score"] = squad.groupby("event", group_keys=False).apply(
        _position_route_score, include_groups=False
    )
    squad["captain_fixture_score"] = (
        0.50
        * squad.groupby("event")["fixture_fpl_difficulty_mean_next1"].transform(
            lambda series: _rank_score(series, higher_is_better=False)
        )
        + 0.25
        * squad.groupby("event")["fixture_double_next1"].transform(
            lambda series: _rank_score(series, higher_is_better=True)
        )
        + 0.25
        * squad.groupby("event")["fixture_blank_next1"].transform(
            lambda series: _rank_score(series, higher_is_better=False)
        )
    )
    squad["captain_candidate_score"] = (
        0.35 * squad["captain_ceiling_score"]
        + 0.20 * squad["captain_form_score"]
        + 0.20 * squad["captain_security_score"]
        + 0.15 * squad["captain_position_route_score"]
        + 0.10 * squad["captain_fixture_score"]
    )
    return squad


def build_captaincy_review(my_squad_df: pd.DataFrame) -> pd.DataFrame:
    """Evaluate actual captaincy against squad and pre-gameweek alternatives."""

    _require_columns(
        my_squad_df,
        {
            "manager_id",
            "event",
            "element",
            "player_web_name",
            "player_position_short",
            "is_captain",
            "is_vice_captain",
            "is_starter",
            "multiplier",
            "actual_points",
            "player_total_points_roll5_mean_prior",
            "player_minutes_roll5_mean_prior",
            "player_start_rate_prior",
            "player_sixty_plus_rate_prior",
        },
        "my squad",
    )

    squad = my_squad_df.copy()
    squad["event"] = squad["event"].astype(int)
    squad["actual_points"] = pd.to_numeric(squad["actual_points"], errors="coerce").fillna(0.0)
    squad["multiplier"] = pd.to_numeric(squad["multiplier"], errors="coerce").fillna(0).astype(int)
    squad["is_captain"] = squad["is_captain"].astype(bool)
    squad["is_vice_captain"] = squad["is_vice_captain"].astype(bool)
    squad["is_starter"] = squad["is_starter"].astype(bool)
    squad = _add_captain_candidate_scores(squad)

    rows: list[dict[str, object]] = []
    for event, group in squad.groupby("event", sort=True):
        captain = group[group["is_captain"]]
        vice = group[group["is_vice_captain"]]
        if len(captain) != 1:
            raise ValueError(f"event {event} has {len(captain)} captains")
        if len(vice) != 1:
            raise ValueError(f"event {event} has {len(vice)} vice-captains")
        captain_row = captain.iloc[0]
        vice_row = vice.iloc[0]
        multiplier = int(captain_row["multiplier"])
        captain_extra_multiplier = max(multiplier - 1, 0)

        best_squad = group.sort_values(["actual_points", "captain_candidate_score"], ascending=[False, False]).iloc[0]
        starters = group[group["is_starter"]]
        best_starter = starters.sort_values(["actual_points", "captain_candidate_score"], ascending=[False, False]).iloc[0]
        best_candidate = starters.sort_values(
            ["captain_candidate_score", "actual_points"],
            ascending=[False, False],
        ).iloc[0]

        rows.append(
            {
                "event": int(event),
                "manager_id": int(captain_row["manager_id"]),
                "captain_player_id": int(captain_row["element"]),
                "captain_name": captain_row["player_web_name"],
                "captain_position": captain_row["player_position_short"],
                "captain_multiplier": multiplier,
                "captain_base_points": float(captain_row["actual_points"]),
                "captain_extra_points": float(captain_row["actual_points"]) * captain_extra_multiplier,
                "vice_captain_player_id": int(vice_row["element"]),
                "vice_captain_name": vice_row["player_web_name"],
                "vice_captain_base_points": float(vice_row["actual_points"]),
                "best_squad_player_id": int(best_squad["element"]),
                "best_squad_name": best_squad["player_web_name"],
                "best_squad_position": best_squad["player_position_short"],
                "best_squad_base_points": float(best_squad["actual_points"]),
                "best_squad_extra_points": float(best_squad["actual_points"]) * captain_extra_multiplier,
                "best_starter_player_id": int(best_starter["element"]),
                "best_starter_name": best_starter["player_web_name"],
                "best_starter_position": best_starter["player_position_short"],
                "best_starter_base_points": float(best_starter["actual_points"]),
                "best_starter_extra_points": float(best_starter["actual_points"]) * captain_extra_multiplier,
                "recommended_candidate_player_id": int(best_candidate["element"]),
                "recommended_candidate_name": best_candidate["player_web_name"],
                "recommended_candidate_position": best_candidate["player_position_short"],
                "recommended_candidate_score": float(best_candidate["captain_candidate_score"]),
                "recommended_candidate_base_points": float(best_candidate["actual_points"]),
                "recommended_candidate_extra_points": float(best_candidate["actual_points"]) * captain_extra_multiplier,
                "captain_candidate_score": float(captain_row["captain_candidate_score"]),
                "captain_form_score": float(captain_row["captain_form_score"]),
                "captain_ceiling_score": float(captain_row["captain_ceiling_score"]),
                "captain_security_score": float(captain_row["captain_security_score"]),
                "captain_position_route_score": float(captain_row["captain_position_route_score"]),
                "captain_fixture_score": float(captain_row["captain_fixture_score"]),
                "delta_vs_best_squad_extra": (
                    float(captain_row["actual_points"]) - float(best_squad["actual_points"])
                )
                * captain_extra_multiplier,
                "delta_vs_best_starter_extra": (
                    float(captain_row["actual_points"]) - float(best_starter["actual_points"])
                )
                * captain_extra_multiplier,
                "delta_vs_recommended_candidate_extra": (
                    float(captain_row["actual_points"]) - float(best_candidate["actual_points"])
                )
                * captain_extra_multiplier,
                "captain_was_best_squad": int(captain_row["element"]) == int(best_squad["element"]),
                "captain_was_best_starter": int(captain_row["element"]) == int(best_starter["element"]),
                "captain_was_recommended_candidate": int(captain_row["element"]) == int(best_candidate["element"]),
                "candidate_score_note": (
                    "pre-GW candidate score combines prior form, minutes security, position-aware scoring routes, "
                    "and upcoming fixture context"
                ),
            }
        )

    return pd.DataFrame(rows).sort_values("event").reset_index(drop=True)


def _valid_outfield_formation(position_counts: dict[str, int]) -> bool:
    return (
        position_counts.get("DEF", 0) >= 3
        and position_counts.get("MID", 0) >= 2
        and position_counts.get("FWD", 0) >= 1
        and sum(position_counts.get(position, 0) for position in ["DEF", "MID", "FWD"]) == 10
    )


def _replaceable_starters(starters: pd.DataFrame, bench_row: pd.Series) -> pd.DataFrame:
    """Return starters who could be replaced by this bench player while preserving formation."""

    bench_position = bench_row["player_position_short"]
    if bench_position == "GKP":
        return starters[starters["player_position_short"].eq("GKP")].copy()

    outfield_starters = starters[starters["player_position_short"].isin(["DEF", "MID", "FWD"])]
    replaceable_rows = []
    for _, starter_row in outfield_starters.iterrows():
        counts = outfield_starters["player_position_short"].value_counts().to_dict()
        counts[starter_row["player_position_short"]] = counts.get(starter_row["player_position_short"], 0) - 1
        counts[bench_position] = counts.get(bench_position, 0) + 1
        if _valid_outfield_formation(counts):
            replaceable_rows.append(starter_row)
    return pd.DataFrame(replaceable_rows)


def build_benching_review(my_squad_df: pd.DataFrame) -> pd.DataFrame:
    """Evaluate bench points and questionable benching decisions."""

    _require_columns(
        my_squad_df,
        {
            "manager_id",
            "event",
            "element",
            "player_web_name",
            "player_position_short",
            "squad_position",
            "is_starter",
            "is_bench",
            "actual_points",
            "player_total_points_roll5_mean_prior",
            "player_minutes_roll5_mean_prior",
            "player_start_rate_prior",
            "player_sixty_plus_rate_prior",
        },
        "my squad",
    )

    squad = my_squad_df.copy()
    squad["event"] = squad["event"].astype(int)
    squad["squad_position"] = squad["squad_position"].astype(int)
    squad["actual_points"] = pd.to_numeric(squad["actual_points"], errors="coerce").fillna(0.0)
    squad["is_starter"] = squad["is_starter"].astype(bool)
    squad["is_bench"] = squad["is_bench"].astype(bool)
    squad = _add_captain_candidate_scores(squad).rename(
        columns={
            "captain_candidate_score": "selection_candidate_score",
            "captain_form_score": "selection_form_score",
            "captain_ceiling_score": "selection_ceiling_score",
            "captain_security_score": "selection_security_score",
            "captain_position_route_score": "selection_position_route_score",
            "captain_fixture_score": "selection_fixture_score",
        }
    )

    rows: list[dict[str, object]] = []
    for event, group in squad.groupby("event", sort=True):
        starters = group[group["is_starter"]].copy()
        bench = group[group["is_bench"]].copy()
        if len(starters) != 11:
            raise ValueError(f"event {event} has {len(starters)} starters")
        if len(bench) != 4:
            raise ValueError(f"event {event} has {len(bench)} bench players")

        bench_points_total = float(bench["actual_points"].sum())
        for _, bench_row in bench.sort_values("squad_position").iterrows():
            replaceable = _replaceable_starters(starters, bench_row)
            if replaceable.empty:
                worst_replaceable = None
                best_replaceable = None
                regret_points = 0.0
                questionable_benching = False
            else:
                worst_replaceable = replaceable.sort_values(
                    ["actual_points", "selection_candidate_score"],
                    ascending=[True, True],
                ).iloc[0]
                best_replaceable = replaceable.sort_values(
                    ["actual_points", "selection_candidate_score"],
                    ascending=[False, False],
                ).iloc[0]
                regret_points = max(float(bench_row["actual_points"]) - float(worst_replaceable["actual_points"]), 0.0)
                questionable_benching = (
                    regret_points > 0
                    and float(bench_row["selection_candidate_score"])
                    >= float(worst_replaceable["selection_candidate_score"])
                )

            rows.append(
                {
                    "event": int(event),
                    "manager_id": int(bench_row["manager_id"]),
                    "bench_player_id": int(bench_row["element"]),
                    "bench_player_name": bench_row["player_web_name"],
                    "bench_position": bench_row["player_position_short"],
                    "bench_order": int(bench_row["squad_position"]) - 11,
                    "bench_actual_points": float(bench_row["actual_points"]),
                    "bench_selection_candidate_score": float(bench_row["selection_candidate_score"]),
                    "bench_position_route_score": float(bench_row["selection_position_route_score"]),
                    "bench_points_total_event": bench_points_total,
                    "replaceable_starter_count": int(len(replaceable)),
                    "worst_replaceable_starter_id": None if worst_replaceable is None else int(worst_replaceable["element"]),
                    "worst_replaceable_starter_name": None
                    if worst_replaceable is None
                    else worst_replaceable["player_web_name"],
                    "worst_replaceable_starter_position": None
                    if worst_replaceable is None
                    else worst_replaceable["player_position_short"],
                    "worst_replaceable_starter_points": None
                    if worst_replaceable is None
                    else float(worst_replaceable["actual_points"]),
                    "worst_replaceable_starter_candidate_score": None
                    if worst_replaceable is None
                    else float(worst_replaceable["selection_candidate_score"]),
                    "best_replaceable_starter_name": None if best_replaceable is None else best_replaceable["player_web_name"],
                    "best_replaceable_starter_points": None
                    if best_replaceable is None
                    else float(best_replaceable["actual_points"]),
                    "bench_outscored_replaceable_starter": regret_points > 0,
                    "bench_regret_points": regret_points,
                    "high_regret_benching": regret_points >= 5,
                    "questionable_benching": bool(questionable_benching),
                    "bench_decision_category": (
                        "questionable_high_regret"
                        if questionable_benching and regret_points >= 5
                        else "questionable"
                        if questionable_benching
                        else "hindsight_only_high_regret"
                        if regret_points >= 5
                        else "hindsight_only"
                        if regret_points > 0
                        else "no_regret"
                    ),
                    "selection_score_note": (
                        "selection_candidate_score uses prior form, ceiling, minutes security, "
                        "position-aware scoring routes, and upcoming fixture context"
                    ),
                }
            )

    return pd.DataFrame(rows).sort_values(["event", "bench_order"]).reset_index(drop=True)


def build_benching_gameweek_summary(benching_review_df: pd.DataFrame) -> pd.DataFrame:
    """Summarise benching regret to one row per gameweek."""

    _require_columns(
        benching_review_df,
        {
            "event",
            "bench_actual_points",
            "bench_regret_points",
            "questionable_benching",
            "high_regret_benching",
        },
        "benching review",
    )
    summary = (
        benching_review_df.groupby("event", as_index=False)
        .agg(
            bench_points=("bench_actual_points", "sum"),
            bench_regret_points=("bench_regret_points", "sum"),
            questionable_benchings=("questionable_benching", "sum"),
            high_regret_benchings=("high_regret_benching", "sum"),
            bench_players=("bench_actual_points", "size"),
        )
        .sort_values("event")
        .reset_index(drop=True)
    )
    return summary
